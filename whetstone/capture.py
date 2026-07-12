"""Phase 3: Stop-hook trigger + direction capture (user-authored text only).

The load-bearing separation: a `direction_record` may be built ONLY from human-typed
user turns bound to the completed task. Everything a model produced -- assistant records,
tool-result turns wearing type=="user", sub-agent (`isSidechain`) turns -- is excluded at
the root. No model receives the text; only a redacted record with bounded provenance
persists. See spec sections 5, 12.
"""
import hashlib
import json
import re
import subprocess
import uuid as _uuid
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
SPEC = ROOT.parent / "spec"
DIRECTIONS = ROOT / "direction_record.jsonl"
MATCHER_VERSION = "matcher_v1.1"

_SCHEMA = json.loads((SPEC / "schemas" / "direction_record.schema.json").read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA)


def _sha(s):
    return hashlib.sha256(s.encode() if isinstance(s, str) else s).hexdigest()


# ---------------------------------------------------------------------------
# Transcript parsing + user/model separation
# ---------------------------------------------------------------------------

# Claude Code wraps slash-command scaffolding the user did not type; strip it so it
# can never be mistaken for authored direction.
_SCAFFOLD = re.compile(
    r"<(command-name|command-message|command-args|command-contents|local-command-stdout)>"
    r".*?</\1>",
    re.DOTALL,
)


def parse_transcript(path):
    """Return [(record_dict, raw_line_str)] preserving exact bytes for hashing.

    A torn final line (crash mid-append) is skipped, never fatal (spec section 14)."""
    out = []
    if path is None:
        return out
    text = Path(path).read_text() if not isinstance(path, (list, tuple)) else "\n".join(path)
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # partial/truncated line skipped
        out.append((rec, line))
    return out


def _authored_text(rec):
    """The human-typed text of a record, or None if it is not user-authored.

    User-authored := type=='user' AND isSidechain is not True AND message.content is a
    plain string (or text blocks) -- NOT a tool_result list, NOT an assistant record.
    Command scaffolding is stripped. Returns None for everything a model produced.
    """
    if rec.get("type") != "user":
        return None
    if rec.get("isSidechain") is True:
        return None
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        # a turn carrying any tool_result is a tool turn, not authored direction
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        text = " ".join(parts)
    else:
        return None
    text = _SCAFFOLD.sub("", text).strip()
    return text or None


def user_direction_records(records):
    """From parsed [(rec, raw)], keep only human-authored user turns with their text."""
    kept = []
    for rec, raw in records:
        text = _authored_text(rec)
        if text is not None:
            kept.append({"rec": rec, "raw": raw, "text": text})
    return kept


# ---------------------------------------------------------------------------
# Task -> direction association (capability-detected, fail closed) -- spec section 5
# ---------------------------------------------------------------------------

def select_window(records, stop_payload, user_prompt_submit=None):
    """Bind a bounded set of user records to THIS completed task.

    Preferred: prompt_id present on the Stop payload AND matched on transcript user
    records. Fallback A: a locally-captured UserPromptSubmit for the same session.
    Fallback B: the final top-level user turn (ancestry). Ambiguity -> (None, None).
    Returns (assoc, [authored_record_dicts]).
    """
    authored = user_direction_records(records)

    pid = stop_payload.get("prompt_id")
    if pid:
        window = [a for a in authored if a["rec"].get("promptId") == pid]
        if window:
            return "prompt_id", window
        # prompt_id given but nothing matches the transcript -> do NOT silently widen
        return None, None

    if user_prompt_submit and user_prompt_submit.get("session_id") == stop_payload.get("session_id"):
        ptext = _SCAFFOLD.sub("", user_prompt_submit.get("prompt_text", "")).strip()
        if ptext:
            synthetic = {
                "rec": {"type": "user", "isSidechain": False, "source": "UserPromptSubmit",
                        "sessionId": user_prompt_submit.get("session_id")},
                "raw": json.dumps(user_prompt_submit, sort_keys=True),
                "text": ptext,
            }
            return "paired", [synthetic]
        return None, None

    if authored:
        return "ancestry", [authored[-1]]  # bounded to the final top-level user turn
    return None, None


# ---------------------------------------------------------------------------
# Redaction (deterministic, runs BEFORE any persistence) -- spec sections 5, 12
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                              # AWS access key id
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                           # OpenAI-style key
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),                          # GitHub PAT
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),                  # Slack token
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),  # email
]


def redact(text):
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


# ---------------------------------------------------------------------------
# Direction record construction (schema-valid, bounded provenance)
# ---------------------------------------------------------------------------

def _provenance_records(window):
    recs = []
    for a in window:
        rec = a["rec"]
        ruuid = rec.get("uuid") or ("rec_" + _sha(a["raw"])[:16])
        recs.append({"record_uuid": ruuid, "record_sha256": _sha(a["raw"])})
    return recs


def build_direction_record(window, assoc, repo_id, session_id, ts,
                           matched_terms=None, matcher_version=MATCHER_VERSION):
    """Build a schema-valid direction_record from a bounded, user-authored window.

    Redaction runs before the excerpt is stored. Provenance hashes the EXACT selected
    records (per-record uuid + byte hash), never the whole transcript. Raises if the
    window is empty or the resulting record is invalid.
    """
    if not window:
        raise ValueError("no user-authored direction window")
    excerpt = redact(" ".join(a["text"] for a in window).strip())
    excerpt_sha = _sha(excerpt)
    direction_id = "d_" + _sha(f"{session_id}|{assoc}|{excerpt_sha}")[:16]
    rec = {
        "direction_id": direction_id,
        "session_id": session_id,
        "prompt_association": assoc,
        "repo_id": repo_id,
        "ts": int(ts),
        "redacted_excerpt": excerpt,
        "excerpt_sha256": excerpt_sha,
        "authorship": "user",
        "matcher_version": matcher_version,
        "provenance": {"records": _provenance_records(window)},
    }
    if matched_terms is not None:
        rec["matched_terms"] = matched_terms
    errs = [e.message for e in sorted(_VALIDATOR.iter_errors(rec), key=str)]
    if errs:
        raise ValueError("invalid direction_record: " + "; ".join(errs))
    return rec


def capture_direction(transcript, stop_payload, repo_id, ts,
                      user_prompt_submit=None, matched_terms=None):
    """End-to-end Phase-3 capture: parse -> select window -> build record, or None.

    Returns (assoc, direction_record) or (None, None) when no user direction can be
    bound to this task (fail closed)."""
    records = parse_transcript(transcript)
    assoc, window = select_window(records, stop_payload, user_prompt_submit)
    if not window:
        return None, None
    session_id = stop_payload.get("session_id", "")
    return assoc, build_direction_record(window, assoc, repo_id, session_id, ts,
                                         matched_terms=matched_terms)


# ---------------------------------------------------------------------------
# Trigger eligibility: a Stop is a "meaningful build" only on a real change
# ---------------------------------------------------------------------------

def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True)


def is_meaningful_build(cwd, checkpoint_head):
    """True iff the repo at cwd shows a relevant diff or a new commit since the
    session checkpoint (spec section 5). No change -> the Stop is ignored.

    checkpoint_head is None on the first Stop of a session (no baseline captured yet):
    fall back to "is the worktree dirty" rather than treating every Stop as meaningful.
    """
    head = _git(cwd, "rev-parse", "HEAD")
    if head.returncode != 0:
        return False
    dirty = bool(_git(cwd, "status", "--porcelain").stdout.strip())
    if checkpoint_head is None:
        return dirty
    if head.stdout.strip() != checkpoint_head:
        return True
    return dirty
