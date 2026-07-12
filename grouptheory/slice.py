"""Whetstone-GT vertical slice: one directing principle, taught and verified-transferred
across two genuinely different group-theory problems, on the shared kernel ledger.

The principle (mirrors the concept paper's worked example, section 5):
    A bounded computational check over small cases is SUPPORT, not a theorem. Identify the
    load-bearing hypothesis and confirm it is load-bearing by weakening it and searching
    for a counterexample.

Problem 1 (taught): "groups of order p^2 are abelian" -- weakening p^2 to p^3 surfaces D4.
Problem 2 (transfer): "groups of order pq with p not dividing q-1 are cyclic" -- weakening
that arithmetic hypothesis surfaces S3. Reusing the SAME principle, unaided, on problem 2
is the transfer the kernel records as `transferred` (from one source identity to another).
"""
import hashlib

import search
from _kernel import events, transfer

PRINCIPLE_ID = "p_bounded_check_is_not_a_theorem"
PRINCIPLE_VERSION = 1
DETECTOR_VERSION = "gt-search-1"
PRINCIPLE_TEXT = (
    "A bounded computational check over small cases is support, not a theorem; identify the "
    "load-bearing hypothesis and confirm it by weakening it and searching for a counterexample.")


class Claim:
    def __init__(self, claim_id, statement, finding, family, hypothesis, conclusion, conclusion_name):
        self.claim_id = claim_id
        self.statement = statement
        self.finding = finding
        self.family = family
        self.hypothesis = hypothesis
        self.conclusion = conclusion
        self.conclusion_name = conclusion_name


def _h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def source_id(context_name):
    """Source identity for a research context (the math analogue of repo_id): different
    problems -> different ids, so reuse across them is a genuine cross-context transfer."""
    return "r_gt_" + _h(context_name)[:16]


# ---------------------------------------------------------------------------
# The four worked claims (all group-theoretically correct; checked by sympy)
# ---------------------------------------------------------------------------

CLAIM_P2 = Claim(
    "order_p2_abelian",
    "Every finite group of order p^2 (p prime) is abelian.",
    "The pattern 'small p^2-order groups are abelian' is being treated as settled without "
    "isolating why order p^2 (not merely 'small prime-power order') is what forces it.",
    search.order_p2_family, lambda G: int(G.order()) in (4, 9, 25), search.is_abelian, "abelian")

WEAKENED_P3 = Claim(
    "order_p3_abelian",
    "Every finite group of order p^3 is abelian.  [deliberately weakened -- FALSE]",
    "", search.order_8_family, lambda G: int(G.order()) == 8, search.is_abelian, "abelian")

CLAIM_PQ = Claim(
    "order_pq_cyclic",
    "Every group of order pq (p<q primes, p not dividing q-1) is cyclic.",
    "A different problem: the same instinct to promote a bounded check to a theorem, now "
    "about cyclicity of order-pq groups, without isolating the arithmetic hypothesis.",
    search.order_15_family, lambda G: int(G.order()) == 15, search.is_cyclic, "cyclic")

WEAKENED_PQ = Claim(
    "order_pq_cyclic_weak",
    "Every group of order pq is cyclic.  [hypothesis dropped -- FALSE]",
    "", search.order_6_family, lambda G: int(G.order()) == 6, search.is_cyclic, "cyclic")


# ---------------------------------------------------------------------------
# Deterministic direction matcher (the group-theory adapter's local matcher)
# ---------------------------------------------------------------------------

_CONTROL = ("counterexample", "weaken", "load-bearing", "load bearing")
_BOUNDARY = ("theorem", "hypothesis", "proof", "promote")


def match_direction(text):
    """Fail-closed: the lecturer's direction must express BOTH the counterexample/weaken
    control AND a theorem/hypothesis boundary to count as the principle's direction leg."""
    t = text.lower()
    return any(c in t for c in _CONTROL) and any(b in t for b in _BOUNDARY)


