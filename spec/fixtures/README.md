# Fixtures

Sanitized, checked-in fixtures the acceptance tests (spec §14) load directly. Expand each set during the phase that needs it; the samples here define the expected shape.

- `claude_stop/` — sanitized `Stop` hook payloads (with and without `prompt_id`, to exercise capability detection and the fallbacks). See spec §5.
- `claude_session_end/` — sanitized `SessionEnd` payloads (the secondary flush).
- `claude_user_prompt_submit/` — sanitized `UserPromptSubmit` captures (fallback A for task→direction association).
- `transcripts/` — tiny sanitized session JSONL transcripts: `user` (with `promptId`, `isSidechain`), `assistant`, tool-result turns — to prove user/model separation and the bounded direction window.
- `repo_identity/` — inputs/outputs for the `repo_id` algorithm: remote+root, no-remote, move, clone, second worktree.
- `structured_output_boundary/` — real code the detector runs against: an unvalidated boundary (`gap.py`), a validated one (`fixed.py`), and the discriminating test (`test_boundary.py`).
- `tell_discrimination/` — cases that prove the discrimination protocol (spec §10): a vacuous test that passes in both states, a baseline that fails from an import error (not the sink assertion), a genuine fail-before/pass-after pair, and an off-target mutation.

Secrets must never appear here; redaction fixtures use synthetic credential shapes only.
