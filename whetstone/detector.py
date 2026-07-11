"""Phase 4: structured-output boundary detector (spec section 7).

A bounded, intraprocedural heuristic: it flags where a model_call result reaches a
state-changing sink with NO validator between them, in the same function scope. It only
PROPOSES; the executable tell (section 10) proves. Full cross-procedure dataflow is out
of scope -> such cases are flagged at lower confidence, never promoted on the heuristic.
"""
import ast
import hashlib

DETECTOR_VERSION = "sob-1"

# Configurable signature lists (spec section 7). Matched by dotted-name suffix.
MODEL_CALL_SUFFIXES = (
    "chat_completions_create", "messages_create", "completions_create",
    "chat.completions.create", "messages.create", "completions.create",
    "responses.create", "generate", "infer",
)
SINK_SUFFIXES = (
    "execute", "executemany", "commit", "post", "put",
    "save", "write", "writerow", "writerows",
    "system", "run", "popen", "check_output", "check_call", "call",
)
# validator: explicit names, dotted signatures, or any callable whose leaf contains
# 'validate' (e.g. a local _validate). Deliberately excludes 'invalid'.
VALIDATOR_NAMES = {"model_validate", "model_validate_json", "typeadapter",
                   "parse_obj", "parse_raw"}
VALIDATOR_DOTTED = ("jsonschema.validate", "type_adapter", "typeadapter")


def _dotted(node):
    """Reconstruct a dotted call name from an ast Call.func (e.g. 'a.b.create')."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _leaf(name):
    return name.rsplit(".", 1)[-1] if name else ""


def _endswith_any(name, suffixes):
    return any(name == s or name.endswith("." + s) or name.endswith(s.replace(".", "_"))
               or _leaf(name) == _leaf(s) for s in suffixes)


def _is_model_call(name):
    return _endswith_any(name, MODEL_CALL_SUFFIXES)


def _is_sink(name):
    leaf = _leaf(name).lower()
    return leaf in {_leaf(s).lower() for s in SINK_SUFFIXES}


def _is_validator(name):
    leaf = _leaf(name).lower()
    if leaf in VALIDATOR_NAMES:
        return True
    if any(sig in name.lower() for sig in VALIDATOR_DOTTED):
        return True
    return "validate" in leaf   # local _validate / validate_output, not 'invalid'


def _calls(expr):
    for n in ast.walk(expr):
        if isinstance(n, ast.Call):
            yield n, _dotted(n.func)


def _names(expr):
    return {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)}


def _has_model_call(expr):
    return any(_is_model_call(name) for _, name in _calls(expr))


def _validator_over(expr, tainted):
    """True if a validator call in expr consumes a currently-tainted name."""
    for call, name in _calls(expr):
        if _is_validator(name) and (_names(call) & tainted):
            return True
    return False


def _iter_stmts(body):
    """Yield statements in source order, descending into compound-statement bodies
    (intraprocedural, condition-agnostic -- conservative for a heuristic)."""
    for stmt in body:
        yield stmt
        for field in ("body", "orelse", "finalbody"):
            inner = getattr(stmt, field, None)
            if isinstance(inner, list):
                yield from _iter_stmts(inner)
        for handler in getattr(stmt, "handlers", []) or []:
            yield from _iter_stmts(handler.body)


def _scan_function(func, source_lines):
    tainted = set()
    gaps = []
    for stmt in _iter_stmts(func.body):
        # 1. sinks first: does a tainted value reach a sink on this statement?
        for call, name in _calls(stmt if not isinstance(stmt, ast.Assign) else stmt.value):
            if _is_sink(name):
                arg_names = set()
                for a in call.args:
                    arg_names |= _names(a)
                for kw in call.keywords:
                    arg_names |= _names(kw.value)
                reached = arg_names & tainted
                direct = _has_model_call(call) and not _validator_over(call, tainted | arg_names)
                if reached or direct:
                    gaps.append({
                        "lineno": call.lineno,
                        "sink": name,
                        "confidence": "confirmed" if reached else "partial",
                        "snippet": source_lines[call.lineno - 1].strip()
                        if call.lineno - 1 < len(source_lines) else "",
                    })
        # 2. then update taint from assignments
        if isinstance(stmt, ast.Assign):
            targets = set()
            for t in stmt.targets:
                targets |= _names(t)
            val = stmt.value
            if _validator_over(val, tainted):
                tainted -= targets                      # validated -> clean
            elif _has_model_call(val):
                tainted |= targets                      # raw model output -> tainted
            elif _names(val) & tainted:
                tainted |= targets                      # derived from tainted, unvalidated
            else:
                tainted -= targets                      # reassigned to something clean
    return gaps


def detect_gaps(source):
    """Return a list of boundary gaps found in Python source (empty if none)."""
    tree = ast.parse(source)
    lines = source.splitlines()
    gaps = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            gaps.extend(_scan_function(node, lines))
    return gaps


def detect_opportunity(source, repo_id, diff_scope="added"):
    """An eligible later opportunity for p_structured_output_boundary (spec section 9):
    a model_call->sink gap present in a diff-scoped region with no validator equivalent.
    Returns an opportunity dict or None (exclusion: a validator already on the path)."""
    gaps = detect_gaps(source)
    if not gaps:
        return None
    confidence = "confirmed" if any(g["confidence"] == "confirmed" for g in gaps) else "partial"
    oid = "o_" + hashlib.sha256(f"{repo_id}|{diff_scope}|{source}".encode()).hexdigest()[:16]
    return {
        "opportunity_id": oid,
        "repo_id": repo_id,
        "detector_version": DETECTOR_VERSION,
        "diff_scope": diff_scope,
        "confidence": confidence,
        "gaps": gaps,
    }
