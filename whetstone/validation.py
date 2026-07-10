#!/usr/bin/env python3
"""Validate proposed gaps against a repository's current working tree.

The model may propose a classification and citations, but code decides whether
those citations are real.  Any actionable verdict without at least one exact,
in-repository file/line/excerpt citation is downgraded to insufficient evidence.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


CODEX = os.environ.get("CODEX_BIN") or shutil.which("codex") or os.path.expanduser("~/.local/bin/codex")
CLASSIFICATIONS = {"confirmed", "partial", "already-handled", "insufficient-evidence"}
ACTIONABLE = {"confirmed", "partial"}
MAX_EVIDENCE_LINES = 20

PROMPT = """You are Whetstone's repository verifier. A separate pass proposed the findings below.
Inspect the CURRENT code in this repository before deciding. Do not rely on commit summaries or the
proposal's confidence. Do not edit anything.

Classify every proposal as exactly one of:
- confirmed: current code clearly lacks the proposed move.
- partial: current code handles part of it, but a specific material gap remains.
- already-handled: current code already implements the move or an equivalent.
- insufficient-evidence: the current repository cannot support a responsible verdict.

For confirmed, partial, or already-handled, cite at least one exact current-code excerpt. Use paths
relative to the repository and 1-based inclusive line numbers. Keep each excerpt to at most 20 lines.
The excerpt MUST exactly equal those complete lines in the current file. Prefer implementation and tests
over documentation. For partial, cite both what is handled and what remains when the code permits it.
Never infer absence merely because one file does not show a feature: search the repository.

Return ONLY a JSON array, with exactly one object per proposal_id and no prose or fences:
{{"proposal_id":"P1","classification":"confirmed|partial|already-handled|insufficient-evidence",
"reason":"specific repository-based reason",
"repository_evidence":[{{"path":"relative/file.py","line_start":1,"line_end":2,
"excerpt":"exact complete lines","supports":"gap|handled|context"}}]}}

