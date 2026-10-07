"""FastAPI app for the public demo.

One service: it serves the single-page frontend and the SSE endpoint that streams a
pipeline run's internals. Same origin throughout, so there is no CORS configuration to get
wrong and no API surface exposed beyond what the page itself uses.

    GET /                      the page
    GET /api/examples          curated questions (all precomputed, all free)
    GET /api/ask/stream        SSE: run the live pipeline
    GET /api/replay/{slug}     SSE: replay a precomputed run
    GET /api/health            index status + today's budget
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src import config, retrieve

from . import bootstrap, limits, replay, runner

STATIC_DIR = Path(__file__).parent / "static"
IS_DEV = os.getenv("DEMO_DEV", "").lower() in ("1", "true", "yes")

_status = {"index": "not loaded", "chunks": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pull the index, warm the caches, and create the limits DB before serving.

    Warming matters: the index load (~100 MB .npy) plus the BM25 postings build costs several
    seconds, and without this the first visitor pays it inside their request.
    """
    limits.init()
    _status["index"] = bootstrap.ensure_index()
    _status["chunks"] = retrieve.warmup()
    print(f"[demo] {_status['index']} ({_status['chunks']} chunks), "
          f"mode={config.RETRIEVAL_MODE}, model={config.ANTHROPIC_MODEL}")
    yield


app = FastAPI(
    title="Ask the UBC Academic Calendar",
    lifespan=lifespan,
    # No interactive API docs in production: the demo's only intended client is its own page.
    docs_url="/docs" if IS_DEV else None,
    redoc_url=None,
    openapi_url="/openapi.json" if IS_DEV else None,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # Everything the page needs is served from this origin; the only external references
    # are the calendar links visitors click.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'"
    )
    return response


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {
        "status": "ok" if _status["chunks"] else "degraded",
        "index": _status["index"],
        "chunks": _status["chunks"],
        "retrieval_mode": config.RETRIEVAL_MODE,
        "model": config.ANTHROPIC_MODEL,
        "top_k": config.TOP_K,
        "usage": limits.snapshot(),
    }


@app.get("/api/examples")
async def examples():
    return {"examples": replay.examples(), "usage": limits.snapshot()}


def _sse_response(generator) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Tell any nginx-style proxy in front of us not to buffer the stream, which
            # would defeat the whole point of streaming the steps as they happen.
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/replay/{slug}")
async def replay_run(slug: str):
    """Stream a precomputed run. Free, so it is deliberately not rate limited."""
    return _sse_response(replay.stream(slug))


@app.get("/api/ask/stream")
async def ask_stream(request: Request, q: str = "", mode: str = "hybrid_rerank", route: str = "auto"):
    """Run the live pipeline and stream its internals.

    SSE over GET because `EventSource` only issues GETs — hence the question in the query
    string rather than a JSON body.
    """
    question, error = limits.validate_question(q)
    if error:
        return JSONResponse({"error": error}, status_code=400)

    if mode not in runner.VALID_MODES:
        return JSONResponse({"error": "That is not a search mode I know."}, status_code=400)
    if route not in runner.VALID_ROUTES:
        return JSONResponse({"error": "That is not a route I know."}, status_code=400)

    ip_hash = limits.hash_ip(limits.client_ip(request))
    decision = limits.check(ip_hash)
    if not decision.allowed:
        return JSONResponse(
            {
                "error": decision.reason,
                "budget_exhausted": decision.budget_exhausted,
                "retry_after": decision.retry_after,
            },
            status_code=429,
            headers={"Retry-After": str(decision.retry_after)} if decision.retry_after else {},
        )

    if not runner.try_admit():
        return JSONResponse(
            {"error": "Busy with another question right now. Try again in a moment."},
            status_code=503,
        )

    # Charged only once the run is actually admitted, so a visitor turned away by a busy
    # queue doesn't lose one of their hourly questions.
    limits.reserve(ip_hash)
    return _sse_response(runner.stream(question, mode, route))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
