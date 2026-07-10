#!/usr/bin/env python3
"""Whetstone CLI — an evidence-bearing learn pipeline."""
import os
import subprocess
import sys
from pathlib import Path

import runs

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def _run(script, *args, env=None):
    return subprocess.run([PYTHON, str(ROOT / script), *map(str, args)], check=True,
                          env={**os.environ, **(env or {})})


def _head(repo):
    result = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def learn(repo, n=14, top=3):
    repo = Path(repo).expanduser().resolve()
    if not repo.is_dir():
        raise ValueError(f"repository does not exist: {repo}")
    run = runs.new(repo, _head(repo))
    env = {"WHETSTONE_RUN_ID": run["run_id"], "WHETSTONE_REPO": str(repo)}
    try:
        print(f"\n▶ 1/4  reading what you build in {repo} …")
        _run("breadcrumbs.py", repo, n, env=env)
        runs.stage(run, "breadcrumbs", "ok")

        print("\n▶ 2/4  finding the gaps vs current best practice …")
        _run("filter.py", repo.name, env=env)
        runs.stage(run, "filter", "ok")

        import teach
        uncertain = teach.mark_needs_verification(repo.name)
        if uncertain:
            print("\n? no longer detected; verify before calling these applied:")
            for item in uncertain:
                print(f"    - {item}")

        print("\n▶ 3/4  teaching the top gaps + banking the commands …\n")
        gaps = [g for g in teach.load_gaps() if g.get("run_id") == run["run_id"]][:int(top)]
        for gap in gaps:
            result = teach.teach_gap(gap)
            print("=" * 72); print(result["lesson"]); print()
        runs.stage(run, "teach", "ok", f"{len(gaps)} lesson(s)")
        runs.finish(run, "complete")

        if not gaps:
            print("no evidence-backed gaps found in this run.")
        print(f"\n✓ 4/4  run {run['run_id'][:8]} complete. {len(gaps)} lesson(s) banked for '{repo.name}'.")
        print(f"  explore: python {ROOT / 'teacher.py'}   →  http://localhost:8099")
        return run
    except Exception as exc:
        runs.stage(run, "pipeline", "failed", str(exc))
        runs.finish(run, "failed", str(exc))
        print(f"\n✗ run {run['run_id'][:8]} failed: {exc}", file=sys.stderr)
        raise


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "learn":
        learn(args[1], *(args[2:4]))
    elif args and args[0] == "watch":
        _run("watch.py", *args[1:])
    elif args and args[0] == "check":
        _run("judge_eval.py")
    else:
        print("usage:\n  whet watch                     refresh the live frontier feed\n  whet learn <repo> [n] [top]    run the evidence pipeline\n  whet check                     calibrate the judge")


if __name__ == "__main__":
    main()