PROPOSALS:
{proposals}
"""


def _parse_json(text):
    text = (text or "").strip()
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        try:
            value = json.loads(text[start:end + 1])
            return value if isinstance(value, list) else []
        except (TypeError, ValueError):
            pass
    return []


def call_codex(repo, prompt):
    """Run a Codex verification pass with the target repo as cwd.

    Prefers the read-only sandbox. If the platform's sandbox cannot initialize
    (e.g. bwrap network setup is blocked -> "Operation not permitted", so Codex
    can read no files and refuses), fall back to a no-sandbox run so validation
    can still happen. Integrity is preserved regardless: the Codex output is an
    untrusted PROPOSAL, and every citation is independently re-checked against
    the real files by verify_repository_evidence — Codex cannot fabricate its way
    past that deterministic gate."""
    prompt_file = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    prompt_file.write(prompt)
    prompt_file.close()

    def _run(sandbox_args):
        output = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False).name
        try:
            with open(prompt_file.name, encoding="utf-8") as stdin:
                subprocess.run(
                    [CODEX, "exec", *sandbox_args,
                     "-c", 'model_reasoning_effort="low"',  # verification is a lookup, not deep reasoning
                     "--skip-git-repo-check", "-o", output, "-"],
                    cwd=repo,
                    stdin=stdin,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=600,  # agentic file exploration on a large repo needs headroom
                    check=True,
                )
            return Path(output).read_text(encoding="utf-8").strip()
        finally:
            try:
                os.unlink(output)
            except OSError:
                pass

    def _sandbox_broken(text):
        low = (text or "").lower()
        return (not text) or "bwrap" in low or (
            "sandbox" in low and ("fail" in low or "not permitted" in low or "cannot" in low)
        )

    try:
        try:
            result = _run(["--sandbox", "read-only"])
        except subprocess.CalledProcessError:
            result = ""
        if _sandbox_broken(result):
            result = _run(["--dangerously-bypass-approvals-and-sandbox"])
        return result
    finally:
        try:
            os.unlink(prompt_file.name)
        except OSError:
            pass


def repository_state(repo):
    """Identify the exact HEAD plus working-tree state used for validation."""
    repo = Path(repo).resolve()

    def git_bytes(*args):
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, check=False
        )
        return result.stdout if result.returncode == 0 else b""

    def git_text(*args):
        return git_bytes(*args).decode("utf-8", errors="replace").strip()

    head = git_text("rev-parse", "HEAD")
    status = git_text("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    fingerprint = hashlib.sha256()
    fingerprint.update(head.encode("utf-8"))
    fingerprint.update("\n".join(status).encode("utf-8"))
    fingerprint.update(git_bytes("diff", "--no-ext-diff", "--binary", "HEAD"))
    untracked = git_bytes("ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    for raw_rel in sorted(path for path in untracked if path):
        fingerprint.update(raw_rel)
        try:
            rel = raw_rel.decode("utf-8")
            path = (repo / rel).resolve()
            if path.is_relative_to(repo) and path.is_file():
                fingerprint.update(path.read_bytes())
        except (OSError, UnicodeError):
            fingerprint.update(b"<unreadable>")
    return {
        "path": str(repo),
        "head": head,
        "dirty": bool(status),
        "status": status,
        "worktree_sha256": fingerprint.hexdigest(),
    }


def verify_repository_evidence(repo, citations):
    """Return (verified, rejected) citations after exact filesystem checks."""
    root = Path(repo).resolve()
    verified, rejected = [], []
    for raw in citations if isinstance(citations, list) else []:
        citation = dict(raw) if isinstance(raw, dict) else {"value": raw}
        try:
            rel = citation.get("path", "")
            start = int(citation.get("line_start"))
            end = int(citation.get("line_end"))
            if not rel or Path(rel).is_absolute():
                raise ValueError("path must be repository-relative")
            path = (root / rel).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("path is not a file inside the repository")
            if start < 1 or end < start or end - start + 1 > MAX_EVIDENCE_LINES:
                raise ValueError("invalid or overlong line range")
            raw_data = path.read_bytes()
            data = raw_data.decode("utf-8")
            lines = data.splitlines()
            if end > len(lines):
                raise ValueError("line range is outside the file")
            expected = "\n".join(lines[start - 1:end])
            if citation.get("excerpt") != expected:
                raise ValueError("excerpt does not exactly match current code")
            verified.append({
                "path": path.relative_to(root).as_posix(),
                "line_start": start,
                "line_end": end,
                "excerpt": expected,
                "supports": citation.get("supports", "context"),
                "file_sha256": hashlib.sha256(raw_data).hexdigest(),
                "verified": True,
            })
        except (OSError, UnicodeError, TypeError, ValueError) as exc:
            rejected.append({**citation, "verified": False, "rejection_reason": str(exc)})
    return verified, rejected


def _insufficient(proposal_id, reason, state, rejected=None):
    return {
        "proposal_id": proposal_id,
        "classification": "insufficient-evidence",
        "reason": reason,
        "repository": state,
        "repository_evidence": [],
        "rejected_repository_evidence": rejected or [],
    }


def validate(proposals, repo, caller=call_codex):
    """Classify every proposal and fail closed when current-code proof is absent."""
    numbered = []
    for index, proposal in enumerate(proposals, 1):
        numbered.append({
            "proposal_id": f"P{index}",
            "pattern": proposal.get("pattern", ""),
            "current_move": proposal.get("current_move", ""),
            "why": proposal.get("why", ""),
            "historical_evidence": proposal.get("evidence", ""),
            "historical_commit": proposal.get("commit", ""),
        })
    if not numbered:
        return []
    if not repo:
        state = {"path": "", "head": "", "dirty": False, "status": [],
                 "worktree_sha256": ""}
        return [
            _insufficient(p["proposal_id"], "target repository path was not provided", state)
            for p in numbered
        ]
    repo = Path(repo).resolve()
    state = repository_state(repo)
    if not repo.is_dir():
        return [_insufficient(p["proposal_id"], "target repository is unavailable", state) for p in numbered]

    try:
        raw_results = _parse_json(caller(repo, PROMPT.format(
            proposals=json.dumps(numbered, indent=2, ensure_ascii=False))))
    except Exception as exc:
        return [
            _insufficient(p["proposal_id"], f"repository validation failed: {exc}", state)
            for p in numbered
        ]
    final_state = repository_state(repo)
    if state["worktree_sha256"] != final_state["worktree_sha256"]:
        return [
            _insufficient(
                p["proposal_id"], "repository changed during validation; rerun against a stable worktree", final_state
            )
            for p in numbered
        ]
    state = final_state

    by_id = {}
    for item in raw_results:
        if isinstance(item, dict) and item.get("proposal_id") not in by_id:
            by_id[item.get("proposal_id")] = item

    results = []
    for proposal in numbered:
        proposal_id = proposal["proposal_id"]
        item = by_id.get(proposal_id)
        if not item:
            results.append(_insufficient(proposal_id, "validator returned no result", state))
            continue
        classification = item.get("classification")
        verified, rejected = verify_repository_evidence(repo, item.get("repository_evidence", []))
        if classification not in CLASSIFICATIONS:
            results.append(_insufficient(
                proposal_id, "validator returned an unknown classification", state, rejected
            ))
        elif classification != "insufficient-evidence" and not verified:
            results.append(_insufficient(
                proposal_id,
                "actionable verdict was downgraded because it had no exact current-code citation",
                state,
                rejected,
            ))
        else:
            results.append({
                "proposal_id": proposal_id,
                "classification": classification,
                "reason": item.get("reason", ""),
                "repository": state,
                "repository_evidence": verified,
                "rejected_repository_evidence": rejected,
            })
    return results


def evidence_tier(finding):
    """Stable, legible rank: doubly grounded first; unverified last."""
    classification = finding.get("classification")
    grounded = bool(finding.get("grounded"))
    if classification in ACTIONABLE and grounded:
        return 0
    if classification in ACTIONABLE:
        return 1
    if classification == "already-handled":
        return 2
    return 3
