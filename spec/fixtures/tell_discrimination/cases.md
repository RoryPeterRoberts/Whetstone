# Tell-discrimination cases (spec §10, §14)

These prove the discrimination protocol accepts only genuinely discriminating tells.

| Case file / setup | Expected verdict | Why |
|-------------------|------------------|-----|
| `vacuous_test.py` — asserts something always true, never reaches the sink | **rejected (vacuous)** | passes in both mutated and un-mutated states |
| baseline probe fails with `ModuleNotFoundError` (missing dep) | **not discriminating** | `failure_kind != expected_sink_assertion` |
| baseline probe errors at collection (bad fixture) | **not discriminating** | `selector_collected == false` |
| `structured_output_boundary/test_boundary.py` against gap→fixed (mutation) | **discriminating** | mutated fails at sink assertion, fixed passes |
| genuine two-commit fail-before/pass-after (`mutation: null`) | **discriminating** | both real states, expected failure then pass |
| mutation edits a file outside the cited validation path | **rejected** | mutation touched more than `target_evidence` |
