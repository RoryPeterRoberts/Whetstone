# Whetstone Source-Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every gap Whetstone's judge flags must cite the real frontier item(s) behind it — or be marked "unverified" — and fabricated citations are caught in code, so a hallucinated source (like the fake arxiv links the self-test produced) can never ride through to a banked finding.

**Architecture:** The live frontier feed already lands in `frontier.jsonl`. We tag each item a short id (`F1…Fn`), show those ids to the judge, and require it to cite the ids that justify each gap (or `[]` for its own knowledge). Code then keeps only ids that actually exist in the feed — fabricated ids are dropped and the gap is marked `grounded: false`. The `grounded` flag and the real `sources` flow through gaps → teach → bank → UI, and the teacher prompt is handed the real sources and told never to invent a citation or URL.

**Tech Stack:** Python 3 standard library only (`json`, `re`, `subprocess`, `pathlib`, `unittest`, `unittest.mock`). Codex CLI (`gpt-5.5`) is the judge/teacher engine, reached via `subprocess`. No web framework — `teacher.py` is `http.server`.

## Global Constraints

- **Stdlib only — no new dependencies.** Tests use `unittest` + `unittest.mock`, not pytest.
- **Run all commands from `/home/rory/JOBS/Whetstone/whetstone/`** (the scripts resolve paths from their own location; the test file imports `filter`/`teach` as top-level modules, which only resolves from this directory).
- **Codex must be on `PATH`** for live runs only. Unit tests mock `call_codex`, so they need no network and no Codex.
- **Ungrounded findings are marked, never dropped.** `source_ids: []` is valid — it means "model knowledge," surfaced as `grounded: false`, not an error.
- **Touch only what each task names.** Match the existing terse style (compact functions, no docstring padding beyond what's shown).
- **The test file is flat:** `whetstone/test_grounding.py` (sits beside `filter.py` so `import filter` works).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `whetstone/filter.py` | The judge: breadcrumbs × frontier → gaps. Owns frontier indexing, the judge prompt, and citation verification. | Modify |
| `whetstone/teach.py` | Gap → lesson + banked command. Passes real sources to the teacher; carries grounding onto the bank entry. | Modify |
| `whetstone/teacher.py` | Local teacher server. `/bank` already returns the whole entry, so grounding passes through untouched. | No change (verified in Task 6) |
| `whetstone/teacher.html` | Teacher UI. Bank cards gain a grounded/unverified line. | Modify |
| `whetstone/test_grounding.py` | Unit tests for indexing, verification, prompt rules, teach grounding. | Create |

---

## Task 1: Frontier ids + index

**Files:**
- Modify: `whetstone/filter.py` (replace `load_frontier`, add `_index` + `frontier_index`)
- Create: `whetstone/test_grounding.py`

**Interfaces:**
- Produces: `filter._index(items: list[dict]) -> (digest: str, id_map: dict[str, dict])` — pure; each item gets id `F{n}`; `id_map["F1"] == {"source","title","link"}`. `filter.frontier_index(cap=45) -> (digest, id_map)` reads `frontier.jsonl`. `filter.load_frontier(cap=45) -> str` returns the digest only (back-compat for `judge`).

- [ ] **Step 1: Write the failing test**

Create `whetstone/test_grounding.py`:

```python
import unittest
from unittest import mock
import filter as flt


class TestIndex(unittest.TestCase):
    def test_index_assigns_ids_and_map(self):
        items = [{"source": "A", "title": "t1", "link": "u1"},
                 {"source": "B", "title": "t2", "link": "u2"}]
        digest, id_map = flt._index(items)
        self.assertIn("F1", digest)
        self.assertIn("F2", digest)
        self.assertIn("t1", digest)
        self.assertEqual(id_map["F1"]["title"], "t1")
        self.assertEqual(id_map["F2"]["link"], "u2")

    def test_index_empty(self):
        digest, id_map = flt._index([])
        self.assertEqual(id_map, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_grounding.TestIndex -v`
Expected: FAIL with `AttributeError: module 'filter' has no attribute '_index'`

- [ ] **Step 3: Write minimal implementation**

In `whetstone/filter.py`, replace the entire existing `load_frontier` function:

```python
def load_frontier(cap=45):
    if not FRONTIER.exists():
        return "(no live frontier feed yet — using your own recent knowledge)"
    lines = []
    for ln in FRONTIER.read_text().splitlines()[:cap]:
        try:
            r = json.loads(ln); lines.append(f"- [{r.get('source')}] {r.get('title')}")
        except Exception:
            pass
    return "\n".join(lines) or "(empty)"
```

with:

```python
def _index(items):
    """Pure: list of frontier item dicts -> (digest with F-ids, id_map)."""
    digest, id_map = [], {}
    for i, it in enumerate(items, 1):
        fid = f"F{i}"
        id_map[fid] = {"source": it.get("source", ""), "title": it.get("title", ""), "link": it.get("link", "")}
        digest.append(f"{fid}  [{it.get('source', '')}] {it.get('title', '')}")
    return ("\n".join(digest) or "(empty)", id_map)


def frontier_index(cap=45):
    """Read frontier.jsonl (up to cap) -> (digest, id_map)."""
    items = []
    if FRONTIER.exists():
        for ln in FRONTIER.read_text().splitlines()[:cap]:
            try: items.append(json.loads(ln))
            except Exception: pass
    if not items:
        return ("(no live frontier feed yet — using your own recent knowledge)", {})
    return _index(items)


def load_frontier(cap=45):
    return frontier_index(cap)[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest test_grounding.TestIndex -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add whetstone/filter.py whetstone/test_grounding.py
git commit -m "feat(grounding): frontier ids + index (F1..Fn -> id_map)"
```

---

## Task 2: Citation verification (`ground`)

**Files:**
- Modify: `whetstone/filter.py` (add `ground`)
- Modify: `whetstone/test_grounding.py` (add `TestGround`)

**Interfaces:**
- Consumes: `id_map` from `filter._index` / `filter.frontier_index`.
- Produces: `filter.ground(gaps: list[dict], id_map: dict) -> list[dict]` — mutates each gap in place: `source_ids` keeps only ids present in `id_map`; adds `grounded: bool` and `sources: list[dict]`. Returns the same list.

- [ ] **Step 1: Write the failing test**

Add to `whetstone/test_grounding.py` (before the `if __name__` line):

```python
class TestGround(unittest.TestCase):
    def setUp(self):
        self.id_map = {"F1": {"source": "A", "title": "t1", "link": "u1"}}

    def test_strips_fabricated(self):
        gaps = [{"source_ids": ["F1", "F99"]}]
        flt.ground(gaps, self.id_map)
        self.assertEqual(gaps[0]["source_ids"], ["F1"])
        self.assertTrue(gaps[0]["grounded"])
        self.assertEqual(gaps[0]["sources"][0]["title"], "t1")

    def test_all_fabricated_is_unverified(self):
        gaps = [{"source_ids": ["F99"]}]
        flt.ground(gaps, self.id_map)
        self.assertEqual(gaps[0]["source_ids"], [])
        self.assertFalse(gaps[0]["grounded"])
        self.assertEqual(gaps[0]["sources"], [])

    def test_empty_is_allowed(self):
        gaps = [{"source_ids": []}]
        flt.ground(gaps, self.id_map)
        self.assertFalse(gaps[0]["grounded"])

    def test_missing_key_is_allowed(self):
        gaps = [{"pattern": "p"}]
        flt.ground(gaps, self.id_map)
        self.assertFalse(gaps[0]["grounded"])
        self.assertEqual(gaps[0]["source_ids"], [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_grounding.TestGround -v`
Expected: FAIL with `AttributeError: module 'filter' has no attribute 'ground'`

- [ ] **Step 3: Write minimal implementation**

In `whetstone/filter.py`, add after the `_index`/`frontier_index`/`load_frontier` block:

```python
def ground(gaps, id_map):
    """Strip fabricated frontier citations; mark grounded + attach the real sources."""
    for g in gaps:
        ids = [s for s in (g.get("source_ids") or []) if s in id_map]
        g["source_ids"] = ids
        g["grounded"] = bool(ids)
        g["sources"] = [id_map[s] for s in ids]
    return gaps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest test_grounding.TestGround -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add whetstone/filter.py whetstone/test_grounding.py
git commit -m "feat(grounding): ground() drops fabricated citations, marks grounded"
```

---

## Task 3: Judge cites (PROMPT + schema)

**Files:**
- Modify: `whetstone/filter.py` (the `PROMPT` string)
- Modify: `whetstone/test_grounding.py` (add `TestPrompt`)

**Interfaces:**
- Produces: `filter.PROMPT` now instructs the judge to emit `source_ids` and never invent an id. `judge`'s output objects gain a `source_ids` field (consumed by `ground` in Task 4).

- [ ] **Step 1: Write the failing test**

Add to `whetstone/test_grounding.py`:

```python
class TestPrompt(unittest.TestCase):
    def test_prompt_requires_source_ids(self):
        self.assertIn("source_ids", flt.PROMPT)
        self.assertIn("NEVER invent", flt.PROMPT)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_grounding.TestPrompt -v`
Expected: FAIL with `AssertionError: 'source_ids' not found in ...`

- [ ] **Step 3: Write minimal implementation**

In `whetstone/filter.py`, in the `PROMPT` string, find this rule line:

```
- Tag each gap's blast radius in "risk": "money" (can cost, charge, or lose money), "data" (can corrupt or lose data), "production" (can break a live system), or "quality" (just better output). Pick the highest that genuinely applies.
```

Add a new rule line immediately after it:

```
- Cite the frontier item ID(s) that justify each gap in "source_ids" (e.g. ["F3"]). If the gap comes from your own general knowledge and NO listed frontier item supports it, set "source_ids" to []. NEVER invent an ID that is not listed above.
```

Then, in the same `PROMPT`, change the schema line from:

```
{{"pattern": "<their pattern>", "gap": true|false, "current_move": "<the sharper move, short>", \
"why": "<one concrete line on why it beats what they do>", "confidence": "high|med|low", "risk": "money|data|production|quality"}}"""
```

to:

```
{{"pattern": "<their pattern>", "gap": true|false, "current_move": "<the sharper move, short>", \
"why": "<one concrete line on why it beats what they do>", "confidence": "high|med|low", "risk": "money|data|production|quality", "source_ids": ["<frontier ids like F3, or [] if none>"]}}"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest test_grounding.TestPrompt -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add whetstone/filter.py whetstone/test_grounding.py
git commit -m "feat(grounding): judge prompt requires source_ids, forbids invented ids"
```

---

## Task 4: Wire `main()` — index, cite, verify, write

**Files:**
- Modify: `whetstone/filter.py` (the `main()` body)
- Modify: `whetstone/test_grounding.py` (add `TestJudgeWiring`)

**Interfaces:**
- Consumes: `frontier_index`, `judge`, `ground`.
- Produces: `gaps.jsonl` rows now include `grounded`, `sources`, `source_ids`. The judge is fed the id-tagged digest.

- [ ] **Step 1: Write the failing test**

Add to `whetstone/test_grounding.py` (note: `call_codex` is mocked, so no Codex/network):

```python
class TestJudgeWiring(unittest.TestCase):
    @mock.patch.object(flt, "call_codex")
    def test_judge_then_ground_marks_real_citation(self, cc):
        cc.return_value = ('[{"pattern":"p","gap":true,"current_move":"m","why":"w",'
                           '"confidence":"high","risk":"quality","source_ids":["F1","F9"]}]')
        digest, id_map = flt._index([{"source": "A", "title": "t1", "link": "u1"}])
        items = flt.judge([{"pattern": "p", "n_repos": 1, "evidence": "e"}], frontier=digest)
        flt.ground(items, id_map)
        self.assertTrue(items[0]["grounded"])
        self.assertEqual(items[0]["source_ids"], ["F1"])
        self.assertEqual(items[0]["sources"][0]["link"], "u1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_grounding.TestJudgeWiring -v`
Expected: PASS *if* `judge`/`ground` already compose (they do after Tasks 1–3). This test guards the composition; if it errors on `flt.judge` signature, fix `main()` in Step 3. Run it and confirm it PASSES before touching `main()` — it verifies the pieces compose. (This task's real change is wiring `main()`, which has no cheap unit test; the test above locks the contract `main()` must use.)

- [ ] **Step 3: Wire `main()`**

In `whetstone/filter.py`, in `main()`, find:

```python
    items = judge(pats)
    gaps = [it for it in items if it.get("gap")]
    meta = {p["pattern"]: p for p in pats}
```

Replace with:

```python
    digest, id_map = frontier_index()
    items = judge(pats, frontier=digest)
    gaps = [it for it in items if it.get("gap")]
    ground(gaps, id_map)
    meta = {p["pattern"]: p for p in pats}
```

Then, in `main()`'s print loop, find:

```python
        print(f"  [{g.get('risk', '?').upper()} · {g.get('confidence', '?').upper()}] {g['pattern']}")
```

Replace with:

```python
        mark = "grounded" if g.get("grounded") else "unverified"
        print(f"  [{g.get('risk', '?').upper()} · {g.get('confidence', '?').upper()} · {mark}] {g['pattern']}")
```

- [ ] **Step 4: Run the full unit suite**

Run: `python3 -m unittest test_grounding -v`
Expected: PASS (all tests so far). Also confirm nothing broke: `python3 -m py_compile filter.py`

- [ ] **Step 5: Commit**

```bash
git add whetstone/filter.py whetstone/test_grounding.py
git commit -m "feat(grounding): main() feeds id-digest to judge, grounds gaps, writes provenance"
```

---

## Task 5: Teach with real sources, never invent

**Files:**
- Modify: `whetstone/teach.py` (add `_sources_block`, use it in `gap_prompt`; carry grounding onto the bank entry)
- Modify: `whetstone/test_grounding.py` (add `TestTeachSources`)

**Interfaces:**
- Consumes: `gap["sources"]`, `gap["grounded"]` from Task 4.
- Produces: `teach.gap_prompt(gap)` embeds the real sources + a "never invent a citation/URL" rule; the banked entry gains `grounded` + `sources`.

- [ ] **Step 1: Write the failing test**

Add to `whetstone/test_grounding.py`:

```python
import teach


class TestTeachSources(unittest.TestCase):
    def test_grounded_prompt_lists_real_sources(self):
        gap = {"pattern": "p", "current_move": "m", "why": "w",
               "sources": [{"source": "A", "title": "t1", "link": "u1"}]}
        p = teach.gap_prompt(gap)
        self.assertIn("t1", p)
        self.assertIn("u1", p)
        self.assertIn("NEVER invent", p)

    def test_ungrounded_prompt_warns_no_fabrication(self):
        gap = {"pattern": "p", "current_move": "m", "why": "w", "sources": []}
        p = teach.gap_prompt(gap)
        self.assertIn("Do NOT invent", p)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_grounding.TestTeachSources -v`
Expected: FAIL — `gap_prompt` does not yet mention sources (`'t1' not found`).

- [ ] **Step 3: Write minimal implementation**

In `whetstone/teach.py`, add this helper immediately above `def gap_prompt(gap):`:

```python
def _sources_block(gap):
    srcs = gap.get("sources") or []
    if srcs:
        lines = "\n".join(f"- {s.get('source', '')}: {s.get('title', '')} ({s.get('link', '')})" for s in srcs)
        return ("This gap is grounded in these REAL frontier sources — reference them by name where it helps, "
                "and NEVER invent a paper, citation, or URL beyond these:\n" + lines + "\n\n")
    return ("This gap is from general practice, not a cited live source. Do NOT invent any paper, citation, "
            "or URL — present it as general best practice.\n\n")
```

Then, in `gap_prompt`, find:

```python
        f"Why it beats theirs: {gap.get('why')}.\n\n"
        "Write the lesson, anchored to their real work:\n"
```

Replace with:

```python
        f"Why it beats theirs: {gap.get('why')}.\n\n"
        + _sources_block(gap) +
        "Write the lesson, anchored to their real work:\n"
```

Then, in `teach_gap`, find the `entry = {` dict and add two keys (place them after the `"current_move": ...,` line):

```python
        "grounded": gap.get("grounded", False), "sources": gap.get("sources", []),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest test_grounding.TestTeachSources -v`
Expected: PASS (2 tests). Then full suite: `python3 -m unittest test_grounding -v` — all PASS. Then `python3 -m py_compile teach.py`.

- [ ] **Step 5: Commit**

```bash
git add whetstone/teach.py whetstone/test_grounding.py
git commit -m "feat(grounding): teacher prompt cites real sources, forbids fabrication; bank carries provenance"
```

---

## Task 6: Show grounding on bank cards

**Files:**
- Modify: `whetstone/teacher.html` (bank card render in `openBank`, plus CSS)

**Interfaces:**
- Consumes: `it.grounded`, `it.sources` on each `/bank` item (already passed through by `teacher.py`, no server change).

- [ ] **Step 1: Add the grounding line to the bank card**

In `whetstone/teacher.html`, inside `openBank`, find this line (the card template):

```javascript
          +'<div class="d">'+esc(it.direction||'')+'</div>'
          +'<div class="bk-b"><button class="cp" data-id="'+id+'">⎘ copy</button><button class="ex" data-id="'+id+'">explain</button></div></div>';
```

Replace with:

```javascript
          +'<div class="d">'+esc(it.direction||'')+'</div>'
          +((it.grounded&&it.sources&&it.sources.length)
              ? '<div class="prov grounded">grounded · '+esc(it.sources[0].source||'')+' — '+esc(it.sources[0].title||'')+'</div>'
              : '<div class="prov unverified">unverified · model knowledge</div>')
          +'<div class="bk-b"><button class="cp" data-id="'+id+'">⎘ copy</button><button class="ex" data-id="'+id+'">explain</button></div></div>';
```

- [ ] **Step 2: Add CSS**

In `whetstone/teacher.html`, find this line (added earlier for review cards):

```css
.bk .rvf{font-family:var(--mono);font-size:10px;color:var(--faint);margin-top:6px}
```

Add immediately after it:

```css
.prov{font-family:var(--mono);font-size:9.5px;margin-top:6px;letter-spacing:.03em}
.prov.grounded{color:var(--brass)}
.prov.unverified{color:var(--faint)}
```

- [ ] **Step 3: Verify the page still parses**

Run: `python3 -c "import pathlib,html.parser; html.parser.HTMLParser().feed(pathlib.Path('teacher.html').read_text()); print('html parses')"`
Expected: `html parses` (no exception).

- [ ] **Step 4: Manual verification**

This is UI — confirm by eye. In a terminal:
```bash
python3 -c "import teacher; teacher.append_jsonl(teacher.BANK, {'ts':1,'project':'demo','pattern':'grounded demo','direction':'do x','risk':'quality','grounded':True,'sources':[{'source':'Simon Willison','title':'a real post','link':'http://x'}]}); teacher.append_jsonl(teacher.BANK, {'ts':2,'project':'demo','pattern':'ungrounded demo','direction':'do y','risk':'quality','grounded':False,'sources':[]})"
```
Restart `teacher.py`, open http://localhost:8099, open the command bank: the first demo card shows `grounded · Simon Willison — a real post`, the second shows `unverified · model knowledge`. Then remove the demo rows: `python3 -c "import pathlib,json; p=pathlib.Path('bank.jsonl'); p.write_text(''.join(l+'\n' for l in p.read_text().splitlines() if 'demo' not in l))"`

- [ ] **Step 5: Commit**

```bash
git add whetstone/teacher.html
git commit -m "feat(grounding): bank cards show grounded source or unverified"
```

---

## Task 7: End-to-end live verification

**Files:** none (verification only)

- [ ] **Step 1: Refresh the frontier**

Run: `python3 whet.py watch`
Expected: `frontier.jsonl: N items from …` (N > 0).

- [ ] **Step 2: Run the loop on Whetstone itself and inspect provenance**

Run: `python3 whet.py learn /home/rory/JOBS/Whetstone 14 2`
Then:
```bash
python3 -c "import json; [print(g.get('grounded'), g.get('source_ids'), '|', g.get('pattern','')[:50]) for g in [json.loads(l) for l in open('gaps.jsonl')]]"
```
Expected: each gap prints `True`/`False`, a list of `F#` ids (all of which exist in `frontier.jsonl`), and the pattern. No id should be absent from the feed — that is the fabrication guard working.

- [ ] **Step 3: Confirm the calibrated judge still passes**

Run: `python3 whet.py check`
Expected: `0 must-catch failures` (grounding must not have regressed detection).

- [ ] **Step 4: Commit any doc/status updates**

```bash
git add -A whetstone/ && git commit -m "chore(grounding): end-to-end verified on self" || echo "nothing to commit"
```

---

## Self-Review

**Spec coverage:** IDs (Task 1) · cite (Task 3) · verify/strip fabrications (Task 2, wired Task 4) · flow to gaps.jsonl (Task 4) · flow to teach + bank + never-invent (Task 5) · flow to UI (Task 6) · "say unknown when it can't" = `grounded:false`/`unverified` (Tasks 2, 4, 6) · live proof (Task 7). All covered.

**Placeholder scan:** none — every code step shows complete code.

**Type consistency:** `_index -> (str, dict)`; `frontier_index -> (str, dict)`; `load_frontier -> str`; `ground(gaps, id_map) -> gaps` adding `source_ids: list[str]`, `grounded: bool`, `sources: list[dict]`; `judge(pats, frontier=None)` unchanged signature. `sources` items are `{source,title,link}` everywhere (filter, teach, html). Consistent.

**Ungrounded handling:** explicitly allowed (not an error) in Tasks 2, 4, 5, 6 — matches the "marked, not rejected" design decision.
