"""The discriminating artifact tell: feed malformed model output, assert the sink is
not reached. This is the test the tell record registers (spec Section 10).

- Against fixed.py  -> PASSES (malformed output rejected before the INSERT).
- Against gap.py    -> FAILS at the expected sink assertion (write count != 0).

The failure on gap.py MUST be `expected_sink_assertion`, not an import/setup error.
No production credentials, no network, no real sink: the DB is an in-memory double and
the model client is a stub returning malformed output.
"""


class FakeModel:
    def chat_completions_create(self, prompt):
        return {"content": "this is not valid json"}   # malformed on purpose


class CountingDB:
    def __init__(self):
        self.writes = 0

    def execute(self, *args, **kwargs):
        self.writes += 1


def _run(handle):
    db = CountingDB()
    try:
        handle(FakeModel(), db)
    except Exception:
        pass                       # rejection is allowed; the assertion below is the tell
    return db.writes


def test_invalid_output_cannot_write():
    # imported by selector; swap the import target per probe run (gap vs fixed).
    from fixed import handle       # baseline_or_mutated probe points this at gap.handle
    assert _run(handle) == 0, "malformed model output reached the sink"
