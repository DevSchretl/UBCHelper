"""Precompute a handful of full pipeline runs for the web demo.

Each cached run is a *real* run captured through `trace.collect()`, so replaying it drives
exactly the same frontend code as a live query — there is no second rendering path that can
drift. The cache buys three things:

  * a first-time visitor sees a complete agentic run instantly, with no wait and no spend;
  * when the daily budget is exhausted the demo degrades to these instead of going dark;
  * the questions are chosen to show what the corpus was *built* to be hard at — colliding
    calendar editions and cohort-split requirement pages, which naive top-k RAG confuses.

    python scripts/build_demo_cache.py               # writes web/cache/demo_runs.json
    python scripts/build_demo_cache.py --only b-sc-credits-2526

The output embeds calendar excerpt text, so it is gitignored and ships in the private
dataset repo alongside the index (see web/bootstrap.py).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import pipeline, trace  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent.parent / "web" / "cache" / "demo_runs.json"

# Curated to cover every interesting behaviour of the pipeline. `category` is what the UI
# prints on the chip; `route` is left to the router except where forcing it is the point.
QUESTIONS = [
    {
        "slug": "cpsc-221-prereqs",
        "question": "What are the prerequisites for CPSC 221?",
        "category": "course lookup",
    },
    {
        "slug": "academic-standing",
        "question": "What are the three levels of academic standing at UBC?",
        "category": "policy",
    },
    {
        "slug": "ba-cohort-comparison",
        "question": (
            "Compare the B.A. degree requirements for students who entered the program in "
            "2023/24 with those who entered in 2024/25 or later."
        ),
        "category": "multi-hop",
    },
    {
        "slug": "bcs-vs-bsc-admission",
        "question": (
            "How does admission to the Bachelor of Computer Science program differ from "
            "B.Sc. admission from secondary school?"
        ),
        "category": "multi-hop",
    },
    {
        "slug": "cpsc-313-chain",
        "question": (
            "I have finished CPSC 210. What else do I need to complete before I can take "
            "CPSC 313?"
        ),
        "category": "prereq chain",
    },
    {
        "slug": "bsc-credits-2526",
        "question": (
            "In the 2025/26 calendar, what is the minimum number of credits required for a "
            "B.Sc. degree?"
        ),
        "category": "edition collision",
    },
    {
        "slug": "bsc-credits-2627",
        "question": (
            "According to the current 2026/27 calendar, what is the minimum number of "
            "credits required for a B.Sc. degree?"
        ),
        "category": "edition collision",
    },
    {
        "slug": "ba-language-requirement",
        "question": (
            "Does a B.A. student who entered the program in 2024/25 or later have to "
            "complete a language requirement?"
        ),
        "category": "cohort collision",
    },
    {
        "slug": "cpsc-210-prereqs",
        "question": "What are the prerequisites for CPSC 210?",
        "category": "course lookup",
    },
    {
        "slug": "cpsc-110-credits",
        "question": "How many credits is CPSC 110 worth and what does it cover?",
        "category": "course lookup",
    },
    {
        "slug": "cpsc-313-prereqs",
        "question": "What are the prerequisites for CPSC 313?",
        "category": "course lookup",
    },
    {
        "slug": "math-200-prereqs",
        "question": "Which courses satisfy the prerequisite for MATH 200, Calculus III?",
        "category": "course lookup",
    },
    {
        "slug": "stat-200",
        "question": "What is STAT 200 about and what are its prerequisites?",
        "category": "course lookup",
    },
    {
        "slug": "cpsc-320-chain",
        "question": "What do I need to complete before I can take CPSC 320?",
        "category": "prereq chain",
    },
    {
        "slug": "cs-major-requirements",
        "question": (
            "What are the requirements for a Computer Science major in the Faculty of "
            "Science?"
        ),
        "category": "program",
    },
    {
        "slug": "cognitive-systems",
        "question": "What is the Cognitive Systems program and what does it require?",
        "category": "program",
    },
    {
        "slug": "intl-economics",
        "question": "What are the requirements for the Bachelor of International Economics?",
        "category": "program",
    },
    {
        "slug": "media-studies",
        "question": "What does the Bachelor of Media Studies require?",
        "category": "program",
    },
    {
        "slug": "science-admission",
        "question": (
            "What are the admission requirements for the Faculty of Science from secondary "
            "school?"
        ),
        "category": "admission",
    },
    {
        "slug": "academic-probation",
        "question": "What happens to a student placed on academic probation at UBC?",
        "category": "policy",
    },
    {
        "slug": "ba-2324-requirements",
        "question": (
            "What are the B.A. degree requirements for students who entered in 2023/24 or "
            "earlier?"
        ),
        "category": "cohort collision",
    },
    {
        "slug": "bsc-vs-ba",
        "question": "How do the B.Sc. and B.A. degree requirements at UBC differ?",
        "category": "multi-hop",
    },
    {
        "slug": "commerce-cohorts",
        "question": (
            "How do the Bachelor of Commerce degree requirements differ between student "
            "cohorts?"
        ),
        "category": "cohort collision",
    },
    {
        "slug": "forestry-cohorts",
        "question": (
            "Compare the B.Sc. Natural Resources requirements for students starting "
            "September 2024 with those who started earlier."
        ),
        "category": "cohort collision",
    },
]

# The static build publishes these runs in a PUBLIC repo, so the excerpt text they carry has
# to stay proportionate quotation rather than a corpus dump. Chunks run to CHUNK_MAX_CHARS
# (1800), so trimming to ~700 keeps every excerpt clearly recognisable and relevant — which is
# all the demo needs to show — while cutting what is republished to well under a percent of
# the corpus. Every excerpt still carries its title, breadcrumb, and a link to the live page.
DEFAULT_MAX_EXCERPT_CHARS = 700
DEFAULT_MAX_PROMPT_CHARS = 3000

_ELLIPSIS = "\n\n[... excerpt trimmed for the public demo — follow the source link for the full page ...]"
_PROMPT_ELLIPSIS = "\n\n[... prompt trimmed for the public demo ...]"


def _clip(text: str, limit: int, marker: str) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + marker


def trim_events(events: list[dict], excerpt_chars: int, prompt_chars: int) -> list[dict]:
    """Trim corpus text carried in a run's events, in place, and return them.

    Two places carry excerpt bodies: the document payloads on `results`/`retrieval_final`, and
    the fully-rendered user turn on `llm_call` (which embeds every excerpt verbatim). Both are
    trimmed, or trimming the first would accomplish nothing.
    """
    for event in events:
        if event["kind"] in ("results", "retrieval_final"):
            for doc in event.get("items", []):
                if doc.get("text"):
                    doc["text"] = _clip(doc["text"], excerpt_chars, _ELLIPSIS)
        elif event["kind"] == "llm_call" and event.get("user"):
            event["user"] = _clip(event["user"], prompt_chars, _PROMPT_ELLIPSIS)
    return events


def build_one(spec: dict, excerpt_chars: int, prompt_chars: int) -> dict:
    events: list[dict] = []
    started = time.perf_counter()
    with trace.collect(events.append):
        result = pipeline.answer(spec["question"], route=spec.get("route"))
    elapsed = round((time.perf_counter() - started) * 1000)
    trim_events(events, excerpt_chars, prompt_chars)

    return {
        "slug": spec["slug"],
        "question": spec["question"],
        "category": spec.get("category", ""),
        "mode": "hybrid_rerank",
        "forced_route": spec.get("route") or "auto",
        "route": result["route"],
        "answer": result["answer"],
        "excerpts": len(result["results"]),
        "ms": elapsed,
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="rebuild just this slug, keeping the rest of the cache")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--max-excerpt-chars", type=int, default=DEFAULT_MAX_EXCERPT_CHARS,
                        help=f"trim each excerpt body (default: {DEFAULT_MAX_EXCERPT_CHARS}; "
                             f"0 disables trimming — do not publish an untrimmed cache)")
    parser.add_argument("--max-prompt-chars", type=int, default=DEFAULT_MAX_PROMPT_CHARS)
    args = parser.parse_args()

    excerpt_chars = args.max_excerpt_chars or 10**9
    prompt_chars = args.max_prompt_chars or 10**9

    existing: dict[str, dict] = {}
    if args.out.exists():
        try:
            with open(args.out, "r", encoding="utf-8") as f:
                existing = {r["slug"]: r for r in json.load(f)["runs"]}
        except (OSError, KeyError, json.JSONDecodeError):
            pass

    todo = [q for q in QUESTIONS if not args.only or q["slug"] == args.only]
    if not todo:
        sys.exit(f"No question with slug {args.only!r}.")

    for i, spec in enumerate(todo, start=1):
        print(f"[{i}/{len(todo)}] {spec['slug']}: {spec['question'][:64]}...", flush=True)
        try:
            run = build_one(spec, excerpt_chars, prompt_chars)
        except Exception as exc:  # noqa: BLE001 - one bad question shouldn't lose the batch
            print(f"    FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        existing[run["slug"]] = run
        print(f"    route={run['route']} excerpts={run['excerpts']} "
              f"events={len(run['events'])} {run['ms']}ms", flush=True)

    # Preserve the curated order rather than whatever order the rebuild happened in.
    ordered = [existing[q["slug"]] for q in QUESTIONS if q["slug"] in existing]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "runs": ordered}, f, ensure_ascii=False)

    size_kb = args.out.stat().st_size / 1024
    print(f"\nWrote {len(ordered)} runs to {args.out} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
