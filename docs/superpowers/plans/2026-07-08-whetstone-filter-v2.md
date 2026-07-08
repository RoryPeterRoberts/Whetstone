# Whetstone Filter v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make recurrence fire (canonical pattern names) and stop the judge over-flagging (calibration hardening) — the two ◑ Partial goals from the source-grounding assessment.

**Architecture:** A new `canon.py` maps free-text breadcrumb pattern names to stable canonical ids (seeded in `canon.jsonl`, grown as new patterns appear, cached in `canon_map.jsonl` so the mapping — and therefore recurrence counts — are stable run to run). `filter.main()` canonicalizes once and passes the map to `select()`, which now counts "recurs across N repos" by canonical id. Separately, the judge `PROMPT` gains explicit not-a-gap anchors and a deficiency-naming rule, and `judge_eval.py` runs the golden set worst-of-N so "calibrated" means *reliably*, not *once*.

**Tech Stack:** Python 3 stdlib only; Codex CLI (`call_codex`) as the model; `unittest` + `unittest.mock`.

## Global Constraints

- Stdlib only — no new dependencies. Tests use `unittest` + `unittest.mock`, NOT pytest.
- Run all commands from `/home/rory/JOBS/Whetstone/whetstone/` (so `import filter`, `import canon`, `import judge_eval` resolve).
- Unit tests mock the model — they never call Codex. `canon.call_codex` and `filter.judge` / `flt.judge` are the mock points.
- New test code goes in one flat file: `whetstone/test_filterv2.py` (beside `filter.py`). Each task adds its own `unittest.TestCase` class.
- `canon.jsonl` is a **source** seed and must be force-added (`git add -f`), because `.gitignore` ignores `*.jsonl`. `canon_map.jsonl` is a runtime cache — leave it gitignored, do NOT commit it.
- Grounding stays intact; do not touch `ground()`, `_index`, `frontier_index`, or the `source_ids` rule.
- Touch only the files each task names. Match the existing terse style (compact `try/except Exception: pass`, single-line conditionals, no type hints).

---

### Task 1: `canon.py` — canonical pattern names (seed, load, grow, cache-mapped canonicalize)

**Files:**
- Create: `whetstone/canon.jsonl` (seed, force-add)
- Create: `whetstone/canon.py`
- Test: `whetstone/test_filterv2.py` (add `TestCanon`)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `canon.canonicalize(patterns) -> {pattern: canon_id}` (str→str dict; unique/non-empty inputs; `{}` for empty input; caches to `canon_map.jsonl`; appends model-proposed new ids to `canon.jsonl`). Also `canon.load_canon() -> list[dict]`, `canon.load_map() -> dict`, and module attrs `canon.CANON`, `canon.CANON_MAP`, `canon.call_codex` (the mock points).

- [ ] **Step 1: Create the seed `canon.jsonl`**

Write exactly these lines to `whetstone/canon.jsonl` (one JSON object per line):

```
{"id": "structured-output-contract", "name": "Structured output contract", "blurb": "schema/tool-enforced output, not string-parsed JSON"}
{"id": "llm-as-judge", "name": "LLM-as-judge", "blurb": "model grades/评估 outputs against a rubric"}
{"id": "eval-set-and-regression-gate", "name": "Eval set + regression gate", "blurb": "golden cases block releases on regression"}
{"id": "retrieval-grounded-generation", "name": "Retrieval-grounded generation", "blurb": "answers grounded in retrieved sources with citations"}
{"id": "citation-provenance", "name": "Citation provenance", "blurb": "verify/strip citations, mark grounded vs unverified"}
{"id": "rate-limit-and-backoff", "name": "Rate limiting + backoff", "blurb": "bounded concurrency, honor Retry-After, jittered backoff"}
{"id": "prompt-versioning-and-telemetry", "name": "Prompt versioning + telemetry", "blurb": "pin model version, log prompt version/tokens/cost/latency"}
{"id": "agent-loop-with-state", "name": "Agent loop with state", "blurb": "explicit resumable state + checkpoints, not a linear chain"}
{"id": "tool-function-calling", "name": "Tool / function calling", "blurb": "structured tool invocation"}
{"id": "prompt-caching", "name": "Prompt caching", "blurb": "cache stable prompt prefixes"}
{"id": "model-routing-fallback", "name": "Model routing / fallback", "blurb": "route or fall back across models"}
{"id": "guardrails-and-validation", "name": "Guardrails + validation", "blurb": "validate/repair model output before use"}
```

