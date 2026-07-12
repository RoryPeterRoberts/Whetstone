#!/usr/bin/env python3
"""Claude Code `Stop` hook entry point.

Register in ~/.claude/settings.json so Claude Code runs it after every completed task:

    {"hooks": {"Stop": [{"hooks": [{"type": "command",
      "command": "python3 /ABS/PATH/whetstone/whetstone_hook.py"}]}]}}

It reads the hook JSON on stdin, drives the pipeline, and persists a per-session
checkpoint so the next Stop can tell what changed. It FAILS OPEN: any error is swallowed
and exit 0 is returned, so Whetstone can never break your session.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
CHECKPOINTS = ROOT / "session_checkpoints.json"


def _load():
    try:
        return json.loads(CHECKPOINTS.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save(d):
    try:
        CHECKPOINTS.write_text(json.dumps(d))
    except OSError:
        pass


def _head(cwd):
    r = subprocess.run(["git", "-C", str(cwd), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        return 0  # malformed input never breaks the host
    try:
        import pipeline
        cps = _load()
        sid = payload.get("session_id", "")
        cwd = payload.get("cwd", ".")
        result = pipeline.handle_stop(payload, checkpoint_head=cps.get(sid))
        cps[sid] = _head(cwd)
        _save(cps)
        sys.stderr.write(json.dumps(result) + "\n")  # diagnostics on stderr; stdout stays clean
    except Exception as e:  # fail open: Whetstone must never break a session
        sys.stderr.write(f"whetstone_hook: swallowed {type(e).__name__}: {e}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
