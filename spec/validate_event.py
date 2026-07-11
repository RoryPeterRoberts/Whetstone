"""Deterministic cross-field validator for product events.

JSON Schema (product_event.schema.json) enforces the required evidence payload per kind.
This module enforces the cross-field invariants schema cannot express:
  - transferred: from_repo_id != to_repo_id (a transfer must cross repositories);
  - applied_again: subject repo must equal the event repo_id (same-repo reuse).

Returns [] when valid, else reject reasons. No third-party deps.
"""


def validate_event(ev):
    reasons = []
    kind = ev.get("kind")
    evd = ev.get("evidence") or {}
    if kind == "transferred":
        if evd.get("from_repo_id") == evd.get("to_repo_id"):
            reasons.append("transferred requires from_repo_id != to_repo_id (must cross repositories)")
    if kind == "applied_again":
        # applied_again is same-repo reuse; if a repo is named it must match the event repo_id
        if "repo_id" in evd and evd.get("repo_id") != ev.get("repo_id"):
            reasons.append("applied_again subject repo must equal the event repo_id")
    return reasons


if __name__ == "__main__":
    import json, sys
    ev = json.load(open(sys.argv[1]))
    errs = validate_event(ev)
    print("VALID" if not errs else "INVALID: " + "; ".join(errs))
    sys.exit(0 if not errs else 1)
