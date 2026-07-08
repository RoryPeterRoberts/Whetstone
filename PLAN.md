# Whetstone — v1 plan

**v1 goal:** the full loop, running on **one repo**. Point Whetstone at a git project + the source list;
it finds the recurring gap between how you build and how the frontier now builds, teaches it, and banks it.
That's the whole value prop, thin — enough to demo end to end.

## Components & status

| Piece | What it does | Status |
|---|---|---|
| `whetstone/teacher.py` + `teacher.html` | The teacher — gate → derive → direction+tell; command bank; wall→improve | **built** (adopted) |
| `whetstone/SOURCES.md` | Curated, watchable AI source list (frontier / papers / benchmarks / local) | **built** (adopted) |
| `whetstone/breadcrumbs.py` | Reads git history → infers LLM-building patterns you used → `breadcrumbs.jsonl` | **built** |
| `whetstone/watch.py` | Scans SOURCES via RSS + page-diff (reuse web-change-detector) → `frontier.jsonl` | to build |
| `whetstone/filter.py` | breadcrumbs × frontier → the recurring gap → the teaching target | to build |
| `whetstone/whet.py` (CLI) | Glue: `whet learn <repo>` runs the loop end to end | to build |

## Build order

1. ✅ **Breadcrumbs** — `breadcrumbs.py` (the "what you do" stream).
2. **Watch** — `watch.py`: turn SOURCES.md into a daily `frontier.jsonl` (RSS where it exists, page-diff via the web-change-detector, `hnrss` for keywords).
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
