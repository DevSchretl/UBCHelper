# Deploying the demo to Hugging Face Spaces

## Which Space type, and why

Hugging Face bills Spaces that run compute, with one exception:

> Static Spaces are free for everyone. Gradio and Docker Spaces run on compute and require a
> paid plan to create: PRO for personal accounts… Free personal accounts in good standing can
> still host up to **2 Gradio Spaces running on ZeroGPU**.
> — [Spaces Overview](https://huggingface.co/docs/hub/spaces-overview)

**The ZeroGPU exception does not apply to this project — verified the hard way.** ZeroGPU
requires the Space to actually contain a GPU workload. Deployed without one, it builds, starts
cleanly, and is then killed:

    errorMessage: No @spaces.GPU function detected during startup

And an existing Gradio Space cannot simply be moved to free CPU hardware on a free account —
`request_space_hardware(space, "cpu-basic")` returns **402 Payment Required**. So for a
pipeline that is numpy plus three hosted APIs, with nothing to put on a GPU, the free Gradio
route is closed. Running this Space needs **HF PRO** ($9/mo), which unlocks creating compute
Spaces; `cpu-basic` hardware itself then costs nothing per hour.

(Adding a `@spaces.GPU` function that is never called would silence the check without
satisfying it. If you want ZeroGPU legitimately, give it real GPU work — swapping the hosted
Cohere reranker for a local cross-encoder would qualify, and would drop a paid dependency, at
the cost of adding torch and regenerating the eval numbers and recorded runs.)

Three deliverables exist in this repo; pick per your account:

| | Gradio Space (`app.py`) | Static Space (`scripts/build_static_site.py`) | Docker (`Dockerfile`) |
|---|---|---|---|
| Cost | HF PRO $9/mo | free | HF PRO $9/mo, or any host |
| Live arbitrary questions | ✅ | ❌ recorded runs only | ✅ |
| API keys | server-side secrets | none exist | server-side secrets |
| Section below | **1–5** | [Appendix A](#appendix-a--the-static-space) | [Appendix B](#appendix-b--self-hosting-with-docker) |

---

## 1. Prerequisites

An HF account with an active **PRO** subscription (see "Which Space type" above for why a free
account cannot run this one). Then two tokens from <https://huggingface.co/settings/tokens>:

| Token | Scope | Used by | Lives where |
|---|---|---|---|
| write | Write | you, locally, to create the Space and push | `hf auth login` |
| read | Read | the running Space, to pull the private index | Space secret `HF_TOKEN` |

Use two. The Space only reads the dataset; a write token there would let anyone who
compromises the container overwrite your repos, for no benefit.

```powershell
hf auth login
hf auth whoami        # this name is <you> below — probably not your GitHub username
```

## 2. Publish the index privately

`index/` is gitignored and must stay that way: `index/metadata.json` holds the full text of all
3,770 chunks, and UBC's Terms of Use don't permit republishing the calendar in bulk (the same
reason `data/pages/` is excluded). The Space pulls it at startup instead.

```powershell
python scripts/publish_index.py --repo <you>/ubchelper-index
```

Creates the dataset **private**, uploads `embeddings.npy` (22 MB) and `metadata.json` (6.7 MB),
and prints a commit sha. **Copy the sha** — pin it as `DEMO_INDEX_REVISION`. Chunk ids are
positional, so a later re-ingest renumbers everything and would silently invalidate the eval's
`gold_ids`.

## 3. Create the Space

Requires an active **HF PRO** subscription (<https://huggingface.co/subscribe/pro>).

```powershell
hf repos create <you>/ubc-calendar-rag --type space --sdk gradio --flavor cpu-basic --public
```

`cpu-basic` (2 vCPU / 16 GB) is the right size: the pipeline is network-bound and the whole
index is 29 MB, so paid hardware buys nothing. On PRO the hardware itself is free — the
subscription is what permits creating a compute Space at all.

If the Space already exists on the wrong hardware:

```powershell
hf spaces settings <you>/ubc-calendar-rag --hardware cpu-basic
hf spaces restart <you>/ubc-calendar-rag
```

## 4. Configure it

Variables (non-sensitive, visible in the UI) use `-e`; secrets use `-s`. Different flags on the
two commands:

```powershell
hf spaces variables add <you>/ubc-calendar-rag `
  -e DEMO_INDEX_REPO=<you>/ubchelper-index `
  -e DEMO_INDEX_REVISION=<sha from step 2> `
  -e DEMO_DAILY_LLM_CALLS=400 `
  -e DEMO_IP_PER_HOUR=6 `
  -e DEMO_IP_PER_DAY=20

# Generate a real salt — never ship the placeholder from .env.example
python -c "import secrets; print(secrets.token_urlsafe(32))"

hf spaces secrets add <you>/ubc-calendar-rag `
  -s OPENAI_API_KEY=sk-... `
  -s COHERE_API_KEY=... `
  -s ANTHROPIC_API_KEY=sk-ant-... `
  -s HF_TOKEN=hf_...              # the READ token `
  -s DEMO_IP_SALT=<generated salt>
```

`DEMO_IP_SALT` is not optional. IPs are stored as `sha256(salt + ip)`; with a known salt those
hashes are trivially brute-forced back to addresses, which defeats the point of hashing them.

Verify (names only — values are never echoed):

```powershell
hf spaces secrets ls <you>/ubc-calendar-rag
hf spaces variables ls <you>/ubc-calendar-rag
```

## 5. Push and verify

The Space is a second git remote alongside GitHub. `README.md` already carries the
`sdk: gradio` frontmatter it needs.

```powershell
git remote add hf https://huggingface.co/spaces/<you>/ubc-calendar-rag
git push hf main
```

Username at the prompt is your HF username, password is your **write token**.

`.gitignore` excludes `index/`, `data/`, `web/cache/`, `site/` and `.env`, so the push carries
source only — a few hundred KB.

```powershell
hf spaces logs <you>/ubc-calendar-rag --build     # image build
hf spaces logs <you>/ubc-calendar-rag             # runtime
```

A healthy startup logs exactly two lines from [app.py](app.py):

```
[demo] index pulled from <you>/ubchelper-index@<sha>
[demo] warm: 3770 chunks, mode=hybrid_rerank, model=claude-haiku-4-5
```

Then open the Space and click a "Try one" example. Startup work is ~2 s (index load + BM25
postings build) on top of the 29 MB download, so a cold start is on the order of half a minute.

**Changing a secret or variable requires a restart** — `hf spaces restart <you>/ubc-calendar-rag`.

---

## Operating it

| Task | Command |
|---|---|
| Tail logs | `hf spaces logs <you>/ubc-calendar-rag` |
| Restart (picks up secrets) | `hf spaces restart <you>/ubc-calendar-rag` |
| Pause | `hf spaces pause <you>/ubc-calendar-rag` |
| Ship a code change | `git push hf main` |
| Ship a new index | re-run `publish_index.py`, update `DEMO_INDEX_REVISION`, restart |

### Two limits to understand

**The budget counter resets on restart.** `DEMO_DB_PATH` defaults to `/tmp`, which is wiped
when the container restarts or wakes from sleep, so the daily cap is a **soft** ceiling. The
real fix is upstream: **set monthly spend caps in the Anthropic, OpenAI and Cohere billing
consoles.** Do that before making the Space public — it's the only limit a process restart
can't reset, and it's the one that protects your card.

**Free Spaces sleep after ~48 h idle** and wake on the next request. If a cold start matters
(a résumé link, say), a GitHub Actions cron keeps it warm for free:

```yaml
# .github/workflows/keep-warm.yml
name: keep demo warm
on:
  schedule: [{ cron: "0 */12 * * *" }]
  workflow_dispatch:
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl -sSf https://<you>-ubc-calendar-rag.hf.space/ > /dev/null
```

Two pings a day is a reasonable footprint. Don't ping every five minutes because you can.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Push rejected: `short_description length must be less than or equal to 60 characters` | A pre-receive hook validates the README frontmatter. Shorten the value (the limit is on the value, not the line). |
| Push rejected: `fetch first` / unrelated histories | `hf repos create` seeds the Space with its own root commit. `git fetch hf && git merge --allow-unrelated-histories hf/main`, keep your README on the conflict. Merging rather than force-pushing preserves HF's `.gitattributes` LFS rules. |
| Starts cleanly, then `No @spaces.GPU function detected during startup` | The Space is on ZeroGPU, which requires real GPU work. Move it to `cpu-basic` (needs PRO) — see "Which Space type" above. |
| `402 Payment Required` changing hardware | Free accounts cannot run Gradio Spaces on `cpu-basic`. Subscribe to PRO, or use the static Space in Appendix A. |
| `'charmap' codec can't encode` from `hf spaces logs` | A local Windows console issue with the progress-bar glyphs, not a Space error. Prefix with `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`. |
| Build fails on frontmatter | The YAML block must be the very first bytes of `README.md`, with `sdk: gradio` and `app_file: app.py` intact. |
| `RuntimeError: No index found` at startup | `DEMO_INDEX_REPO` unset/misspelled, or `HF_TOKEN` lacks read access to the *private* dataset. Check with `hf repos ls --type dataset`. |
| 401/403 pulling the dataset | The Space's `HF_TOKEN` is missing, expired, or predates the dataset. Re-issue a read token, re-add the secret, restart. |
| Gradio version mismatch on build | `sdk_version` in `README.md` must be a version HF serves. It is pinned to the one verified locally (6.26.0). |
| Every visitor shares one rate limit | `x-forwarded-for` isn't arriving. `app.py:_client_ip` reads the first hop; confirm traffic comes through the Space proxy. |
| Answers fail, retrieval works | Expired or unfunded `ANTHROPIC_API_KEY`. The real exception is in the runtime log; visitors see a generic message by design. |
| Panels render unstyled | `web/static/panels.css` didn't ship. It is loaded by `app.py` at import — confirm it's in the commit. |

---

## Appendix A — the static Space

Free, no ZeroGPU slot, no keys, but **recorded runs only** — a static Space serves files and
runs no Python server-side.

```powershell
python scripts/build_demo_cache.py       # record runs (spends a little API credit)
python scripts/build_static_site.py      # -> site/
python -m http.server -d site 8080       # preview exactly as HF serves it

hf repos create <you>/ubc-calendar-rag-static --type space --sdk static --public
cd site
git init -b main; git add -A; git commit -m "demo"
git remote add space https://huggingface.co/spaces/<you>/ubc-calendar-rag-static
git push -f space main
```

`build_static_site.py` preserves `site/.git`, so later updates are rebuild + commit + push. It
also **refuses to publish** a cache whose excerpts exceed 1,200 characters — the ~700-character
trim is what keeps republished calendar text proportionate in a public repo.

## Appendix B — self-hosting with Docker

[Dockerfile](Dockerfile) serves the FastAPI app in [web/](web/) — the original SSE frontend,
with live questions, per-IP limits and the budget cap. Use it on HF PRO
(`--sdk docker`), Fly.io (~$2–4/mo always-on), or any VPS.

```powershell
docker build -t ubchelper-demo .
docker run --rm -p 7860:7860 --env-file .env ubchelper-demo
```

Same environment variables as section 4, plus `DEMO_DEV=1` to enable `/docs`.
