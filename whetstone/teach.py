#!/usr/bin/env python3
"""Whetstone — teach a gap.

Turn a filter gap (a sharper current move you're not using) into a lesson that obeys the
teaching method — gate, analogy, command-altitude practice — and bank the command so it's
reusable. Reuses the teacher's method, Codex call, and command bank.

    python teach.py [top=1]     # teach the top N gaps from gaps.jsonl, bank the commands
"""
import json, re, sys, time
from pathlib import Path
import teacher  # reuse METHOD, call_codex, BANK, append_jsonl, read_jsonl

ROOT = Path(__file__).resolve().parent
GAPS = ROOT / "gaps.jsonl"


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
        "Output the direction on its own line EXACTLY as `DIRECTION: <exact copy-paste prompt for their agent>`.\n"
        "End with one final line `TELL: <how they know it worked>`.\n"
        "Plain, concrete, no filler. Markdown only. Do NOT edit files or run commands."
    )


def extract_direction(text):
    m = re.search(r'^DIRECTION:\s*(.+)$', text or "", re.M | re.I)
    return m.group(1).strip().strip('"“”') if m else ""


def teach_gap(gap, bank=True):
    lesson = teacher.call_codex(gap_prompt(gap))
    direction = extract_direction(lesson)
    if bank and direction:
        existing = {r.get("direction") for r in teacher.read_jsonl(teacher.BANK)}
        if direction not in existing:
            teacher.append_jsonl(teacher.BANK, {"ts": int(time.time()), "concept": gap.get("pattern", ""),
                                                "direction": direction, "source": "whet"})
    return {"lesson": lesson, "direction": direction}


def load_gaps():
    out = []
    if GAPS.exists():
        for ln in GAPS.read_text().splitlines():
            try: out.append(json.loads(ln))
            except Exception: pass
    return out


def main():
    gaps = load_gaps()
    if not gaps:
        print("no gaps — run filter.py first"); return
    top = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for g in gaps[:top]:
        r = teach_gap(g)
        print("=" * 72)
        print(r["lesson"])
        print()
    print(f"(banked {min(top, len(gaps))} command(s) — open the teacher to reuse them)")


if __name__ == "__main__":
    main()
