#!/usr/bin/env python3
"""TeachRoryLLMs — local teacher server (dynamic, self-improving).

Codex (bootstrap teacher) generates every reply live, obeying TEACHING_METHOD.md and DESIGN.md.
- Curiosity-driven: Rory leads; any selected span can be questioned.
- Harness-cored: each reply tagged spine or adventure.
- Self-improving: every interaction is logged; Rory flags walls; /improve reads the walls +
  history and distills concrete rules into LEARNED.md, which is injected into every future reply.
stdlib only — no new dependencies.
"""
import json, os, re, shutil, subprocess, sys, tempfile, threading, time, socketserver, http.server
from pathlib import Path

ROOT     = Path(__file__).resolve().parent
METHOD   = (ROOT / "TEACHING_METHOD.md").read_text()
PROFILE  = ROOT / "profile.json"
PAGE     = ROOT / "teacher.html"
LOG      = ROOT / "interactions.jsonl"
WALLS    = ROOT / "walls.jsonl"
LEARNED  = ROOT / "LEARNED.md"
BANK     = ROOT / "bank.jsonl"
REVIEWS  = ROOT / "reviews.jsonl"
PORT     = 8099
CODEX    = os.environ.get("CODEX_BIN") or shutil.which("codex") or os.path.expanduser("~/.local/bin/codex")
TAG_RE   = re.compile(r"<<\s*(spine|adventure)[^>]*>>\s*$", re.I)
WHET     = ROOT / "whet.py"
LEARN    = {"running": False, "lines": [], "repo": ""}


