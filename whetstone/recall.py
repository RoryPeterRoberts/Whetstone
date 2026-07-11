"""Phase 5: the recall interaction (spec sections 5, 11).

When an eligible opportunity appears in a later build, Whetstone prompts ONE recall at
command altitude (Direction / Principle / Tell, <30s, reveal always allowed) and records
the outcome from the user's own authored direction -- never a model's:

  matched user direction   -> direction_recalled
  answered but no match     -> recall_unmatched   (matcher_failed)
  no authored direction     -> recall_deferred     (no_response)

The strong `transferred` claim is NOT made here; that needs the executable tell (Phase 6).
"""
import events
import matcher

PRINCIPLE_ID = "p_structured_output_boundary"
PRINCIPLE_VERSION = 1

CARD = {
    "direction": ("require model output to be schema-validated and rejected before it "
                  "crosses a state boundary (db write, API response, file/subprocess)"),
    "principle": "constrain uncertainty at boundaries",
    "tell": "malformed model output cannot reach the sink",
}


def recall_prompt():
    """The three-line command-altitude card shown to the builder (no code)."""
    return (f"Direction: {CARD['direction']}\n"
            f"Principle: {CARD['principle']}\n"
            f"Tell: {CARD['tell']}")


def prompt_recall(opportunity_id, repo_id, session_id, host="claude_code",
                  risk_snapshot=None, path=events.EVENTS):
    """Record that a recall was surfaced for this opportunity. Returns the card text."""
    evidence = {"opportunity_id": opportunity_id}
    if risk_snapshot is not None:
        evidence["risk_snapshot"] = risk_snapshot
    events.emit("recall_prompted", PRINCIPLE_ID, PRINCIPLE_VERSION, repo_id, host,
                session_id, evidence, path=path)
    return recall_prompt()


def resolve_recall(opportunity_id, direction_record, repo_id, session_id,
                   host="claude_code", path=events.EVENTS):
    """Resolve a surfaced recall from the user's captured direction (or None).

    Returns (outcome, event). Emits exactly one of direction_recalled / recall_unmatched
    / recall_deferred. Only a user-authored, matched direction advances toward transfer.
    """
    if direction_record is None:
        ev = events.emit("recall_deferred", PRINCIPLE_ID, PRINCIPLE_VERSION, repo_id,
                         host, session_id,
                         {"opportunity_id": opportunity_id, "reason": "no_response"},
                         path=path)
        return "recall_deferred", ev

    # a direction leg only counts if authored by the user (Phase 3 guarantees this)
    assert direction_record.get("authorship") == "user"
    result = matcher.match(direction_record["redacted_excerpt"])
    if not result["matched"]:
        ev = events.emit("recall_unmatched", PRINCIPLE_ID, PRINCIPLE_VERSION, repo_id,
                         host, session_id,
                         {"opportunity_id": opportunity_id,
                          "direction_id": direction_record["direction_id"],
                          "reason": "matcher_failed"},
                         path=path)
        return "recall_unmatched", ev

    ev = events.emit("direction_recalled", PRINCIPLE_ID, PRINCIPLE_VERSION, repo_id,
                     host, session_id,
                     {"opportunity_id": opportunity_id,
                      "direction_id": direction_record["direction_id"],
                      "excerpt_sha256": direction_record["excerpt_sha256"]},
                     path=path)
    return "direction_recalled", ev
