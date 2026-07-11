"""Repository identity (spec section 6): stable, path-independent repo_id.

Computed once, persisted in <git-common-dir>/whetstone_repo_id, read thereafter -- so a
later remote rename cannot change it. Worktrees share the common dir (same id); a move
changes only local_path; a clone of the same remote resolves to the SAME id (recomputed
deterministically), never a new repository. local_path / current remote are metadata
only, never used to establish transfer.
"""
import hashlib
import json
import re
import subprocess
import time
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator

SPEC = Path(__file__).resolve().parent.parent / "spec"
_SCHEMA = json.loads((SPEC / "schemas" / "repository_identity.schema.json").read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA)
PERSIST_NAME = "whetstone_repo_id"


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def canonical_remote(url):
    """credential-stripped, scp<->https normalized, .git-stripped, host-lowercased."""
    url = (url or "").strip()
    if url.endswith(".git"):
        url = url[:-4]
    if "://" in url:                       # scheme://[creds@]host/path
        rest = url.split("://", 1)[1]
    elif "@" in url and ":" in url.split("/", 1)[0]:   # scp form git@host:path
        left, _, path = url.partition(":")
        host = left.split("@")[-1]
        return host.lower() + "/" + path
    else:
        rest = url
    if "@" in rest.split("/", 1)[0]:       # strip user[:pass]@ from the authority
        rest = rest.split("@", 1)[1]
    host, sep, path = rest.partition("/")
    return host.lower() + (sep + path if sep else "")


def sorted_root_commits(repo):
    r = _git(repo, "rev-list", "--max-parents=0", "--all")
    return sorted(c for c in r.stdout.split() if c)


def _remote_url(repo):
    r = _git(repo, "remote", "get-url", "origin")
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    r = _git(repo, "remote")
    names = [n for n in r.stdout.split() if n]
    if names:
        r2 = _git(repo, "remote", "get-url", names[0])
        if r2.returncode == 0 and r2.stdout.strip():
            return r2.stdout.strip()
    return None


def _common_dir(repo):
    r = _git(repo, "rev-parse", "--git-common-dir")
    if r.returncode != 0:
        return None
    p = Path(r.stdout.strip())
    return p if p.is_absolute() else (Path(repo) / p).resolve()


def _compute(repo):
    remote = _remote_url(repo)
    roots = sorted_root_commits(repo)
    if remote:
        canon = canonical_remote(remote)
        rid = "r_" + hashlib.sha256((canon + "\n" + "\n".join(roots)).encode()).hexdigest()
        basis = {"canonical_remote_at_creation": canon, "sorted_root_commits": roots or ["0"]}
        return rid, "remote", basis, canon
    return "r_" + uuid.uuid4().hex, "local_uuid", None, None


def resolve(repo):
    """Return the persisted repository_identity record, computing+persisting on first use."""
    common = _common_dir(repo)
    if common is None:
        raise ValueError(f"not a git repository: {repo}")
    persist = common / PERSIST_NAME
    local_path = str(Path(repo).resolve())
    if persist.exists():
        rec = json.loads(persist.read_text())
        rec["local_path"] = local_path            # metadata only; identity is fixed
        return rec
    rid, origin_kind, basis, canon = _compute(repo)
    rec = {
        "repo_id": rid,
        "origin_kind": origin_kind,
        "persisted_at": str(int(time.time())),
        "local_path": local_path,
        "current_normalized_remote": canon,
    }
    if basis is not None:
        rec["identity_basis"] = basis
    errs = sorted(_VALIDATOR.iter_errors(rec), key=str)
    if errs:
        raise ValueError("invalid repository_identity: " + "; ".join(e.message for e in errs))
    # persist WITHOUT the mutable local_path so a move cannot rewrite identity
    persisted = {k: v for k, v in rec.items() if k != "local_path"}
    persist.write_text(json.dumps(persisted))
    return rec


def repo_id(repo):
    return resolve(repo)["repo_id"]
