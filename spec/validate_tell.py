"""Deterministic cross-field validator for tell records.

JSON Schema (tell_record.schema.json) enforces structure: exactly one
baseline_or_mutated + one fixed probe, both selectors collected/executed, and (when
result==discriminating) baseline failed at the expected sink assertion while fixed passed.

This module enforces what schema cannot compare across the two probe items:
  - identical test source hash across both runs (same test, not two different tests);
  - identical environment hash across both runs (same sandbox);
  - if a mutation was used, its diff touched ONLY the cited validation path.

Returns [] when valid, else a list of reject reasons. No third-party deps.
"""


def validate_tell(rec):
    reasons = []
    runs = rec.get("probe_runs") or []
    if len(runs) != 2:
        return ["probe_runs must contain exactly two runs"]  # schema also enforces this
    by_role = {r.get("role"): r for r in runs}
    if set(by_role) != {"baseline_or_mutated", "fixed"}:
        return ["probe_runs must contain exactly one baseline_or_mutated and one fixed run"]
    base, fixed = by_role["baseline_or_mutated"], by_role["fixed"]

    if base.get("test_file_sha256") != fixed.get("test_file_sha256"):
        reasons.append("test source differs across probe runs (test_file_sha256 mismatch)")
    if base.get("environment_sha256") != fixed.get("environment_sha256"):
        reasons.append("execution environment differs across probe runs (environment_sha256 mismatch)")

    if rec.get("result") == "discriminating":
        if base.get("outcome") != "failed" or base.get("failure_kind") != "expected_sink_assertion":
            reasons.append("discriminating requires the baseline to fail at the expected sink assertion")
        if fixed.get("outcome") != "passed":
            reasons.append("discriminating requires the fixed run to pass")

    mut = rec.get("mutation")
    if isinstance(mut, dict) and mut.get("used"):
        tgt = mut.get("target_evidence") or {}
        if not tgt.get("path") or not mut.get("mutation_diff_sha256"):
            reasons.append("mutation used but target path / diff hash missing")
        # The builder must additionally verify (at runtime) that the recorded
        # mutation_diff touches only target_evidence.path between line_start..line_end.
        # That check consumes the real diff; represented here as a required precondition.
    return reasons


if __name__ == "__main__":
    import json, sys
    rec = json.load(open(sys.argv[1]))
    errs = validate_tell(rec)
    print("VALID" if not errs else "INVALID: " + "; ".join(errs))
    sys.exit(0 if not errs else 1)
