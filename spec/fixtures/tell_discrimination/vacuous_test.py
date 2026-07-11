"""A VACUOUS test: it passes regardless of whether the validator exists, because it
never drives malformed model output through the boundary. The discrimination protocol
must REJECT a tell backed by this test (it passes in both mutated and un-mutated states).
"""


def test_looks_related_but_proves_nothing():
    # never constructs malformed output, never touches the sink
    assert 1 + 1 == 2
