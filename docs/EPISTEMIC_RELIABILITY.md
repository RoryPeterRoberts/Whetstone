# Epistemic reliability

Whetstone treats a model-generated gap as a proposal, not a fact. A proposal becomes a teaching target only after a separate read-only pass inspects the target repository's current working tree and returns current-code evidence that deterministic checks can reproduce.

## Evidence chain

Every record in the local `whetstone/findings.jsonl` snapshot exposes three links:

1. **History** — the breadcrumb evidence and commit that caused the pattern to be considered.
2. **Frontier** — the live feed IDs cited by the gap judge. Code strips IDs absent from the indexed feed and attaches only the corresponding real source metadata.
3. **Repository** — the target HEAD, dirty-worktree status, validator verdict and reason, plus current file citations. Each accepted citation contains a repository-relative path, a 1-based inclusive range of at most 20 lines, the exact excerpt, and a SHA-256 hash of the cited file.

The repository validator runs Codex read-only with the target checkout as its working directory. Its citations are still untrusted model output until `validation.verify_repository_evidence` confirms that:

- the path is relative and resolves inside the target repository;
- symlink and traversal escapes are rejected;
- the path is a readable UTF-8 file;
- the line range exists and is no longer than 20 lines; and
- the excerpt exactly equals the current complete lines.

An actionable model verdict with no surviving citation is deterministically downgraded to `insufficient-evidence`. Missing validator results, validator errors and unknown classifications fail closed the same way.

## Classifications

| Classification | Meaning | Eligible for teaching? |
|---|---|---|
| `confirmed` | Current code clearly lacks the proposed move. | Yes |
| `partial` | Current code handles part of the concern, but a specific material gap remains. | Yes |
| `already-handled` | Current code already implements the move or an equivalent. | No |
| `insufficient-evidence` | The repository does not support a responsible verdict, or evidence verification failed. | No |

Every proposal remains in `findings.jsonl`, including rejected citations and their rejection reasons. `gaps.jsonl` is a derived snapshot containing only `confirmed` and `partial` teaching targets.

## Ranking

Risk and model confidence never outrank evidence quality. Findings sort by this evidence tier first:

1. repository-confirmed (`confirmed` or `partial`) **and** frontier-grounded;
2. repository-confirmed but frontier-unverified;
3. repository-evidenced `already-handled` proposals;
4. `insufficient-evidence` proposals.

Risk and confidence break ties only inside a tier. This prevents a high-confidence unsupported claim from outranking a lower-confidence finding grounded in both current code and a real frontier source.

## Validated example

[`examples/validated-finding.json`](../examples/validated-finding.json) is a real finding against Whetstone itself. It identifies the live filter's single Codex judgment while showing that worst-of-N repetition exists only in the separate calibration harness. The example cites exact current lines in both files and stores their hashes. `test_validated_example.py` re-verifies those citations against the checkout, so stale example evidence fails the test suite.

## Boundary of the guarantee

Exact citations establish that the cited code exists in the identified working tree; they do not make the model's semantic interpretation infallible. Whetstone therefore preserves the validator's reason, rejected evidence, frontier status and dirty-worktree state for human review, continues to wrap directions in an evaluate-first gate, and does not equate a disappeared finding with an applied fix.
