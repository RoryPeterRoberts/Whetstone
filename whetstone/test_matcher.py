"""Phase 4 exit tests (matcher): deterministic, fail-closed, prohibition fix."""
import json

import matcher

CFG = json.loads((matcher.SPEC / "matcher_v1.1.json").read_text())


def test_frozen_pass_examples_match():
    for text in CFG["examples"]["pass"]:
        assert matcher.match(text)["matched"] is True, text


def test_frozen_fail_examples_do_not_match():
    for case in CFG["examples"]["fail"]:
        assert matcher.match(case["text"])["matched"] is False, case


def test_prohibition_directive_is_affirmative_not_negation():
    # round-6 fix: 'never allow' affirms the control; must not trip its own negation guard
    r = matcher.match("never allow unvalidated model output to reach the database write.")
    assert r["matched"] is True
    assert "never allow" in r["matched_terms"]["directive"]


def test_true_negation_still_fails_closed():
    # same control+boundary+directive but genuinely negated -> no direction leg
    assert matcher.match("don't validate output before the database write.")["matched"] is False


def test_question_fails_closed():
    assert matcher.match("should we validate output before the database write?")["matched"] is False


def test_incidental_statement_needs_a_directive():
    # control+boundary present but no directive/imperative -> not a direction
    assert matcher.match("schema validation exists before the database write.")["matched"] is False


def test_captured_direction_matches():
    # the exact user-authored direction from the transcript fixture
    text = "Validate model output against the schema and reject invalid results before writing to the database."
    r = matcher.match(text)
    assert r["matched"] is True
    assert r["matched_terms"]["control"] and r["matched_terms"]["boundary"]


def test_out_of_lexicon_fails_closed():
    assert matcher.match("please refactor the parser for readability.")["matched"] is False