(The `评估` in the `llm-as-judge` blurb is a typo — write it as `"model grades/scores outputs against a rubric"`.)

Then verify it is valid JSONL:

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -c "import json;[json.loads(l) for l in open('canon.jsonl')];print('canon.jsonl ok')"`
Expected: `canon.jsonl ok`

- [ ] **Step 2: Write the failing test (`TestCanon`)**

Add to `whetstone/test_filterv2.py`:

```python
import json, unittest, tempfile, pathlib
from unittest import mock
import canon


class TestCanon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = (canon.CANON, canon.CANON_MAP)
        canon.CANON = pathlib.Path(self.tmp) / "canon.jsonl"
        canon.CANON_MAP = pathlib.Path(self.tmp) / "canon_map.jsonl"
        canon.CANON.write_text(
            json.dumps({"id": "structured-output-contract", "name": "Structured output", "blurb": ""}) + "\n")

    def tearDown(self):
        canon.CANON, canon.CANON_MAP = self._orig

    @mock.patch("canon.call_codex")
    def test_maps_to_existing_then_caches(self, cc):
        cc.return_value = '{"structured JSON output": "structured-output-contract"}'
        m = canon.canonicalize(["structured JSON output"])
        self.assertEqual(m["structured JSON output"], "structured-output-contract")
        # second call for the same pattern must hit the cache, not the model
        cc.side_effect = AssertionError("codex called for an already-cached pattern")
        m2 = canon.canonicalize(["structured JSON output"])
        self.assertEqual(m2["structured JSON output"], "structured-output-contract")

    @mock.patch("canon.call_codex")
    def test_proposes_and_appends_new_canon(self, cc):
        cc.return_value = '{"some novel trick": "novel-trick"}'
        m = canon.canonicalize(["some novel trick"])
        self.assertEqual(m["some novel trick"], "novel-trick")
        self.assertIn("novel-trick", {c["id"] for c in canon.load_canon()})

    def test_empty_input(self):
        self.assertEqual(canon.canonicalize([]), {})
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m unittest test_filterv2.TestCanon -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'canon'` (or `AttributeError` on `canon.CANON`).

- [ ] **Step 4: Write `whetstone/canon.py`**

```python
#!/usr/bin/env python3
"""Whetstone — canonical pattern names.

Free-text breadcrumb pattern names ("structured JSON output" vs "schema-constrained
outputs") describe the same habit differently, so recurrence across repos never
accumulates. This maps each free-text pattern to a STABLE canonical id: seeded in
canon.jsonl, grown as new patterns appear, and cached in canon_map.jsonl so the same
pattern always resolves to the same id (stable recurrence, run to run).
"""
import json, os, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANON = ROOT / "canon.jsonl"          # the taxonomy (seed; source-controlled)
CANON_MAP = ROOT / "canon_map.jsonl"  # {pattern -> canon_id} cache (runtime; gitignored)
CODEX = os.environ.get("CODEX_BIN") or shutil.which("codex") or os.path.expanduser("~/.local/bin/codex")

MAP_PROMPT = """You normalise LLM-building pattern names to a canonical taxonomy.

Canonical patterns (id — name):
{canon}

Map each observed pattern name below to the single best-fitting canonical id above. If none genuinely \
fits, propose a NEW canonical id instead (lowercase-kebab-case, short, e.g. "prompt-caching").

Observed patterns:
{patterns}

Return ONLY a JSON object, no prose, no fences: {{"<observed pattern>": "<canonical-id>", ...}}. \
Every observed pattern must appear as a key."""


