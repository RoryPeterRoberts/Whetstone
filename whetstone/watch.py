#!/usr/bin/env python3
"""Whetstone — watch. Turn SOURCES.md into a live "what's now possible" feed.

Fetches the curated RSS/Atom sources (stdlib only, no deps) and writes frontier.jsonl:
recent frontier items — model releases, papers, techniques, benchmarks. filter.py reads
this so "current" is genuinely current, not the model's memory. Page-diff sources
(leaderboards) come later via the web-change-detector; this covers the RSS bulk.

    python watch.py [per_feed=6]
"""
import json, sys, time, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTIER = ROOT / "frontier.jsonl"
UA = "Mozilla/5.0 (Whetstone watcher)"

FEEDS = [
    ("Simon Willison",     "https://simonwillison.net/atom/everything/"),
    ("HF Daily Papers",    "https://papers.takara.ai/api/feed"),
    ("r/LocalLLaMA",       "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=day"),
    ("TLDR AI",            "https://tldr.tech/api/rss/ai"),
    ("Interconnects",      "https://www.interconnects.ai/feed"),
    ("Latent Space",       "https://www.latent.space/feed"),
    ("Ahead of AI",        "https://magazine.sebastianraschka.com/feed"),
    ("Hacker News (LLM)",  "https://hnrss.org/newest?q=LLM+OR+%22language+model%22"),
    ("arXiv cs.CL",        "https://rss.arxiv.org/rss/cs.CL"),
    ("llama.cpp releases", "https://github.com/ggml-org/llama.cpp/releases.atom"),
]


def _ns(tag):
    return tag.split('}', 1)[-1].lower()


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def parse(raw, per_feed):
    root = ET.fromstring(raw)
    items = []
    for el in root.iter():
        if _ns(el.tag) not in ("item", "entry"):
            continue
        f = {_ns(c.tag): c for c in el}
        title = " ".join(_text(f.get("title")).split())
        link = ""
        le = f.get("link")
        if le is not None:
            link = le.get("href") or _text(le)
        date = (_text(f.get("pubdate")) or _text(f.get("published"))
                or _text(f.get("updated")) or _text(f.get("date")))
        summ = _text(f.get("description")) or _text(f.get("summary")) or _text(f.get("content"))
        summ = " ".join(summ.split())[:300]
        if title:
            items.append({"title": title, "link": link, "date": date, "summary": summ})
        if len(items) >= per_feed:
            break
    return items


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    all_items, ok, fail = [], 0, 0
    for name, url in FEEDS:
        try:
            items = parse(fetch(url), per)
            for it in items:
                all_items.append({"ts": int(time.time()), "source": name, **it})
            print(f"  ok  {name}: {len(items)}")
            ok += 1
        except Exception as e:
            print(f"  --  {name}: {type(e).__name__}")
            fail += 1
    with open(FRONTIER, "w") as fh:
        for it in all_items:
            fh.write(json.dumps(it) + "\n")
    print(f"\nfrontier.jsonl: {len(all_items)} items from {ok}/{len(FEEDS)} feeds ({fail} failed)")


if __name__ == "__main__":
    main()