def _do_learn(repo, n, top):
    LEARN.update(running=True, lines=[f"learning {repo} …"], repo=repo)
    try:
        proc = subprocess.Popen([sys.executable, str(WHET), "learn", repo, str(n), str(top)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(ROOT), text=True)
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if line:
                LEARN["lines"].append(line)
        proc.wait()
    except Exception as e:
        LEARN["lines"].append(f"(error: {e})")
    finally:
        LEARN["running"] = False
        LEARN["lines"].append("✓ done — open the bank")


def load_profile():
    if PROFILE.exists():
        try: return json.loads(PROFILE.read_text())
        except Exception: pass
    return {"known": [], "asked": [], "served": []}


def save_profile(p):
    PROFILE.write_text(json.dumps(p, indent=2))


def append_jsonl(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def read_jsonl(path):
    if not path.exists():
        return []
    out = []
    for ln in path.read_text().splitlines():
        try: out.append(json.loads(ln))
        except Exception: pass
    return out


def parse_tag(s):
    m = TAG_RE.search(s or "")
    return m.group(1).lower() if m else None


def build_prompt(req):
    p         = load_profile()
    msgs      = req.get("messages") or []
    topic     = (req.get("concept") or "").strip()
    action    = req.get("action")
    selection = (req.get("selection") or "").strip()
    question  = (req.get("question") or "").strip()
    learned   = LEARNED.read_text().strip() if LEARNED.exists() else ""

    note = ""
    if p["known"]:
        note += f"\nRory already knows (do NOT re-teach): {', '.join(p['known'][:40])}."
    if p["asked"]:
        note += f"\nHe has asked to simplify these before (lead plainly): {', '.join(p['asked'][:40])}."

    transcript = "\n\n".join(
        ("RORY: " if m.get("role") == "you" else "TEACHER: ") + (m.get("content") or "")
        for m in msgs
    ) or "(no messages yet)"

    acts = {
        "simpler":    f'Rory selected "{selection}" and wants it SIMPLER. Explain just that in one plainer sentence (<25 words), concrete.',
        "deeper":     f'Rory selected "{selection}" and wants to go DEEPER — conceptually, only as far as harnessing needs, at COMMAND altitude (the plain direction he would give his agent + the tell to judge it, NOT code). <90 words. If this is theory not needed to harness LLMs, say so in the first line.',
        "challenge":  f'Rory challenges "{selection}": "{question or "is this right, and do I actually need it?"}". Answer straight and honest in <90 words. Concede if he is right.',
        "verify":     f'Rory wants to VERIFY "{selection}" — is it real and discussed? Name 2-3 concrete, well-known external sources with real URLs where he can check, and say plainly if it is niche or contested. Never invent a URL.',
        "framebreak": f'Give the FRAMEBREAK from "{selection}": the general principle and where else it points, <80 words.',
        "ask":        f'About "{selection}", Rory asks: "{question}". Answer straight and tight.',
        "explain":    f'Explain this banked command so Rory can trust and use it: "{selection}". Context: {question}. Give the LOGIC as a short chain — from a fact about his code, step by step, to why this is the right move, each step checkable — then one line on when to reach for it. Plain, command-altitude, no code.',
        "technical":  f'Rory wants "{selection}" MORE TECHNICAL — the mechanism underneath, still command-altitude (direct and judge, not code to hand-write). <90 words.',
        "context":    f'Rory wants MORE CONTEXT around "{selection}": where it comes from, why it matters, and the provenance/logic chain that makes it trustworthy. <110 words.',
        "high_orbit": f'Re-explain "{selection}" at HIGH ORBIT: ONE sentence — the capability and why it matters to him. Nothing else, no code.',
        "low_orbit":  f'Re-explain "{selection}" at LOW ORBIT: the shape of it in plain English — what it does and the core idea. No code. <40 words.',
        "helicopter": f'Re-explain "{selection}" at HELICOPTER: how it works — the moving parts and how they fit, conceptually. No code. <90 words.',
        "closeup":    f'Re-explain "{selection}" at CLOSE-UP: the approach a builder would take — the technique and key decisions, bridging toward code but not full code. <110 words.',
        "microscope": f'Re-explain "{selection}" at MICROSCOPE: show the ACTUAL code/diff for this, concretely. This is the one altitude where code IS the answer — show it, briefly labelled.',
    }
    act_line = acts.get(action, "") if (action and selection) else ""

    guide = (
        "GOAL (spine vs adventure): teach Rory to HARNESS LLMs for utility, not to study the field. "
        "Teach at the harnessing level. Deep theory is an 'adventure' — conceptual only, and only because his curiosity asked; "
        "if a thing is an adventure, say so plainly so he can choose. "
        "For a NEW concept: a Gate (why he needs it to harness LLMs, plain), then analogy <30 words, then practice <100 words. "
        "For follow-ups and actions: answer straight and tight — plain, concrete, honest, no filler, no flattery; a fresh analogy only if it compresses. "
        "He learns by DERIVING: where natural, ask him to predict or explain it back rather than telling him; affirm the true part, sharpen the imprecise part. "
        "If his own local model could simply DO the thing, say so instead of teaching mechanics. "
        "COMMAND ALTITUDE (critical): Rory COMMANDS a coding model (Claude Code / KERN) and NEVER writes code himself. Teach at his altitude — name the capability, when to reach for it, the plain-English DIRECTION he would give his agent — output that direction on its own line EXACTLY as `DIRECTION: <the exact copy-paste prompt for his agent>` so it is captured as a one-click reusable command — and the TELL (how he judges it worked). Do NOT present code/JSON/Python as the thing to learn; that is binary to him and his agent writes it. Only show a snippet if he explicitly asks, labelled 'what your agent produces', never something he must write. "
        "END your reply with a tag on its own final line: <<spine>> if it is core to harnessing LLMs, or <<adventure>> if it is deeper theory not needed to harness it."
    )

    learned_block = f"\n\n## Learned about this student — apply these:\n{learned}" if learned else ""
    body = act_line or "Reply as TEACHER to Rory's last message."
    return (
        f"{METHOD}{learned_block}\n\n---\nYou are the teacher, mid-conversation with Rory"
        + (f' about "{topic}"' if topic else "")
        + f". Obey the contract above EXACTLY.{note}\n\n{guide}\n\n"
        f"Conversation so far:\n{transcript}\n\n{body}\nMarkdown only. Do NOT edit files or run commands."
    )


def run_improve():
    walls = read_jsonl(WALLS)[-12:]
    inter = read_jsonl(LOG)[-40:]
    if not walls and not inter:
        return "_(nothing tracked yet — use it, flag the walls, then improve)_"
    prompt = (
        f"{METHOD}\n\n---\nYou are improving the teacher for ONE student (Rory), from real interaction data.\n\n"
        f"WALLS he flagged (the teaching failed him here):\n{json.dumps(walls)[:6000]}\n\n"
        f"RECENT INTERACTIONS:\n{json.dumps(inter)[:9000]}\n\n"
        "Find where the teaching failed him — the flagged walls, and patterns: repeated simplifies on one idea, "
        "challenges, abandoned threads, filler, or a missed analogy. Distill 1-5 CONCRETE rules to make the teacher "
        "better FOR HIM. Each rule: what went wrong -> what to do instead. Plain, specific, no filler. Markdown bullets only. "
        "Do NOT edit files or run commands."
    )
    rules = call_codex(prompt)
    with open(LEARNED, "a") as f:
        f.write(f"\n\n## Session {int(time.time())}\n{rules}\n")
    return rules


def call_codex(prompt):
    pf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    pf.write(prompt); pf.close()
    out = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False).name
    try:
        with open(pf.name) as stdin:
            subprocess.run([CODEX, "exec", "--skip-git-repo-check", "-o", out, "-"],
                           stdin=stdin, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           cwd=str(ROOT), timeout=240, check=True)
        return Path(out).read_text().strip() or "_(the teacher returned nothing — try again)_"
    finally:
        for x in (pf.name, out):
            try: os.unlink(x)
            except OSError: pass


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/profile":
            self._send(200, json.dumps(load_profile()))
        elif self.path == "/bank":
            seen, items = set(), []
            for r in reversed(read_jsonl(BANK)):
                d = (r.get("direction") or "").strip()
                if d and d not in seen:
                    seen.add(d); items.append(r)
            self._send(200, json.dumps(items))
        elif self.path == "/reviews":
            seen, items = set(), []
            for r in reversed(read_jsonl(REVIEWS)):
                k = (r.get("repo", ""), r.get("title", ""))
                if k not in seen:
                    seen.add(k); items.append(r)
            self._send(200, json.dumps(items))
        elif self.path == "/learn_status":
            self._send(200, json.dumps(LEARN))
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or "{}")
        except Exception:
            return self._send(400, json.dumps({"error": "bad json"}))

        if self.path == "/teach":
            try:
                lesson = call_codex(build_prompt(req))
            except subprocess.TimeoutExpired:
                return self._send(200, json.dumps({"lesson": "_(teacher timed out — try again)_"}))
            except Exception as e:
                return self._send(200, json.dumps({"lesson": f"_(error: {e})_"}))
            last_user = next((m.get("content") for m in reversed(req.get("messages") or [])
                              if m.get("role") == "you"), "")
            append_jsonl(LOG, {"ts": int(time.time()), "kind": req.get("action") or "ask",
                               "concept": req.get("concept", ""), "selection": req.get("selection", ""),
                               "user": last_user, "reply": lesson, "tag": parse_tag(lesson)})
            self._send(200, json.dumps({"lesson": lesson}))

        elif self.path == "/learn":
            repo = (req.get("repo") or "").strip()
            if not repo or LEARN["running"]:
                return self._send(200, json.dumps({"ok": False, "running": LEARN["running"]}))
            if not (Path(repo).exists() and (Path(repo) / ".git").exists()):
                return self._send(200, json.dumps({"ok": False, "error": "not a git repo path"}))
            threading.Thread(target=_do_learn, args=(repo, int(req.get("n", 14)), int(req.get("top", 3))), daemon=True).start()
            return self._send(200, json.dumps({"ok": True}))

        elif self.path == "/wall":
            append_jsonl(WALLS, {"ts": int(time.time()), "concept": req.get("concept", ""),
                                 "note": req.get("note", ""), "recent": (req.get("messages") or [])[-4:]})
            self._send(200, json.dumps({"ok": True}))

        elif self.path == "/improve":
            try:
                self._send(200, json.dumps({"rules": run_improve()}))
            except Exception as e:
                self._send(200, json.dumps({"rules": f"_(improve failed: {e})_"}))

        elif self.path == "/bank":
            d = (req.get("direction") or "").strip()
            if d:
                existing = {(r.get("direction") or "").strip() for r in read_jsonl(BANK)}
                if d not in existing:
                    append_jsonl(BANK, {"ts": int(time.time()), "concept": req.get("concept", ""), "direction": d})
            self._send(200, json.dumps({"ok": True}))

        elif self.path == "/review":
            entry = {"ts": int(time.time()), "repo": req.get("repo", ""), "title": req.get("title", ""),
                     "what": req.get("what", ""), "why": req.get("why", ""), "tell": req.get("tell", ""),
                     "files": req.get("files", ""), "direction": req.get("direction", "")}
            if entry["title"] or entry["what"]:
                append_jsonl(REVIEWS, entry)
            self._send(200, json.dumps({"ok": True}))

        elif self.path == "/profile":
            save_profile(req); self._send(200, json.dumps({"ok": True}))

        else:
            self._send(404, "{}")

    def log_message(self, *a):
        pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    print(f"TeachRoryLLMs teacher → http://localhost:{PORT}   (Ctrl-C to stop)")
    print(f"codex: {CODEX}")
    Server(("127.0.0.1", PORT), Handler).serve_forever()
