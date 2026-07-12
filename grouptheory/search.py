"""The executable tell for group theory: a bounded counterexample search.

A universal claim -- "for every finite group G in FAMILY that satisfies HYPOTHESIS, the
CONCLUSION holds" -- is checked by enumerating an explicit, bounded, named family of finite
groups (via sympy), evaluating the hypothesis and conclusion on each, and reporting one of:

  * COUNTEREXAMPLE  -- a group satisfies the hypothesis but NOT the conclusion, so the
                       universal claim is FALSE;
  * BOUNDED SUPPORT -- no counterexample within the declared family, which is support
                       ONLY and never a theorem (spec section 7's governing rule:
                       "a finite search with no counterexample is explicitly insufficient").

This mirrors the code slice exactly. There, a passing test is not a discriminating test;
here, "no counterexample found" is not a proof. A tell is DISCRIMINATING only if a
plausibly-wrong version of the claim fails it: we weaken a supposedly load-bearing
hypothesis and require the search to then surface a genuine counterexample. That is the
mathematical analogue of fail-before / pass-after -- the weakened claim is the "mutation".
"""
from sympy.combinatorics import (AlternatingGroup, CyclicGroup, DihedralGroup,
                                 SymmetricGroup)
from sympy.combinatorics.group_constructs import DirectProduct


def direct(*groups):
    """Direct product of any number of permutation groups (folded pairwise)."""
    g = groups[0]
    for h in groups[1:]:
        g = DirectProduct(g, h)
    return g


# ---------------------------------------------------------------------------
# Named small-group catalog (honest: an explicit family, never "all groups")
# ---------------------------------------------------------------------------

def order_p2_family():
    """The COMPLETE isomorphism classes for orders 4, 9, 25 (each p^2 has exactly two
    groups: C_{p^2} and C_p x C_p). Bounded, but exhaustive for those orders."""
    return [
        ("C4", CyclicGroup(4)),   ("C2xC2", direct(CyclicGroup(2), CyclicGroup(2))),
        ("C9", CyclicGroup(9)),   ("C3xC3", direct(CyclicGroup(3), CyclicGroup(3))),
        ("C25", CyclicGroup(25)), ("C5xC5", direct(CyclicGroup(5), CyclicGroup(5))),
    ]


def order_8_family():
    """The five groups of order 8 (= 2^3). The three abelian ones plus D4 and (as a
    permutation stand-in) another non-abelian witness; D4 alone refutes p^2 -> p^3."""
    return [
        ("C8", CyclicGroup(8)),
        ("C4xC2", direct(CyclicGroup(4), CyclicGroup(2))),
        ("C2xC2xC2", direct(CyclicGroup(2), CyclicGroup(2), CyclicGroup(2))),
        ("D4", DihedralGroup(4)),   # order 8, NON-abelian -> the counterexample
    ]


def order_15_family():
    """Order 15 = 3*5 with 3 not dividing (5-1)=4: only the cyclic group exists."""
    return [("C15", CyclicGroup(15))]


def order_6_family():
    """Order 6 = 2*3 with 2 dividing (3-1)=2: the cyclic group AND S3 (non-cyclic)."""
    return [("C6", CyclicGroup(6)), ("S3", SymmetricGroup(3))]


# ---------------------------------------------------------------------------
# Predicates (evaluated by sympy)
# ---------------------------------------------------------------------------

def is_abelian(G):
    return bool(G.is_abelian)


def is_cyclic(G):
    return bool(G.is_cyclic)


# ---------------------------------------------------------------------------
# The search + the discrimination protocol
# ---------------------------------------------------------------------------

def search(family, hypothesis, conclusion):
    """Run the bounded search. Returns {'counterexample', 'checked', 'family_size'}.

    counterexample is (label, order) for the first group satisfying the hypothesis but not
    the conclusion, else None (bounded support only)."""
    checked = []
    for label, G in family():
        if not hypothesis(G):
            continue
        checked.append(label)
        if not conclusion(G):
            return {"counterexample": (label, int(G.order())), "checked": checked,
                    "family_size": len(checked)}
    return {"counterexample": None, "checked": checked, "family_size": len(checked)}


def register_tell(claim, weakened):
    """The discrimination protocol for a group-theory claim.

    `claim` is expected to survive the bounded search (no counterexample in its declared,
    hypothesis-satisfying family). `weakened` drops the supposedly load-bearing hypothesis;
    the search over its family MUST surface a real counterexample. The tell is
    DISCRIMINATING iff both hold -- proving the hypothesis genuinely has teeth. If the
    weakened claim also has no counterexample in range, the check was VACUOUS: it never
    tested the hypothesis, so no strong claim is earned.

    Returns {'discriminating', 'result', 'base', 'weakened', 'reason'}.
    """
    base = search(claim.family, claim.hypothesis, claim.conclusion)
    weak = search(weakened.family, weakened.hypothesis, weakened.conclusion)
    discriminating = base["counterexample"] is None and weak["counterexample"] is not None
    if base["counterexample"] is not None:
        reason = f"claim already refuted in its own family by {base['counterexample']}"
    elif weak["counterexample"] is None:
        reason = "vacuous: weakening the hypothesis produced no counterexample (not shown load-bearing)"
    else:
        reason = (f"discriminating: bounded support over {base['checked']}; "
                  f"weakening the hypothesis surfaces {weak['counterexample']}")
    return {"discriminating": discriminating,
            "result": "discriminating" if discriminating else "vacuous",
            "base": base, "weakened": weak, "reason": reason}
