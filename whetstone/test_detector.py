"""Phase 4 exit tests (detector + opportunity): flags the gap, clears the fixed path."""
from pathlib import Path

import detector
import events

SOB = Path(detector.__file__).resolve().parent.parent / "spec" / "fixtures" / "structured_output_boundary"
GAP = (SOB / "gap.py").read_text()
FIXED = (SOB / "fixed.py").read_text()
R_B = "r_" + "b" * 16


def test_gap_is_flagged():
    gaps = detector.detect_gaps(GAP)
    assert len(gaps) >= 1
    g = gaps[0]
    assert g["confidence"] == "confirmed"
    assert "execute" in g["sink"]


def test_fixed_is_not_flagged():
    # a validator sits on the model_call -> sink path, so no gap
    assert detector.detect_gaps(FIXED) == []


def test_direct_model_call_into_sink_flagged():
    src = (
        "def h(client, db):\n"
        "    db.execute('INSERT', (client.messages_create(prompt='x'),))\n"
    )
    gaps = detector.detect_gaps(src)
    assert len(gaps) == 1


def test_reassignment_clears_taint():
    src = (
        "def h(client, db):\n"
        "    r = client.messages_create(prompt='x')\n"
        "    r = 'safe literal'\n"
        "    db.execute('INSERT', (r,))\n"
    )
    assert detector.detect_gaps(src) == []


def test_opportunity_on_gap_and_none_on_fixed():
    opp = detector.detect_opportunity(GAP, R_B, diff_scope="added")
    assert opp is not None
    assert opp["opportunity_id"].startswith("o_")
    assert opp["detector_version"] == detector.DETECTOR_VERSION
    assert detector.detect_opportunity(FIXED, R_B) is None


def test_opportunity_makes_a_valid_event():
    # the detector output feeds a schema-valid opportunity_detected event
    opp = detector.detect_opportunity(GAP, R_B, diff_scope="added")
    ev = events.make_event(
        "opportunity_detected", "p_structured_output_boundary", 1, R_B,
        "claude_code", "s1",
        {"opportunity_id": opp["opportunity_id"], "repo_id": R_B,
         "diff_scope": opp["diff_scope"], "detector_version": opp["detector_version"]},
        detector_version=opp["detector_version"],
    )
    assert ev["kind"] == "opportunity_detected"
