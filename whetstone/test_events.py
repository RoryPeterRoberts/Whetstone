"""Phase 2 exit tests: event ledger replay reproduces state; migration runs once."""
import json
from pathlib import Path

import pytest

import events


R_A = "r_" + "a" * 16
R_B = "r_" + "b" * 16
P = "p_structured_output_boundary"


def _emit(tmp, kind, evidence, repo_id=R_A, pv=1, **fields):
    return events.emit(kind, P, pv, repo_id, "claude_code", "s1", evidence,
                       path=tmp, **fields)


# --- validation: an invalid event can never be written -----------------------

def test_invalid_event_refused(tmp_path):
    ledger = tmp_path / "events.jsonl"
    # transferred with from==to violates the cross-field invariant
    with pytest.raises(ValueError):
        events.emit("transferred", P, 1, R_A, "claude_code", "s1",
                    {"opportunity_id": "o1", "direction_id": "d1", "tell_id": "t1",
                     "from_repo_id": R_A, "to_repo_id": R_A}, path=ledger)
    # empty evidence for a kind that requires a payload
    with pytest.raises(ValueError):
        events.emit("transferred", P, 1, R_A, "claude_code", "s1", {}, path=ledger)
    # nothing was written
    assert not ledger.exists() or ledger.read_text().strip() == ""


def test_bad_exit_code_style_payload_rejected(tmp_path):
    ledger = tmp_path / "events.jsonl"
    with pytest.raises(ValueError):
        events.emit("deliberately_omitted", P, 1, R_A, "claude_code", "s1",
                    {"finding_id": "f1", "user_reason": ""}, path=ledger)  # empty reason


# --- replay: current state is derived, and a fresh replay reproduces it -------

def test_replay_reproduces_state(tmp_path):
    ledger = tmp_path / "events.jsonl"
    _emit(ledger, "proposed", {"finding_id": "f1", "classification": "confirmed"})
    _emit(ledger, "accepted", {"finding_id": "f1"})
    _emit(ledger, "opportunity_detected",
          {"opportunity_id": "o1", "repo_id": R_B, "detector_version": "d1"}, repo_id=R_B)
    _emit(ledger, "direction_recalled",
          {"opportunity_id": "o1", "direction_id": "d1", "excerpt_sha256": "x"}, repo_id=R_B)
    _emit(ledger, "transferred",
          {"opportunity_id": "o1", "direction_id": "d1", "tell_id": "t1",
           "from_repo_id": R_A, "to_repo_id": R_B}, repo_id=R_B)

    first = events.build_projections(path=ledger)
    # rebuild from scratch off the same immutable log -> identical
    second = events.build_projections(events.load_events(ledger))
    assert first == second

    assert first["global_learner"]["ever_transferred"] is True
    assert first["global_learner"]["ever_recalled"] is True
    assert first["per_repo_disposition"][R_B][P]["kind"] == "transferred"
    assert first["versioned_principle_status"][f"{P}@1"]["kind"] == "transferred"


def test_versioned_status_does_not_reopen_history(tmp_path):
    ledger = tmp_path / "events.jsonl"
    _emit(ledger, "transferred",
          {"opportunity_id": "o1", "direction_id": "d1", "tell_id": "t1",
           "from_repo_id": R_A, "to_repo_id": R_B}, repo_id=R_B, pv=1)
    # a detector bump opens a NEW versioned key, leaving v1 settled
    _emit(ledger, "proposed", {"finding_id": "f2", "classification": "confirmed"}, pv=2)
    proj = events.build_projections(path=ledger)
    assert proj["versioned_principle_status"][f"{P}@1"]["kind"] == "transferred"
    assert proj["versioned_principle_status"][f"{P}@2"]["kind"] == "proposed"


def test_projections_rebuildable_after_delete(tmp_path):
    ledger = tmp_path / "events.jsonl"
    _emit(ledger, "proposed", {"finding_id": "f1", "classification": "confirmed"})
    out = tmp_path / "projections"
    events.rebuild_projections(path=ledger, out_dir=out)
    snap = json.loads((out / "global_learner.json").read_text())
    # delete + rebuild reproduces the same snapshot
    (out / "global_learner.json").unlink()
    events.rebuild_projections(path=ledger, out_dir=out)
    assert json.loads((out / "global_learner.json").read_text()) == snap


# --- migration: taught.jsonl -> seed events, once and idempotent -------------

def _write_taught(tmp_path):
    rows = [
        {"ts": 1, "project": "fixerupper", "pattern": "Structured JSON output",
         "current_move": "Schema-constrained", "status": "open"},
        {"ts": 2, "project": "Whetstone", "pattern": "Pipeline orchestration",
         "current_move": "Agent loop", "status": "needs_verification"},
        {"ts": 3, "project": "X", "pattern": "Weird", "current_move": "?", "status": "mystery"},
    ]
    p = tmp_path / "taught.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_migration_runs_once_and_is_idempotent(tmp_path):
    taught = _write_taught(tmp_path)
    ledger = tmp_path / "events.jsonl"

    r1 = events.migrate_taught(taught, ledger)
    assert r1 == {"appended": 3, "skipped": 0}
    kinds = [e["kind"] for e in events.load_events(ledger)]
    assert kinds.count("proposed") == 1              # the 'open' row
    assert kinds.count("needs_verification") == 2    # needs_verification + fail-safe 'mystery'

    # re-run: nothing new, projections identical
    before = events.build_projections(path=ledger)
    r2 = events.migrate_taught(taught, ledger)
    assert r2 == {"appended": 0, "skipped": 3}
    assert events.build_projections(path=ledger) == before


def test_migration_never_invents_transferred(tmp_path):
    taught = _write_taught(tmp_path)
    ledger = tmp_path / "events.jsonl"
    events.migrate_taught(taught, ledger)
    proj = events.build_projections(path=ledger)
    assert proj["global_learner"]["ever_transferred"] is False
    # legacy repo ids are namespaced so they cannot collide with real repo_ids
    assert all(r.startswith("r_legacy_") for r in proj["per_repo_disposition"])


def test_real_taught_migrates_clean(tmp_path):
    """The actual repo taught.jsonl migrates without error and invents no transfer."""
    real = Path(events.TAUGHT)
    if not real.exists():
        pytest.skip("no taught.jsonl in repo")
    ledger = tmp_path / "events.jsonl"
    res = events.migrate_taught(real, ledger)
    assert res["appended"] > 0
    assert events.build_projections(path=ledger)["global_learner"]["ever_transferred"] is False