# ---------------------------------------------------------------------------
# Intervention card (concept paper, section 5, Step 6)
# ---------------------------------------------------------------------------

def intervention_card(claim, tell, direction_text):
    base_cex = tell["base"]["counterexample"]
    if base_cex is not None:
        state = f"REFUTED in its own family by {base_cex}"
    elif tell["discriminating"]:
        state = ("bounded-computational support over " + ", ".join(tell["base"]["checked"]) +
                 f"; hypothesis confirmed load-bearing ({tell['weakened']['counterexample']} on weakening). "
                 "Explicitly NOT promoted to a theorem.")
    else:
        state = "VACUOUS tell -- no strong claim earned"
    return {
        "finding": claim.finding,
        "direction": direction_text,
        "principle": PRINCIPLE_TEXT,
        "tell": tell["reason"],
        "state": state,
    }


# ---------------------------------------------------------------------------
# Lifecycle on the shared kernel ledger
# ---------------------------------------------------------------------------

def teach(claim, weakened, direction_text, context, session, path):
    """First encounter: detect the opportunity, register the discriminating tell, and (if
    the direction matches and the tell discriminates) accept the principle in this context."""
    tell = search.register_tell(claim, weakened)
    ctx = source_id(context)
    opp = "o_" + _h(context + claim.claim_id)[:16]
    finding = "f_" + _h(context + claim.claim_id)[:12]
    events.emit("opportunity_detected", PRINCIPLE_ID, PRINCIPLE_VERSION, ctx, "other", session,
                {"opportunity_id": opp, "repo_id": ctx, "diff_scope": claim.claim_id,
                 "detector_version": DETECTOR_VERSION}, detector_version=DETECTOR_VERSION, path=path)
    events.emit("proposed", PRINCIPLE_ID, PRINCIPLE_VERSION, ctx, "other", session,
                {"finding_id": finding, "classification": "confirmed"},
                detector_version=DETECTOR_VERSION, path=path)
    if match_direction(direction_text) and tell["discriminating"]:
        events.emit("accepted", PRINCIPLE_ID, PRINCIPLE_VERSION, ctx, "other", session,
                    {"finding_id": finding}, path=path)
    return {"context_id": ctx, "finding_id": finding, "tell": tell,
            "card": intervention_card(claim, tell, direction_text)}


def transfer_to(claim, weakened, direction_text, from_ctx_id, context, finding_id, session, path):
    """Later, a different problem: the lecturer reuses the principle. The kernel's own
    transfer decision table records the outcome (transferred iff both legs, cross-context)."""
    tell = search.register_tell(claim, weakened)
    to_ctx = source_id(context)
    opp = "o_" + _h(context + claim.claim_id)[:16]
    matched = None
    if match_direction(direction_text):
        d_id = "d_" + _h(context + direction_text)[:16]
        events.emit("recall_prompted", PRINCIPLE_ID, PRINCIPLE_VERSION, to_ctx, "other", session,
                    {"opportunity_id": opp}, path=path)
        events.emit("direction_recalled", PRINCIPLE_ID, PRINCIPLE_VERSION, to_ctx, "other", session,
                    {"opportunity_id": opp, "direction_id": d_id, "excerpt_sha256": _h(direction_text)},
                    path=path)
        matched = {"direction_id": d_id}
    tell_result = {"discriminating": tell["discriminating"],
                   "tell_record": {"tell_id": "t_" + _h(context + claim.claim_id)[:16]}}
    outcome, ev = transfer.verify_transfer(
        opportunity_id=opp, finding_id=finding_id, from_repo_id=from_ctx_id, to_repo_id=to_ctx,
        matched_direction=matched, tell_result=tell_result,
        principle_id=PRINCIPLE_ID, principle_version=PRINCIPLE_VERSION,
        session_id=session, host="other", path=path)
    return {"context_id": to_ctx, "outcome": outcome, "event": ev, "tell": tell,
            "card": intervention_card(claim, tell, direction_text)}
