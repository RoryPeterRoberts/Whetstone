"""Phase 5 exit tests: recall interaction contract + CLI control surface."""
import hashlib
import json
from pathlib import Path

import capture
import cli
import events
import recall

R_B = "r_" + "b" * 16


def _direction_record(excerpt):
    return {
        "direction_id": "d_" + hashlib.sha256(excerpt.encode()).hexdigest()[:16],
        "authorship": "user",
        "redacted_excerpt": excerpt,
        "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
    }


# --- recall outcomes (spec section 11) --------------------------------------

def test_no_direction_defers(tmp_path):
    ledger = tmp_path / "events.jsonl"
    outcome, ev = recall.resolve_recall("o1", None, R_B, "s1", path=ledger)
    assert outcome == "recall_deferred"
    assert ev["kind"] == "recall_deferred" and ev["evidence"]["reason"] == "no_response"


def test_answered_but_unmatched(tmp_path):
    ledger = tmp_path / "events.jsonl"
    dr = _direction_record("please refactor the parser for readability")
    outcome, ev = recall.resolve_recall("o1", dr, R_B, "s1", path=ledger)
    assert outcome == "recall_unmatched"
    assert ev["evidence"]["reason"] == "matcher_failed"


def test_matched_user_direction_recalled(tmp_path):
    ledger = tmp_path / "events.jsonl"
    dr = _direction_record(
        "validate model output against the schema and reject invalid results before writing to the database")
    outcome, ev = recall.resolve_recall("o1", dr, R_B, "s1", path=ledger)
    assert outcome == "direction_recalled"
    assert ev["evidence"]["direction_id"] == dr["direction_id"]
    assert ev["evidence"]["excerpt_sha256"] == dr["excerpt_sha256"]


def test_prompt_recall_is_command_altitude():
    card = recall.recall_prompt()
    assert "Direction:" in card and "Principle:" in card and "Tell:" in card
    # command altitude: no code in the card
    assert "def " not in card and "import " not in card


# --- CLI control surface (spec section 5) -----------------------------------

def test_on_off_toggles_config(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CONFIG", tmp_path / "cfg.json")
    cli.cmd_on()
    assert json.loads((tmp_path / "cfg.json").read_text())["enabled"] is True
    cli.cmd_off()
    assert json.loads((tmp_path / "cfg.json").read_text())["enabled"] is False


def test_status_reads_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CONFIG", tmp_path / "cfg.json")
    ledger = tmp_path / "events.jsonl"
    events.emit("transferred", "p_structured_output_boundary", 1, R_B, "claude_code", "s1",
                {"opportunity_id": "o1", "direction_id": "d1", "tell_id": "t1",
                 "from_repo_id": "r_" + "a" * 16, "to_repo_id": R_B}, path=ledger)
    out = cli.cmd_status(events_path=ledger)
    assert "principles ever transferred: 1" in out


def test_delete_data_removes_product_records_only(tmp_path, monkeypatch):
    ledger = tmp_path / "events.jsonl"
    directions = tmp_path / "direction_record.jsonl"
    proj = tmp_path / "projections"
    ledger.write_text("{}\n")
    directions.write_text("{}\n")
    proj.mkdir()
    (proj / "global_learner.json").write_text("{}")
    build_ev = tmp_path / "build_evidence.jsonl"
    build_ev.write_text("{}\n")  # governance ledger must survive
    monkeypatch.setattr(capture, "DIRECTIONS", directions)
    monkeypatch.setattr(events, "PROJECTIONS", proj)

    cli.cmd_delete_data(events_path=ledger)
    assert not ledger.exists()
    assert not directions.exists()
    assert not proj.exists()
    assert build_ev.exists()  # untouched


def test_diagnostic_reports_versions(tmp_path):
    info = json.loads(cli.cmd_diagnostic(events_path=tmp_path / "events.jsonl"))
    assert info["matcher_version"] and info["detector_version"]
    assert "telemetry" in info["trust"]


def test_cli_main_dispatch(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "CONFIG", tmp_path / "cfg.json")
    assert cli.main(["on"]) == 0
    assert cli.main(["bogus"]) == 2
