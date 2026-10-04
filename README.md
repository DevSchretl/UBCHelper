---
title: UBC Calendar RAG
emoji: 🎓
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.26.0
app_file: app.py
python_version: "3.12"
short_description: Ask the UBC calendar, and watch the search work
pinned: false
---

<!-- The block above is Hugging Face Spaces configuration (GitHub renders it as a table).
     See "The demo" below, and DEPLOY.md for the deployment runbook. -->

# UBCHelper: RAG over the UBC Vancouver Academic Calendar

A retrieval-augmented **academic-calendar advisor**. Ask a question about UBC Vancouver
courses, programs, or policies → the system retrieves the relevant calendar excerpts from a
local index → an LLM writes a grounded answer that points you at the official calendar page.
Embeddings run on the **OpenAI API**, reranking on the **Cohere API**, and generation on
**Claude (Anthropic API)** by default, with an optional local generation backend via LM Studio.

Built on the same engine as [RAGChef](../RAGChef), pointed at a scraped calendar corpus
instead of a recipe CSV. No LangChain or LlamaIndex: hybrid dense + BM25 retrieval, RRF
fusion, hosted rerank, an adaptive router with a decompose→multi-hop→synthesize agent, and a
two-tier eval harness, all written out directly.

```
              ┌────────────────────────── run once ──────────────────────────────┐
  scrape.py ──►  data/pages/  ──►  chunk.py  ──►  ingest.py  ──►  index/ (numpy + json)
              └──────────────────────────────────────────────────────────────────┘

  "What are the prerequisites for CPSC 210?"
           │
           ▼
  retrieve.py ──┬─► dense - embed the query (OpenAI API), cosine search ─► ~50 ──┐
                └─► sparse - BM25 keyword search (src/bm25.py)          ─► ~50 ──┤
                                                                                 ▼
                    RRF fusion  ──►  rerank (Cohere API, src/rerank.py)  ──►  top-k
           │
           ▼
       generate.py ──► grounded prompt ──► Claude (Anthropic API) ──► answer + source URL
```

Complex questions can take the adaptive path instead (`ask.py --adaptive`): a router
classifies the question, and **complex** ones go through the agent: decompose into
sub-questions → retrieve each → merge → synthesize one answer.

---

## The corpus, and the traps built into it

`src/scrape.py` crawls the calendar into `data/pages/`. One JSON record per page, with
provenance (canonical URL, edition, fetch time, content hash). Two editions are collected:

- **live 2026/27** from `vancouver.calendar.ubc.ca`, discovered from the sitemap: every
  faculty, college and school, all campus-wide policies, and a course-description page for
  each of the 264 subjects.
- **archive 2025/26** from `archive.calendar.ubc.ca/vancouver/2526/...`: a narrow slice of the
  same subtrees, covering only the requirement-bearing pages where the editions collide.

That asymmetry is deliberate, and it gives the corpus two traps that naive top-k RAG walks
straight into. **Edition collisions**: near-identical pages that differ only in calendar year.
**Cohort splits**: B.A. requirements for students entering 2023/24-or-earlier read almost the
same as the 2024/25-or-later version. `src/chunk.py` folds the disambiguators into every
chunk's title and text (e.g. `Bachelor of Arts - Degree Requirements ... (2024/25 or later)
[2026/27]`) and carries them as structured metadata, so retrieval, prompts, and the eval can
all tell the twins apart.

**Scraping etiquette and Terms of Use:** the crawl honors robots.txt (10 s crawl delay), sends
a descriptive User-Agent, caches every page (re-runs use conditional GETs), and the scraped
content is **never committed or redistributed**. `data/pages/` is gitignored; only the scraper
and engine code live in the repo. Rebuild the corpus locally with:

```powershell
python -m src.scrape --dry-run    # enumerate in-scope URLs, fetch nothing
python -m src.scrape --sample     # just the 5 representative sample pages (quick start)
python -m src.scrape              # full in-scope crawl (slow by design: 10 s/request)
```

---

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env   # then edit .env
```

- `OPENAI_API_KEY`: **required**; embeddings run on OpenAI (`text-embedding-3-small`).
- `COHERE_API_KEY`: **required** for the default `hybrid_rerank` mode (`rerank-v3.5`).
  Not needed with `UBCAL_RETRIEVAL_MODE=dense` or `hybrid`.
