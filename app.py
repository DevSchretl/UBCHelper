"""Gradio entry point for the Hugging Face Space.

Why Gradio and not the FastAPI app in `web/`: a Space that runs Python must use a supported
SDK, and Gradio is the one that fits a single interactive page. It runs the same
`pipeline.answer()` the CLI does; the trace events it emits are rendered to HTML by
`web/render.py` instead of being streamed to a browser-side renderer.

There is no `@spaces.GPU` here because there is nothing to put on a GPU — the pipeline is
numpy plus three hosted APIs. That rules out ZeroGPU, which kills a Space with "No
@spaces.GPU function detected during startup", so this Space runs on `cpu-basic` hardware
(free per-hour, but creating a compute Space needs an HF PRO account). See DEPLOY.md.

The spend controls from the FastAPI build carry over unchanged (`web/limits.py`): a global
daily ceiling on paid API calls and per-IP sliding windows, keyed on a salted hash of the
address Gradio hands us in `gr.Request`.

    python app.py          # local
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

import gradio as gr

from src import config, pipeline, retrieve, trace
from web import bootstrap, limits
from web.render import Renderer

HERE = Path(__file__).resolve().parent
# panels.css only, never styles.css: the latter carries page chrome with bare `body`,
# `button` and `select` selectors, which would restyle Gradio's own widgets.
CSS = (HERE / "web" / "static" / "panels.css").read_text(encoding="utf-8")

MODES = {
    "Hybrid + rerank (default)": "hybrid_rerank",
    "Hybrid: vector + keyword": "hybrid",
    "Vector search only": "dense",
}
ROUTES = {
    "Auto: let the router pick": "auto",
    "Always single-shot": "simple",
    "Always multi-step": "complex",
}

EXAMPLES = [
    "What are the prerequisites for CPSC 221?",
    "What are the three levels of academic standing at UBC?",
    "Compare the B.A. degree requirements for students who entered the program in 2023/24 "
    "with those who entered in 2024/25 or later.",
    "I have finished CPSC 210. What else do I need to complete before I can take CPSC 313?",
    "In the 2025/26 calendar, what is the minimum number of credits required for a B.Sc. degree?",
    "According to the current 2026/27 calendar, what is the minimum number of credits "
    "required for a B.Sc. degree?",
    "How does admission to the Bachelor of Computer Science program differ from B.Sc. "
    "admission from secondary school?",
    "What are the requirements for a Computer Science major in the Faculty of Science?",
]

# Pull the index and warm the caches at import, before Gradio starts serving — otherwise the
# first visitor pays the 22 MB load plus the BM25 postings build inside their request.
print(f"[demo] {bootstrap.ensure_index()}", flush=True)
CHUNKS = retrieve.warmup()
limits.init()
print(f"[demo] warm: {CHUNKS} chunks, mode={config.RETRIEVAL_MODE}, "
      f"model={config.ANTHROPIC_MODEL}", flush=True)


# Events that change the shape of the page rather than just filling one in. Painting on each
# of these guarantees every stage is visibly reached, however fast the run is.
_ALWAYS_PAINT = frozenset({
    "step", "route", "subquestions", "merge", "retrieval_start", "retrieval_final", "llm_call",
})


def _client_ip(request: gr.Request | None) -> str:
    """The visitor's address, through the Space's reverse proxy.

    Spaces terminate TLS upstream, so the direct peer is the proxy for everyone. Reading the
    first hop of X-Forwarded-For is what makes the per-IP limit per-*visitor* rather than one
    shared bucket for the entire internet.
    """
    if request is None:
        return "local"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = getattr(request, "client", None)
    return getattr(client, "host", None) or "unknown"


def answer(question: str, mode_label: str, route_label: str, request: gr.Request):
    """Stream the pipeline's internals as it runs. A Gradio generator: each yield repaints."""
    mode = MODES.get(mode_label, "hybrid_rerank")
    route = ROUTES.get(route_label, "auto")

    question, error = limits.validate_question(question)
    if error:
        yield "", "", f'<div class="notice">{error}</div>', _usage_line()
        return

    ip_hash = limits.hash_ip(_client_ip(request))
    decision = limits.check(ip_hash)
    if not decision.allowed:
        yield "", "", f'<div class="notice">{decision.reason}</div>', _usage_line()
        return
    limits.reserve(ip_hash)

    renderer = Renderer(question)
    events: queue.Queue = queue.Queue()
    box: dict = {}
    counts: dict = {"llm": 0, "embed": 0, "rerank": 0}

    def work() -> None:
        """Run the pipeline on a worker thread, tallying and billing paid calls at the source.

        Billing happens *here*, in this thread's finally, rather than after the streaming loop
        below. Gradio closes the generator when a visitor navigates away or drops the
        connection, which raises GeneratorExit at a yield — but this thread is detached and
        uncancellable, so it goes on to complete every paid OpenAI/Cohere/Anthropic call. If
        the tally lived with the consumer, those calls would never reach the daily ceiling
        that is the demo's actual spend bound. Counting at the source is the only place the
        number is complete. (web/runner.py:work does the same, for the same reason.)
        """
        def emit(event: dict) -> None:
            limits.tally(counts, event)
            events.put(event)

        try:
            with trace.collect(emit):
                box["result"] = pipeline.answer(
                    question, mode=mode, route=None if route == "auto" else route
                )
        except Exception as exc:  # noqa: BLE001 - surfaced to the visitor as a generic note
            box["error"] = exc
        finally:
            if any(counts.values()):
                limits.record(**counts)
            events.put(None)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()

    trace_html, retrieval_html, answer_html = renderer.panels(running=True)
    yield trace_html, retrieval_html, answer_html, _usage_line()

    # Drain events as they arrive, repainting so the stepper animates.
    last_paint = 0.0
    while True:
        event = events.get()
        if event is None:
            break
        renderer.feed(event)
        # Always repaint on a structural change, so no stage is ever skipped over; otherwise
        # coalesce, since a retrieval stage fires several events back to back and there is no
        # point repainting dozens of times a second.
        now = time.perf_counter()
        if event["kind"] in _ALWAYS_PAINT or now - last_paint > 0.04:
            last_paint = now
            trace_html, retrieval_html, answer_html = renderer.panels(running=True)
            yield trace_html, retrieval_html, answer_html, _usage_line()

    thread.join(timeout=5)

    if "error" in box:
        print(f"[demo] run failed: {type(box['error']).__name__}: {box['error']}", flush=True)
        renderer.error = ("That run did not finish. Try again, or pick one of the examples "
                          "below.")
    else:
        result = box["result"]
        renderer.answer_text = result["answer"]
        renderer.route = result["route"]

    trace_html, retrieval_html, answer_html = renderer.panels(running=False)
    yield trace_html, retrieval_html, answer_html, _usage_line()


