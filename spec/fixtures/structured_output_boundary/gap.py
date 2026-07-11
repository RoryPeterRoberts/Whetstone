"""GAP fixture: model output crosses a state boundary with NO validation.

The detector (spec Section 7) should flag this intraprocedural pattern:
a model_call result reaches a sink (db write) with no validator between them.
The tell (spec Section 10) proves it: malformed output reaches the sink here.
"""


def handle(model_client, db):
    result = model_client.chat_completions_create(prompt="return a user record as JSON")
    record = result["content"]          # raw model output, unvalidated
    db.execute("INSERT INTO users (data) VALUES (?)", (record,))   # sink: reached unguarded
    return record