- `ANTHROPIC_API_KEY`: **required** for the default generation backend (Claude Haiku 4.5).

> The embedding model used to **build** the index and the one used to **query** it must be
> the same, or retrieval is meaningless. Re-run ingest if you change `UBCAL_EMBED_MODEL`.

Optional local generation (embeddings/rerank stay hosted): start any OpenAI-compatible
server and set `UBCAL_LLM_BACKEND=local`, `UBCAL_BASE_URL_LLM`, `UBCAL_CHAT_MODEL`.

## Run it

```powershell
python -m src.ingest      # chunk + embed the cached pages -> index/
python ask.py "What are the prerequisites for CPSC 210?"
python ask.py --show-context "What is the academic standing policy?"
python ask.py --adaptive --trace "Compare the B.A. degree requirements for students who entered in 2023/24 vs 2024/25"
```

Example output:

```
Retrieved excerpts:
  [0.818] (id=8)   Computer Science, Faculty of Science [2026/27]
  [0.808] (id=179) Computer Science, Faculty of Science [2025/26]
  ...

Answer:
The prerequisites for CPSC 210 (Software Construction) are one of: CPSC 107 or CPSC 110.
For the current 2026/27 calendar see:
https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv
```

---

## The demo

A web UI that shows the work behind each answer: which route the router chose, how a complex
question got broken up, what dense and BM25 each put forward, which candidates survived RRF
fusion and reranking, and the exact prompt sent to the model at every step. A run is drawn as
four connected stages, Plan, Search, Rank and Answer, whose cards fill in live as the pipeline
moves. The Answer panel stays open during a run, and clicking a card opens that stage.

It ships in three forms from one codebase, because Hugging Face charges for Spaces that run
compute.

| Form | Entry point | Cost | Live questions |
|---|---|---|---|
| **Gradio Space** (published) | [app.py](app.py) | `cpu-basic` is free per hour, but creating the Space needs PRO | ✅ |
| **FastAPI** (local / self-host) | [web/app.py](web/app.py) | your API usage | ✅ |
| **Static Space** | [scripts/build_static_site.py](scripts/build_static_site.py) | free | ❌ saved runs only |

```powershell
pip install -r requirements.txt -r requirements-web.txt gradio

python app.py                              # Gradio: what the Space runs
uvicorn web.app:app --port 8000            # FastAPI: the SSE build

python scripts/build_demo_cache.py         # record runs (spends a little API credit)
python scripts/build_static_site.py        # build site/ for a static Space
python -m http.server -d site 8080         # preview it exactly as HF serves it
```

The three share everything that matters. `src/` is untouched by any of them, the panel styling
in [web/static/panels.css](web/static/panels.css) is common,
[web/static/stages.js](web/static/stages.js) handles moving between stages in all of them, and
the only difference is how trace events reach a screen: [web/render.py](web/render.py) builds
the HTML server-side for Gradio, while [web/static/app.js](web/static/app.js) builds the same
markup client-side from an SSE stream or from an embedded recording.

| File | Role |
|------|------|
| [app.py](app.py)                     | Gradio entry point, which is what the Hugging Face Space runs. |
| [web/render.py](web/render.py)       | Trace events → the stage cards and panels, server-side, for the Gradio build. |
| [web/app.py](web/app.py)             | FastAPI app: the page, the SSE endpoints, security headers. |
| [web/runner.py](web/runner.py)       | Runs the pipeline in a worker thread, streams its trace events as SSE. |
| [web/limits.py](web/limits.py)       | Per-IP rate limits + the global daily API budget (SQLite). |
| [web/replay.py](web/replay.py)       | Streams saved runs: same frames, zero cost. |
| [web/bootstrap.py](web/bootstrap.py) | Pulls the prebuilt index from a private dataset repo at startup. |
| [web/static/](web/static/)           | The single page: no framework, no build step. Branches on `window.DEMO_RUNS` to run with or without a backend. `stages.js` (which stage is open) is shared with the Space, and `gradio.css` holds the Space's own layout. |
| [scripts/build_demo_cache.py](scripts/build_demo_cache.py) | Records real pipeline runs as trace-event streams. |
| [scripts/build_static_site.py](scripts/build_static_site.py) | Bundles those runs + the page into `site/` for the static Space. |

