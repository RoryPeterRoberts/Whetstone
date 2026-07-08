#!/usr/bin/env python3
"""Whetstone — teach a gap.

Turn a filter gap into a lesson (gate, analogy, command-altitude practice) and bank a rich,
reusable entry: the command wrapped in an evaluate-first GATE, the transferable PRINCIPLE, the
project, the risk, and the provenance — so the bank is a learning surface, not a drawer of strings.
Also records taught gaps so the loop can later confirm they were applied (close-the-loop).
"""
import json, re, sys, time
from pathlib import Path
import teacher  # reuse METHOD, call_codex, BANK, append_jsonl, read_jsonl

ROOT = Path(__file__).resolve().parent
GAPS = ROOT / "gaps.jsonl"
TAUGHT = ROOT / "taught.jsonl"

GATE = ("Whetstone flagged this from my git history — verify before acting. Proposed change: {d} "
        "First, judge it against this actual codebase: is it a genuine, valuable enhancement here, or "
        "already handled / not applicable / risky? Give me your honest read. If you agree, show me the "
        "plan — don't edit yet. If you don't, tell me why.")


def gap_prompt(gap):
    return (
        f"{teacher.METHOD}\n\n---\n"
        "You are the teacher. Teach ONE thing: a sharper current move the builder is not yet using, "
        "found in their own real work. Obey the contract above EXACTLY.\n\n"
        f"They already do: {gap.get('pattern')}.\n"
        f"The sharper current move: {gap.get('current_move')}.\n"
        f"Why it beats theirs: {gap.get('why')}.\n\n"
        "Write the lesson, anchored to their real work:\n"
        "1. Gate — why they need this, plain (they hold the veto).\n"
        "2. Analogy — under 30 words.\n"
        "3. Practice — under 100 words, command-altitude: what to tell their coding agent, not code to write.\n"
        "Then three tagged lines at the very end, each starting at the start of its own line, "
        "with NO backticks, quotes, or bold around them:\n"
        "DIRECTION: <the exact copy-paste command for their agent>\n"
        "PRINCIPLE: <one line — the transferable rule behind this, that they could re-derive from>\n"
        "TELL: <how they know it worked>\n"
        "Plain, concrete, no filler. Markdown only. Do NOT edit files or run commands."
    )


def _line(text, key):
    # tolerate the model wrapping the tag line in backticks, bold, or blockquote markup
    m = re.search(rf'^[\s`*>_-]*{key}:\s*(.+)$', text or "", re.M | re.I)
    return m.group(1).strip().strip('`*"“” ') if m else ""


def teach_gap(gap, bank=True):
    lesson = teacher.call_codex(gap_prompt(gap))
    direction = _line(lesson, "DIRECTION")
    principle = _line(lesson, "PRINCIPLE")
    tell = _line(lesson, "TELL")
    entry = {
        "ts": int(time.time()), "project": gap.get("project", ""), "pattern": gap.get("pattern", ""),
        "concept": gap.get("pattern", ""), "risk": gap.get("risk", "quality"),
        "direction": direction, "gated": GATE.format(d=direction) if direction else "",
        "principle": principle, "tell": tell, "why": gap.get("why", ""),
        "current_move": gap.get("current_move", ""), "evidence": gap.get("evidence", ""), "source": "whet",
    }
    if bank and direction:
        existing = {r.get("direction") for r in teacher.read_jsonl(teacher.BANK)}
        if direction not in existing:
            teacher.append_jsonl(teacher.BANK, entry)
        teacher.append_jsonl(TAUGHT, {"ts": entry["ts"], "project": entry["project"],
                                      "pattern": entry["pattern"], "current_move": entry["current_move"],
                                      "status": "open"})
    return {"lesson": lesson, "direction": direction, "principle": principle}


def load_gaps():
    return teacher.read_jsonl(GAPS)


def close_loop(project):
    """Any gap previously taught for this project that the filter no longer flags = applied. Mark it done.
    Heuristic: relies on the gap dropping out of the fresh filter run for this project."""
    rows = teacher.read_jsonl(TAUGHT)
    open_here = {t["pattern"] for t in rows if t.get("project") == project and t.get("status") == "open"}
    current = {g.get("pattern") for g in load_gaps()}
    resolved = sorted(open_here - current)
    if resolved:
        for t in rows:
            if t.get("project") == project and t.get("pattern") in resolved and t.get("status") == "open":
                t["status"] = "done"; t["closed_ts"] = int(time.time())
        with open(TAUGHT, "w") as f:
            for t in rows:
                f.write(json.dumps(t) + "\n")
    return resolved


def main():
    gaps = load_gaps()
    if not gaps:
        print("no gaps — run filter.py first"); return
    top = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for g in gaps[:top]:
        r = teach_gap(g)
        print("=" * 72); print(r["lesson"]); print()
    print(f"(banked {min(top, len(gaps))} — open the teacher to explore them)")


if __name__ == "__main__":
    main()
