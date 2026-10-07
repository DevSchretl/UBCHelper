"""Build the self-contained static site published to Hugging Face Spaces.

Hugging Face now bills Gradio and Docker Spaces (they run compute), while **static Spaces
stay free for everyone**. A static Space serves files and nothing else — no Python, no
server — so the published demo cannot run the pipeline live. What it can do is replay real
runs: `scripts/build_demo_cache.py` captures the engine's own trace events, and the same
frontend that renders a live SSE stream renders those frames identically.

That trade is better than it sounds. The security requirements that shaped `web/limits.py`
existed because the demo held API keys; a static build holds none, spends nothing, has
nothing to rate limit, and never sleeps. Only arbitrary questions are lost.

    python scripts/build_static_site.py            # -> site/
    cd site && git init -b main && git add -A && git commit -m "demo"
    git remote add space https://huggingface.co/spaces/<you>/ubc-calendar-rag
    git push -f space main

`site/` is generated output and is gitignored in this repo; it is its own git repo pushed to
the Space.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIC_SRC = ROOT / "web" / "static"
CACHE_PATH = ROOT / "web" / "cache" / "demo_runs.json"
DEFAULT_OUT = ROOT / "site"

# Space card. `sdk: static` is the free tier; `app_file` names the entry point.
README = """---
title: UBC Calendar RAG
emoji: 🎓
colorFrom: blue
colorTo: indigo
sdk: static
app_file: index.html
pinned: false
license: mit
---

# Ask the UBC Academic Calendar

A walkthrough of a retrieval-augmented question answering pipeline over the UBC Vancouver
Academic Calendar. It routes each question, breaks the hard ones into sub-questions, searches
with both vectors and keywords, fuses the two rankings, and reranks the shortlist.

Every run on this page was recorded from the real pipeline, step by step, so the routing
decisions, sub-questions, candidate rankings and prompts are what actually happened. The page
itself is static. It holds no API keys and calls no service, so it can only replay the {n}
questions that were recorded. Source and instructions for running it live:
<https://github.com/DevSchretl/UBCHelper>

Calendar excerpts are quoted with attribution and every result links to its official page at
<https://vancouver.calendar.ubc.ca>, which is always the official word. This is a student
project, not academic advising.
"""


def _chunk_count() -> int:
    """The indexed chunk count, read from the index rather than hardcoded.

    It is only shown in the page's status line, so a missing index degrades to 0 rather than
    failing the build. Reading it here keeps the published number from silently going stale
    every time the corpus is re-ingested.
    """
    if not config.METADATA_PATH.exists():
        print("  ! no index found; publishing chunk count as 0")
        return 0
    with open(config.METADATA_PATH, "r", encoding="utf-8") as f:
        return len(json.load(f))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cache", type=Path, default=CACHE_PATH)
    args = parser.parse_args()

    if not args.cache.exists():
        sys.exit(f"No demo cache at {args.cache}. Build it first:\n"
                 f"  python scripts/build_demo_cache.py")

    with open(args.cache, "r", encoding="utf-8") as f:
        cache = json.load(f)
    runs = cache.get("runs", [])
    if not runs:
        sys.exit("The demo cache has no runs in it.")

    # Refuse to publish a cache that still carries full-length excerpts. The static site goes
    # into a public repo, and the trimming in build_demo_cache.py is what keeps the amount of
    # republished calendar text proportionate.
    longest = max(
        (len(doc.get("text", ""))
         for run in runs for ev in run["events"]
         if ev["kind"] in ("results", "retrieval_final")
         for doc in ev.get("items", [])),
        default=0,
    )
    if longest > 1200:
        sys.exit(f"Cache holds untrimmed excerpts (longest {longest} chars). Rebuild with\n"
                 f"  python scripts/build_demo_cache.py\n"
                 f"so excerpt text stays proportionate before publishing it publicly.")

    out = args.out
    if out.exists():
        # Preserve the Space's git history if the directory is already a pushed repo.
        for item in out.iterdir():
            if item.name == ".git":
                continue
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    out.mkdir(parents=True, exist_ok=True)

    for name in ("index.html", "panels.css", "styles.css", "app.js", "stages.js"):
        shutil.copy2(STATIC_SRC / name, out / name)

    # The page loads assets from /static/* when FastAPI serves it; flatten those for a static
    # host, where everything sits beside index.html.
    html = (out / "index.html").read_text(encoding="utf-8")
    html = html.replace('href="/static/panels.css"', 'href="panels.css"')
    html = html.replace('href="/static/styles.css"', 'href="styles.css"')
    html = html.replace('src="/static/app.js"', 'src="app.js"')
    html = html.replace('src="/static/stages.js"', 'src="stages.js"')
    # runs.js must be evaluated before app.js, which branches on window.DEMO_RUNS at load.
    html = html.replace('<script src="app.js"></script>',
                        '<script src="runs.js"></script>\n<script src="app.js"></script>')
    (out / "index.html").write_text(html, encoding="utf-8")

    payload = {
        "built_at": cache.get("built_at", ""),
        "chunks": _chunk_count(),
        "retrieval_mode": config.RETRIEVAL_MODE,
        "model": config.ANTHROPIC_MODEL,
        "runs": runs,
    }
    # A plain assignment rather than JSON + fetch(): a file:// open of the built site works,
    # and there is no second request to fail on a cold CDN.
    (out / "runs.js").write_text(
        "window.DEMO_RUNS = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )

    (out / "README.md").write_text(README.format(n=len(runs)), encoding="utf-8")
    (out / ".gitattributes").write_text("*.js text eol=lf\n*.css text eol=lf\n*.html text eol=lf\n",
                                        encoding="utf-8")

    total_kb = sum(p.stat().st_size for p in out.iterdir() if p.is_file()) / 1024
    routes = {}
    for run in runs:
        routes[run["route"]] = routes.get(run["route"], 0) + 1

    print(f"Built {out}")
    for name in sorted(p.name for p in out.iterdir() if p.is_file()):
        print(f"  {name:16} {(out / name).stat().st_size / 1024:8.1f} KB")
    print(f"\n{len(runs)} runs ({', '.join(f'{v} {k}' for k, v in sorted(routes.items()))}), "
          f"{total_kb:.0f} KB total, longest excerpt {longest} chars")
    print(f"\nPreview locally:  python -m http.server -d {out} 8080")


if __name__ == "__main__":
    main()
