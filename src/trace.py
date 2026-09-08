"""
Trace — optional, human-readable logging of every pipeline step and API prompt.

Off by default: `enable()` flips a module-global, so normal CLI runs and the eval loop stay
silent and behave exactly as before. When on (via `ask.py --trace`), each stage prints what
it is doing and the EXACT (system, user) prompt sent to the LLM, so the whole
route -> retrieve -> generate loop is visible for learning and debugging.

Output is plain ASCII to stdout so it renders in any terminal and interleaves in order with
the CLI's own prints.

There are two independent consumers of a trace, and they are deliberately decoupled:

  printing   the CLI's `--trace` flag; a process-wide `_enabled` flag, stdout, humans.
  capture    `collect()` binds a per-request sink so a caller (the web demo) receives the
             same stages as structured dicts. Never prints.

Neither gates the other: the CLI prints without a sink, the server captures without
printing. The sink lives in a ContextVar rather than a module global because the server
runs one pipeline per request in a worker thread — `run_in_threadpool` copies the calling
context into the thread, so each request's events stay bound to that request even when
several are in flight.
"""

from __future__ import annotations

import contextvars
import sys
from contextlib import contextmanager
from typing import Callable, Iterator

_enabled = False

# The per-request structured-event sink (None = nobody is capturing).
_sink: contextvars.ContextVar[Callable[[dict], None] | None] = contextvars.ContextVar(
    "trace_sink", default=None
)


@contextmanager
def collect(emit_fn: Callable[[dict], None]) -> Iterator[None]:
    """Send every trace event to `emit_fn` for the duration of the block.

    `emit_fn` receives one dict per event, always carrying a "kind" key. Restores the
    previous sink on exit, so nesting is safe.
    """
    token = _sink.set(emit_fn)
    try:
        yield
    finally:
        _sink.reset(token)


def event(kind: str, **payload) -> None:
    """Record one structured event. Never prints — the sink is the only consumer.

    A failing sink must never take the pipeline down with it: a dropped trace frame is a
    cosmetic loss, an exception here would cost the user their answer.
    """
    sink = _sink.get()
    if sink is None:
        return
    try:
        sink({"kind": kind, **payload})
    except Exception:
        pass


def enable() -> None:
    """Turn tracing on for the rest of this process."""
    global _enabled
    _enabled = True
    # Traces print full excerpt context and model replies, which often contain non-ASCII
    # (degree signs, fractions, accents). Switch stdout to UTF-8 so a cp1252 Windows console
    # doesn't raise UnicodeEncodeError; errors="replace" is a last-resort guard.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def enabled() -> bool:
    return _enabled


def step(title: str) -> None:
    """A top-level stage banner."""
    event("step", title=title)
    if _enabled:
        print(f"\n=== {title} ===")


def detail(label: str, value: object = "") -> None:
    """One indented `label: value` line (or just a label if value is empty)."""
    event("detail", label=label, value=str(value))
    if _enabled:
        print(f"    {label}: {value}" if value != "" else f"    {label}")


def results(items) -> None:
    """Print a list of retrieve.Result rows as [score] (id) title."""
    event("results", items=[describe(r) for r in items])
    if _enabled:
        for r in items:
            print(f"      [{r.score:.3f}] (id={r.id}) {r.recipe['title']}")


def prompt(system: str, user: str, model: str) -> None:
    """Show one LLM API call: the system prompt and the user turn sent to `model`."""
    if _enabled:
        print(f"    --- API call -> {model} ---")
        _block("SYSTEM", system)
        _block("USER", user)


def response(text: str) -> None:
    """Show the model's reply for the call printed by `prompt`."""
    if _enabled:
        _block("RESPONSE", text)


# Chunk metadata keys worth showing in a UI. `text` is carried separately (it is long) and
# the rest of the 19-key record is ingest bookkeeping the reader doesn't need.
_DOC_FIELDS = (
    "title", "section", "url", "edition_year", "source", "page_type",
    "faculty", "program", "specialization", "cohort_qualifier", "subject_code",
)


def describe(result) -> dict:
    """Flatten one retrieve.Result into a JSON-safe dict for the event stream."""
    chunk = result.recipe
    doc = {key: chunk.get(key) for key in _DOC_FIELDS}
    doc["id"] = result.id
    doc["score"] = round(float(result.score), 6)
    doc["text"] = chunk.get("text", "")
    return doc


def _block(label: str, text: str) -> None:
    print(f"    [{label}]")
    for line in (text.splitlines() or [""]):
        print(f"      {line}")