**How the steps get out of the engine.** `pipeline.answer()` returns only
`{answer, results, route}`, and the sub-questions, candidate sets and RRF scores used to exist
only as `print()` side effects, so the web UI had nothing to show. Changing those return types
would have meant touching code the eval depends on, so [src/trace.py](src/trace.py) got a
second, independent consumer instead: `trace.collect(fn)` binds a per-request sink in a
`ContextVar`, and `trace.event()` records structured frames without printing. The CLI prints
without a sink; the server captures without printing. `ask.py --trace` output is byte-for-byte
unchanged.

**Cost and abuse controls (local / self-hosted mode).** Whenever the app is serving live
questions it is spending on three paid APIs, so the aim is that hitting a limit slows the demo
down rather than running up a bill:

- a **global daily ceiling on paid API calls**, counted from the event stream rather than
  estimated, since every call announces itself there. When it is reached, live querying stops
  and the UI falls back to the saved runs, so the site never goes dark.
- **per-IP sliding windows** (hour and day). Addresses are stored only as salted SHA-256, so
  the limiter recognises a repeat visitor while the demo keeps no PII.
- **one run at a time.** Cohere trial keys allow 10 rerank calls a minute and a single agentic
  run makes up to 3, so overlapping runs would trip the provider's limit, which shows up as a
  90 s stall rather than a clean error.
- question length capped and validated before any paid call. No user-controlled model, prompt,
  or sampling parameters, only a retrieval mode and route override from fixed enums.

The published static Space needs none of this, because it spends nothing.

**Publishing.** The calendar text is not ours to republish in bulk, and
`index/metadata.json` carries the full text of every chunk, which is why `index/`,
`data/pages/` and `web/cache/` are all gitignored. The static site ships **trimmed** excerpts
(~700 chars, from an 1,800-char chunk ceiling), each with its title, breadcrumb and a link to
the authoritative calendar page. `build_static_site.py` refuses to publish a cache that still
holds full-length excerpts.

For a self-hosted *live* deployment the [Dockerfile](Dockerfile) is ready, and
[scripts/publish_index.py](scripts/publish_index.py) pushes the index to a **private** HF
Dataset that the container pulls at startup. Pin the revision: chunk ids are positional, so a
re-ingest renumbers them all.

**[DEPLOY.md](DEPLOY.md) is the full runbook**, with the exact `hf` CLI commands, why the Space
is set up the way it is, and a troubleshooting table.

---

## The code

| File | Role |
|------|------|
| [src/config.py](src/config.py)     | Every tunable + path (env prefix `UBCAL_`). |
| [src/scrape.py](src/scrape.py)     | Polite sitemap-driven crawler → `data/pages/` + manifest. |
| [src/chunk.py](src/chunk.py)       | Page HTML → markdown-ish chunk records (tables kept whole, cohort/edition metadata parsed). |
| [src/ingest.py](src/ingest.py)     | Cached pages → chunks → embeddings → saved index. |
| [src/embed.py](src/embed.py)       | Shared embedding function (same model for index & query). |
| [src/retrieve.py](src/retrieve.py) | The funnel: dense + BM25 → RRF fuse → rerank → top-k (with ids). |
| [src/bm25.py](src/bm25.py)         | Hand-rolled BM25 Okapi keyword search (numpy). |
| [src/rerank.py](src/rerank.py)     | Reranker via Cohere's hosted rerank API. |
| [src/generate.py](src/generate.py) | Excerpts + question → grounded prompt → answer with source URLs. |
| [src/router.py](src/router.py)     | Classifies each question simple vs complex. |
| [src/agent.py](src/agent.py)       | Complex path: decompose → multi-hop retrieve → merge → synthesize. |
| [src/pipeline.py](src/pipeline.py) | The one adaptive entry point (`answer()`). |
| [ask.py](ask.py)                   | The CLI that wires it all together. |

Design notes carried over from RAGChef: brute-force cosine search on a numpy matrix instead
of a vector DB (transparent, and instant at this scale); BM25 built in memory from the indexed
metadata; hosted rerank so there is no local torch. New here: calendar pages are long and
heterogeneous, so unlike recipes they get **chunked**, split on headings, capped at
~`UBCAL_CHUNK_MAX_CHARS`, with requirement tables never split. BM25 matters even more in this
domain, because course codes ("CPSC 320", "BUCS") are exactly the rare, high-signal tokens
that dense embeddings under-weight.

