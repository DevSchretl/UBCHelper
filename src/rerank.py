"""
Rerank — the precision stage of the retrieval funnel.

The bi-encoder (embeddings) scores query and document *separately*, so it can only
compare their summaries. A cross-encoder reads the query and a document *together* and
scores the pair jointly — far sharper, but far too slow to run against the whole corpus.
So it only ever sees the short candidate list that the cheap recall stage (dense + BM25)
already produced.

Reranking runs on Cohere's hosted rerank API (config.RERANKER_MODEL). Keeping it hosted
means no local torch / sentence-transformers dependency, so the service deploys on an
ordinary CPU host. Excerpts longer than the model's window are truncated server-side,
which is fine: the title/section header + the start of the body carry the ranking signal.
"""

from __future__ import annotations

import time

from . import config
from .retrieve import Result

# The Cohere client is created lazily and cached: only the hybrid_rerank mode needs it,
# so dense/hybrid modes never construct it.
_client = None


def _get_client():
    global _client
    if _client is None:
        import cohere

        _client = cohere.Client(config.COHERE_API_KEY)
    return _client


def rerank(query: str, candidates: list[Result], top_k: int) -> list[Result]:
    """Re-score `candidates` jointly against `query`; return the top_k, best first.

    The returned Results carry the Cohere relevance score (0-1, higher is better),
    replacing whatever score the recall stage assigned.
    """
    import cohere

    client = _get_client()
    # Trial keys are capped at 10 calls/minute; back off and retry on 429 so a batch
    # (e.g. the eval loop) doesn't die mid-run.
    for attempt in range(4):
        try:
            response = client.rerank(
                model=config.RERANKER_MODEL,
                query=query,
                documents=[r.recipe["text"] for r in candidates],
                top_n=top_k,
            )
            break
        except cohere.errors.TooManyRequestsError:
            if attempt == 3:
                raise
            time.sleep(15 * (attempt + 1))
    return [
        Result(
            id=candidates[result.index].id,
            score=result.relevance_score,
            recipe=candidates[result.index].recipe,
        )
        for result in response.results
    ]
