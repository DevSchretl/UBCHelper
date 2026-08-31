"""
Trace — optional, human-readable logging of every pipeline step and API prompt.

Off by default: `enable()` flips a module-global, so normal CLI runs and the eval loop stay
silent and behave exactly as before. When on (via `ask.py --trace`), each stage prints what
it is doing and the EXACT (system, user) prompt sent to the LLM, so the whole
route -> retrieve -> generate loop is visible for learning and debugging.

Output is plain ASCII to stdout so it renders in any terminal and interleaves in order with
the CLI's own prints.
"""

from __future__ import annotations

import sys

_enabled = False


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
    if _enabled:
        print(f"\n=== {title} ===")


def detail(label: str, value: object = "") -> None:
    """One indented `label: value` line (or just a label if value is empty)."""
    if _enabled:
        print(f"    {label}: {value}" if value != "" else f"    {label}")


def results(items) -> None:
    """Print a list of retrieve.Result rows as [score] (id) title."""
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


def _block(label: str, text: str) -> None:
    print(f"    [{label}]")
    for line in (text.splitlines() or [""]):
        print(f"      {line}")
