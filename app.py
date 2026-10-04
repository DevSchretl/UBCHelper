"""Gradio entry point for the Hugging Face Space.

Why Gradio and not the FastAPI app in `web/`: a Space that runs Python must use a supported
SDK, and Gradio is the one that fits a single interactive page. It runs the same
`pipeline.answer()` the CLI does; the trace events it emits are rendered to HTML by
`web/render.py` instead of being streamed to a browser-side renderer.

The page shows each run as four connected stages (Plan, Search, Rank, Answer): a row of stage
cards that fills in live, and one panel per stage. Which panel shows is the visitor's choice,
kept in the browser by `web/static/stages.js`, so the live updates below never move anyone off
the stage they are reading. The Answer panel is open by default.

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

from src import config, generate, pipeline, retrieve, trace
from web import bootstrap, limits
from web.render import Renderer

HERE = Path(__file__).resolve().parent
STATIC = HERE / "web" / "static"
# panels.css and gradio.css only, never styles.css: the latter carries page chrome with bare
# `body`, `button` and `select` selectors, which would restyle Gradio's own widgets.
CSS = "\n".join((STATIC / name).read_text(encoding="utf-8") for name in ("panels.css", "gradio.css"))
# stages.js keeps track of which stage panel is open. It goes in through `head` because Gradio 6
# runs a <script> there on every page load.
HEAD = f"<script>\n{(STATIC / 'stages.js').read_text(encoding='utf-8')}\n</script>"

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

# (label on the example chip, the question it asks)
EXAMPLES = [
    ("CPSC 221 prerequisites", "What are the prerequisites for CPSC 221?"),
    ("Levels of academic standing", "What are the three levels of academic standing at UBC?"),
    ("B.A. rules: 2023/24 vs 2024/25",
     "Compare the B.A. degree requirements for students who entered the program in 2023/24 "
     "with those who entered in 2024/25 or later."),
    ("After CPSC 210, what for 313?",
     "I have finished CPSC 210. What else do I need to complete before I can take CPSC 313?"),
    ("B.Sc. credits, 2025/26 calendar",
     "In the 2025/26 calendar, what is the minimum number of credits required for a B.Sc. degree?"),
    ("B.Sc. credits, 2026/27 calendar",
     "According to the current 2026/27 calendar, what is the minimum number of credits "
     "required for a B.Sc. degree?"),
    ("BCS vs B.Sc. admission",
     "How does admission to the Bachelor of Computer Science program differ from B.Sc. "
     "admission from secondary school?"),
    ("CS major requirements",
     "What are the requirements for a Computer Science major in the Faculty of Science?"),
]

# Pull the index and warm the caches at import, before Gradio starts serving — otherwise the
# first visitor pays the 22 MB load plus the BM25 postings build inside their request.
print(f"[demo] {bootstrap.ensure_index()}", flush=True)
CHUNKS = retrieve.warmup()
limits.init()
MODEL = generate.active_model()
print(f"[demo] warm: {CHUNKS} chunks, mode={config.RETRIEVAL_MODE}, "
      f"model={config.ANTHROPIC_MODEL}", flush=True)


# Events that change the shape of the page rather than just filling one in. Painting on each
# of these guarantees every stage is visibly reached, however fast the run is. `candidates` and
# `shortlist` are here because they move a card from Search to Rank, and the reranker call that
# follows them can take a second or more.
_ALWAYS_PAINT = frozenset({
    "step", "route", "subquestions", "merge", "retrieval_start", "retrieval_final", "llm_call",
    "candidates", "shortlist",
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


def _frame(renderer: Renderer, running: bool, sent: dict[int, str]) -> tuple:
    """One repaint: every output, with gr.skip() for any that has not changed since the last.

    The Search and Rank panels carry every candidate list, tens of kilobytes each, and most
    events change one card or one line of status. Skipping the unchanged outputs keeps a run
    from re-sending the same lists dozens of times.
    """
    values = (*renderer.panels(running=running), _usage_line())
    frame = tuple(gr.skip() if sent.get(i) == value else value for i, value in enumerate(values))
    sent.update(enumerate(values))
    return frame


def answer(question: str, mode_label: str, route_label: str, request: gr.Request):
    """Stream the pipeline's internals as it runs. A Gradio generator: each yield repaints."""
    mode = MODES.get(mode_label, "hybrid_rerank")
    route = ROUTES.get(route_label, "auto")
    sent: dict[int, str] = {}

    question, error = limits.validate_question(question)
    if error:
        refused = Renderer(question, CHUNKS, MODEL)
        refused.error = error
        yield _frame(refused, False, sent)
        return

    ip_hash = limits.hash_ip(_client_ip(request))
    decision = limits.check(ip_hash)
    if not decision.allowed:
        refused = Renderer(question, CHUNKS, MODEL)
        refused.error = decision.reason
        yield _frame(refused, False, sent)
        return
    limits.reserve(ip_hash)

    renderer = Renderer(question, CHUNKS, MODEL)
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

    yield _frame(renderer, True, sent)

    # Drain events as they arrive, repainting so the stage cards animate.
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
            yield _frame(renderer, True, sent)

    thread.join(timeout=5)

    if "error" in box:
        print(f"[demo] run failed: {type(box['error']).__name__}: {box['error']}", flush=True)
        renderer.error = ("That run did not finish. Try again, or pick one of the examples "
                          "above.")
    else:
        result = box["result"]
        renderer.answer_text = result["answer"]
        renderer.route = result["route"]

    yield _frame(renderer, False, sent)


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
        "to the official calendar page. <span class=\"intro-more\">The stages below show the "
        "work behind it: how the question got routed, what each of the two search methods "
        "turned up, which excerpts made the final cut, and the exact prompt the model saw.</span>",
        elem_id="intro",
    )

    with gr.Row(elem_id="ask-row"):
        # Length is enforced server-side in limits.validate_question, before any paid call;
        # a client-side cap would only be a convenience.
        question = gr.Textbox(
            label="", placeholder="Ask about UBC courses, programs, or policies…",
            scale=5, container=False, elem_id="question",
        )
        submit = gr.Button("Ask", variant="primary", scale=1, elem_id="ask-btn")

    # One row of short labels that scrolls sideways; stages.js adds arrow buttons on a laptop.
    examples = gr.Examples(
        examples=[[q] for _, q in EXAMPLES], inputs=[question],
        example_labels=[label for label, _ in EXAMPLES], examples_per_page=len(EXAMPLES),
        label="Try one", elem_id="examples",
    )

    with gr.Accordion("Search settings", open=False, elem_id="settings"):
        with gr.Row():
            mode = gr.Dropdown(list(MODES), value=list(MODES)[0], label="Search", scale=1)
            route = gr.Dropdown(list(ROUTES), value=list(ROUTES)[0], label="Route", scale=1)

    # The pipeline: the stage cards, then one panel per stage. stages.js shows one panel at a
    # time by setting data-selected on #pipe, and panels.css hides the rest.
    idle = Renderer("", CHUNKS, MODEL).panels()
    with gr.Column(elem_id="pipe"):
        bar_out = gr.HTML(idle[0], elem_id="stage-bar")
        plan_out = gr.HTML(idle[1], elem_id="panel-plan")
        search_out = gr.HTML(idle[2], elem_id="panel-search")
        rank_out = gr.HTML(idle[3], elem_id="panel-rank")
        with gr.Column(elem_id="panel-answer"):
            head_out = gr.HTML(idle[4], elem_id="answer-head")
            with gr.Row(elem_id="answer-row", equal_height=False):
                with gr.Column(scale=3, min_width=300):
                    # gr.Markdown, not gr.HTML: the model answers in Markdown and Gradio renders it.
                    answer_out = gr.Markdown(idle[5], buttons=["copy"], elem_id="answer-md")
                with gr.Column(scale=2, min_width=260):
                    side_out = gr.HTML(idle[6], elem_id="answer-side")
            nav_out = gr.HTML(idle[7], elem_id="answer-nav")

    usage = gr.Markdown(_usage_line(), elem_id="usage")

    gr.Markdown(
        "Excerpts are quoted from the [UBC Vancouver Academic Calendar]"
        "(https://vancouver.calendar.ubc.ca), and every result links to the page it came "
        "from. The calendar is the official word, so check it there before you act on "
        "anything you read here. This is a student project, not academic advising. "
        "[Source](https://github.com/DevSchretl/UBCHelper).",
        elem_id="footer",
    )

    outputs = [bar_out, plan_out, search_out, rank_out, head_out, answer_out, side_out, nav_out, usage]

    # One registration for both triggers (gr.on), rather than binding twice — two bindings
    # would expose two identical API endpoints.
    #
    # concurrency_limit=1 is load-bearing, not tidiness: Cohere trial keys allow 10 rerank
    # calls a minute and one agentic run makes up to 3, so letting runs overlap would trip
    # the provider's limit — which surfaces as a 90 s stall, not a clean error. The example
    # chips below share the same concurrency_id, so they wait in the same one-at-a-time line.
    gr.on(
        triggers=[submit.click, question.submit],
        fn=answer,
        inputs=[question, mode, route],
        outputs=outputs,
        concurrency_limit=1,
        concurrency_id="answer",
        api_name="answer",
        show_progress="minimal",
        show_progress_on=[head_out],
    )

    # Clicking an example fills the box, then asks it. Private, so it adds no second API
    # endpoint; the run still goes through answer() and its spend controls.
    examples.load_input_event.then(
        answer,
        inputs=[question, mode, route],
        outputs=outputs,
        concurrency_limit=1,
        concurrency_id="answer",
        api_visibility="private",
        show_progress="minimal",
        show_progress_on=[head_out],
    )


if __name__ == "__main__":
    # Gradio 6 moved `css`, `head` and `theme` off the Blocks constructor onto launch().
    demo.queue(max_size=8).launch(css=CSS, head=HEAD, theme=gr.themes.Soft())
