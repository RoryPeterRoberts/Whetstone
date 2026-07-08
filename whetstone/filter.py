#!/usr/bin/env python3
"""Whetstone — filter (the heart).

Read your breadcrumbs (what you do) and judge each against current best practice:
where is there a sharper current move you are probably NOT using? Those gaps are the
teaching targets — the only things worth your time.

v1 uses the model's own recent knowledge as the frontier proxy; watch.py will feed it
live sources (SOURCES.md) later, so "current" can't drift back to legacy.

    python filter.py            # filter breadcrumbs.jsonl -> gaps.jsonl
"""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BREADCRUMBS = ROOT / "breadcrumbs.jsonl"
GAPS = ROOT / "gaps.jsonl"
FRONTIER = ROOT / "frontier.jsonl"
CODEX = os.environ.get("CODEX_BIN") or shutil.which("codex") or os.path.expanduser("~/.local/bin/codex")

PROMPT = """You are Whetstone's filter — the part that decides what is worth teaching a builder.

Here are the LLM-building patterns this developer ALREADY USES, inferred from their real git history:
{patterns}

Here is what the frontier is ACTUALLY publishing right now (recent items from curated sources — use these \
as ground truth for what "current" means; if this is empty, fall back to your own recent knowledge):
{frontier}

For EACH pattern, judge it honestly against CURRENT best practice — what strong practitioners and the \
frontier do NOW: is there a materially sharper, newer, or more robust move for that same job that this \
developer is probably NOT using yet?

Rules:
- Flag a gap ONLY if there is a specific, nameable better technique or tool — never a vague "could improve".
- If they are already doing it the current best way, set gap=false. Be STRICT; expect most to be false.
- The better move must be current and trustworthy, and useful to someone who COMMANDS a coding agent — \
a technique to DIRECT and JUDGE, not code to hand-write.
- Rank gaps by leverage: how much it would actually improve their work. Patterns marked "recurs across N of your repos" are higher-leverage — a fix there compounds across projects.

Return ONLY a JSON array, no prose, no fences. One item per pattern:
{{"pattern": "<their pattern>", "gap": true|false, "current_move": "<the sharper move, short>", \
"why": "<one concrete line on why it beats what they do>", "confidence": "high|med|low"}}"""


def call_codex(prompt):
    pf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False); pf.write(prompt); pf.close()
    out = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False).name
    try:
        with open(pf.name) as stdin:
            subprocess.run([CODEX, "exec", "--skip-git-repo-check", "-o", out, "-"], stdin=stdin,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300, check=True)
        return Path(out).read_text().strip()
    finally:
        for x in (pf.name, out):
            try: os.unlink(x)
            except OSError: pass


def parse_json(s):
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
    a, b = s.find("["), s.rfind("]")
    if a >= 0 and b > a:
        try: return json.loads(s[a:b + 1])
        except Exception: pass
    return []


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


def load_breadcrumbs():
    rows = []
    if BREADCRUMBS.exists():
        for ln in BREADCRUMBS.read_text().splitlines():
            try: rows.append(json.loads(ln))
            except Exception: pass
    return rows


def select(rows, target):
    """Unique patterns; if a target repo is given, focus on its patterns. Each pattern is
    annotated with how many distinct repos it recurs in — the recurrence (compounding) signal."""
    repos_of = {}
    for r in rows:
        repos_of.setdefault(r.get("pattern"), set()).add(r.get("repo"))
    seen, out = set(), []
    for r in rows:
        p = r.get("pattern")
        if not p or p in seen:
            continue
        if target and r.get("repo") != target:
            continue
        seen.add(p)
        out.append({**r, "n_repos": len(repos_of.get(p, set()))})
    return out


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    rows = load_breadcrumbs()
    pats = select(rows, target) or select(rows, None)
    if not pats:
        print("no breadcrumbs yet — run breadcrumbs.py <repo> first"); return

    def fmt(p):
        rec = f" (recurs across {p['n_repos']} of your repos)" if p.get("n_repos", 1) > 1 else ""
        return f"- {p['pattern']}{rec} — {p.get('evidence', '')}"

    listing = "\n".join(fmt(p) for p in pats)
    items = parse_json(call_codex(PROMPT.format(patterns=listing, frontier=load_frontier())))
    gaps = [it for it in items if it.get("gap")]
    order = {"high": 0, "med": 1, "low": 2}
    gaps.sort(key=lambda g: order.get(g.get("confidence", "low"), 3))

    with open(GAPS, "w") as f:
        for g in gaps:
            f.write(json.dumps({"ts": int(time.time()), **g}) + "\n")

    print(f"{len(pats)} patterns checked · {len(gaps)} gaps (teaching targets)\n")
    for g in gaps:
        print(f"  [{g.get('confidence', '?').upper()}] {g['pattern']}")
        print(f"      → {g.get('current_move', '')}")
        print(f"        {g.get('why', '')}\n")
    print(f"({len(pats) - len(gaps)} already at current best practice — nothing to teach there.)")


if __name__ == "__main__":
    main()
