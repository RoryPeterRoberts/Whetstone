#!/usr/bin/env python3
"""Record phase_verified evidence into build_evidence.jsonl.

Runs each exit test, captures its REAL stdout and exit code, computes hashes, builds
a phase_verified record, validates it against build_evidence.schema.json, and appends
(fsync) one record per test.

A non-zero exit for any test aborts WITHOUT writing anything: a failed phase cannot be
recorded as verified. This is enforced twice over -- here (we refuse to build the record)
and by the schema itself (exit_code is const 0).

Usage:
    python3 spec/record_phase.py <phase-int> "<notes>" -- <argv...> [-- <argv...> ...]

Each "-- argv..." group is one exit test, run from the repo root. Example (Phase 1):
    python3 spec/record_phase.py 1 "vertical-slice foundation" \
        -- python3 -m pytest whetstone -q \
        -- python3 spec/schema_tests/run_schema_tests.py
"""
import json, hashlib, subprocess, sys, os, time
from jsonschema import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCHEMA = json.load(open(os.path.join(HERE, "schemas", "build_evidence.schema.json")))
LEDGER = os.path.join(ROOT, "build_evidence.jsonl")
MANIFEST = os.path.join(HERE, "schema_tests", "manifest.json")
VALIDATOR = Draft202012Validator(SCHEMA)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def current_commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def split_argv_groups(argv):
    groups, cur = [], None
    for tok in argv:
        if tok == "--":
            if cur is not None:
                groups.append(cur)
            cur = []
        elif cur is not None:
            cur.append(tok)
    if cur:
        groups.append(cur)
    return [g for g in groups if g]


def build_record(phase, argv, notes, commit, manifest_sha):
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(f"ABORT: exit test failed (exit {proc.returncode}); nothing written.\n")
        sys.stderr.write(f"  argv: {' '.join(argv)}\n")
        sys.stderr.write(proc.stdout[-2000:] + "\n" + proc.stderr[-2000:] + "\n")
        return None
    rec = {
        "kind": "phase_verified",
        "phase": phase,
        "commit": commit,
        "test_command_argv": argv,
        "exit_code": proc.returncode,
        "stdout_sha256": sha_bytes(proc.stdout.encode()),
        "test_manifest_sha256": manifest_sha,
        "ts": int(time.time()),
        "notes": notes,
    }
    errs = sorted(VALIDATOR.iter_errors(rec), key=str)
    if errs:
        sys.stderr.write("ABORT: record fails build_evidence.schema.json; nothing written.\n")
        for e in errs:
            sys.stderr.write("  - " + e.message + "\n")
        return None
    return rec


def append(rec):
    with open(LEDGER, "a") as f:
        f.write(json.dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main(argv):
    phase = int(argv[0])
    notes = argv[1]
    groups = split_argv_groups(argv[2:])
    if not groups:
        sys.stderr.write("no exit-test argv groups given (need at least one -- argv...)\n")
        return 2
    commit = current_commit()
    manifest_sha = sha_bytes(open(MANIFEST, "rb").read())
    records = []
    for g in groups:
        rec = build_record(phase, g, notes, commit, manifest_sha)
        if rec is None:
            return 1  # abort before any write
        records.append(rec)
    # all tests passed and all records valid -> commit them together
    for rec in records:
        append(rec)
    print(f"recorded {len(records)} phase_verified entries for phase {phase} at commit {commit[:10]} -> {LEDGER}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
