"""Runnable end-to-end demo of Whetstone-GT.

    python3 grouptheory/demo.py     (or: cd grouptheory && python3 demo.py)

Teaches one directing principle on a first group-theory problem, then verifies that the
same principle transfers -- proven by a discriminating bounded search, not a guess -- to a
genuinely different second problem. Everything is recorded on the shared Whetstone kernel
ledger, and the kernel's own metrics read it back.
"""
import os
import tempfile

import slice as gt
from _kernel import metrics

DIRECTION = ("Before promoting this to a theorem, identify the load-bearing hypothesis and "
             "weaken it to search for a counterexample.")


def _card(title, card):
    line = "-" * 78
    print(f"\n{line}\n  {title}\n{line}")
    for key in ("finding", "direction", "principle", "tell", "state"):
        label = key.upper() + ":"
        print(f"  {label:11} {card[key]}")


def main():
    d = tempfile.mkdtemp(prefix="whetstone_gt_")
    ledger = os.path.join(d, "events.jsonl")

    print("=" * 78)
    print("  WHETSTONE-GT  |  one directing principle, taught once, verified-transferred")
    print("=" * 78)
    print("  Principle: " + gt.PRINCIPLE_TEXT)

    t1 = gt.teach(gt.CLAIM_P2, gt.WEAKENED_P3, DIRECTION, "order-p2-abelian", "s1", ledger)
    print(f"\n  PROBLEM 1: {gt.CLAIM_P2.statement}")
    _card("Intervention card  (taught in context: order-p2-abelian)", t1["card"])

    res = gt.transfer_to(gt.CLAIM_PQ, gt.WEAKENED_PQ, DIRECTION, t1["context_id"],
                         "order-pq-cyclic", t1["finding_id"], "s2", ledger)
    print(f"\n  PROBLEM 2 (different problem): {gt.CLAIM_PQ.statement}")
    _card("Intervention card  (transfer verified in context: order-pq-cyclic)", res["card"])

    print("\n" + "=" * 78)
    print(f"  KERNEL VERDICT: {res['outcome'].upper()}")
    ev = res["event"]["evidence"]
    print(f"    from source {ev['from_repo_id']}  ->  to source {ev['to_repo_id']}   (cross-context)")
    m = metrics.compute_metrics(path=ledger)
    print("  KERNEL METRICS (read from the shared ledger):")
    for k in ("unaided_transfer_count", "unaided_transfer_rate",
              "comparable_later_opportunities", "prompted_recall_rate"):
        print(f"    {k:32} {m[k]}")
    print("=" * 78)
    print("  Note: 'no counterexample in the bounded family' is SUPPORT, never a theorem.")
    print("  The strong claim here is transfer of the DIRECTING PRINCIPLE, verified by a")
    print("  discriminating search -- exactly the software-engineering kernel, re-used.")


if __name__ == "__main__":
    main()
