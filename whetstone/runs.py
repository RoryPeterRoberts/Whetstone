"""Durable records for Whetstone's evidence pipeline."""
import json
import os
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs.jsonl"


def new(repo, head=""):
    return {"run_id": uuid.uuid4().hex, "started_ts": int(time.time()),
            "repo": str(Path(repo).resolve()), "project": Path(repo).resolve().name,
            "head": head, "status": "running", "stages": []}


def stage(run, name, status, detail=""):
    run["stages"].append({"name": name, "status": status, "detail": detail})
    return run


def finish(run, status, error=""):
    run["status"] = status
    run["finished_ts"] = int(time.time())
    if error:
        run["error"] = error
    append(run)
    return run


def append(record, path=None):
    path = Path(path or RUNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def replace_jsonl(path, records):
    """Atomically replace a snapshot, preserving the old file on failure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
