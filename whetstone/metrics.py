"""Phase 8: pilot instrumentation -- metrics computed FROM the event ledger (spec section 15).

The ledger IS the exportable instrumentation. These are the pilot metrics; the crucial
denominator rule (Rory's): the transfer denominator is lessons for which a genuinely
comparable later opportunity occurred (a recall was prompted) -- NOT total lessons.

Attention-time and per-intervention model cost need capture fields the slice deliberately
did not add (the slice is deterministic -- no model -- so model cost is 0); those surface
as null/0 with a note rather than a fabricated number.
"""
from collections import Counter, defaultdict

import events


def _rate(n, d):
    return (n / d) if d else None


def compute_metrics(path=events.EVENTS):
    evs = events.load_events(path)
    c = Counter(e["kind"] for e in evs)

    proposed = c["proposed"]
    accepted = c["accepted"]
    rejected = c["rejected"]
    already_handled = c["already_handled"]
    already_known = c["already_known"]
    applied = c["applied"]
    recall_prompted = c["recall_prompted"]
    direction_recalled = c["direction_recalled"]
    transferred = c["transferred"]

    # a surfaced finding the user actually judged (real gap vs not)
    judged = accepted + rejected + already_handled + already_known
    comparable_later = recall_prompted  # denominator: only lessons with a comparable later opportunity

    # recurrence: a principle whose opportunity appears in more than one repo_id
    repos_by_principle = defaultdict(set)
    for e in evs:
        if e["kind"] == "opportunity_detected":
            repos_by_principle[e["principle_id"]].add(e["repo_id"])
    principles_with_opp = len(repos_by_principle)
    recurring = sum(1 for r in repos_by_principle.values() if len(r) > 1)

    total_model_cost = 0.0  # slice is deterministic (no model in the transfer path)

    return {
        "counts": dict(c),
        "findings_proposed": proposed,
        "acceptance_rate": _rate(accepted, proposed),
        "top_finding_precision": _rate(accepted, judged),
        "false_positive_rate": _rate(rejected + already_handled, proposed),
        "application_rate": _rate(applied, accepted),
        "recurrence_rate": _rate(recurring, principles_with_opp),
        "prompted_recall_rate": _rate(direction_recalled, recall_prompted),
        "unaided_transfer_count": transferred,
        "unaided_transfer_rate": _rate(transferred, comparable_later),
        "comparable_later_opportunities": comparable_later,
        "cost_per_transferred_principle": _rate(total_model_cost, transferred),
        "median_attention_seconds": None,
        "notes": ("attention-time and per-intervention model cost need instrumentation "
                  "fields deferred past the slice; the slice is deterministic (model cost 0)."),
    }
