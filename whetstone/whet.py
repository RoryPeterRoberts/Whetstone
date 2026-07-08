#!/usr/bin/env python3
"""Whetstone CLI — the whole loop in one command.

    whet learn <repo> [n_commits=14] [top_gaps=3]

Runs: breadcrumbs (what you do) -> filter (the recurring gap vs current best practice)
-> teach (a lesson per gap) -> bank (the reusable command). Then open the teacher to explore.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _run(script, *args):
    subprocess.run([PY, str(ROOT / script), *map(str, args)], check=False)


def learn(repo, n=14, top=3):
    print(f"\n▶ 1/4  reading what you build in {repo} …")
    _run("breadcrumbs.py", repo, n)
    print("\n▶ 2/4  finding the gaps vs current best practice …")
    _run("filter.py")
    print("\n▶ 3/4  teaching the top gaps + banking the commands …\n")
    import teach
    gaps = teach.load_gaps()[:int(top)]
    if not gaps:
        print("no gaps found — you're at current best practice on what you did here."); return
    for g in gaps:
        r = teach.teach_gap(g)
        print("=" * 72); print(r["lesson"]); print()
    print(f"\n✓ 4/4  loop complete. {len(gaps)} lesson(s) taught, commands banked.")
    print(f"  explore + bank more:  python {ROOT / 'teacher.py'}   →  http://localhost:8099")


def main():
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "learn":
        learn(a[1], *(a[2:4]))
    elif a and a[0] == "watch":
        _run("watch.py", *a[1:])
    else:
        print("usage:\n  whet watch                     refresh the live frontier feed (run daily via cron)\n  whet learn <repo> [n] [top]    run the loop on a repo")


if __name__ == "__main__":
    main()
