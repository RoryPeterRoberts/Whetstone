"""Whetstone-GT tests: the math is correct, the tell discriminates, transfer is recorded."""
import search
import slice as gt
from _kernel import events, metrics, transfer

GOOD_DIRECTION = ("Before promoting this to a theorem, identify the load-bearing hypothesis "
                  "and weaken it to search for a counterexample.")


# --- the mathematics (checked by sympy) -------------------------------------

def test_p2_family_has_no_counterexample_to_abelian():
    r = search.search(search.order_p2_family, lambda G: True, search.is_abelian)
    assert r["counterexample"] is None
    assert "C2xC2" in r["checked"] and "C3xC3" in r["checked"]


def test_order_8_refutes_abelian_with_D4():
    r = search.search(search.order_8_family, lambda G: True, search.is_abelian)
    assert r["counterexample"] == ("D4", 8)


def test_order_15_supports_cyclic_order_6_refutes_it():
    assert search.search(search.order_15_family, lambda G: True, search.is_cyclic)["counterexample"] is None
    assert search.search(search.order_6_family, lambda G: True, search.is_cyclic)["counterexample"] == ("S3", 6)


# --- the discrimination protocol --------------------------------------------

def test_p2_claim_is_discriminating_via_weakening():
    t = search.register_tell(gt.CLAIM_P2, gt.WEAKENED_P3)
    assert t["discriminating"] is True
    assert t["base"]["counterexample"] is None
    assert t["weakened"]["counterexample"] == ("D4", 8)


def test_pq_claim_is_discriminating_via_weakening():
    t = search.register_tell(gt.CLAIM_PQ, gt.WEAKENED_PQ)
    assert t["discriminating"] is True
    assert t["weakened"]["counterexample"] == ("S3", 6)


def test_vacuous_when_weakening_finds_no_counterexample():
    # "weaken" to the same claim: nothing is shown load-bearing -> not discriminating
    t = search.register_tell(gt.CLAIM_P2, gt.CLAIM_P2)
    assert t["discriminating"] is False and t["result"] == "vacuous"


def test_claim_refuted_in_its_own_family_is_not_discriminating():
    # asserting order-8 groups are abelian is false in its own family (D4) -> not a tell
    false_claim = gt.WEAKENED_P3
    t = search.register_tell(false_claim, gt.WEAKENED_P3)
    assert t["discriminating"] is False
    assert t["base"]["counterexample"] == ("D4", 8)


# --- the direction matcher --------------------------------------------------

def test_direction_matcher():
    assert gt.match_direction(GOOD_DIRECTION) is True
    assert gt.match_direction("please compute the character table") is False


# --- full slice on the shared kernel ledger ---------------------------------

def test_principle_transfers_across_two_problems(tmp_path):
    ledger = tmp_path / "events.jsonl"
    t1 = gt.teach(gt.CLAIM_P2, gt.WEAKENED_P3, GOOD_DIRECTION, "order-p2-abelian", "s1", ledger)
    assert t1["tell"]["discriminating"] is True

    res = gt.transfer_to(gt.CLAIM_PQ, gt.WEAKENED_PQ, GOOD_DIRECTION,
                         t1["context_id"], "order-pq-cyclic", t1["finding_id"], "s2", ledger)
    assert res["outcome"] == "transferred"
    ev = res["event"]["evidence"]
    assert ev["from_repo_id"] == t1["context_id"] and ev["to_repo_id"] == res["context_id"]
    assert ev["from_repo_id"] != ev["to_repo_id"]

    # the SAME kernel metrics module reads the shared ledger
    m = metrics.compute_metrics(path=ledger)
    assert m["unaided_transfer_count"] == 1
    # teaching is suppressed in the transfer context once it has transferred
    assert transfer.should_teach(res["context_id"], gt.PRINCIPLE_ID, path=ledger) is False


def test_no_direction_is_practice_present_not_transferred(tmp_path):
    ledger = tmp_path / "events.jsonl"
    t1 = gt.teach(gt.CLAIM_P2, gt.WEAKENED_P3, GOOD_DIRECTION, "order-p2-abelian", "s1", ledger)
    # a discriminating tell but NO qualifying human direction -> practice_present, never transferred
    res = gt.transfer_to(gt.CLAIM_PQ, gt.WEAKENED_PQ, "compute something unrelated",
                         t1["context_id"], "order-pq-cyclic", t1["finding_id"], "s2", ledger)
    assert res["outcome"] == "practice_present"
    assert all(e["kind"] != "transferred" for e in events.load_events(ledger))