```powershell
$env:UBCAL_RETRIEVAL_MODE = "dense"          # baseline (pure vector search)
$env:UBCAL_RETRIEVAL_MODE = "hybrid"         # dense + BM25, RRF-fused
$env:UBCAL_RETRIEVAL_MODE = "hybrid_rerank"  # + hosted rerank (the default)
```

## Evaluation

The two-tier harness scores the frozen test set through the same retrieve → generate
pipeline: **Tier 1** deterministic retrieval metrics (`hit@k`, `recall@k`, `MRR`:
[eval/retrieval_metrics.py](eval/retrieval_metrics.py)) and **Tier 2** RAGAS-style judged
metrics (faithfulness, answer relevancy, context precision/recall:
[eval/judge.py](eval/judge.py)); the headline number is hallucination rate = 1 − faithfulness.
[eval/run_ablation.py](eval/run_ablation.py) additionally answers every question closed-book
to measure what retrieval is actually worth.

```powershell
# Generate candidate questions from the indexed corpus, then CURATE BY HAND:
python -m eval.make_testset --num 20

# The before/after retrieval sweep (fast, deterministic):
$env:UBCAL_RETRIEVAL_MODE="dense";         python -m eval.run_eval --retrieval-only --name baseline-dense
$env:UBCAL_RETRIEVAL_MODE="hybrid";        python -m eval.run_eval --retrieval-only --name hybrid
$env:UBCAL_RETRIEVAL_MODE="hybrid_rerank"; python -m eval.run_eval --retrieval-only --name hybrid-rerank

# Full judged run + ablation (judge defaults to a local LM Studio model, see UBCAL_JUDGE_MODEL):
python -m eval.run_eval --name full
python -m eval.run_ablation --name rag-vs-norag
```

The test set targets three deliberately hard categories: **code-lookup** (hinges on a course
or program code, which is BM25's job), **multi-hop** (prerequisite and requirement chains
spanning pages, which is the reranker's and the agent's job), and **edition/cohort-collision**
(near-duplicate pages differing only by calendar year or student cohort, the trap this corpus
was built to test).

Results on the 12-question set at k=4, before and after the corpus grew from 3,770 to 16,576
chunks (full ledger in `eval/reports/history.csv`):

| retrieval | 3,770 chunks | 16,576 chunks |
|---|---|---|
| dense only | 0.500 / 0.458 / 0.403 | 0.500 / 0.458 / 0.417 |
| hybrid, no rerank | 0.667 / 0.625 / 0.542 | 0.667 / 0.583 / 0.444 |
| hybrid + rerank | 0.667 / 0.625 / 0.542 | 0.667 / 0.625 / 0.542 |
| hybrid + rerank, 50-wide stage 1 | 0.833 / 0.750 / 0.653 | **0.833 / 0.708 / 0.667** |

(hit@4 / recall@4 / MRR. Bottom right is the current default.)

Two things worth reading off that table. The bigger corpus costs stage-1 ranking real ground
(hybrid recall 0.625 → 0.583, MRR 0.542 → 0.444) and the reranker absorbs all of it, which is
the first time reranking has measurably earned its place here: at 3,770 chunks hybrid and
hybrid + rerank scored identically. And widening stage 1 from 20 to 50 candidates is worth more
than the corpus change either way, because the golds the reranker kept missing were sitting at
stage-1 ranks 20-50 where it never saw them. Twelve questions is a small sample, so treat the
ordering as real and the decimals as noisy.

Each test item carries `gold_keys`, not just positional `gold_ids`. A chunk's `id` is its
position in the index, so adding or dropping a single page renumbers everything after it;
`gold_keys` name the chunk by where it came from (edition, page, heading, ordinal) and
`eval/retrieval_metrics.py:resolve_gold_ids` maps them to current ids at load time. If a key
no longer resolves, the eval stops with an error instead of quietly scoring that question
zero, which would look exactly like a retrieval regression.

> **The calendar is authoritative and it changes.** Answers always carry the official calendar
> URL; verify anything that matters there. This is an educational project, not academic
> advising.
