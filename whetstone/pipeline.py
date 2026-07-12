"""Live orchestrator: the entry a Claude Code `Stop` hook invokes (spec sections 5, 9).

Composes the proven modules into one call. On a meaningful build it resolves the repo
identity, captures any user-authored direction, runs the detector over the changed
Python, and records the deterministic events (opportunity_detected, and a proposed
finding on first encounter). The strong, tell-dependent claims (transfer) stay in the
verify path -- this orchestrator never asserts transfer from the heuristic alone.
"""
import subprocess
import time
from pathlib import Path

import capture
import detector
import events
import repo_id

PRINCIPLE_ID = "p_structured_output_boundary"
PRINCIPLE_VERSION = 1
HOST = "claude_code"


def _changed_python(cwd, checkpoint_head):
    """(relpath, source) for .py files changed since the checkpoint or in the worktree."""
    names = set()
    if checkpoint_head:
        r = subprocess.run(["git", "-C", str(cwd), "diff", "--name-only",
                            f"{checkpoint_head}..HEAD"], capture_output=True, text=True)
        names.update(r.stdout.split())
    r = subprocess.run(["git", "-C", str(cwd), "diff", "--name-only", "HEAD"],
                       capture_output=True, text=True)
    names.update(r.stdout.split())
    out = []
    for n in sorted(names):
        if n.endswith(".py"):
            p = Path(cwd) / n
            if p.exists():
                out.append((n, p.read_text()))
    return out


def handle_stop(payload, *, user_prompt_submit=None, checkpoint_head=None,
                changed_sources=None, path=events.EVENTS):
    """Process one completed task. Returns a summary dict; records deterministic events."""
    cwd = payload.get("cwd")
    session_id = payload.get("session_id", "")
    rec = repo_id.resolve(cwd)
    rid = rec["repo_id"]

    if not capture.is_meaningful_build(cwd, checkpoint_head):
        return {"status": "ignored", "reason": "no relevant diff since checkpoint", "repo_id": rid}

    assoc, direction = capture.capture_direction(
        payload.get("transcript_path"), payload, rid, ts=int(time.time()),
        user_prompt_submit=user_prompt_submit)

    sources = changed_sources if changed_sources is not None else _changed_python(cwd, checkpoint_head)
    proj = events.build_projections(path=path)
    seen = proj["per_repo_disposition"]
    settled_elsewhere = any(r != rid and PRINCIPLE_ID in principles for r, principles in seen.items())

    results = []
    for relpath, src in sources:
        opp = detector.detect_opportunity(src, rid, diff_scope=relpath)
        if not opp:
            continue
        events.emit("opportunity_detected", PRINCIPLE_ID, PRINCIPLE_VERSION, rid, HOST,
                    session_id,
                    {"opportunity_id": opp["opportunity_id"], "repo_id": rid,
                     "diff_scope": relpath, "detector_version": opp["detector_version"]},
                    detector_version=opp["detector_version"], path=path)
        if settled_elsewhere:
            # a later repo where the principle already applied elsewhere -> recall candidate
            results.append({"file": relpath, "opportunity_id": opp["opportunity_id"],
                            "action": "recall_candidate", "confidence": opp["confidence"]})
        else:
            finding_id = "f_" + opp["opportunity_id"][2:14]
            events.emit("proposed", PRINCIPLE_ID, PRINCIPLE_VERSION, rid, HOST, session_id,
                        {"finding_id": finding_id, "classification": opp["confidence"]},
                        detector_version=opp["detector_version"], path=path)
            results.append({"file": relpath, "opportunity_id": opp["opportunity_id"],
                            "action": "proposed", "finding_id": finding_id})

    return {"status": "processed", "repo_id": rid,
            "direction_captured": bool(direction),
            "direction_association": assoc,
            "results": results}
