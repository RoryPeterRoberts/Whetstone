#!/usr/bin/env python3
"""Whetstone — breadcrumbs.

Read a repo's recent git history and infer the LLM-building patterns the
developer actually used. This is the "what you do" stream: cheap, after-the-fact,
no live session hook. A model reads the diffs; you never watch the stream.

    python breadcrumbs.py <repo-path> [n_commits=12]
"""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BREADCRUMBS = ROOT / "breadcrumbs.jsonl"
CODEX = os.environ.get("CODEX_BIN") or shutil.which("codex") or os.path.expanduser("~/.local/bin/codex")
CODE_GLOBS = ["*.py", "*.js", "*.ts", "*.tsx", "*.jsx", "*.go", "*.rs"]
MAX_DIFF = 12000

PROMPT = """You are analysing a developer's recent git history to find which LLM-BUILDING PATTERNS \
they used — reusable techniques for building WITH large language models. Examples: constrained / \
structured output (JSON schema, grammars), tool / function calling, RAG / retrieval, embeddings, \
prompt caching, streaming, retries / backoff on API errors, model routing or fallback, evals or \
LLM-as-judge, multi-agent orchestration, chunking, fine-tuning, quantization, local inference, \
guardrails, batching, system-prompt design.

Recent commit messages:
{msgs}

Recent code diffs (truncated):
{diff}

Return ONLY a JSON array — no prose, no markdown fences. Each item:
{{"pattern": "<short canonical name>", "evidence": "<file or one-line why it's here>", "commit": "<sha if identifiable else ''>"}}
Only include patterns ACTUALLY present in the code / commits. If none, return []."""


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True).stdout


def collect(repo, n):
    msgs = git(repo, "log", f"-n{n}", "--pretty=format:%h %s")
    diff = git(repo, "log", f"-n{n}", "-p", "--", *CODE_GLOBS)
    if len(diff) > MAX_DIFF:
        diff = diff[:MAX_DIFF] + "\n…(truncated)"
    return msgs, diff


def call_codex(prompt):
    pf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False); pf.write(prompt); pf.close()
    out = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False).name
    try:
        with open(pf.name) as stdin:
            subprocess.run([CODEX, "exec", "--skip-git-repo-check", "-o", out, "-"], stdin=stdin,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240, check=True)
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


def main():
    repo = os.path.abspath(os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "."))
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    name = os.path.basename(repo.rstrip("/"))
    msgs, diff = collect(repo, n)
    if not msgs.strip():
        print(f"no git history in {repo}"); return
    items = parse_json(call_codex(PROMPT.format(msgs=msgs, diff=diff)))

    existing = set()
    if BREADCRUMBS.exists():
        for ln in BREADCRUMBS.read_text().splitlines():
            try:
                r = json.loads(ln); existing.add((r.get("repo"), r.get("pattern")))
            except Exception: pass

    added = 0
    with open(BREADCRUMBS, "a") as f:
        for it in items:
            pat = (it.get("pattern") or "").strip()
            if not pat or (name, pat) in existing:
                continue
            f.write(json.dumps({"ts": int(time.time()), "repo": name, "pattern": pat,
                                "evidence": it.get("evidence", ""), "commit": it.get("commit", "")}) + "\n")
            existing.add((name, pat)); added += 1

    print(f"{name}: {len(items)} patterns found, {added} new breadcrumbs")
    for it in items:
        print(f"  · {it.get('pattern')} — {it.get('evidence', '')}")


if __name__ == "__main__":
    main()