def call_codex(prompt):
    pf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False); pf.write(prompt); pf.close()
    out = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False).name
    try:
        with open(pf.name) as stdin:
            subprocess.run([CODEX, "exec", "--skip-git-repo-check", "-o", out, "-"], stdin=stdin,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180, check=True)
        return Path(out).read_text().strip()
    finally:
        for x in (pf.name, out):
            try: os.unlink(x)
            except OSError: pass


def parse_obj(s):
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
    a, b = s.find("{"), s.rfind("}")
    if a >= 0 and b > a:
        try: return json.loads(s[a:b + 1])
        except Exception: pass
    return {}


def _slug(s):
    return "-".join("".join(ch if ch.isalnum() else " " for ch in (s or "").lower()).split())[:40] or "uncategorised"


def load_canon():
    rows = []
    if CANON.exists():
        for ln in CANON.read_text().splitlines():
            ln = ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except Exception: pass
    return rows


def load_map():
    m = {}
    if CANON_MAP.exists():
        for ln in CANON_MAP.read_text().splitlines():
            try:
                r = json.loads(ln); m[r["pattern"]] = r["canon"]
            except Exception: pass
    return m


def _append_canon(cid):
    if cid in {c.get("id") for c in load_canon()}:
        return
    with open(CANON, "a") as f:
        f.write(json.dumps({"id": cid, "name": cid, "blurb": ""}) + "\n")


def _save_map(pairs):
    with open(CANON_MAP, "a") as f:
        for p, c in pairs.items():
            f.write(json.dumps({"pattern": p, "canon": c}) + "\n")


def canonicalize(patterns):
    """Map free-text patterns -> canonical ids. Cached ones are reused (stable);
    only new patterns hit the model. Model-proposed new ids are appended to the canon.
    Returns {pattern: canon_id}; empty input -> {}."""
    patterns = [p for p in dict.fromkeys(patterns) if p]  # unique, non-empty, order-preserving
    if not patterns:
        return {}
    cached = load_map()
    out = {p: cached[p] for p in patterns if p in cached}
    todo = [p for p in patterns if p not in cached]
    if todo:
        canon = load_canon()
        listing = "\n".join(f"{c['id']} — {c.get('name', c['id'])}" for c in canon) or "(none yet)"
        plist = "\n".join(f"- {p}" for p in todo)
        mapping = parse_obj(call_codex(MAP_PROMPT.format(canon=listing, patterns=plist)))
        known = {c.get("id") for c in canon}
        fresh = {}
        for p in todo:
            cid = (mapping.get(p) or "").strip() or _slug(p)
            fresh[p] = cid; out[p] = cid
            if cid not in known:
                _append_canon(cid); known.add(cid)
        _save_map(fresh)
    return out
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m unittest test_filterv2.TestCanon -v`
Expected: PASS (3 tests). Also run `python3 -m py_compile canon.py` — no output.

- [ ] **Step 6: Commit**

```bash
cd /home/rory/JOBS/Whetstone
git add -f whetstone/canon.jsonl
git add whetstone/canon.py whetstone/test_filterv2.py
git commit -m "feat(filterv2): canon.py — canonical pattern names (seed + cached canonicalize)"
```
(Do NOT `git add` `canon_map.jsonl` — it stays gitignored.)

---

### Task 2: recurrence by canonical id in `filter.select()` + wire `canonicalize` in `filter.main()`

**Files:**
- Modify: `whetstone/filter.py` (`select` signature/body; `main` body)
- Test: `whetstone/test_filterv2.py` (add `TestSelectRecurrence`)

**Interfaces:**
- Consumes: `canon.canonicalize(patterns) -> {pattern: canon_id}` (Task 1).
- Produces: `filter.select(rows, target, cmap=None) -> list[dict]` where each dict gains a `canon` key and `n_repos` counts distinct repos by canonical id (falls back to the free-text pattern when `cmap` is None or a pattern is absent from it).

- [ ] **Step 1: Write the failing test (`TestSelectRecurrence`)**

Add to `whetstone/test_filterv2.py`:

```python
import filter as flt


