"""FIXED fixture: the same boundary, now schema-validated and reject-on-invalid.

The detector should NOT flag this (a validator sits on the model_call -> sink path).
The tell passes here: malformed model output is rejected before the sink.
"""


class InvalidModelOutput(Exception):
    pass


def _validate(raw):
    # stand-in for pydantic / jsonschema: require a JSON object with an "id"
    import json
    try:
        obj = json.loads(raw)
    except Exception:
        raise InvalidModelOutput("not JSON")
    if not isinstance(obj, dict) or "id" not in obj:
        raise InvalidModelOutput("missing required field 'id'")
    return obj


def handle(model_client, db):
    result = model_client.chat_completions_create(prompt="return a user record as JSON")
    record = _validate(result["content"])          # reject-on-invalid BEFORE the sink
    db.execute("INSERT INTO users (data) VALUES (?)", (record["id"],))
    return record
