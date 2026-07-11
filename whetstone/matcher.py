"""Phase 4: deterministic, local, fail-closed direction matcher (spec section 8).

Loads spec/matcher_v1.1.json directly. A model never sees the text. Anything outside
the frozen lexicon, or any ambiguity, fails closed (no direction leg).

Key correctness point (round-6 fix): affirmative controls phrased as prohibitions
('never allow ... to reach the db') satisfy the directive requirement and their spans
are removed BEFORE negation scanning, so they are not misread as negations.
"""
import json
import re
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent / "spec"
_CFG = json.loads((SPEC / "matcher_v1.1.json").read_text())
MATCHER_VERSION = _CFG["matcher_version"]

_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|`[^`]*`")
_WS = re.compile(r"\s+")
_LEADING_Q = re.compile(_CFG["question_markers"]["leading"])
_IMPERATIVE = [re.compile(p) for p in _CFG["imperative_patterns"]]
_NEGATION = [re.compile(p) for p in _CFG["negation_markers"]]
_SENT_SPLIT = re.compile(r"(?<=[.!?\n])")


def _normalize(text):
    text = text.lower()
    text = _QUOTED.sub(" ", text)          # drop quoted spans (example output, not instruction)
    return _WS.sub(" ", text).strip()


def _is_question(sentence):
    s = sentence.strip()
    return s.endswith("?") or bool(_LEADING_Q.match(s))


def _found(terms, text):
    return [t for t in terms if t in text]


def _evaluate_sentence(sentence):
    """Return matched-term dict if this sentence is a positive direction, else None."""
    is_q = _is_question(sentence)                      # classify BEFORE stripping delimiters
    s = sentence.strip().rstrip(".!?").strip()

    prohibitions = _found(_CFG["prohibition_directives"], s)
    s_noproh = s
    for p in prohibitions:
        s_noproh = s_noproh.replace(p, " ")            # remove before negation scan

    control = _found(_CFG["control_terms"], s)
    boundary = _found(_CFG["boundary_terms"], s)
    directive = _found(_CFG["directive_terms"], s)
    imperative = any(p.match(s) for p in _IMPERATIVE)
    directive_ok = bool(directive) or imperative or bool(prohibitions)
    negated = any(p.search(s_noproh) for p in _NEGATION)

    if control and boundary and directive_ok and not is_q and not negated:
        return {"control": control, "boundary": boundary,
                "directive": sorted(set(directive) | set(prohibitions))}
    return None


def match(text):
    """Match a direction. Returns {matched, matched_terms, excerpts, matcher_version}.

    Accept iff >=1 positive-direction sentence exists and no sentence conflicts. Fail
    closed on anything else.
    """
    norm = _normalize(text)
    sentences = [s for s in _SENT_SPLIT.split(norm) if s.strip()]
    hits, excerpts = [], []
    for sent in sentences:
        m = _evaluate_sentence(sent)
        if m:
            hits.append(m)
            excerpts.append(sent.strip())

    if not hits:
        return {"matched": False, "matched_terms": None, "excerpts": [],
                "matcher_version": MATCHER_VERSION}

    merged = {"control": [], "boundary": [], "directive": []}
    for h in hits:
        for k in merged:
            for v in h[k]:
                if v not in merged[k]:
                    merged[k].append(v)
    return {"matched": True, "matched_terms": merged, "excerpts": excerpts,
            "matcher_version": MATCHER_VERSION}
