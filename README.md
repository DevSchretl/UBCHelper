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
     See "The demo" below for how the Space is deployed. -->

# UBCHelper: RAG over the UBC Vancouver Academic Calendar

A retrieval-augmented **academic-calendar advisor**. Ask a question about UBC Vancouver
courses, programs, or policies → the system retrieves the relevant calendar excerpts from a
local index → an LLM writes a grounded answer that points you at the official calendar page.
Embeddings run on the **OpenAI API**, reranking on the **Cohere API**, and generation on
**Claude (Anthropic API)** by default, with an optional local generation backend via LM Studio.

Built on the same engine as [RAGChef](../RAGChef), pointed at a scraped calendar corpus
instead of a recipe CSV. No LangChain or LlamaIndex: hybrid dense + BM25 retrieval, RRF
fusion, hosted rerank, an adaptive router with a decompose→multi-hop→synthesize agent, and a
two-tier eval harness that also scores the router and the agent against the single-shot
baseline, all written out directly.

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
sub-questions → retrieve each → merge → synthesize one answer. The agent measurably beats
single-shot retrieval on multi-hop questions and measurably *loses* on edition collisions;
the router, as tuned, does not pay for itself. Numbers and the argument are under
[Evaluation](#evaluation).

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

[scripts/setup_space.py](scripts/setup_space.py) creates and configures the Space in one step:
it sets the API keys as Space secrets over the API, so they never pass through a command line,
and checks that the read token can actually see the private index before anything deploys.

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
| [eval/run_eval.py](eval/run_eval.py) | Tier 1 + Tier 2 over the single-shot path, by category, plus stage-1 shortlist recall. |
| [eval/run_ablation.py](eval/run_ablation.py) | RAG vs closed-book, both scored against the gold excerpt. |
| [eval/run_agent_eval.py](eval/run_agent_eval.py) | Router accuracy + agent vs single-shot vs a budget-matched control, through `pipeline.answer()`. |

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
to measure what retrieval is actually worth, over the 12 specific questions plus the four
broader ones in `eval/testset.general.json`.

Those two runners call `retrieve.retrieve()` directly, so neither touches the Phase-4 router
or agent. [eval/run_agent_eval.py](eval/run_agent_eval.py) is the one that does: it goes
through `pipeline.answer()` with the route **forced**, and runs three arms over every
question — the shipped single-shot path, the agent, and a budget-matched control that
one-shot-retrieves as deep as the agent's merge. Every comparative metric is scored at the
same depth `k` on all three, because the agent returns up to 12 excerpts and the simple path
returns 4; scoring it deeper would be a gift rather than a comparison.

```powershell
# Generate candidate questions from the indexed corpus, then CURATE BY HAND:
python -m eval.make_testset --num 20   # writes eval/testset.candidates.json, not the curated set

# The before/after retrieval sweep (fast, deterministic):
$env:UBCAL_RETRIEVAL_MODE="dense";         python -m eval.run_eval --retrieval-only --name baseline-dense
$env:UBCAL_RETRIEVAL_MODE="hybrid";        python -m eval.run_eval --retrieval-only --name hybrid
$env:UBCAL_RETRIEVAL_MODE="hybrid_rerank"; python -m eval.run_eval --retrieval-only --name hybrid-rerank

# Full judged run + ablation (judge defaults to a local LM Studio model, see UBCAL_JUDGE_MODEL):
python -m eval.run_eval --name full
python -m eval.run_ablation --name rag-vs-norag

# Router + agent, three arms through the real pipeline (~18 min, ~$0.28 on a paid key):
python -m eval.run_agent_eval --selftest                      # pure helpers, no network
python -m eval.run_agent_eval --limit 3 --mode dense --no-judge   # cheap iteration loop
python -m eval.run_agent_eval --name agent-v1 --router-votes 3 --pace 10
```

Two levers make the agent eval cheap while iterating: `--mode dense` or `--mode hybrid`
makes **no Cohere calls at all** (the `shortlist` trace event only fires in `hybrid_rerank`),
and `--no-judge` drops the local judge, which is what actually dominates wall clock. `--pace`
spaces the questions out — one agent-eval question makes up to five rerank calls and a Cohere
trial key allows ten a minute, so an unpaced run can walk into
[src/rerank.py](src/rerank.py)'s 90 s backoff. Never run two evals at once.

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
| hybrid, no rerank (20-wide stage 1) | 0.667 / 0.625 / 0.542 | 0.667 / 0.583 / 0.444 |
| hybrid + rerank (20-wide stage 1) | 0.667 / 0.625 / 0.542 | 0.667 / 0.625 / 0.542 |
| hybrid, no rerank (50-wide stage 1) | — | 0.667 / 0.583 / 0.472 |
| hybrid + rerank (50-wide stage 1) | 0.833 / 0.750 / 0.653 | **0.833 / 0.708 / 0.667** |

(hit@4 / recall@4 / MRR. Bottom right is the current default. The 50-wide no-rerank cell is
the control that isolates the reranker at the shipped configuration; the 3,770-chunk half
would need an index rebuild to measure and has not been run.)

Three things worth reading off that table. The bigger corpus costs stage-1 ranking real ground
(hybrid recall 0.625 → 0.583, MRR 0.542 → 0.444) and the reranker absorbs all of it, which is
the first time reranking has measurably earned its place here: at 3,770 chunks hybrid and
hybrid + rerank scored identically.

Second, **widening stage 1 does almost nothing on its own.** Going 20-wide → 50-wide without
the reranker leaves recall flat (0.583 either way) and moves MRR by 0.028. The same widening
*with* the reranker is worth 0.625 → 0.708 recall and 0.542 → 0.667 MRR. So the win belongs
to the pair, not to the wider shortlist — the reranker was starved of candidates, not the
retriever.

Third, that mechanism is now **measured rather than inferred**. The judged run scores the
stage-1 shortlist itself before the reranker reorders anything: **recall@20 = 0.750,
recall@50 = 0.917.** The 0.167 gap is precisely the recall a 20-wide stage 1 never showed the
reranker. It also exposes the current ceiling — a 0.917 shortlist yields a 0.708 final
recall@4, so the rerank-and-cut-to-4 step still discards about a fifth of the recall already
in hand. Twelve questions is a small sample, so treat the ordering as real and the decimals
as noisy.

Per category, at the current default (`eval/reports/report.md`):

| category | n | hit@4 | recall@4 | MRR |
|---|---|---|---|---|
| code-lookup | 5 | 0.800 | 0.700 | 0.800 |
| collision | 3 | 1.000 | 1.000 | 0.667 |
| multi-hop | 3 | 0.667 | 0.333 | 0.333 |
| policy | 1 | 1.000 | 1.000 | 1.000 |

Collisions are solved; multi-hop is where single-shot retrieval falls over, which is what the
agent is for — see below.

### Tier 2: judged generation, and what retrieval is worth

Judged run over the 12 specific questions at the current corpus and default retrieval
(`--name full-16576`, judge `google/gemma-4-e4b` via LM Studio, zero parse failures):

| metric | score |
|---|---|
| faithfulness | 0.903 |
| answer relevancy | 0.774 |
| context precision | 0.859 |
| context recall | 0.792 |
| **hallucination rate** (1 − faithfulness) | **0.097** |

The ablation answers all 16 questions a second time closed-book and scores both arms against
the **gold** excerpt, so the two are directly comparable:

| set | n | RAG groundedness | no-RAG groundedness | RAG halluc. | no-RAG halluc. |
|---|---|---|---|---|---|
| overall | 16 | 0.700 | 0.332 | 0.300 | 0.668 |
| specific | 12 | 0.764 | 0.335 | 0.236 | 0.665 |
| general | 4 | 0.510 | 0.324 | 0.490 | 0.676 |

Retrieval roughly halves the hallucination rate on specific-source questions (0.665 → 0.236).
On the four broad questions it helps far less (0.676 → 0.490), which is the expected shape:
a closed-book model can make a reasonable attempt at "what is academic standing", and the
groundedness judge marks a plausible-but-different answer unsupported either way.

### Does the router and the agent earn their keep?

Three arms over all 16 questions, every metric at k=4 (`eval/reports/agent.md`):

| arm | hit@4 | recall@4 | MRR | groundedness |
|---|---|---|---|---|
| `simple` (shipped single-shot) | 0.750 | 0.656 | 0.552 | 0.602 |
| `simple_matched` (one-shot, agent's depth) | 0.750 | 0.656 | 0.552 | 0.717 |
| `agent` (decompose → multi-hop → merge) | **0.875** | **0.781** | **0.615** | **0.879** |

The control matters: `simple_matched` retrieves as deep as the agent's merge (5.19 excerpts on
average) and its retrieval metrics come out **identical** to the plain simple arm. So the
agent's +0.125 recall is not "it got more excerpts" — it is *which* excerpts it got.

But the attribution in [src/agent.py](src/agent.py) is only half right. `decompose` returned a
**single** sub-question on 11 of 16 items (mean 1.38), and it does not restate the question
verbatim — it rewrites it. On two of the three items where the agent found golds the simple
arm missed, that one-hop rewrite is the entire mechanism: "How many credits is CPSC 110 worth
and what does it cover?" became "CPSC 110 credit value and course description/content
coverage", which retrieved both golds where the original retrieved none. Only `q006` won
through the documented round-robin merge — two cohort sub-questions, one gold from each hop,
interleaved into the top 4. Across the set, hops 2 and 3 first surfaced 4 golds. **A good part
of the "agent win" is query rewriting, not multi-hop retrieval.**

The agent also has a real failure mode: on **collision** questions it *loses* 0.333 recall and
0.389 MRR, because rewriting drops the disambiguating edition or cohort phrase. `q011` lost a
gold the simple arm had.

| bucket | n | Δ recall@4 | Δ MRR | Δ groundedness |
|---|---|---|---|---|
| overall | 16 | +0.125 | +0.062 | +0.277 |
| multi-hop | 3 | +0.333 | +0.278 | +0.305 |
| code-lookup | 5 | +0.200 | +0.067 | +0.233 |
| collision | 3 | **−0.333** | **−0.389** | +0.250 |

The router classifies with accuracy **0.875** and stability 0.938 over three votes. It catches
every genuinely complex question (recall 1.000 on the `complex` class) but over-calls two
simple ones, so precision is 0.667. Accuracy flatters it: only 4 of 16 questions are complex,
so "always simple" scores 0.750.

What that routing is actually worth, scored from the arms above:

| policy | recall@4 | groundedness | LLM calls/q | est. cost |
|---|---|---|---|---|
| `always_simple` | 0.656 | 0.602 | 1.00 | $0.056 |
| `always_complex` | **0.781** | **0.879** | 2.00 | $0.092 |
| `router` (as shipped) | 0.656 | 0.743 | 1.38 | $0.077 |
| `oracle` (perfect routing) | 0.719 | 0.709 | 1.25 | $0.072 |

**The adaptive router does not currently pay for itself.** It lands on exactly
`always_simple`'s recall while spending 38% more LLM calls, because its two false-`complex`
calls give back what its correct ones gain. And `always_complex` beats even perfect routing,
since the agent also helps on questions a human would label simple. On this evidence the
cheapest real improvement is to drop the router and always take the complex path — or better,
to split `decompose`'s query rewriting from its multi-hop expansion and apply the rewriting
everywhere except collisions. Sixteen questions is a small sample and `decompose` is
nondeterministic (no temperature is sent to Anthropic), so a delta under 1/16 = 0.063 is not a
result; `eval/reports/agent.md` records every sub-question verbatim so two runs can be diffed.

Each test item carries `gold_keys`, not just positional `gold_ids`. A chunk's `id` is its
position in the index, so adding or dropping a single page renumbers everything after it;
`gold_keys` name the chunk by where it came from (edition, page, heading, ordinal) and
`eval/retrieval_metrics.py:resolve_gold_ids` maps them to current ids at load time. If a key
no longer resolves, the eval stops with an error instead of quietly scoring that question
zero, which would look exactly like a retrieval regression.

> **The calendar is authoritative and it changes.** Answers always carry the official calendar
> URL; verify anything that matters there. This is an educational project, not academic
> advising.
