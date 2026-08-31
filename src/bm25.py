"""
BM25 — hand-rolled sparse (keyword) retrieval, the other half of hybrid search.

Dense embeddings capture *meaning* but under-weight rare, high-signal tokens: a query
about "CPSC 320" lands near generic computer-science text because the code barely moves
the vector. BM25 is the opposite — it scores documents by exact term overlap, weighting
each term by how rare it is in the corpus (IDF), saturating repeated occurrences (k1), and
penalizing long documents (b). Rare course-code/program tokens are exactly where it
shines, which is why fusing it with dense retrieval helps.

This is the classic Okapi BM25 formula, built with numpy so the mechanism stays visible
(same spirit as the hand-rolled vector store):

    score(q, d) = sum over query terms t of
        idf(t) * tf(t,d) * (k1 + 1) / (tf(t,d) + k1 * (1 - b + b * |d| / avgdl))
    idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

Everything inside the sum depends only on the corpus, so each term's per-document
contribution is precomputed at build time; scoring a query is then just summing a few
postings arrays. The index is built in memory from the text the dense index already
stores (a few seconds even for tens of thousands of chunks, once per process) — no new artifact on disk and
no re-ingest needed.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np

# Standard Okapi parameters.
K1 = 1.5  # term-frequency saturation: repeats help, with diminishing returns
B = 0.75  # document-length normalization strength

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens. Used for BOTH documents and queries — the sparse
    analogue of "the same embedding model must embed the index and the query"."""
    return _TOKEN_RE.findall(text.lower())


@dataclass
class _Index:
    # term -> (doc indices, that term's precomputed idf*tf-saturation score per doc)
    postings: dict[str, tuple[np.ndarray, np.ndarray]]
    n_docs: int


def _build(texts: list[str]) -> _Index:
    docs = [Counter(tokenize(t)) for t in texts]
    doc_lens = np.array([sum(c.values()) for c in docs], dtype=np.float64)
    avgdl = doc_lens.mean() or 1.0
    n = len(texts)

    # Document frequency: in how many docs does each term appear?
    df: Counter[str] = Counter()
    for counts in docs:
        df.update(counts.keys())

    # Per-document length penalty (the k1 * (1 - b + b*|d|/avgdl) denominator part).
    norm = K1 * (1 - B + B * doc_lens / avgdl)

    by_term: dict[str, tuple[list[int], list[float]]] = {t: ([], []) for t in df}
    for i, counts in enumerate(docs):
        for term, tf in counts.items():
            indices, weights = by_term[term]
            indices.append(i)
            weights.append(tf * (K1 + 1) / (tf + norm[i]))

    postings = {}
    for term, (indices, weights) in by_term.items():
        idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
        postings[term] = (
            np.array(indices, dtype=np.int32),
            idf * np.array(weights, dtype=np.float32),
        )
    return _Index(postings=postings, n_docs=n)


# Built once per process on first search, cached for the corpus it was built from.
_index: _Index | None = None
_source: list[str] | None = None


def _get_index(texts: list[str]) -> _Index:
    global _index, _source
    if _index is None or _source is not texts:
        _index = _build(texts)
        _source = texts
    return _index


def search(query: str, k: int, texts: list[str]) -> list[tuple[int, float]]:
    """Return the top-k (doc index, BM25 score) pairs for `query`, best first.

    Only documents sharing at least one term with the query are returned, so the list
    can be shorter than k.
    """
    index = _get_index(texts)
    scores = np.zeros(index.n_docs, dtype=np.float32)
    for term in tokenize(query):
        entry = index.postings.get(term)
        if entry is not None:
            indices, weights = entry
            scores[indices] += weights

    k = min(k, index.n_docs)
    top_idx = np.argpartition(scores, -k)[-k:]
    top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]
    return [(int(i), float(scores[i])) for i in top_idx if scores[i] > 0]
