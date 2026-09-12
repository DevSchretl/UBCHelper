"""
Retrieve — given a question, return the most relevant calendar excerpts.

This is the "R" in RAG. Phase 2 turns it into a two-stage funnel:

    stage 1 — RECALL     dense (vector) and sparse (BM25) search each nominate ~50
                         candidates; Reciprocal Rank Fusion merges the two rankings.
    stage 2 — PRECISION  a cross-encoder re-scores the fused shortlist jointly with
                         the query; the final top-k come out the top.

Which stages run is a config knob (UBCAL_RETRIEVAL_MODE), so the eval can compare:

    dense          Phase-1 pure vector search (the baseline)
    hybrid         stage 1 only (dense + BM25, RRF-fused)
    hybrid_rerank  both stages (the Phase-2 default)

Why RRF for fusion? Cosine similarities and BM25 scores live on totally different
scales, so averaging them is meaningless. RRF ignores the scores entirely and combines
*ranks* — a document's fused score is sum(1 / (RRF_K + rank)) across the lists it
appears in — sidestepping the calibration problem.

Exposing the doc `id` on every result is deliberate: the Phase 3 evaluation harness
matches retrieved ids against "gold" chunk ids to compute hit@k / recall@k.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass

import numpy as np

from . import bm25, config, embed, trace


@dataclass
class Result:
    """One retrieved excerpt (chunk record) plus its retrieval score.

    What `score` means depends on the mode that produced it: cosine similarity (dense),
    RRF fused score (hybrid), or a cross-encoder logit (hybrid_rerank). Higher is always
    better within one result list, but values are not comparable across modes.
    """

    id: int
    score: float
    recipe: dict  # the full metadata record from the index


# The index is loaded once and cached for the process lifetime.
_embeddings: np.ndarray | None = None
_metadata: list[dict] | None = None
_texts: list[str] | None = None


def _load_index() -> tuple[np.ndarray, list[dict]]:
    global _embeddings, _metadata
    if _embeddings is None or _metadata is None:
        if not config.EMBEDDINGS_PATH.exists() or not config.METADATA_PATH.exists():
            sys.exit(
                "No index found. Build it first with:  python -m src.ingest"
            )
        _embeddings = np.load(config.EMBEDDINGS_PATH)
        with open(config.METADATA_PATH, "r", encoding="utf-8") as f:
            _metadata = json.load(f)
    return _embeddings, _metadata


def _corpus_texts() -> list[str]:
    """The raw document texts, id-aligned with the index (what BM25 searches over)."""
    global _texts
    if _texts is None:
        _, metadata = _load_index()
        _texts = [r["text"] for r in metadata]
    return _texts


def _dense_search(query: str, k: int) -> list[tuple[int, float]]:
    """Embed the query and rank every chunk by cosine similarity; top-k, best first."""
    embeddings, metadata = _load_index()

    # Embed the query (shape (1, dim)) and reduce to a 1-D vector.
    query_vec = embed.embed_texts([query])[0]

    # Cosine similarity == dot product, since every vector is unit-length.
    # scores[i] is the similarity between the query and chunk i.
    scores = embeddings @ query_vec

    # Indices of the top_k highest scores. argpartition finds them without fully
    # sorting the whole array; we then sort just those k by score, descending.
    k = min(k, len(metadata))
    top_idx = np.argpartition(scores, -k)[-k:]
    top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]
    return [(int(i), float(scores[i])) for i in top_idx]


def _rrf_fuse(rankings: list[list[int]]) -> list[tuple[int, float]]:
    """Merge ranked doc-id lists with Reciprocal Rank Fusion; best fused score first."""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (config.RRF_K + rank)
    return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)


def _as_results(ranked: list[tuple[int, float]], limit: int) -> list[Result]:
    _, metadata = _load_index()
    return [Result(id=i, score=s, recipe=metadata[i]) for i, s in ranked[:limit]]


def _candidates(ranked: list[tuple[int, float]]) -> list[dict]:
    """Render a ranked (id, score) list for the trace event stream.

    Just enough to show a candidate column in a UI — the full record follows on the final
    results, so there is no point carrying 20 chunk bodies per stage.
    """
    _, metadata = _load_index()
    return [
        {"id": i, "score": round(float(s), 6), "title": metadata[i]["title"]}
        for i, s in ranked
    ]


def warmup() -> int:
    """Load the index and build the BM25 postings up front; returns the chunk count.

    Both are lazily cached module globals, so without this the *first* query of a process
    pays the 22 MB .npy load plus the in-memory BM25 build. Fine for the CLI, bad for the
    first visitor to a web demo.
    """
    _, metadata = _load_index()
    bm25.search("warmup", 1, _corpus_texts())
    return len(metadata)


def retrieve(query: str, top_k: int | None = None, mode: str | None = None) -> list[Result]:
    """Return the top_k excerpts most relevant to `query`, best first.

    `mode` defaults to config.RETRIEVAL_MODE (see the module docstring for the three
    modes). The signature and Result shape are stable across modes — the eval harness
    and CLI call this one function regardless of pipeline.
    """
    top_k = top_k or config.TOP_K
    mode = mode or config.RETRIEVAL_MODE
    if mode not in ("dense", "hybrid", "hybrid_rerank"):
        sys.exit(
            f"Unknown retrieval mode {mode!r} — expected dense, hybrid, or hybrid_rerank."
        )
    # The query is echoed so a consumer can attribute this whole block to the right hop of
    # a multi-hop agent run without having to infer boundaries from the surrounding steps.
    trace.event("retrieval_start", query=query, mode=mode, top_k=top_k)
    trace.detail("retrieve mode", mode)
    trace.detail("embed query (OpenAI API)", repr(query))

    if mode == "dense":
        dense_hits = _dense_search(query, top_k)
        trace.event("candidates", stage="dense", items=_candidates(dense_hits))
        out = _as_results(dense_hits, top_k)
        trace.results(out)
        trace.event("retrieval_final", query=query, items=[trace.describe(r) for r in out])
        return out

    # Stage 1 — recall: each retriever nominates candidates, RRF merges the rankings.
    dense_hits = _dense_search(query, config.DENSE_K)
    sparse_hits = bm25.search(query, config.SPARSE_K, _corpus_texts())
    dense_ids = [i for i, _ in dense_hits]
    sparse_ids = [i for i, _ in sparse_hits]
    fused = _rrf_fuse([dense_ids, sparse_ids])
    trace.event("candidates", stage="dense", items=_candidates(dense_hits))
    trace.event("candidates", stage="bm25", items=_candidates(sparse_hits))
    trace.event("candidates", stage="rrf", items=_candidates(fused))
    trace.detail("stage 1 recall", f"dense={len(dense_ids)} + bm25={len(sparse_ids)} "
                                   f"-> RRF-fused to {len(fused)} unique")

    if mode == "hybrid":
        out = _as_results(fused, top_k)
        trace.results(out)
        trace.event("retrieval_final", query=query, items=[trace.describe(r) for r in out])
        return out

    # Stage 2 — precision: the cross-encoder re-scores the fused shortlist.
    # Imported here so dense/hybrid modes never pay the multi-second torch import.
    from . import rerank

    shortlist = _as_results(fused, config.RERANK_CANDIDATES)
    trace.event("shortlist", ids=[r.id for r in shortlist])
    trace.detail("stage 2 precision", f"rerank {len(shortlist)} candidates (Cohere API) "
                                      f"-> top {top_k}")
    out = rerank.rerank(query, shortlist, top_k)
    trace.results(out)
    trace.event("retrieval_final", query=query, items=[trace.describe(r) for r in out])
    return out


if __name__ == "__main__":
    # Quick manual check:  python -m src.retrieve "prerequisites for CPSC 210"
    # (set UBCAL_RETRIEVAL_MODE to compare modes)
    question = " ".join(sys.argv[1:]) or "prerequisites for CPSC 210"
    for r in retrieve(question):
        print(f"[{r.score:.3f}] (id={r.id}) {r.recipe['title']}")
