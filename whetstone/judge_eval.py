#!/usr/bin/env python3
"""Whetstone — calibrated judge harness.

The filter is an LLM-as-judge; its verdicts are the whole product. This runs the REAL judge
(filter.judge) against golden cases whose answers we already know, and reports whether it still
catches known gaps and resists known non-gaps. If it fails a must-catch case, the judge is not
calibrated — do not trust its rankings until it passes.

    python judge_eval.py
"""
import json, sys
from pathlib import Path
import filter as flt

ROOT = Path(__file__).resolve().parent
GOLDEN = ROOT / "golden.jsonl"


def load_golden():
    rows = []
    if GOLDEN.exists():
        for ln in GOLDEN.read_text().splitlines():
            ln = ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except Exception: pass
    return rows


def _norm(s):
    return " ".join((s or "").lower().split())


def _one_run(golden, pats):
    items = flt.judge(pats)
    if len(items) == len(golden):
        got_list = [bool(it.get("gap")) for it in items]
    else:
        vmap = {_norm(it.get("pattern")): bool(it.get("gap")) for it in items}
        got_list = [vmap.get(_norm(g["pattern"])) for g in golden]
    rows, passed, must_fail = [], 0, 0
    for g, got in zip(golden, got_list):
        exp = bool(g["expect"])
        ok = (got == exp)
        passed += ok
        if not ok and g.get("must"):
            must_fail += 1
        mark = "ok" if ok else ("MISS" if exp else ("FALSE+" if got is not None else "MISSING"))
        rows.append((mark, "*" if g.get("must") else " ", exp, got, g["pattern"]))
    return rows, passed, must_fail


def run(n_runs=3):
    golden = load_golden()
    if not golden:
        print("no golden cases — write golden.jsonl first"); return 1

    pats = [{"pattern": g["pattern"], "evidence": g.get("evidence", ""), "n_repos": 1} for g in golden]
    n_runs = max(1, n_runs)
    worst = None  # (rows, passed, must_fail) — most must-fails, then fewest passed
    for _ in range(n_runs):
        rows, passed, must_fail = _one_run(golden, pats)
        if worst is None or must_fail > worst[2] or (must_fail == worst[2] and passed < worst[1]):
            worst = (rows, passed, must_fail)
    rows, passed, must_fail = worst

    n = len(golden)
    print(f"\ncalibrated judge harness — worst of {n_runs} runs: {passed}/{n} correct  ({must_fail} must-catch failures)\n")
    for mark, star, exp, got, pat in rows:
        eg = "gap" if exp else "no-gap"
        gg = ("gap" if got else "no-gap") if got is not None else "MISSING"
        print(f"  [{mark:7}]{star} expect {eg:6} · got {gg:7} · {pat[:64]}")
    print()
    if must_fail:
        print(f"✗ judge is NOT calibrated — {must_fail} must-catch case(s) wrong in the worst of {n_runs} runs. "
              "Fix the judge (prompt/rubric) before trusting its rankings.")
        return 1
    if passed < n:
        print(f"~ judge passed every must-catch case across {n_runs} runs but missed {n - passed} softer one(s) — usable, watch the rankings.")
        return 0
    print(f"✓ judge is calibrated — every golden case correct across {n_runs} runs.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
