"""Bridge the synchronous pipeline to an async SSE stream.

`pipeline.answer()` is ordinary blocking Python — it makes network calls, and
`rerank.rerank` can sleep for up to 90 s backing off a Cohere 429. Running that on the
event loop would freeze every other connection, so it runs in a worker thread and pushes
trace events back through an asyncio queue.

Concurrency is deliberately capped at one run at a time. Two independent reasons:

  * Cohere trial keys allow 10 rerank calls/minute and a single complex-route run makes up
    to 3. Serialising keeps a burst of visitors from tripping the provider's limit — which
    would show up as a 90 s stall, not a clean error.
  * The free HF Spaces CPU is 2 vCPU. The 16576x1536 dense matmul plus BM25 scoring is
    comfortable serially and thrashes in parallel.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import AsyncIterator

from starlette.concurrency import run_in_threadpool

from src import pipeline, trace

from . import limits

# One live pipeline run at a time; a few may wait, the rest are told to come back.
_semaphore = asyncio.Semaphore(1)
_waiting = 0
MAX_WAITING = 3

HEARTBEAT_SECONDS = 15
RUN_TIMEOUT_SECONDS = 120

VALID_MODES = ("dense", "hybrid", "hybrid_rerank")
VALID_ROUTES = ("auto", "simple", "complex")


def sse(kind: str, payload: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def count_api_calls(events: list[dict]) -> dict:
    """Derive the paid-API call counts for a finished run from its own event stream.

    Every paid call announces itself: `llm_call` per generation, `retrieval_start` per query
    embedding, `shortlist` per Cohere rerank (only emitted on the hybrid_rerank path). So
    the accounting is exact rather than estimated, and it stays correct automatically if the
    pipeline's shape ever changes.
    """
    counts = {"llm": 0, "embed": 0, "rerank": 0}
    for event in events:
        limits.tally(counts, event)
    return counts


def try_admit() -> bool:
    """Claim a slot in the run queue, or return False if it is already full.

    Admission is synchronous and separate from `stream()` because an async generator does
    not execute a single line until it is first iterated — which happens after the endpoint
    has already returned its response. Deciding here lets the endpoint answer a busy demo
    with a clean 503 instead of an error buried mid-stream.
    """
    global _waiting
    if _waiting >= MAX_WAITING:
        return False
    _waiting += 1
    return True


async def stream(question: str, mode: str, route: str) -> AsyncIterator[str]:
    """Run the pipeline and yield SSE frames as its trace events arrive.

    Yields the raw event stream first (so the UI animates in real time), then an `answer`
    and a `done` frame. Call `try_admit()` first — this releases the slot it claimed.
    """
    global _waiting
    try:
        async with _semaphore:
            async for frame in _run(question, mode, route):
                yield frame
    finally:
        _waiting -= 1


async def _run(question: str, mode: str, route: str) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    captured: list[dict] = []
    started = time.perf_counter()

    def emit(ev: dict) -> None:
        # Called from the worker thread — hop back onto the loop to touch the queue.
        captured.append(ev)
        loop.call_soon_threadsafe(queue.put_nowait, ev)

    def work() -> dict:
        # The sink is bound *inside* the worker thread, so the ContextVar is set on the
        # thread that actually runs the pipeline. No context propagation to reason about.
        try:
            with trace.collect(emit):
                return pipeline.answer(
                    question, mode=mode, route=None if route == "auto" else route
                )
        finally:
            # Billed here, in the worker thread, rather than beside the streaming loop:
            # the paid calls happen whether or not the visitor is still connected, and a
            # client that disconnects mid-run closes the generator without draining the
            # queue. Recording at the source is the only place the count is complete.
            counts = count_api_calls(captured)
            if any(counts.values()):
                limits.record(**counts)

    task = asyncio.ensure_future(run_in_threadpool(work))
    deadline = loop.time() + RUN_TIMEOUT_SECONDS

    yield sse("accepted", {"question": question, "mode": mode, "route": route})

    try:
        while not (task.done() and queue.empty()):
            if loop.time() > deadline:
                yield sse("error", {"message": "That took too long, so it was stopped."})
                return
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                # Keeps intermediaries from dropping a connection that is legitimately
                # waiting on a slow model call.
                yield ": heartbeat\n\n"
                continue
            yield sse(event["kind"], event)

        result = await task
    except Exception as exc:  # noqa: BLE001 - the stream must report, never crash
        # The detail goes to the server log, not the visitor: provider exceptions can carry
        # request context, and a public demo has no reason to hand that out.
        print(f"[demo] run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        yield sse("error", {"message": "That run did not finish. Try again, or pick "
                                       "one of the saved runs."})
        return
    finally:
        # A worker thread cannot be cancelled — on timeout or client disconnect it keeps
        # running to completion. Waiting for it here means the caller's semaphore is not
        # released while that thread is still calling Cohere, which is what makes the
        # one-run-at-a-time limit actually hold.
        if not task.done():
            await asyncio.gather(task, return_exceptions=True)

    yield sse("answer", {"text": result["answer"], "route": result["route"]})
    yield sse(
        "done",
        {
            "route": result["route"],
            "excerpts": len(result["results"]),
            "ms": round((time.perf_counter() - started) * 1000),
            "api_calls": count_api_calls(captured),
        },
    )