class TestSelectRecurrence(unittest.TestCase):
    def test_recurrence_counts_by_canon(self):
        rows = [
            {"repo": "A", "pattern": "structured JSON output", "evidence": "x"},
            {"repo": "B", "pattern": "schema-constrained outputs", "evidence": "y"},
        ]
        cmap = {"structured JSON output": "structured-output-contract",
                "schema-constrained outputs": "structured-output-contract"}
        out = flt.select(rows, None, cmap)
        self.assertEqual(len(out), 2)                       # two distinct free-text patterns
        for p in out:
            self.assertEqual(p["n_repos"], 2)               # both share one canon -> recurs across 2 repos
            self.assertEqual(p["canon"], "structured-output-contract")

    def test_backcompat_without_cmap(self):
        rows = [{"repo": "A", "pattern": "P", "evidence": ""},
                {"repo": "B", "pattern": "P", "evidence": ""}]
        out = flt.select(rows, None)
        self.assertEqual(out[0]["n_repos"], 2)              # identical free-text still counts
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m unittest test_filterv2.TestSelectRecurrence -v`
Expected: FAIL — `TypeError: select() takes 2 positional arguments but 3 were given` (on the first test) or `KeyError: 'canon'`.

- [ ] **Step 3: Modify `select` in `filter.py`**

Replace the existing `select` function with:

```python
def select(rows, target, cmap=None):
    """Unique patterns; if a target repo is given, focus on its patterns. Recurrence
    (the compounding signal) is counted by CANONICAL id when cmap is given, so the same
    habit under different free-text names accumulates across repos; falls back to the
    raw pattern text when no cmap is available (back-compat)."""
    def key(p):
        return (cmap or {}).get(p, p)
    repos_of = {}
    for r in rows:
        repos_of.setdefault(key(r.get("pattern")), set()).add(r.get("repo"))
    seen, out = set(), []
    for r in rows:
        p = r.get("pattern")
        if not p or p in seen:
            continue
        if target and r.get("repo") != target:
            continue
        seen.add(p)
        out.append({**r, "canon": key(p), "n_repos": len(repos_of.get(key(p), set()))})
    return out
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m unittest test_filterv2.TestSelectRecurrence -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Wire `canonicalize` into `filter.main()`**

In `filter.py` `main()`, find:

```python
    rows = load_breadcrumbs()
    pats = select(rows, target) or select(rows, None)
```

Replace with:

```python
    rows = load_breadcrumbs()
    import canon
    cmap = canon.canonicalize([r.get("pattern") for r in rows if r.get("pattern")])
    pats = select(rows, target, cmap) or select(rows, None, cmap)
```

