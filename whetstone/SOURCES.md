# AI Source Watchlist — the "what's now possible" stream

The currency half of the teacher. Watchers scan these; the **filter** (recurring gap × your breadcrumbs)
culls them down to the one or two items that upgrade a move you already make often. Without the filter this
is just a second firehose — so the sources are deliberately **curated, not exhaustive** (~a dozen core, not 100).

Bias: **practitioner-distilled** (a human already did a curation pass) over raw firehoses. Frontier **and** local
(your 5090 arc). Command-altitude — sources that surface *new techniques and capability shifts a builder can use*,
not academic trivia.

Watch method key: **RSS** (feed) · **DIFF** (page-hash, no feed — reuse the web-change-detector) · **API**.
The watcher should **validate each feed on first add** (fail-fast if it 404s) — some feeds below are standard patterns, not individually hand-verified.

---

## Tier 1 — Core watchlist (start here: ~8, highest signal-per-token)

| Source | Watch | For | Cadence |
|---|---|---|---|
| **Simon Willison's Weblog** — `simonwillison.net` | RSS `https://simonwillison.net/atom/everything/` | The single best builder signal — annotates every real LLM development with *"what you can now do."* | ~daily |
| **Hugging Face Daily Papers** — `huggingface.co/papers` | RSS `https://papers.takara.ai/api/feed` (or self-host `github.com/capjamesg/hugging-face-papers-rss`) | New techniques, community-upvoted — the papers firehose already filtered. | daily |
| **r/LocalLLaMA** — `reddit.com/r/LocalLLaMA` | RSS `https://www.reddit.com/r/LocalLLaMA/top/.rss?t=day` | The pulse for local/open + 5090: new models, quantization, real benchmarks, hardware. | daily |
| **TLDR AI** — `tldr.tech/ai` | RSS `https://tldr.tech/api/rss/ai` | Densest daily triage — papers, repos, releases, least promotional. | daily |
| **Interconnects (Nathan Lambert)** — `interconnects.ai` | RSS `https://www.interconnects.ai/feed` | Compresses frontier-lab dynamics + post-training, applied. | ~weekly |
| **Latent Space (swyx)** — `latent.space` | RSS `https://www.latent.space/feed` | The AI-engineering discipline: agents, tooling, the layer between models and shipped products. | ~weekly |
| **Ahead of AI (Raschka)** — `magazine.sebastianraschka.com` | RSS `https://magazine.sebastianraschka.com/feed` | Deep, diagram-led LLM architecture + post-training; paper roundups. | ~monthly |
| **Capability ground-truth** — Artificial Analysis + Aider + SWE-bench | DIFF (see Benchmarks) | The hard "now possible" signal — what the best models can actually do this week. | weekly |

---

## Tier 2 — Depth by category

### Papers / new techniques
- **HF Daily Papers** — (Tier 1). The curated intake.
- **AINews / smol.ai** — `news.smol.ai` — summarizes subreddits + papers + Discords daily (swyx's team). RSS on site.
- **arXiv** cs.CL / cs.LG / cs.AI — RSS `https://rss.arxiv.org/rss/cs.CL` — firehose; **keyword-filter only** (LLM, agent, RAG, quantization, distillation…).
- **Lilian Weng** — `lilianweng.github.io` — deep technique explainers; rare, gold. RSS on site.

### Benchmarks / leaderboards (DIFF — the hard signal; no RSS, hash the table)
- **Artificial Analysis** — `artificialanalysis.ai` — intelligence index, speed, cost, one screen.
- **Aider Polyglot** — `aider.chat/docs/leaderboards` — practical multi-file coding (closest to how you build).
- **SWE-bench** — `swebench.com` — autonomous bug-fixing (you named this one).
- **LMArena** — `lmarena.ai/leaderboard` — human-preference A/B voting.
- **LiveCodeBench** — `livecodebench.github.io` · **llm-stats.com** — aggregates 300+ benchmarks in one place.

### Local / open models (the 5090 arc)
- **Ollama blog** — `ollama.com/blog` — new models, usually within days of open-weight release. RSS on site.
- **HF trending models** — `huggingface.co/models?sort=trending` — DIFF.
- **llama.cpp releases** — `github.com/ggml-org/llama.cpp/releases` — RSS `.../releases.atom` — engine features that unlock new models/quants.
- **vLLM releases** — `github.com/vllm-project/vllm/releases.atom` — serving/throughput.

### Official labs (DIFF, or their feed where it exists)
- **Anthropic** `anthropic.com/news` · **OpenAI** `openai.com/news` (RSS `openai.com/news/rss.xml`) · **Google DeepMind** `deepmind.google/discover/blog`
- Open-weight frontier you route to: **Qwen** `qwenlm.github.io/blog` · **DeepSeek** · **Z.ai/GLM** · **Moonshot/Kimi** · **Mistral** — DIFF each blog.

### Community / real-time keyword watch
- **Hacker News** keyword feed — `https://hnrss.org/newest?q=LLM` (one per term you care about) — breaking + the discussion that judges it.
- **GitHub Trending** (Python/AI) — via `mshibanami.github.io/GitHubTrendingRSS`.

---

## How it plugs in
1. **Watch** — reuse the web-change-detector: RSS where it exists, DIFF (page-hash) for leaderboards/lab blogs, `hnrss` for keywords.
2. **Filter** — cheap local pass on the 5090: does this item touch a pattern in your breadcrumbs, and is it *new to your scaffold*? Discard the rest, unread, guilt-free.
3. **Teach** — only survivors reach the expensive teacher: derive the principle, bank the command, anchor it to the real task it upgrades.

The list is the intake. The **filter is the value.** Adding more sources without a sharper filter just moves the firehose.
