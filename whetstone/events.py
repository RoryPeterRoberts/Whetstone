"""Product event ledger (events.jsonl) + three contextual projections + legacy migration.

Immutable, append-only source of truth: current state is DERIVED by replay, never
mutated in place (spec section 4). Reuses runs.append (fsync) for durability and the
enforcing schema + cross-field validator under spec/ so an invalid event cannot be
written.

Three projections, all rebuildable and safe to delete (dispositions are contextual):
  1. global learner   -- has the person ever recalled/transferred anywhere;
  2. per-repository    -- disposition of a principle within one repo_id;
  3. versioned status  -- status keyed by (principle_id, principle_version), so a
                          detector change never silently re-opens settled history.
"""
import hashlib
import importlib.util
import json
import time
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator

import runs

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
SPEC = REPO_ROOT / "spec"
EVENTS = ROOT / "events.jsonl"
TAUGHT = ROOT / "taught.jsonl"
PROJECTIONS = ROOT / "projections"

SCHEMA_VERSION = 1
WHETSTONE_VERSION = "0.1.0-mvp"
POLICY_VERSION = "slice-1"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_validate_event = _load_module("whetstone_validate_event", SPEC / "validate_event.py").validate_event
_SCHEMA = json.loads((SPEC / "schemas" / "product_event.schema.json").read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA)


# ---------------------------------------------------------------------------
# Event construction (validated before it can be written)
# ---------------------------------------------------------------------------

def _audit(**overrides):
    base = {
        "schema_version": SCHEMA_VERSION,
        "whetstone_version": WHETSTONE_VERSION,
        "policy_version": POLICY_VERSION,
        "detector_version": None,
        "model_id": None,
        "mapping_prompt_hash": None,
        "worktree_sha256": None,
    }
    base.update(overrides)
    return base


def make_event(kind, principle_id, principle_version, repo_id, host, session_id,
               evidence, ts=None, event_id=None, **fields):
    """Build a schema-valid event or raise ValueError. Does NOT write."""
    ev = {
        "event_id": event_id or ("e_" + uuid.uuid4().hex),
        "ts": int(ts if ts is not None else time.time()),
        "kind": kind,
        "principle_id": principle_id,
        "principle_version": principle_version,
        "repo_id": repo_id,
        "host": host,
        "session_id": session_id,
        "evidence": evidence,
    }
    # optional top-level fields (local_path, head, confidence) if supplied
    for k in ("local_path", "head", "confidence"):
        if k in fields:
            ev[k] = fields.pop(k)
    ev.update(_audit(**fields))
    errors = validate(ev)
    if errors:
        raise ValueError("invalid event: " + "; ".join(errors))
    return ev


def validate(ev):
    """Return a list of reject reasons ([] if valid): schema + cross-field invariants."""
    reasons = [e.message for e in sorted(_VALIDATOR.iter_errors(ev), key=str)]
    reasons.extend(_validate_event(ev))
    return reasons


def append_event(ev, path=EVENTS):
    """Validate then durably append. Refuses to write an invalid event."""
    errors = validate(ev)
    if errors:
        raise ValueError("refusing to append invalid event: " + "; ".join(errors))
    runs.append(ev, path=path)
    return ev


def emit(kind, principle_id, principle_version, repo_id, host, session_id,
         evidence, path=EVENTS, **fields):
    return append_event(
        make_event(kind, principle_id, principle_version, repo_id, host, session_id,
                   evidence, **fields),
        path=path,
    )


# ---------------------------------------------------------------------------
# Replay + projections
# ---------------------------------------------------------------------------

def load_events(path=EVENTS):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # a torn final line from a crash mid-append is skipped, never fatal
            continue
    return out


_RECALL_KINDS = {"direction_recalled", "recall_deferred", "recall_unmatched"}
_TRANSFER_KINDS = {"transferred", "repeated_unaided_transfer"}