Verify the module still compiles and the full suite passes:

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m py_compile filter.py && python3 -m unittest test_filterv2 test_grounding -v 2>&1 | tail -4`
Expected: `OK` (all tests, including the pre-existing `test_grounding` suite — no regressions).

- [ ] **Step 6: Commit**

```bash
cd /home/rory/JOBS/Whetstone
git add whetstone/filter.py whetstone/test_filterv2.py
git commit -m "feat(filterv2): recurrence counts by canonical id; filter.main canonicalizes"
```

---

### Task 3: judge `PROMPT` — not-a-gap anchors + deficiency-naming rule

**Files:**
- Modify: `whetstone/filter.py` (the `PROMPT` string only)
- Test: `whetstone/test_filterv2.py` (add `TestPromptV2`)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing new — hardens the existing judge prompt. Grounding rules stay unchanged.

- [ ] **Step 1: Write the failing test (`TestPromptV2`)**

Add to `whetstone/test_filterv2.py`:

```python
class TestPromptV2(unittest.TestCase):
    def test_not_a_gap_anchors_present(self):
        self.assertIn("NOT gaps", flt.PROMPT)
        self.assertIn("type hints", flt.PROMPT)

    def test_deficiency_rule_present(self):
        self.assertIn("specifically lacks", flt.PROMPT)
        self.assertIn("not merely that the topic", flt.PROMPT)

    def test_prompt_still_formats(self):
        # the added rules must not break the .format() placeholders
        flt.PROMPT.format(patterns="p", frontier="f")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m unittest test_filterv2.TestPromptV2 -v`
Expected: FAIL — `AssertionError` (the strings are not yet in `PROMPT`).

- [ ] **Step 3: Add the two rules to `PROMPT`**

In `filter.py`, find the source-grounding rule line (it ends the Rules list, immediately before the blank line and `Return ONLY a JSON array`):

```python
- Cite the frontier item ID(s) that justify each gap in "source_ids" (e.g. ["F3"]). If the gap comes from your own general knowledge and NO listed frontier item supports it, set "source_ids" to []. NEVER invent an ID that is not listed above.
```

Insert these TWO lines immediately AFTER it (still inside the Rules list, before the blank line):

```python
- These are NOT gaps — set gap=false and do not manufacture a sharper move: writing type hints or docstrings, using simple f-string prompt templates, or any practice that is already current best practice or baseline hygiene.
- A gap must name what the developer's CURRENT practice specifically lacks versus a sharper move — not merely that the topic is active on the frontier. A pattern being widely discussed now is not evidence that their way of doing it is behind.
```

(Match the existing rule style: each rule is one line starting with `- `. The `PROMPT` string uses `{{` / `}}` only in the JSON schema block near the end — the lines you are adding contain no braces, so `.format()` stays valid.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m unittest test_filterv2.TestPromptV2 -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/rory/JOBS/Whetstone
git add whetstone/filter.py whetstone/test_filterv2.py
git commit -m "feat(filterv2): judge prompt gains not-a-gap anchors + deficiency-naming rule"
```

---

### Task 4: `judge_eval.py` — worst-of-N calibration bar

**Files:**
- Modify: `whetstone/judge_eval.py` (`run`; extract a per-run helper)
- Test: `whetstone/test_filterv2.py` (add `TestWorstOfN`)

**Interfaces:**
- Consumes: `filter.judge` (unchanged).
- Produces: `judge_eval.run(n_runs=3) -> int` (0 calibrated / 1 not). Reports the WORST of `n_runs` runs; "calibrated" requires 0 must-catch failures in every run. `whet check` calls `run()` with the default, so no `whet.py` change is needed.

- [ ] **Step 1: Write the failing test (`TestWorstOfN`)**

Add to `whetstone/test_filterv2.py`:

```python
import judge_eval


class TestWorstOfN(unittest.TestCase):
    @mock.patch("judge_eval.flt.judge")
    @mock.patch("judge_eval.load_golden")
    def test_any_run_must_fail_flags_not_calibrated(self, lg, jm):
        lg.return_value = [{"pattern": "P", "evidence": "", "expect": False, "must": True}]
        # 3 runs: clean, clean, then a must-case over-flag
        jm.side_effect = [
            [{"pattern": "P", "gap": False}],
            [{"pattern": "P", "gap": False}],
            [{"pattern": "P", "gap": True}],
        ]
        self.assertEqual(judge_eval.run(3), 1)   # worst-of-3 catches the failing run

    @mock.patch("judge_eval.flt.judge")
    @mock.patch("judge_eval.load_golden")
    def test_all_runs_clean_passes(self, lg, jm):
        lg.return_value = [{"pattern": "P", "evidence": "", "expect": False, "must": True}]
        jm.side_effect = [[{"pattern": "P", "gap": False}]] * 3
        self.assertEqual(judge_eval.run(3), 0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m unittest test_filterv2.TestWorstOfN -v`
Expected: FAIL — `TypeError: run() takes 0 positional arguments but 1 was given`.

- [ ] **Step 3: Rewrite `run` in `judge_eval.py` (extract `_one_run`, loop worst-of-N)**

Replace the entire `run()` function with:

```python
def _one_run(golden, pats):
    items = flt.judge(pats)
    if len(items) == len(golden):
        got_list = [bool(it.get("gap")) for it in items]
    else:
        vmap = {_norm(it.get("pattern")): bool(it.get("gap")) for it in items}
        got_list = [vmap.get(_norm(g["pattern"])) for g in golden]
    rows, passed, must_fail = [], 0, 0
    for g, got in zip(golden, got_list):
        exp = bool(g["expect"])
        ok = (got == exp)
        passed += ok
        if not ok and g.get("must"):
            must_fail += 1
        mark = "ok" if ok else ("MISS" if exp else ("FALSE+" if got is not None else "MISSING"))
        rows.append((mark, "*" if g.get("must") else " ", exp, got, g["pattern"]))
    return rows, passed, must_fail


def run(n_runs=3):
    golden = load_golden()
    if not golden:
        print("no golden cases — write golden.jsonl first"); return 1

    pats = [{"pattern": g["pattern"], "evidence": g.get("evidence", ""), "n_repos": 1} for g in golden]
    n_runs = max(1, n_runs)
    worst = None  # (rows, passed, must_fail) — most must-fails, then fewest passed
    for _ in range(n_runs):
        rows, passed, must_fail = _one_run(golden, pats)
        if worst is None or must_fail > worst[2] or (must_fail == worst[2] and passed < worst[1]):
            worst = (rows, passed, must_fail)
    rows, passed, must_fail = worst

    n = len(golden)
    print(f"\ncalibrated judge harness — worst of {n_runs} runs: {passed}/{n} correct  ({must_fail} must-catch failures)\n")
    for mark, star, exp, got, pat in rows:
        eg = "gap" if exp else "no-gap"
        gg = ("gap" if got else "no-gap") if got is not None else "MISSING"
        print(f"  [{mark:7}]{star} expect {eg:6} · got {gg:7} · {pat[:64]}")
    print()
    if must_fail:
        print(f"✗ judge is NOT calibrated — {must_fail} must-catch case(s) wrong in the worst of {n_runs} runs. "
              "Fix the judge (prompt/rubric) before trusting its rankings.")
        return 1
    if passed < n:
        print(f"~ judge passed every must-catch case across {n_runs} runs but missed {n - passed} softer one(s) — usable, watch the rankings.")
        return 0
    print(f"✓ judge is calibrated — every golden case correct across {n_runs} runs.")
    return 0
```

(`load_golden`, `_norm`, the imports, and the `__main__` guard `sys.exit(run())` are unchanged and stay as-is.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m unittest test_filterv2.TestWorstOfN -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Full-suite check + compile**

Run: `cd /home/rory/JOBS/Whetstone/whetstone && python3 -m py_compile judge_eval.py && python3 -m unittest test_filterv2 test_grounding -v 2>&1 | tail -4`
Expected: `OK` (all Filter v2 + grounding tests pass).

- [ ] **Step 6: Commit**

```bash
cd /home/rory/JOBS/Whetstone
git add whetstone/judge_eval.py whetstone/test_filterv2.py
git commit -m "feat(filterv2): judge_eval worst-of-N calibration bar (default 3 runs)"
```

---

## Notes for the executor

- **Golden regression cases already exist.** The three jitter cases (type-hints, plain f-string templates, "structured output done right") are already in `golden.jsonl` with the right `expect`/`must` flags — the spec's "pin them as regression traps" is already satisfied. Do NOT rewrite `golden.jsonl`.
- **Live verification is out of this plan.** Whether the hardened judge actually holds 0 must-catch worst-of-3, and whether recurrence now fires on real repos, is a live Codex run — do it after merge (`whet check`, then `whet learn` on a repo), not in these unit tasks.

## Self-review (author)

- **Spec coverage:** Part A (canonical names → recurrence) = Tasks 1–2; Part B (not-a-gap anchors + deficiency-naming = Task 3; worst-of-N = Task 4; golden pinning already present). All spec items covered.
- **Placeholders:** none — every code step is complete.
- **Type consistency:** `canonicalize(patterns) -> {pattern: canon_id}` (Task 1) is consumed by `filter.main` and passed as `cmap` to `select(rows, target, cmap)` (Task 2); `select` keys recurrence via `cmap.get(pattern, pattern)`. `run(n_runs=3) -> int` matches the `whet check` caller (`sys.exit(run())`). Consistent.