def _usage_line() -> str:
    usage = limits.snapshot()
    if usage["budget_exhausted"]:
        # No "see the recorded runs instead" here: web/replay.py and web/cache/ belong to
        # the FastAPI and static builds, and neither ships with this Space.
        return "**Out of model calls for today.** The limit resets at 00:00 UTC."
    return (f"{usage['llm_calls_remaining']}/{usage['llm_calls_limit']} model calls left today "
            f"· {usage['per_ip_hour']}/hour per visitor · {CHUNKS:,} chunks indexed "
            f"· {config.RETRIEVAL_MODE} · {config.ANTHROPIC_MODEL}")


with gr.Blocks(title="Ask the UBC Academic Calendar") as demo:
    gr.Markdown(
        "# Ask the UBC Academic Calendar\n"
        "Ask about a course, a program, or a policy and you get an answer that links back "
        "to the official calendar page. The panels below show the work behind it: how the "
        "question got routed, what each of the two search methods turned up, which excerpts "
        "made the final cut, and the exact prompt the model saw."
    )

    with gr.Row():
        # Length is enforced server-side in limits.validate_question, before any paid call;
        # a client-side cap would only be a convenience.
        question = gr.Textbox(
            label="", placeholder="Ask about UBC courses, programs, or policies…",
            scale=5, container=False,
        )
        submit = gr.Button("Ask", variant="primary", scale=1)

    with gr.Row():
        mode = gr.Dropdown(list(MODES), value=list(MODES)[0], label="Search", scale=1)
        route = gr.Dropdown(list(ROUTES), value=list(ROUTES)[0], label="Route", scale=1)

    usage = gr.Markdown(_usage_line())
    gr.Examples(examples=[[e] for e in EXAMPLES], inputs=[question], label="Try one")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Steps")
            trace_out = gr.HTML(
                '<div class="empty">Ask a question and the steps will show up here.</div>')
        with gr.Column():
            gr.Markdown("### Search results")
            retrieval_out = gr.HTML(
                '<div class="empty">The excerpts each search finds will show up here.</div>')

    # gr.Markdown, not gr.HTML: the model answers in Markdown and Gradio renders it.
    answer_out = gr.Markdown()

    gr.Markdown(
        "Excerpts are quoted from the [UBC Vancouver Academic Calendar]"
        "(https://vancouver.calendar.ubc.ca), and every result links to the page it came "
        "from. The calendar is the official word, so check it there before you act on "
        "anything you read here. This is a student project, not academic advising. "
        "[Source](https://github.com/DevSchretl/UBCHelper)."
    )

    # One registration for both triggers (gr.on), rather than binding twice — two bindings
    # would expose two identical API endpoints.
    #
    # concurrency_limit=1 is load-bearing, not tidiness: Cohere trial keys allow 10 rerank
    # calls a minute and one agentic run makes up to 3, so letting runs overlap would trip
    # the provider's limit — which surfaces as a 90 s stall, not a clean error.
    gr.on(
        triggers=[submit.click, question.submit],
        fn=answer,
        inputs=[question, mode, route],
        outputs=[trace_out, retrieval_out, answer_out, usage],
        concurrency_limit=1,
        api_name="answer",
    )


if __name__ == "__main__":
    # Gradio 6 moved `css` and `theme` off the Blocks constructor onto launch().
    demo.queue(max_size=8).launch(css=CSS, theme=gr.themes.Soft())
