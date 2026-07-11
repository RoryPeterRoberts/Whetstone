"""Phase 6 exit tests: executable tell discrimination + two-leg transfer (learning cases)."""
from pathlib import Path

import events
import tell
import transfer

SOB = Path(tell.__file__).resolve().parent.parent / "spec" / "fixtures" / "structured_output_boundary"
DISC = tell.SPEC / "fixtures" / "tell_discrimination"
GAP = (SOB / "gap.py").read_text()
FIXED = (SOB / "fixed.py").read_text()
TEST = (SOB / "test_boundary.py").read_text()
VACUOUS = (DISC / "vacuous_test.py").read_text()

R_A = "r_" + "a" * 16
R_B = "r_" + "b" * 16
P = "p_structured_output_boundary"


def _discriminating_tell(repo_id=R_B):
    return tell.register_tell(GAP, FIXED, TEST, P, repo_id,
                             mutation=tell.mutation_block(FIXED, GAP))


def _direction():
    return {"direction_id": "d_match", "authorship": "user"}


# --- the executable tell (spec section 10 discrimination cases) --------------

def test_genuine_tell_is_discriminating():
    r = _discriminating_tell()
    assert r["discriminating"] is True and r["result"] == "discriminating"
    roles = {p["role"]: p for p in r["tell_record"]["probe_runs"]}
    assert roles["baseline_or_mutated"]["failure_kind"] == "expected_sink_assertion"
    assert roles["fixed"]["outcome"] == "passed"


def test_vacuous_tell_rejected():
    r = tell.register_tell(GAP, FIXED, VACUOUS, P, R_B)
    assert r["discriminating"] is False and r["result"] == "vacuous"


def test_import_error_baseline_not_discriminating():
    bad = "from nonexistent_pkg import thing\ndef test_x():\n    assert thing() == 0\n"
    r = tell.register_tell(GAP, FIXED, bad, P, R_B)
    assert r["discriminating"] is False
    assert r["tell_record"] is None  # a non-collecting probe cannot be encoded


def test_probes_share_test_and_environment():
    r = _discriminating_tell()
    pb, pf = r["tell_record"]["probe_runs"]
    assert pb["test_file_sha256"] == pf["test_file_sha256"]
    assert pb["environment_sha256"] == pf["environment_sha256"]


# --- two-leg transfer decision table (spec section 11) ----------------------

def test_both_legs_different_repo_is_transferred(tmp_path):
    ledger = tmp_path / "events.jsonl"
    outcome, ev = transfer.verify_transfer(
        opportunity_id="o1", finding_id="f1", from_repo_id=R_A, to_repo_id=R_B,
        matched_direction=_direction(), tell_result=_discriminating_tell(R_B), path=ledger)
    assert outcome == "transferred"
    assert ev["evidence"]["from_repo_id"] != ev["evidence"]["to_repo_id"]


def test_both_legs_same_repo_is_applied_again(tmp_path):
    ledger = tmp_path / "events.jsonl"
    outcome, ev = transfer.verify_transfer(
        opportunity_id="o1", finding_id="f1", from_repo_id=R_B, to_repo_id=R_B,
        matched_direction=_direction(), tell_result=_discriminating_tell(R_B), path=ledger)
    assert outcome == "applied_again"
    assert ev["kind"] == "applied_again"


def test_direction_only_is_recalled_not_transferred(tmp_path):
    ledger = tmp_path / "events.jsonl"
    vac = tell.register_tell(GAP, FIXED, VACUOUS, P, R_B)  # not discriminating
    outcome, ev = transfer.verify_transfer(
        opportunity_id="o1", finding_id="f1", from_repo_id=R_A, to_repo_id=R_B,
        matched_direction=_direction(), tell_result=vac, path=ledger)
    assert outcome == "direction_recalled" and ev is None
    assert events.load_events(ledger) == []  # no strong claim recorded


def test_artifact_only_is_practice_present(tmp_path):
    ledger = tmp_path / "events.jsonl"
    outcome, ev = transfer.verify_transfer(
        opportunity_id="o1", finding_id="f1", from_repo_id=R_A, to_repo_id=R_B,
        matched_direction=None, tell_result=_discriminating_tell(R_B), path=ledger)
    assert outcome == "practice_present"
    assert ev["kind"] == "practice_present"


def test_unstable_worktree_fails_closed(tmp_path):
    ledger = tmp_path / "events.jsonl"
    outcome, ev = transfer.verify_transfer(
        opportunity_id="o1", finding_id="f1", from_repo_id=R_A, to_repo_id=R_B,
        matched_direction=_direction(), tell_result=_discriminating_tell(R_B),
        worktree_stable=False, path=ledger)
    assert outcome == "none" and ev is None
    assert events.load_events(ledger) == []
