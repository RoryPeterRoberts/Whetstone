---
name: whetstone
description: Learn the recurring gap between how THIS repo is built and how the frontier now builds, then safely apply one improvement. A different model (Whetstone / Codex) finds the gap; you review it against the real code with an evaluate-first gate and never blind-implement — you plan, get approval, implement, verify. Use when the user runs /whetstone [repo], or asks to "level up" a repo, find what to improve, or apply a current best-practice to their code.
user-invocable: true
---

# Whetstone — improve a repo, safely

You find and apply the sharpest gap between how a repo is built and how the frontier now builds. But the point of this skill is the **safety**: a proposed change is reviewed against the real code before anything is touched, and you refuse changes you disagree with. **You are the gate.**

Whetstone (a separate tool using the builder’s authenticated Codex CLI and configured model) does the **finding**. You (the Claude Code agent) do the **reviewing and implementing**. That split is deliberate — you are judging *another model's* proposal, not your own, so your review has teeth.

## 0. Scope the target
- Target repo = the argument if given, else the current working directory.
- Confirm it is a git repo (`git -C <repo> rev-parse --is-inside-work-tree`). If not, say so and stop.
- `WHETSTONE_HOME` = `$WHETSTONE_HOME` if set, else `~/JOBS/Whetstone/whetstone`. `codex` must be on `PATH`.

## 1. Find the gaps (independent finder)
Run Whetstone’s pre-build loop on the repo (writes into `WHETSTONE_HOME`):
```
python3 "$WHETSTONE_HOME/whet.py" prepare <repo>
```
It refreshes the curated frontier first, reads the repo’s git history, infers the LLM-building patterns it uses, proposes gaps against the live frontier, then validates every proposal against the repo's current code. It writes the full classified audit to `findings.jsonl`; only `confirmed` and `partial` findings reach risk-ranked `gaps.jsonl` and receive a copy-paste DIRECTION.

If Whetstone is not installed or Codex is unavailable, **fall back to a native find**: read the repo's recent `git log` and its key files yourself and identify the single sharpest, nameable gap vs current best practice. Say plainly that you used the native fallback (no independent finder — your review is on your own suggestion, so weigh it harder).

## 2. Present the top gap with provenance
Read `$WHETSTONE_HOME/findings.jsonl` for the complete audit and `$WHETSTONE_HOME/gaps.jsonl` for validated teaching targets. Findings are ordered by evidence quality before risk and confidence. For the top gap, show the user plainly:
- the pattern (what the repo does now) and the git evidence it was found from,
- the sharper current move + why it beats the current one,
- its repository classification (`confirmed` or `partial`) and validation reason,
- every verified current-code file/line citation,
- whether its frontier evidence is grounded or unverified, with the real sources when grounded,
- the risk tag,
- **who found it** (Whetstone / Codex) — so it is clearly a proposal to check, not a fact.

Offer at most the top 1–3 validated targets. Never present `already-handled` or `insufficient-evidence` findings as changes to make; report them only when their audit context matters.

## 3. THE GATE — independently review before touching anything
Treat Whetstone's repository classification as evidence, not authority. Re-read the cited current code and search for counter-evidence. Then answer honestly, against specific files:
- Is this a genuine, valuable enhancement for THIS repo as it stands?
- Or is it already handled / not applicable here / risky / not worth the churn?

You are reviewing another model's suggestion — push back if it does not hold up. State your verdict and the reasoning.

**If you do not agree it is a real improvement for this repo, say why and STOP. Do not implement a change you disagree with.** That refusal is the skill working, not failing.

## 4. Plan — do not edit yet
If you agree it is worth doing:
- Write a concrete plan: the exact files you would touch, the change, what could break, and how you will verify it (use the DIRECTION's TELL).
- If the risk tag is money / data / production — or the code is clearly live — flag it and be conservative.
- Show the plan and get the user's explicit approval before editing.

## 5. Implement + verify
On approval:
- Make the change **surgically** — match the repo's existing style, touch only what the change needs, do not refactor adjacent code.
- Verify it: run the relevant test or the TELL. If it fails, fix or roll back; report honestly.

## 6. Bank the principle
State the one-line transferable **principle** behind the change (why it was right) — the durable takeaway that compounds, separate from the diff.

## Mode: `/whetstone review` — teach the builder what was done
Run this AFTER changes have been implemented (by `/whetstone` or any coding work the user directed). Its job: keep the user — who commands the coding agent but does not read code — current on what actually changed, taught at COMMAND ALTITUDE on the teacher UI.

1. Identify the change: the diff just applied — uncommitted changes (`git -C <repo> diff`) or the specific commit(s) the user names. Tie it back to the gap/direction it implemented, if there was one.
2. Write the review at command altitude — NOT a code walkthrough. For each distinct change, give:
   - **title** — the capability in a few words,
   - **what** — what the repo can now do that it couldn't, in plain English (no code),
   - **why** — the gap it closed / the reason,
   - **tell** — how the user would know it is working (the observable signal),
   - **files** — a short list of what was touched (orientation only, not the lesson).
   Translate the code UP to what the user can direct and judge. If you catch yourself pasting a diff, stop — that is the wrong altitude.
3. Push each change to the teacher UI:
   ```
   curl -s -X POST http://localhost:8099/review -H 'Content-Type: application/json' \
     -d '{"repo":"<repo>","title":"...","what":"...","why":"...","tell":"...","files":"..."}'
   ```
   If the teacher is not reachable, tell the user to start it (`python3 $WHETSTONE_HOME/teacher.py`) and re-run.
4. Tell the user it is on http://localhost:8099 under "what was built" — they can open any entry and dig in.

## Hard rules
- Never edit before **gate → plan → approval**.
- If you disagree with the proposed change, **refuse it with reasons**. Catching a bad or dangerous suggestion is the primary job of this skill.
- Smallest change that captures the improvement. No scope creep.
- You are the safety layer between a surfaced prompt and the repo. Act like it.
