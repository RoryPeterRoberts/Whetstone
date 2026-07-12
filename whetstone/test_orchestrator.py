"""Tests for the live orchestrator (pipeline.handle_stop) + the Stop-hook entry."""
import json
import subprocess
import sys
from pathlib import Path

import events
import pipeline

SOB = Path(pipeline.__file__).resolve().parent.parent / "spec" / "fixtures" / "structured_output_boundary"
GAP = (SOB / "gap.py").read_text()
FIXED = (SOB / "fixed.py").read_text()
DIRECTION = ("Validate model output against the schema and reject invalid results "
             "before writing to the database.")


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def _repo(path, dirty=False):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    (path / "seed.py").write_text("x = 1\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "init")
    if dirty:
        (path / "scratch.py").write_text("y = 2\n")  # leaves the worktree dirty
    return path


def _payload(cwd, session="s1", transcript=None, prompt=None):
    p = {"session_id": session, "cwd": str(cwd), "hook_event_name": "Stop"}
    if transcript:
        p["transcript_path"] = str(transcript)
    if prompt:
        p["prompt_id"] = prompt
    return p


def test_clean_repo_is_ignored(tmp_path):
    repo = _repo(tmp_path / "r")
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    out = pipeline.handle_stop(_payload(repo), checkpoint_head=head,
                               changed_sources=[], path=tmp_path / "events.jsonl")
    assert out["status"] == "ignored"


def test_gap_on_first_encounter_is_proposed(tmp_path):
    repo = _repo(tmp_path / "r", dirty=True)
    ledger = tmp_path / "events.jsonl"
    out = pipeline.handle_stop(_payload(repo), changed_sources=[("h.py", GAP)], path=ledger)
    assert out["status"] == "processed"
    actions = {r["action"] for r in out["results"]}
    assert "proposed" in actions
    kinds = {e["kind"] for e in events.load_events(ledger)}
    assert {"opportunity_detected", "proposed"} <= kinds


def test_no_gap_records_nothing(tmp_path):
    repo = _repo(tmp_path / "r", dirty=True)
    ledger = tmp_path / "events.jsonl"
    out = pipeline.handle_stop(_payload(repo), changed_sources=[("h.py", FIXED)], path=ledger)
    assert out["results"] == []
    assert events.load_events(ledger) == []


def test_direction_captured_from_transcript(tmp_path):
    repo = _repo(tmp_path / "r", dirty=True)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({
        "type": "user", "isSidechain": False, "promptId": "prm-1",
        "message": {"content": DIRECTION}}) + "\n")
    out = pipeline.handle_stop(
        _payload(repo, transcript=transcript, prompt="prm-1"),
        changed_sources=[("h.py", GAP)], path=tmp_path / "events.jsonl")
    assert out["direction_captured"] is True
    assert out["direction_association"] == "prompt_id"


def test_recall_candidate_when_principle_settled_elsewhere(tmp_path):
    repo = _repo(tmp_path / "r", dirty=True)
    ledger = tmp_path / "events.jsonl"
    # a DIFFERENT repo already accepted the principle
    events.emit("accepted", pipeline.PRINCIPLE_ID, 1, "r_" + "z" * 16, "claude_code", "s0",
                {"finding_id": "f0"}, path=ledger)
    out = pipeline.handle_stop(_payload(repo), changed_sources=[("h.py", GAP)], path=ledger)
    actions = {r["action"] for r in out["results"]}
    assert actions == {"recall_candidate"}


def test_hook_fails_open_on_garbage_stdin():
    # the Stop hook must never break the host, even on malformed input
    proc = subprocess.run(
        [sys.executable, str(Path(pipeline.__file__).resolve().parent / "whetstone_hook.py")],
        input="not json at all", capture_output=True, text=True)
    assert proc.returncode == 0
