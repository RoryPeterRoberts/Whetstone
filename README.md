# Whetstone

**The layer that makes you a better LLM builder — while you build.**

Coding agents (OpenClaw, Claude Code, KERN) do the work. That's the problem: the agent does the
reps, so it banks the gains, not you. You ship apps and stay roughly the same builder. Your hours
don't compound.

Whetstone sits alongside whatever harness you use and turns those same hours into compounding skill.
It reads what you actually build, watches what's now possible on the frontier, and teaches you the
**recurring gap** between the two — at the level of *directing and judging* an agent, never writing code.
Then it banks the move so you never re-learn it. Every run is evidence-bearing: failed stages stop the loop, every proposed gap is checked against current repository code, and a vanished finding is never mistaken for proof that the code changed. Model-cited file evidence is accepted only when its path, line range, and exact excerpt match the working tree.

## How it works (the loop)

1. **Breadcrumbs** — reads your git history and infers the LLM-building patterns you actually used. No live hook; a model reads the diffs after the fact.
2. **Watch** — scans a curated source list (frontier releases, papers, benchmarks) for what's now possible.
3. **Filter** — the heart: where do the two diverge *and recur*? A move you make often, done a stale way, when a sharper current one exists. Everything else is discarded.
4. **Validate** — inspects the target's current working tree, classifies every proposal as `confirmed`, `partial`, `already-handled`, or `insufficient-evidence`, and fails closed when an actionable verdict lacks an exact code citation.
5. **Teach** — only `confirmed` or `partial` survivors reach the teacher: *why you need it* (you hold the veto) → the principle, derived (you follow the logic, you own it) → the direction to give your agent, and the tell to judge it.
6. **Bank** — two ledgers compound: the **principle** in your head (derived, so it sticks) and the **command** in a reusable bank (so your memory is offloaded).

Full architecture: [`MACHINE.md`](MACHINE.md). Teaching contract: [`whetstone/TEACHING_METHOD.md`](whetstone/TEACHING_METHOD.md). Source list: [`whetstone/SOURCES.md`](whetstone/SOURCES.md).

## Why it's different

Every other tool in this space *does the work*. Whetstone makes **you** better at commanding those tools —
the one thing that compounds and the one thing they can't sell you. It's the difference between 20 hours
of experience and 20 hours of expertise.

## Status

Working research prototype: the complete evidence-bearing loop runs locally on one git repository. The learning effect is not yet externally validated; see [`PLAN.md`](PLAN.md).

## Five-minute quickstart

Prerequisites: Python 3.11+, git, and an installed and authenticated [Codex CLI](https://github.com/openai/codex). Whetstone otherwise uses only the Python standard library.

```bash
git clone https://github.com/RoryPeterRoberts/Whetstone.git
cd Whetstone

# Before a build: refresh the frontier, analyse your existing patterns,
# and teach up to three relevant gaps
python whetstone/whet.py prepare ~/your-project 14 3

# Open the local learning surface
WHETSTONE_LEARNER="Your name" python whetstone/teacher.py
# Visit http://localhost:8099
```

Runtime observations, profiles, lessons, full classified finding snapshots (`findings.jsonl`), validated teaching targets (`gaps.jsonl`), and run ledgers are local JSONL files ignored by git. Each finding carries history → frontier → current-repository evidence, including the target HEAD/worktree state and hashes for exact code citations. The `prepare` command prints and each run records the Codex model and reasoning effort inherited from the builder’s local `~/.codex/config.toml`; Whetstone does not invoke the models used by the target repository. Set `WHETSTONE_LEARNER` to personalize the teacher; it defaults to `Builder`.

## Model and data flow

The frontier refresh is ordinary RSS/Atom fetching; it uses no model. Pattern inference, canonicalization, gap judgment, repository validation, and lesson generation run through the builder’s authenticated Codex CLI. Repository validation runs read-only in the target checkout; deterministic code then rejects fabricated, stale, out-of-repository, or mismatched citations. Whetstone inherits the user’s configured Codex model and reasoning effort, prints them before `prepare`, and records them with the run. Target-repository models—Gemini, Claude, local models, or others—are inspected as code patterns but are not invoked.

## What to expect

Whetstone’s `prepare` command refreshes the curated frontier before the build, reads recent code history, compares recurring LLM-building patterns with its current frontier snapshot, then checks every proposed gap against present code. Findings with verified frontier and repository evidence rank first; repository-confirmed but frontier-unverified findings follow; already-handled and insufficient-evidence findings remain visible but are never taught.

See [Epistemic reliability](docs/EPISTEMIC_RELIABILITY.md) for the evidence contract and [the checked-in validated example](examples/validated-finding.json).

## License

[MIT](LICENSE).
