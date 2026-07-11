"""Phase 7 acceptance: the slice, end to end (spec section 14).

Positive path (records transferred), learning negatives (must NOT), and operational cases
including the real repo_id algorithm. Building blocks (capture, detector, matcher, recall,
tell, transfer, events, repo_id) are wired together here across two simulated repos.
"""
import json
import subprocess
from pathlib import Path

import capture
import detector
import events
import matcher
import recall
import repo_id
import tell
import transfer

SOB = tell.SPEC / "fixtures" / "structured_output_boundary"
GAP = (SOB / "gap.py").read_text()
FIXED = (SOB / "fixed.py").read_text()
TEST = (SOB / "test_boundary.py").read_text()
VACUOUS = (tell.SPEC / "fixtures" / "tell_discrimination" / "vacuous_test.py").read_text()
DIRECTION_TEXT = ("Validate model output against the schema and reject invalid results "
                  "before writing to the database.")
P = "p_structured_output_boundary"


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def _make_repo(path, remote=None):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    (path / "seed.py").write_text("x = 1\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "init")
    if remote:
        _git(path, "remote", "add", "origin", remote)
    return path


def _discriminating_tell(rid):
    return tell.register_tell(GAP, FIXED, TEST, P, rid, mutation=tell.mutation_block(FIXED, GAP))


def _captured_direction(rid, text=DIRECTION_TEXT, prompt="prm-b", session="sess-b"):
    lines = [json.dumps({"type": "user", "isSidechain": False, "promptId": prompt,
                         "sessionId": session, "message": {"content": text}})]
    stop = {"session_id": session, "prompt_id": prompt}
    assoc, rec = capture.capture_direction(lines, stop, rid, ts=100)
    return rec


# --- repo_id operational cases (spec section 6 / 14) ------------------------

def test_repo_id_clone_and_worktree_and_move(tmp_path):
    url = "git@github.com:org/repo.git"
    a = _make_repo(tmp_path / "A")
    _git(a, "remote", "add", "origin", url)
    clone = tmp_path / "CLONE"
    subprocess.run(["git", "clone", "-q", str(a), str(clone)], check=True, capture_output=True)
    _git(clone, "remote", "set-url", "origin", url)  # same canonical remote

    id_a = repo_id.repo_id(a)
    id_clone = repo_id.repo_id(clone)
    assert id_a == id_clone, "a clone of the same remote is the SAME repo_id"

    # second worktree shares the git-common-dir -> same id
    wt = tmp_path / "WT"
    _git(a, "worktree", "add", "-q", str(wt))
    assert repo_id.repo_id(wt) == id_a

    # moving the repo changes only local_path, not identity
    moved = tmp_path / "A_moved"
    a.rename(moved)
    rec = repo_id.resolve(moved)
    assert rec["repo_id"] == id_a
    assert rec["local_path"].endswith("A_moved")


def test_repo_id_no_remote_is_local_uuid(tmp_path):
    r = _make_repo(tmp_path / "solo")
    rec = repo_id.resolve(r)
    assert rec["origin_kind"] == "local_uuid" and rec["repo_id"].startswith("r_")


def test_canonical_remote_normalizes_scp_and_https():
    assert repo_id.canonical_remote("git@github.com:Org/Repo.git") == "github.com/Org/Repo"
    assert repo_id.canonical_remote("https://user:tok@GitHub.com/Org/Repo.git") == "github.com/Org/Repo"


# --- positive path: transferred, then teaching suppressed -------------------

def test_positive_path_records_transferred(tmp_path):
    ledger = tmp_path / "events.jsonl"
    a = _make_repo(tmp_path / "A", remote="git@github.com:org/a.git")
    b = _make_repo(tmp_path / "B", remote="git@github.com:org/b.git")
    id_a, id_b = repo_id.repo_id(a), repo_id.repo_id(b)
    assert id_a != id_b

    # Repo A: gap detected, lesson accepted
    opp_a = detector.detect_opportunity(GAP, id_a)
    assert opp_a is not None
    events.emit("proposed", P, 1, id_a, "claude_code", "sA",
                {"finding_id": "f1", "classification": "confirmed"}, path=ledger)
    events.emit("accepted", P, 1, id_a, "claude_code", "sA", {"finding_id": "f1"}, path=ledger)

    # Repo B: comparable opportunity + recall + user direction captured & matched
    opp_b = detector.detect_opportunity(GAP, id_b)
    recall.prompt_recall(opp_b["opportunity_id"], id_b, "sB", path=ledger)
    dr = _captured_direction(id_b)
    assert matcher.match(dr["redacted_excerpt"])["matched"] is True
    outcome, ev = recall.resolve_recall(opp_b["opportunity_id"], dr, id_b, "sB", path=ledger)
    assert outcome == "direction_recalled"

    # Repo B artifact tell discriminating on a stable worktree
    t = _discriminating_tell(id_b)
    assert t["discriminating"] is True

    assert transfer.should_teach(id_b, path=ledger) is True
    outcome, ev = transfer.verify_transfer(
        opportunity_id=opp_b["opportunity_id"], finding_id="f1",
        from_repo_id=id_a, to_repo_id=id_b, matched_direction=dr, tell_result=t, path=ledger)
    assert outcome == "transferred"
    assert ev["evidence"]["from_repo_id"] == id_a and ev["evidence"]["to_repo_id"] == id_b
    # teaching suppressed now that it transferred in Repo B
    assert transfer.should_teach(id_b, path=ledger) is False
    # global learner reflects a transfer
    assert events.build_projections(path=ledger)["global_learner"]["ever_transferred"] is True


# --- learning negatives: must NOT record transferred ------------------------

def test_agent_inserted_is_practice_present_not_transferred(tmp_path):
    ledger = tmp_path / "events.jsonl"
    outcome, ev = transfer.verify_transfer(
        opportunity_id="o1", finding_id="f1", from_repo_id="r_" + "a"*16, to_repo_id="r_" + "b"*16,
        matched_direction=None, tell_result=_discriminating_tell("r_" + "b"*16), path=ledger)
    assert outcome == "practice_present"
    assert all(e["kind"] != "transferred" for e in events.load_events(ledger))


def test_irrelevant_direction_no_leg(tmp_path):
    ledger = tmp_path / "events.jsonl"
    dr = _captured_direction("r_" + "b"*16, text="Please refactor the parser for readability.")
    # matcher fails closed on an out-of-lexicon direction -> recall_unmatched, never transferred
    outcome, ev = recall.resolve_recall("o1", dr, "r_" + "b"*16, "sB", path=ledger)
    assert outcome == "recall_unmatched"


def test_artifact_fails_tell_stays_recalled(tmp_path):
    ledger = tmp_path / "events.jsonl"
    dr = _captured_direction("r_" + "b"*16)
    vac = tell.register_tell(GAP, FIXED, VACUOUS, P, "r_" + "b"*16)
    outcome, _ = transfer.verify_transfer(
        opportunity_id="o1", finding_id="f1", from_repo_id="r_" + "a"*16, to_repo_id="r_" + "b"*16,
        matched_direction=dr, tell_result=vac, path=ledger)
    assert outcome == "direction_recalled"
    assert events.load_events(ledger) == []


def test_ineligible_repo_no_opportunity():
    assert detector.detect_opportunity(FIXED, "r_" + "b"*16) is None


def test_worktree_changed_fails_closed(tmp_path):
    ledger = tmp_path / "events.jsonl"
    outcome, ev = transfer.verify_transfer(
        opportunity_id="o1", finding_id="f1", from_repo_id="r_" + "a"*16, to_repo_id="r_" + "b"*16,
        matched_direction=_captured_direction("r_" + "b"*16),
        tell_result=_discriminating_tell("r_" + "b"*16), worktree_stable=False, path=ledger)
    assert outcome == "none" and events.load_events(ledger) == []


def test_already_known_and_deliberately_omitted_are_distinct(tmp_path):
    ledger = tmp_path / "events.jsonl"
    rid = "r_" + "b"*16
    events.emit("already_known", P, 1, rid, "claude_code", "s", {"finding_id": "f1"}, path=ledger)
    events.emit("deliberately_omitted", P, 1, rid, "claude_code", "s",
                {"finding_id": "f2", "user_reason": "not needed on this internal path"}, path=ledger)
    kinds = {e["kind"] for e in events.load_events(ledger)}
    assert {"already_known", "deliberately_omitted"} <= kinds


# --- operational cases ------------------------------------------------------

def test_duplicated_trigger_one_lesson():
    # same build (same repo + same diff-scoped source) -> deterministic opportunity_id
    a = detector.detect_opportunity(GAP, "r_" + "b"*16, diff_scope="added")
    b = detector.detect_opportunity(GAP, "r_" + "b"*16, diff_scope="added")
    assert a["opportunity_id"] == b["opportunity_id"]


def test_truncated_jsonl_skipped(tmp_path):
    ledger = tmp_path / "events.jsonl"
    events.emit("proposed", P, 1, "r_" + "b"*16, "claude_code", "s",
                {"finding_id": "f1", "classification": "confirmed"}, path=ledger)
    with open(ledger, "a") as fh:
        fh.write('{"kind": "proposed", "truncated')  # torn final line, no newline
    ev = events.load_events(ledger)
    assert len(ev) == 1  # the torn line is skipped, not fatal


def test_version_expiry_does_not_reopen(tmp_path):
    ledger = tmp_path / "events.jsonl"
    rid = "r_" + "b"*16
    events.emit("transferred", P, 1, rid, "claude_code", "s",
                {"opportunity_id": "o1", "direction_id": "d1", "tell_id": "t1",
                 "from_repo_id": "r_" + "a"*16, "to_repo_id": rid}, path=ledger)
    events.emit("expired", P, 1, rid, "claude_code", "s",
                {"principle_id": P, "old_version": 1, "new_version": 2}, path=ledger)
    proj = events.build_projections(path=ledger)
    assert proj["versioned_principle_status"][f"{P}@1"]["kind"] in {"transferred", "expired"}
