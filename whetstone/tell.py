"""Phase 6: the executable tell + discrimination protocol (spec section 10).

Standard: "the tell passed" must be as mechanically trustworthy as the repository
citation gate. A passing test is not a discriminating test. Two probe runs execute the
SAME test in an isolated throwaway sandbox (never the user's tree; in-memory doubles, so
no production credentials, network, or real sink by construction):

  baseline_or_mutated  -- the validator removed/bypassed -> MUST fail at the sink assertion
  fixed                -- the validator present          -> MUST pass

The tell is `discriminating` only if the baseline failed for the EXPECTED reason
(expected_sink_assertion, not an import/collection/setup error) and the fixed run passed,
with identical test source and environment across both runs. A test that passes in both
states is `vacuous` and the tell is rejected. A non-zero exit code alone never validates.
"""
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator

SPEC = Path(__file__).resolve().parent.parent / "spec"
_SCHEMA = json.loads((SPEC / "schemas" / "tell_record.schema.json").read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA)
_validate_tell = None


def _load_validate_tell():
    global _validate_tell
    if _validate_tell is None:
        spec = importlib.util.spec_from_file_location("whetstone_validate_tell",
                                                      SPEC / "validate_tell.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _validate_tell = mod.validate_tell
    return _validate_tell


SINK_ASSERTION_MARKERS = ("reached the sink", "malformed model output reached")


def _sha(s):
    return hashlib.sha256(s.encode() if isinstance(s, str) else s).hexdigest()


def _environment_sha256():
    return _sha(sys.version + "|" + platform.platform())


def _worktree_sha256(workdir):
    h = hashlib.sha256()
    for f in sorted(Path(workdir).rglob("*")):
        if f.is_file():
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def _classify(rc, out, err):
    """Return (collected, executed, outcome, failure_kind) from a pytest run."""
    combined = out + "\n" + err
    if rc == 0:
        return True, True, "passed", None
    if rc == 5:
        return False, False, "failed", "collection_error"        # no tests collected
    if rc == 2 or "errors during collection" in combined or "ERROR " in combined:
        if "ModuleNotFoundError" in combined or "ImportError" in combined:
            return False, False, "failed", "import_error"
        return False, False, "failed", "collection_error"
    if rc == 1:
        if any(m in combined for m in SINK_ASSERTION_MARKERS):
            return True, True, "failed", "expected_sink_assertion"
        if "ModuleNotFoundError" in combined or "ImportError" in combined:
            return False, False, "failed", "import_error"
        return True, True, "failed", "other"
    return False, False, "failed", "other"


def run_probe(role, fixed_source, test_source):
    """Run the test once with `fixed.py` = fixed_source, in an isolated sandbox."""
    with tempfile.TemporaryDirectory(prefix="whetstone_probe_") as d:
        wd = Path(d)
        (wd / "fixed.py").write_text(fixed_source)
        (wd / "test_boundary.py").write_text(test_source)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "test_boundary.py", "-q",
             "-p", "no:cacheprovider", "--tb=short"],
            cwd=wd, capture_output=True, text=True,
        )
        collected, executed, outcome, fkind = _classify(proc.returncode, proc.stdout, proc.stderr)
        return {
            "role": role,
            "commit": "sandbox:" + _sha(fixed_source)[:12],
            "worktree_sha256": _worktree_sha256(wd),
            "selector_collected": collected,
            "selector_executed": executed,
            "outcome": outcome,
            "failure_kind": fkind,
            "failure_signature_sha256": _sha(proc.stdout + proc.stderr) if outcome == "failed" else None,
            "exit_code": proc.returncode,
            "stdout_sha256": _sha(proc.stdout),
            "stderr_sha256": _sha(proc.stderr),
            "test_file_sha256": _sha(test_source),
            "environment_sha256": _environment_sha256(),
        }


def register_tell(baseline_source, fixed_source, test_source, principle_id, repo_id,
                  mutation=None):
    """Run both probes and build a validated tell_record.

    Returns {discriminating, result, tell_record|None, reason}. The tell_record is None
    (and discriminating False) when a probe did not collect+execute -- such a probe cannot
    be encoded as a valid probe_run, so the tell is rejected rather than forced.
    """
    pb = run_probe("baseline_or_mutated", baseline_source, test_source)
    pf = run_probe("fixed", fixed_source, test_source)

    if not (pb["selector_collected"] and pb["selector_executed"]
            and pf["selector_collected"] and pf["selector_executed"]):
        return {"discriminating": False, "result": None, "tell_record": None,
                "reason": f"a probe did not collect+execute "
                          f"(baseline failure_kind={pb['failure_kind']})"}

    discriminating = (pb["outcome"] == "failed"
                      and pb["failure_kind"] == "expected_sink_assertion"
                      and pf["outcome"] == "passed")
    result = "discriminating" if discriminating else "vacuous"

    tell_record = {
        "tell_id": "t_" + uuid.uuid4().hex[:16],
        "principle_id": principle_id,
        "repo_id": repo_id,
        "test_command_argv": [sys.executable, "-m", "pytest", "test_boundary.py", "-q"],
        "probe_runs": [pb, pf],
        "mutation": mutation,
        "result": result,
    }
    errs = [e.message for e in sorted(_VALIDATOR.iter_errors(tell_record), key=str)]
    errs.extend(_load_validate_tell()(tell_record))
    if errs:
        return {"discriminating": False, "result": result, "tell_record": None,
                "reason": "tell_record invalid: " + "; ".join(errs)}
    return {"discriminating": discriminating, "result": result,
            "tell_record": tell_record, "reason": "ok"}


def mutation_block(fixed_source, baseline_source, path="fixed.py"):
    """Describe the validator-bypass mutation (fixed -> baseline) for the record."""
    return {
        "used": True,
        "target_evidence": {
            "path": path,
            "line_start": 1,
            "line_end": len(fixed_source.splitlines()),
            "file_sha256": _sha(fixed_source),
        },
        "mutation_diff_sha256": _sha(fixed_source + "\n->\n" + baseline_source),
    }
