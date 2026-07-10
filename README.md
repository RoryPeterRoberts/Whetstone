# Whetstone

**The layer that makes you a better LLM builder — while you build.**

Coding agents (OpenClaw, Claude Code, KERN) do the work. That's the problem: the agent does the
reps, so it banks the gains, not you. You ship apps and stay roughly the same builder. Your hours
don't compound.

Whetstone sits alongside whatever harness you use and turns those same hours into compounding skill.
It reads what you actually build, watches what's now possible on the frontier, and teaches you the
**recurring gap** between the two — at the level of *directing and judging* an agent, never writing code.
Then it banks the move so you never re-learn it. Every run is evidence-bearing: failed stages stop the loop, findings stay tied to their target repo, and a vanished finding is never mistaken for proof that the code changed.

## How it works (the loop)

1. **Breadcrumbs** — reads your git history and infers the LLM-building patterns you actually used. No live hook; a model reads the diffs after the fact.
2. **Watch** — scans a curated source list (frontier releases, papers, benchmarks) for what's now possible.
3. **Filter** — the heart: where do the two diverge *and recur*? A move you make often, done a stale way, when a sharper current one exists. Everything else is discarded.
4. **Teach** — only survivors reach the teacher: *why you need it* (you hold the veto) → the principle, derived (you follow the logic, you own it) → the direction to give your agent, and the tell to judge it.
5. **Bank** — two ledgers compound: the **principle** in your head (derived, so it sticks) and the **command** in a reusable bank (so your memory is offloaded).

Full architecture: [`MACHINE.md`](MACHINE.md). Teaching contract: [`whetstone/TEACHING_METHOD.md`](whetstone/TEACHING_METHOD.md). Source list: [`whetstone/SOURCES.md`](whetstone/SOURCES.md).

## Why it's different

Every other tool in this space *does the work*. Whetstone makes **you** better at commanding those tools —
the one thing that compounds and the one thing they can't sell you. It's the difference between 20 hours
of experience and 20 hours of expertise.

## Status

Working research prototype: the complete evidence-bearing loop runs locally on one git repository. The learning effect is not yet externally validated; see [`PLAN.md`](PLAN.md).

## Five-minute quickstart

Prerequisites: Python 3.10+, git, and an installed and authenticated [Codex CLI](https://github.com/openai/codex). Whetstone otherwise uses only the Python standard library.

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

Runtime observations, profiles, lessons, and run ledgers are local JSONL files ignored by git. Set `WHETSTONE_LEARNER` to personalize the teacher; it defaults to `Builder`.

## What to expect

Whetstone’s `prepare` command refreshes the curated frontier before the build, then reads recent code history, compares recurring LLM-building patterns with its current frontier snapshot, and banks only the gaps that survive the filter. Treat every finding as a proposal: inspect its evidence and use the evaluate-first command before changing production code.

## License

[MIT](LICENSE).
