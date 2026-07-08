# Whetstone — v1 plan

**v1 goal:** the full loop, running on **one repo**. Point Whetstone at a git project + the source list;
it finds the recurring gap between how you build and how the frontier now builds, teaches it, and banks it.
That's the whole value prop, thin — enough to demo end to end.

## v1.1 — the bank became a learning surface (built 2026-07-08, verified end to end)
- **Gate wrapper** — every banked command carries an evaluate-first gate ("judge it against this codebase; if you agree, plan it, don't edit yet"), so a blind paste can't blind-execute. `teach.py` GATE.
- **Risk lens** — the filter tags each gap money / data / production / quality and sorts money-risk to the top. Verified: fixerupper's concurrency gap surfaced `[MONEY · HIGH]` first.
- **Principle-banking** — each lesson banks the one-line transferable principle (the rod), not just the command (the fish).
- **Explain + refine** — every bank card has an `explain` button that opens the teacher on that command's logic chain; `simpler / technical / + context` refine without retyping. New teacher acts: explain/technical/context.
- **Organised by project** — the bank groups commands under the repo they came from.
- **Close-the-loop** — `taught.jsonl` logs each taught gap; next `whet learn` marks any gap that's dropped out of the filter as applied and shows the win. Heuristic: relies on the gap leaving the fresh filter run (filter variance can false-close — tighten with an explicit "now best-practice" signal later).

Still deferred: canonical pattern names (so recurrence fires), OpenBrain write-back, page-diff leaderboards, de-personalise for public.

## Built 2026-07-08: /whetstone as a Claude Code skill (+ review mode)
Instead of (or alongside) a standalone bundle, ship Whetstone as a Claude Code skill: `/whetstone [repo]`, default = the current repo.

**Why this is the right form — it makes the safety structural.** The process we ran by hand this session — Whetstone surfaces a gap + direction, the agent WITH FULL REPO CONTEXT reviews whether it is a genuine enhancement for THIS code, agrees or refuses with reasons, plans, and implements only on approval — becomes the skill's *defined workflow*, not a hopeful line inside a pasted prompt. A user cannot strip the gate and an agent cannot be handed a raw command it disagrees with or that would damage the repo; the evaluate-first step is guaranteed by the skill, not merely suggested.

**Bonus:** it sidesteps the bundle / launcher / API-key questions — Claude Code is the runtime, its model is already present, the current repo is the default target, and the agent that evaluates the fix is the one that implements it.

**Open design question (decide at build):** keep the gap-finder/teacher on Codex so the finder is a DIFFERENT model than the implementer (independent judgment = a safety plus), or go fully native on Claude's own model (simpler, no external dependency).

**STATUS — built 2026-07-08.** Live at `~/.claude/skills/whetstone/SKILL.md` (source in `skill/whetstone/`). Open question resolved: **Codex stays the finder** (finder ≠ implementer = independent judgment). Also added the `/whetstone review` mode: after changes land, the agent writes a command-altitude review (title / what / why / tell, no code) and POSTs it to the teacher `/review` endpoint; the UI shows them in a "what was built" drawer, grouped by repo, with dig-in. To use the new bits: restart `teacher.py` (new `/review` + `/reviews` endpoints) and start a fresh Claude Code session (skills load at session start).

## Built 2026-07-08: altitude dial (Rory's idea)
Replace the ad-hoc refine buttons (simpler / technical / + context) everywhere — lessons, bank, reviews — with ONE altitude dial the user controls:
**High Orbit** (one line — capability + why) → **Low Orbit** (the shape, no code) → **Helicopter** (how it works, conceptually) → **Close-up** (the builder's approach, bridging toward code) → **Microscope** (the actual code / diff).
Microscope is the escape hatch that resolves "command altitude, never code": code isn't forbidden, it's the deepest zoom — shown only when the user chooses to descend. **BUILT** — 5 teacher acts + the dial replaces simpler/technical/context; verified the range (high orbit = one sentence; microscope = the actual code/diff). The dial acts on the last teacher answer, so it covers lessons, bank dig-in, and review dig-in without per-card buttons.

## Components & status

| Piece | What it does | Status |
|---|---|---|
| `whetstone/teacher.py` + `teacher.html` | The teacher — gate → derive → direction+tell; command bank; wall→improve | **built** (adopted) |
| `whetstone/SOURCES.md` | Curated, watchable AI source list (frontier / papers / benchmarks / local) | **built** (adopted) |
| `whetstone/breadcrumbs.py` | Reads git history → infers LLM-building patterns you used → `breadcrumbs.jsonl` | **built** |
| `whetstone/watch.py` | Scans SOURCES via RSS → `frontier.jsonl` (10 feeds live; page-diff via web-change-detector later) | **built** |
| `whetstone/filter.py` | breadcrumbs × frontier → the recurring gap → the teaching target | to build |
| `whetstone/whet.py` (CLI) | Glue: `whet learn <repo>` runs the loop end to end | to build |

## Build order

1. ✅ **Breadcrumbs** — `breadcrumbs.py` (the "what you do" stream).
2. ✅ **Watch** — `watch.py`: SOURCES.md → live `frontier.jsonl` (10 RSS/Atom feeds + `hnrss` keywords, stdlib only). Page-diff leaderboards via the web-change-detector: later.
3. **Filter** — `filter.py`: for each recurring breadcrumb pattern, is there a sharper current move in `frontier.jsonl` that you're not using? Cheap local pass (5090). Output = the teaching target(s).
4. **Wire** — feed the target into the existing teacher; the lesson's direction lands in the command bank.
5. **CLI** — `whet learn <repo>` runs 1→4 and opens the teacher on the result.
6. **Demo** — run the whole thing on one real repo (DeepResearch or FixerUpper).

## Decisions locked
- Standalone product, **not** embedded in Sapien. Output (banked principles) *can* write to OpenBrain so it resurfaces in real sessions — later.
- Breadcrumbs from **git diffs**, not a live session hook (zero coupling, works today).
- Codex is the bootstrap engine; a local 5090 model replaces it for the cheap passes (breadcrumbs, filter) later.
- Per-user teaching profile: v1 is tuned to one builder; generalise to per-user config after it proves out.

## Not in v1 (deferred)
- Multi-repo / whole-workspace scanning.
- The spaced-return / retention scheduler.
- Live session hook (richer breadcrumbs).
- Packaging, auth, hosting — it's a local tool until the loop earns it.
