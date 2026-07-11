"""Phase 6: the two-leg transfer verifier (spec section 11).

`transferred` is the only strong claim and it needs BOTH legs plus a cross-repo identity:
  direction leg  -- a user-authored direction, captured before agent expansion, matched;
  artifact leg   -- the executable tell is discriminating on a stable worktree.

Decision table (fail closed):
  both legs, different repo_id   -> transferred
  both legs, SAME repo_id        -> applied_again
  direction leg only             -> direction_recalled (no strong claim)
  artifact leg only              -> practice_present   (NOT human transfer)
  worktree changed mid-verify    -> none (nothing recorded)
"""
import events

PRINCIPLE_ID = "p_structured_output_boundary"
PRINCIPLE_VERSION = 1


_SETTLED = {"transferred", "applied_again", "deliberately_omitted", "already_known"}


def should_teach(repo_id, principle_id=PRINCIPLE_ID, path=events.EVENTS):
    """Teaching is suppressed once a principle is settled in a repo (spec section 14:
    transfer recorded -> teaching suppressed)."""
    proj = events.build_projections(path=path)
    disp = proj["per_repo_disposition"].get(repo_id, {}).get(principle_id)
    return not (disp and disp["kind"] in _SETTLED)


def verify_transfer(*, opportunity_id, finding_id, from_repo_id, to_repo_id,
                    matched_direction, tell_result, worktree_stable=True,
                    principle_id=PRINCIPLE_ID, principle_version=PRINCIPLE_VERSION,
                    session_id="s1", host="claude_code", path=events.EVENTS):
    """Return (outcome, event|None). Emits only the strong, tell-dependent claims
    (transferred / applied_again / practice_present); direction-only and fail-closed
    outcomes record no new event here."""
    if not worktree_stable:
        return "none", None  # spec section 11: worktree changed -> fail closed

    has_direction = matched_direction is not None
    tell = tell_result or {}
    discriminating = bool(tell.get("discriminating"))
    tell_id = (tell.get("tell_record") or {}).get("tell_id")
    same_repo = from_repo_id == to_repo_id

    if has_direction and discriminating:
        if same_repo:
            ev = events.emit("applied_again", principle_id, principle_version, to_repo_id,
                             host, session_id, {"finding_id": finding_id, "tell_id": tell_id},
                             path=path)
            return "applied_again", ev
        ev = events.emit("transferred", principle_id, principle_version, to_repo_id,
                         host, session_id,
                         {"opportunity_id": opportunity_id,
                          "direction_id": matched_direction["direction_id"],
                          "tell_id": tell_id,
                          "from_repo_id": from_repo_id, "to_repo_id": to_repo_id},
                         path=path)
        return "transferred", ev

    if has_direction and not discriminating:
        return "direction_recalled", None  # direction leg only; already recorded at recall

    if discriminating and not has_direction:
        ev = events.emit("practice_present", principle_id, principle_version, to_repo_id,
                         host, session_id, {"opportunity_id": opportunity_id, "tell_id": tell_id},
                         path=path)
        return "practice_present", ev

    return "none", None
