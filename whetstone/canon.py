#!/usr/bin/env python3
"""Whetstone — canonical pattern names.

Free-text breadcrumb pattern names ("structured JSON output" vs "schema-constrained
outputs") describe the same habit differently, so recurrence across repos never
accumulates. This maps each free-text pattern to a STABLE canonical id: seeded in
canon.jsonl and extended in the runtime cache; mappings are cached in canon_map.jsonl so the same
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
    only new patterns hit the model. Model-proposed ids are kept in the runtime map; the source-controlled seed is never mutated.
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
            known.add(cid)
        _save_map(fresh)
    return out
