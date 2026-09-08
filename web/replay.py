"""Replay precomputed pipeline runs as a live-looking event stream.

Every cached run was produced by the real pipeline under `trace.collect()` (see
`scripts/build_demo_cache.py`), so replaying its frames drives exactly the same UI code as
a live run — there is no second rendering path to keep in sync.

This is what makes the demo safe to leave running unattended: first-time visitors get an
instant, zero-cost complex-route example, and when the daily budget is spent the site
degrades to these instead of going dark.
"""

from __future__ import annotations

import asyncio
import json

from .bootstrap import CACHE_PATH
from .runner import sse

# Small per-frame delay so the stepper animates rather than appearing all at once.
FRAME_DELAY = 0.06
STAGE_DELAY = 0.25

_runs: dict[str, dict] | None = None


def load() -> dict[str, dict]:
    """Cached runs keyed by slug. Missing or unreadable cache is not fatal."""
    global _runs
    if _runs is None:
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _runs = {run["slug"]: run for run in json.load(f)["runs"]}
        except (OSError, KeyError, json.JSONDecodeError):
            _runs = {}
    return _runs


def examples() -> list[dict]:
    """The curated question list for the UI's example chips."""
    return [
        {
            "slug": run["slug"],
            "question": run["question"],
            "category": run.get("category", ""),
            "route": run.get("route", ""),
            "cached": True,
        }
        for run in load().values()
    ]


async def stream(slug: str):
    """Yield the cached run's frames with human-paced delays."""
    run = load().get(slug)
    if run is None:
        yield sse("error", {"message": "That example is not available."})
        return

    yield sse(
        "accepted",
        {
            "question": run["question"],
            "mode": run.get("mode", "hybrid_rerank"),
            "route": run.get("forced_route", "auto"),
            "replay": True,
        },
    )
    for event in run["events"]:
        await asyncio.sleep(STAGE_DELAY if event["kind"] == "step" else FRAME_DELAY)
        yield sse(event["kind"], event)

    yield sse("answer", {"text": run["answer"], "route": run["route"]})
    yield sse(
        "done",
        {
            "route": run["route"],
            "excerpts": run.get("excerpts", 0),
            "ms": run.get("ms", 0),
            "replay": True,
        },
    )
