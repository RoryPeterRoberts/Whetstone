"""Phase 8 exit tests: pilot metrics are computable from the ledger (spec section 15)."""
import json

import cli
import events
import metrics

P = "p_structured_output_boundary"
R_A = "r_" + "a" * 16
R_B = "r_" + "b" * 16
R_C = "r_" + "c" * 16


def _emit(ledger, kind, repo, evidence):
    events.emit(kind, P, 1, repo, "claude_code", "s", evidence, path=ledger)


def test_empty_ledger_is_computable_no_crash(tmp_path):
    m = metrics.compute_metrics(path=tmp_path / "events.jsonl")
    # rates over an empty ledger are None (never a ZeroDivisionError)
    assert m["acceptance_rate"] is None
    assert m["unaided_transfer_rate"] is None
    assert m["unaided_transfer_count"] == 0
    assert m["counts"] == {}


def test_full_lifecycle_metrics(tmp_path):
    ledger = tmp_path / "events.jsonl"
    # two findings surfaced; one accepted, one rejected
    _emit(ledger, "proposed", R_A, {"finding_id": "f1", "classification": "confirmed"})
    _emit(ledger, "proposed", R_A, {"finding_id": "f2", "classification": "confirmed"})
    _emit(ledger, "accepted", R_A, {"finding_id": "f1"})
    _emit(ledger, "rejected", R_A, {"finding_id": "f2"})
    _emit(ledger, "applied", R_A, {"finding_id": "f1", "tell_id": "t1", "worktree_sha256": "w"})
    # same principle recurs as an opportunity across two DIFFERENT repos
    _emit(ledger, "opportunity_detected", R_B, {"opportunity_id": "o1", "repo_id": R_B, "detector_version": "sob-1"})
    _emit(ledger, "opportunity_detected", R_C, {"opportunity_id": "o2", "repo_id": R_C, "detector_version": "sob-1"})
    # a comparable later opportunity -> recall prompted -> recalled -> transferred
    _emit(ledger, "recall_prompted", R_B, {"opportunity_id": "o1"})
    _emit(ledger, "direction_recalled", R_B, {"opportunity_id": "o1", "direction_id": "d1", "excerpt_sha256": "x"})
    _emit(ledger, "transferred", R_B, {"opportunity_id": "o1", "direction_id": "d1", "tell_id": "t1",
                                       "from_repo_id": R_A, "to_repo_id": R_B})

    m = metrics.compute_metrics(path=ledger)
    assert m["acceptance_rate"] == 0.5              # 1 accepted / 2 proposed
    assert m["top_finding_precision"] == 0.5        # 1 accepted / (1 accepted + 1 rejected)
    assert m["false_positive_rate"] == 0.5          # 1 rejected / 2 proposed
    assert m["application_rate"] == 1.0             # 1 applied / 1 accepted
    assert m["recurrence_rate"] == 1.0             # the principle recurs across 2 repos
    assert m["prompted_recall_rate"] == 1.0         # 1 recalled / 1 prompted
    assert m["unaided_transfer_count"] == 1
    # Rory's denominator: transfers over lessons with a comparable later opportunity
    assert m["comparable_later_opportunities"] == 1
    assert m["unaided_transfer_rate"] == 1.0
    assert m["cost_per_transferred_principle"] == 0.0   # deterministic slice, no model cost


def test_transfer_denominator_is_comparable_opportunities_not_total(tmp_path):
    ledger = tmp_path / "events.jsonl"
    # three proposed findings but only ONE comparable later opportunity (one recall prompted)
    for i in range(3):
        _emit(ledger, "proposed", R_A, {"finding_id": f"f{i}", "classification": "confirmed"})
    _emit(ledger, "recall_prompted", R_B, {"opportunity_id": "o1"})
    _emit(ledger, "transferred", R_B, {"opportunity_id": "o1", "direction_id": "d1", "tell_id": "t1",
                                       "from_repo_id": R_A, "to_repo_id": R_B})
    m = metrics.compute_metrics(path=ledger)
    # rate is 1/1 (comparable opportunities), NOT 1/3 (total findings)
    assert m["unaided_transfer_rate"] == 1.0
    assert m["comparable_later_opportunities"] == 1


def test_cli_metrics_command(tmp_path):
    out = cli.cmd_metrics(events_path=tmp_path / "events.jsonl")
    parsed = json.loads(out)
    assert "unaided_transfer_rate" in parsed and "recurrence_rate" in parsed
