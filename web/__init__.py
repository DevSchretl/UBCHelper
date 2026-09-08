"""Web demo — a thin FastAPI layer over the existing pipeline.

Nothing in `src/` imports from here. This package only *consumes* the engine: it calls
`pipeline.answer()` exactly as the CLI does and streams the structured trace events that
`src.trace.collect()` hands it.
"""
