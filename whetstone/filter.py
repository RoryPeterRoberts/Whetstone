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
import runs
import validation

ROOT = Path(__file__).resolve().parent
BREADCRUMBS = ROOT / "breadcrumbs.jsonl"
GAPS = ROOT / "gaps.jsonl"
FINDINGS = ROOT / "findings.jsonl"
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
- Tag each gap's blast radius in "risk": "money" (can cost, charge, or lose money), "data" (can corrupt or lose data), "production" (can break a live system), or "quality" (just better output). Pick the highest that genuinely applies.
- Cite the frontier item ID(s) that justify each gap in "source_ids" (e.g. ["F3"]). If the gap comes from your own general knowledge and NO listed frontier item supports it, set "source_ids" to []. NEVER invent an ID that is not listed above.
- These are NOT gaps — set gap=false and do not manufacture a sharper move: writing type hints or docstrings, using simple f-string prompt templates, or any practice that is already current best practice or baseline hygiene.
- A gap must name what the developer's CURRENT practice specifically lacks versus a sharper move — not merely that the topic is active on the frontier. A pattern being widely discussed now is not evidence that their way of doing it is behind.

Return ONLY a JSON array, no prose, no fences. One item per pattern:
{{"pattern": "<their pattern>", "gap": true|false, "current_move": "<the sharper move, short>", \
"why": "<one concrete line on why it beats what they do>", "confidence": "high|med|low", "risk": "money|data|production|quality", "source_ids": ["<frontier ids like F3, or [] if none>"]}}"""


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
            try:
                r = json.loads(ln)
                if isinstance(r, dict): items.append(r)
            except Exception: pass
    if not items:
        return ("(no live frontier feed yet — using your own recent knowledge)", {})
    return _index(items)


def load_frontier(cap=45):
    return frontier_index(cap)[0]


def ground(gaps, id_map):
    """Strip fabricated frontier citations; mark grounded + attach the real sources."""
    for g in gaps:
        ids = [s for s in (g.get("source_ids") or []) if s in id_map]
        g["source_ids"] = ids
        g["grounded"] = bool(ids)
        g["sources"] = [id_map[s] for s in ids]
    return gaps


def load_breadcrumbs():
    rows = []
    if BREADCRUMBS.exists():
        for ln in BREADCRUMBS.read_text().splitlines():
            try: rows.append(json.loads(ln))
            except Exception: pass
    return rows


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


def judge(pats, frontier=None):
    """Run the REAL filter judgment on pattern dicts -> parsed items
    ({pattern, gap, current_move, why, confidence, risk}). This is the judge the harness calibrates."""
    def fmt(p):
        rec = f" (recurs across {p['n_repos']} of your repos)" if p.get("n_repos", 1) > 1 else ""
        return f"- {p['pattern']}{rec} — {p.get('evidence', '')}"
    listing = "\n".join(fmt(p) for p in pats)
    if frontier is None:
        frontier = load_frontier()
    return parse_json(call_codex(PROMPT.format(patterns=listing, frontier=frontier)))


def main():
    target_arg = sys.argv[1] if len(sys.argv) > 1 else None
    target = Path(target_arg).name if target_arg else None
    repo_arg = os.environ.get("WHETSTONE_REPO") or target_arg
    candidate = Path(repo_arg).expanduser() if repo_arg else None
    repo = candidate.resolve() if candidate and candidate.is_dir() else None
    rows = load_breadcrumbs()
    import canon
    cmap = canon.canonicalize([r.get("pattern") for r in rows if r.get("pattern")])
    pats = select(rows, target, cmap) if target else select(rows, None, cmap)
    if not pats:
        runs.replace_jsonl(GAPS, [])
        runs.replace_jsonl(FINDINGS, [])
        print("no breadcrumbs for this target — run breadcrumbs.py <repo> first"); return

    digest, id_map = frontier_index()
    items = judge(pats, frontier=digest)
    proposals = [it for it in items if it.get("gap")]
    ground(proposals, id_map)
    meta = {p["pattern"]: p for p in pats}
    for g in proposals:
        src = meta.get(g.get("pattern"), {})
        g["project"] = target or src.get("repo", "")
        g["evidence"] = src.get("evidence", "")
        g["commit"] = src.get("commit", "")
        g["n_repos"] = src.get("n_repos", 1)

    validations = validation.validate(proposals, repo)
    for finding, result in zip(proposals, validations):
        finding["proposal_id"] = result["proposal_id"]
        finding["classification"] = result["classification"]
        finding["validation_reason"] = result["reason"]
        finding["repository_evidence"] = result["repository_evidence"]
        finding["rejected_repository_evidence"] = result["rejected_repository_evidence"]
        finding["evidence_chain"] = {
            "history": {
                "evidence": finding.get("evidence", ""),
                "commit": finding.get("commit", ""),
            },
            "frontier": {
                "grounded": finding.get("grounded", False),
                "source_ids": finding.get("source_ids", []),
                "sources": finding.get("sources", []),
            },
            "repository": {
                "classification": result["classification"],
                "reason": result["reason"],
                "state": result["repository"],
                "evidence": result["repository_evidence"],
                "rejected_evidence": result["rejected_repository_evidence"],
            },
        }
        finding["evidence_rank"] = validation.evidence_tier(finding)
    conf = {"high": 0, "med": 1, "low": 2}
    risk = {"money": 0, "data": 1, "production": 2, "quality": 3}
    proposals.sort(key=lambda g: (
        g["evidence_rank"],
        risk.get(g.get("risk", "quality"), 4),
        conf.get(g.get("confidence", "low"), 3),
    ))
    gaps = [g for g in proposals if g.get("classification") in validation.ACTIONABLE]

    run_id = os.environ.get("WHETSTONE_RUN_ID", "")
    now = int(time.time())
    findings = [{"ts": now, "run_id": run_id, **g} for g in proposals]
    records = [{"ts": now, "run_id": run_id, **g} for g in gaps]
    runs.replace_jsonl(FINDINGS, findings)
    runs.replace_jsonl(GAPS, records)

    print(f"{len(pats)} patterns checked · {len(proposals)} proposed · "
          f"{len(gaps)} validated teaching targets\n")
    for g in proposals:
        frontier_mark = "frontier-grounded" if g.get("grounded") else "frontier-unverified"
        print(f"  [{g.get('classification', '?').upper()} · {frontier_mark} · "
              f"rank {g['evidence_rank']}] {g['pattern']}")
        print(f"      → {g.get('current_move', '')}")
        print(f"        proposal: {g.get('why', '')}")
        history = g["evidence_chain"]["history"]
        commit = f" @ {history.get('commit')}" if history.get("commit") else ""
        print(f"        history: {history.get('evidence') or '(none)'}{commit}")
        sources = g["evidence_chain"]["frontier"]["sources"]
        if sources:
            for source in sources:
                print(f"        frontier: {source.get('source', '')} — {source.get('title', '')} "
                      f"({source.get('link', '')})")
        else:
            print("        frontier: no verified live source")
        print(f"        repository: {g.get('validation_reason', '')}")
        for evidence in g.get("repository_evidence", []):
            print(f"          {evidence['path']}:{evidence['line_start']}-{evidence['line_end']} "
                  f"[{evidence.get('supports', 'context')}]")
        print()
    handled = sum(g.get("classification") == "already-handled" for g in proposals)
    insufficient = sum(g.get("classification") == "insufficient-evidence" for g in proposals)
    print(f"({handled} already handled · {insufficient} insufficient evidence · "
          f"{len(pats) - len(proposals)} judged not to be gaps.)")


if __name__ == "__main__":
    main()
