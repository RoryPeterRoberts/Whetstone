# Whetstone Filter v2 — canonical pattern names + judge calibration (design)

**Date:** 2026-07-08 · **Status:** design/spec — awaiting approval before `writing-plans`.

## Why
The source-grounding assessment left two goals at ◑ Partial, and the GPT-5.5 review independently flagged the *same two* as what stands between "clever tool" and "proven compounding layer":

1. **Recurrence underfires** — the compounding signal ("recurs across N repos") needs the same habit to get the same name across repos; today breadcrumb pattern names are free-text, so it rarely fires. Without it, Whetstone may over-teach one-offs and miss real habits.
2. **Judge jitters** — `whet check` gives 0–1 must-catch failures run to run; the judge sits on the calibration line and the fresh 60-item frontier primes mild over-flagging of benign practice.

Both live in the filter/judge layer. This spec fixes both, minimally, on the existing code.

## Part A — Canonical pattern names (make recurrence fire)
**Problem.** `breadcrumbs.py` infers free-text pattern names from git diffs; "structured JSON output" in one repo and "schema-constrained outputs" in another are the same habit with different names, so `select()`'s per-pattern repo count never accumulates. The compounding claim rests on this signal.

**Design.**
- **A seed canon** — a small curated list of canonical LLM-building pattern names (`whetstone/canon.jsonl`): e.g. `structured-output-contract`, `llm-as-judge`, `retrieval-grounded-generation`, `rate-limit-and-backoff`, `eval-set-and-regression-gate`, `prompt-versioning-and-telemetry`, `citation-provenance`, `agent-loop-with-state`. Each `{id, name, blurb}`.
- **A normalize step** — after breadcrumbs are inferred, map each free-text pattern to its nearest canonical id in one Codex call ("which canonical pattern is this, or propose a NEW canonical name if none fits"). Cache the map — one call per fresh batch.
- **Grow the canon** — model-proposed new names are appended (light dedup by name), so the taxonomy grows with real use rather than being frozen.
- **Recurrence by canon id** — `select()` counts distinct repos per *canonical id*, not per free-text string. "recurs across N repos" now fires reliably.

**Decision made (flag for veto):** seed taxonomy + LLM-nearest-match + propose-new — not (a) a frozen fixed list (too rigid, misses new habits) or (b) pure LLM clustering each run (unstable — the same habit clusters differently run to run, which is the exact failure we're fixing). Seed gives stability; match handles wording variation; propose-new keeps it open.

## Part B — Judge calibration hardening (kill the must-catch jitter)
**Problem.** The traps that flip (type-hints+docstrings, plain f-string templates, structured-output-done-right) are benign or already-best-practice. The judge over-flags them, especially with 60 fresh frontier items priming "there must be a sharper move."

**Design.**
- **Best-practice anchors** — add to the judge PROMPT a short explicit "these are NOT gaps" list (baseline hygiene + already-current practices): "if the pattern is already current best practice or baseline hygiene, set `gap=false` — do not manufacture a sharper move."
- **Deficiency-naming requirement** — a gap must name what is *deficient* in the current practice, not merely that the topic is active on the frontier. (The structured-output trap over-flags precisely because the feed is full of structured-output content — *trending ≠ your practice is behind*.) Tie it to grounding: the cited source must show a move the practice actually **lacks**.
- **Worst-of-N calibration bar** — `whet check` runs the golden set N times (default 3) and reports the WORST run; it passes only if 0 must-catch across all N. Pin the three observed jitter cases into `golden.jsonl` as regression traps. This makes "calibrated" mean *reliably*, not *once* — honest against a non-deterministic judge.

**Decision made (flag for veto):** prompt anchors + deficiency-naming + worst-of-N — not fine-tuning or merely enlarging the golden set. Cheapest, targets the actual failure mode (topic-trending mistaken for practice-deficiency), and makes the bar honest.

## Scope / constraints
- Stdlib only; extend existing `filter.py`, `breadcrumbs.py`, `whet.py`, `golden.jsonl`. No new deps.
- Grounding stays intact — Part B builds on it (a deficiency must be source-backed).
- TDD; `unittest`; run from `whetstone/`.

## Out of scope (deferred)
- The post-build auto-nudge cadence (the review's UX point) — separate, and only worth it after recurrence + calibration hold.
- Local-model replacement for Codex (the autonomy arc).
- The 2-week real-usage proof run — a usage discipline, not a build. It is the true test of compounding; this spec makes that test *meaningful* (recurrence must work for the floor-rise metric to mean anything).

## Next
`writing-plans` → `subagent-driven-development` to build.
