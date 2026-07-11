#!/usr/bin/env python3
"""Adversarial schema + validator test suite — the Phase 1 gate.

Proves the JSON files ENFORCE the prose, not merely describe it:
  1. every schema strict-compiles under Draft 2020-12 (catches non-standard keywords);
  2. every valid/ instance is accepted by its schema AND its cross-field validator;
  3. every invalid/ instance is REJECTED by its schema or its cross-field validator.

Run:  python3 run_schema_tests.py    (exit 0 = all enforced; nonzero = a hole remains)
Requires: jsonschema.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.dirname(HERE)
SCHEMAS = os.path.join(SPEC, "schemas")
sys.path.insert(0, SPEC)
from validate_event import validate_event
from validate_tell import validate_tell
from jsonschema import Draft202012Validator

CROSS = {"event": validate_event, "tell": validate_tell}


def load(p):
    return json.load(open(p))


def schema_for(name):
    return Draft202012Validator(load(os.path.join(SCHEMAS, name + ".schema.json")))


def cross_errors(kind, inst):
    return CROSS[kind](inst) if kind else []


def main():
    fails = []

    # 1. strict compilation of every schema
    for f in sorted(os.listdir(SCHEMAS)):
        if f.endswith(".schema.json"):
            try:
                Draft202012Validator.check_schema(load(os.path.join(SCHEMAS, f)))
            except Exception as e:
                fails.append(f"SCHEMA DOES NOT COMPILE: {f}: {e}")

    man = load(os.path.join(HERE, "manifest.json"))

    # 2. valid instances must pass schema AND cross-validator
    for fname, schema, cross in man["valid"]:
        inst = load(os.path.join(HERE, "valid", fname))
        serrs = sorted(schema_for(schema).iter_errors(inst), key=str)
        cerrs = cross_errors(cross, inst)
        if serrs or cerrs:
            fails.append(f"VALID case rejected: {fname} :: schema={[e.message for e in serrs]} cross={cerrs}")

    # 3. invalid instances must be rejected by schema OR cross-validator
    for fname, schema, cross in man["invalid"]:
        inst = load(os.path.join(HERE, "invalid", fname))
        serrs = list(schema_for(schema).iter_errors(inst))
        cerrs = cross_errors(cross, inst)
        if not serrs and not cerrs:
            fails.append(f"INVALID case ACCEPTED (hole!): {fname}")

    total = 1 + len(man["valid"]) + len(man["invalid"])
    if fails:
        print(f"FAIL ({len(fails)} problem(s) of {total} checks):")
        for x in fails:
            print("  -", x)
        return 1
    print(f"OK: schemas strict-compile; {len(man['valid'])} valid accepted; {len(man['invalid'])} invalid rejected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
