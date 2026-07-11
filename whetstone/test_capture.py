"""Phase 3 exit tests: user/model separation + task-bound direction capture on fixtures."""
import hashlib
import json
import subprocess
from pathlib import Path

import capture

FIX = capture.SPEC / "fixtures"
TRANSCRIPT = FIX / "transcripts" / "example_session.jsonl"
STOP_PID = json.loads((FIX / "claude_stop" / "with_prompt_id.json").read_text())
STOP_NOPID = json.loads((FIX / "claude_stop" / "without_prompt_id.json").read_text())
UPS = json.loads((FIX / "claude_user_prompt_submit" / "example.json").read_text())
R_A = "r_" + "a" * 16


def _sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


# --- the load-bearing separation --------------------------------------------

def test_user_model_separation():
    records = capture.parse_transcript(TRANSCRIPT)
    assert len(records) == 3  # user(direction), assistant, user(tool_result)
    authored = capture.user_direction_records(records)
    # exactly ONE human-authored turn survives: the assistant + tool-result are dropped
    assert len(authored) == 1
    assert "reject invalid results" in authored[0]["text"]
    assert authored[0]["rec"]["promptId"] == "prm-0001"
    # nothing a model produced leaked through
    joined = " ".join(a["text"] for a in authored)
    assert "I'll add pydantic" not in joined
    assert "tool_result" not in joined


def test_sidechain_and_tool_turns_excluded():
    lines = [
        json.dumps({"type": "user", "isSidechain": True, "message": {"content": "subagent text"}}),
        json.dumps({"type": "user", "isSidechain": False,
                    "message": {"content": [{"type": "tool_result", "content": "x"}]}}),
        json.dumps({"type": "assistant", "message": {"content": "model text"}}),
    ]
    assert capture.user_direction_records(capture.parse_transcript(lines)) == []


# --- task -> direction association (capability-detected, fail closed) --------

def test_prompt_id_binds_the_task_window():
    assoc, window = capture.select_window(capture.parse_transcript(TRANSCRIPT), STOP_PID)
    assert assoc == "prompt_id"
    assert len(window) == 1 and window[0]["rec"]["promptId"] == "prm-0001"


def test_prompt_id_present_but_unmatched_fails_closed():
    payload = dict(STOP_PID, prompt_id="prm-DOES-NOT-EXIST")
    assoc, window = capture.select_window(capture.parse_transcript(TRANSCRIPT), payload)
    assert assoc is None and window is None


def test_paired_fallback_uses_userpromptsubmit():
    # no prompt_id on Stop; a UserPromptSubmit for the SAME session supplies the direction
    assoc, rec = capture.capture_direction(
        [], STOP_NOPID, R_A, ts=100, user_prompt_submit=UPS)
    assert assoc == "paired"
    assert "reject invalid results" in rec["redacted_excerpt"]
    assert rec["prompt_association"] == "paired"


def test_paired_fallback_wrong_session_ignored():
    ups = dict(UPS, session_id="other-session")
    assoc, window = capture.select_window(
        capture.parse_transcript(TRANSCRIPT), STOP_NOPID, user_prompt_submit=ups)
    # falls through to ancestry (last authored turn), not the wrong-session UPS
    assert assoc == "ancestry"


# --- direction record: schema-valid, authored, bounded provenance -----------

def test_direction_record_valid_and_bounded_provenance():
    assoc, rec = capture.capture_direction(TRANSCRIPT, STOP_PID, R_A, ts=100)
    assert assoc == "prompt_id"
    assert rec["authorship"] == "user"
    assert rec["direction_id"].startswith("d_")
    assert rec["excerpt_sha256"] == _sha(rec["redacted_excerpt"])
    # provenance is per-record byte hash of the EXACT transcript line, not the whole file
    raw_lines = [l for l in TRANSCRIPT.read_text().splitlines() if l.strip()]
    direction_line = raw_lines[0]
    assert len(rec["provenance"]["records"]) == 1
    assert rec["provenance"]["records"][0]["record_sha256"] == _sha(direction_line)
    assert rec["provenance"]["records"][0]["record_sha256"] != _sha(TRANSCRIPT.read_text())


def test_redaction_runs_before_persist():
    secret = "AKIAIOSFODNN7EXAMPLE"
    lines = [json.dumps({"type": "user", "isSidechain": False, "promptId": "p1",
                         "message": {"content": f"Use key {secret} to validate output before the write."}})]
    payload = {"session_id": "s", "prompt_id": "p1"}
    assoc, rec = capture.capture_direction(lines, payload, R_A, ts=1)
    assert secret not in rec["redacted_excerpt"]
    assert "[REDACTED]" in rec["redacted_excerpt"]


# --- trigger eligibility -----------------------------------------------------

def _git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True)


def test_meaningful_build_only_on_change(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("1")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    # no change since checkpoint -> not meaningful
    assert capture.is_meaningful_build(repo, head) is False
    # uncommitted change -> meaningful
    (repo / "a.txt").write_text("2")
    assert capture.is_meaningful_build(repo, head) is True
    # a new commit -> meaningful
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "second")
    assert capture.is_meaningful_build(repo, head) is True
