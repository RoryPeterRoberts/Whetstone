"""Phase 5: the MVP control surface (spec sections 5, 12).

Status is a COMMAND, not a dashboard. The trust contract is visible: no account, no
telemetry; `delete-data` removes the local product records on demand.

    python3 cli.py {on|off|status|delete-data|diagnostic}   (run from the whetstone/ dir)
"""
import json
import sys
from pathlib import Path

import capture
import detector
import events
import matcher

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "whetstone_config.json"


def _load_config():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return {"enabled": False}


def _save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n")


def cmd_on():
    _save_config({**_load_config(), "enabled": True})
    return "whetstone: capture ON"


def cmd_off():
    _save_config({**_load_config(), "enabled": False})
    return "whetstone: capture OFF"


def cmd_status(events_path=events.EVENTS):
    """Command-altitude learner state, derived from the ledger (no dashboard)."""
    proj = events.build_projections(path=events_path)
    g = proj["global_learner"]
    lines = [
        f"capture: {'on' if _load_config().get('enabled') else 'off'}",
        f"principles ever transferred: {g['transferred_count']}",
        f"principles ever recalled:    {g['recalled_count']}",
        f"repositories seen:           {len(proj['per_repo_disposition'])}",
    ]
    for repo, principles in sorted(proj["per_repo_disposition"].items()):
        for pid, st in sorted(principles.items()):
            lines.append(f"  {repo[:14]}  {pid[:28]:28}  {st['kind']}")
    return "\n".join(lines)


def cmd_delete_data(events_path=events.EVENTS):
    """Remove local product records on demand (events, directions, projections).

    Leaves build_evidence.jsonl (dev governance) and taught.jsonl (legacy engine input)
    untouched -- this deletes the USER's captured product data only."""
    removed = []
    targets = [Path(events_path), capture.DIRECTIONS, events.PROJECTIONS]
    for t in targets:
        t = Path(t)
        if t.is_dir():
            for f in t.glob("*"):
                f.unlink()
            t.rmdir()
            removed.append(str(t))
        elif t.exists():
            t.unlink()
            removed.append(str(t))
    return "deleted: " + (", ".join(removed) if removed else "(nothing to delete)")


def cmd_diagnostic(events_path=events.EVENTS):
    """Report capability + versions; prompt_id is capability-detected at RUNTIME per Stop."""
    n_events = len(events.load_events(events_path))
    n_dir = len(capture.DIRECTIONS.read_text().splitlines()) if capture.DIRECTIONS.exists() else 0
    info = {
        "enabled": _load_config().get("enabled", False),
        "schema_version": events.SCHEMA_VERSION,
        "whetstone_version": events.WHETSTONE_VERSION,
        "policy_version": events.POLICY_VERSION,
        "matcher_version": matcher.MATCHER_VERSION,
        "detector_version": detector.DETECTOR_VERSION,
        "prompt_id": "capability-detected per Stop (fallbacks: paired UserPromptSubmit, ancestry)",
        "events_recorded": n_events,
        "direction_records": n_dir,
        "trust": "no account, no telemetry, no unsandboxed fallback",
    }
    return json.dumps(info, indent=2)


_COMMANDS = {
    "on": cmd_on, "off": cmd_off, "status": cmd_status,
    "delete-data": cmd_delete_data, "diagnostic": cmd_diagnostic,
}


def main(argv):
    if not argv or argv[0] not in _COMMANDS:
        sys.stderr.write("usage: whetstone.cli {on|off|status|delete-data|diagnostic}\n")
        return 2
    print(_COMMANDS[argv[0]]())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
