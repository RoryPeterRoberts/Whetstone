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

Early — building v1 (the full loop on one repo). See [`PLAN.md`](PLAN.md).

- Working: the teacher (local, Codex-backed), the command bank, the curated source list, breadcrumb capture.
- Building: the watchers, the filter, the CLI glue.

## Quickstart (dev)

```bash
# infer the LLM-building patterns from a repo's recent history
python whetstone/breadcrumbs.py ~/your-project

# run the teacher (local web app)
python whetstone/teacher.py   # http://localhost:8099
```

Requires [Codex CLI](https://github.com/openai/codex) on PATH (the bootstrap teacher/inference engine; a local model replaces it later). No other dependencies — Python stdlib only.