def project_global_learner(events):
    """Has this person ever recalled / transferred a principle, anywhere."""
    ever_recalled = any(e["kind"] == "direction_recalled" for e in events)
    ever_transferred = any(e["kind"] in _TRANSFER_KINDS for e in events)
    return {
        "ever_recalled": ever_recalled,
        "ever_transferred": ever_transferred,
        "transferred_count": sum(1 for e in events if e["kind"] in _TRANSFER_KINDS),
        "recalled_count": sum(1 for e in events if e["kind"] == "direction_recalled"),
    }


def project_per_repo_disposition(events):
    """Latest disposition of each principle within each repo_id.

    The append-only log order is the authoritative causal sequence, so the LAST
    matching event in ledger order wins -- never wall-clock ts, which can tie within
    a second or run backwards across hosts.
    """
    out = {}
    for e in events:
        repo = out.setdefault(e["repo_id"], {})
        repo[e["principle_id"]] = {"kind": e["kind"], "ts": e["ts"],
                                   "principle_version": e["principle_version"]}
    return out


def project_versioned_principle_status(events):
    """Latest status keyed by (principle_id, principle_version), in ledger order --
    history is versioned so a detector bump never re-opens a settled version."""
    out = {}
    for e in events:
        key = f"{e['principle_id']}@{e['principle_version']}"
        out[key] = {"kind": e["kind"], "ts": e["ts"], "repo_id": e["repo_id"]}
    return out


def build_projections(events=None, path=EVENTS):
    events = load_events(path) if events is None else events
    return {
        "global_learner": project_global_learner(events),
        "per_repo_disposition": project_per_repo_disposition(events),
        "versioned_principle_status": project_versioned_principle_status(events),
    }


def rebuild_projections(path=EVENTS, out_dir=PROJECTIONS):
    """Persist the three projections as rebuildable JSON snapshots (safe to delete)."""
    out_dir = Path(out_dir)
    proj = build_projections(path=path)
    for name, data in proj.items():
        runs.replace_jsonl(out_dir / f"{name}.json", [data])
    return proj


# ---------------------------------------------------------------------------
# Legacy migration (taught.jsonl -> seed events). Runs once, idempotent.
# ---------------------------------------------------------------------------

_STATUS_TO_KIND = {"open": "proposed", "needs_verification": "needs_verification"}


def _h(*parts):
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _seed_event_id(row):
    canonical = json.dumps(row, sort_keys=True, ensure_ascii=False)
    return "e_migrate_" + _h(canonical)[:16]


def _migrate_row(row):
    """Map one legacy taught.jsonl row to a deterministic seed event (or None to skip).

    Legacy rows are heterogeneous patterns with no resolved repo identity, so they get
    explicitly LEGACY-NAMESPACED synthetic ids that cannot collide with a real
    algorithm-derived repo_id (spec section 6) nor be read as a transfer. Fail-safe per
    the section 13 table: anything not 'open'/'needs_verification' -> needs_verification.
    """
    kind = _STATUS_TO_KIND.get(row.get("status"), "needs_verification")
    principle_id = "p_legacy_" + _h(row.get("pattern", ""))[:12]
    repo_id = "r_legacy_" + _h(row.get("project", ""))[:16]
    finding_id = "f_legacy_" + _h(_seed_event_id(row))[:12]
    if kind == "proposed":
        evidence = {"finding_id": finding_id, "classification": "partial"}
    else:  # needs_verification
        evidence = {"finding_id": finding_id, "reason": "migrated_legacy"}
    return make_event(
        kind, principle_id, 1, repo_id, "other", "migration", evidence,
        ts=row.get("ts"), event_id=_seed_event_id(row),
    )


def migrate_taught(taught_path=TAUGHT, events_path=EVENTS):
    """Replay taught.jsonl rows into seed events once. Idempotent: deterministic seed
    event_ids are deduplicated against events already in the ledger, so re-running
    appends nothing new."""
    taught_path = Path(taught_path)
    if not taught_path.exists():
        return {"appended": 0, "skipped": 0}
    existing = {e["event_id"] for e in load_events(events_path)}
    appended = skipped = 0
    for line in taught_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        ev = _migrate_row(row)
        if ev["event_id"] in existing:
            skipped += 1
            continue
        append_event(ev, path=events_path)
        existing.add(ev["event_id"])
        appended += 1
    return {"appended": appended, "skipped": skipped}
