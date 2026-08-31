"""
Embeddings — the single source of truth for turning text into vectors.

Both ingest.py (indexing documents) and retrieve.py (embedding the user's query) call
`embed_texts` here. Routing every embedding through one function guarantees the golden
rule of dense retrieval is never broken: the SAME model embeds the documents and the
queries, so their vectors live in the same space and cosine similarity is meaningful.

We talk to OpenAI's hosted `/v1/embeddings` endpoint (config.EMBED_*), so there is no
local model-server or torch dependency — just the `openai` client and numpy.
"""

from __future__ import annotations

import numpy as np
from openai import OpenAI

from . import config

# One shared client, created lazily on first use (so merely importing this module
# doesn't require the endpoint to be reachable).
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=config.EMBED_BASE_URL,
            api_key=config.EMBED_API_KEY,
        )
    return _client


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Embed a list of strings into an (N, dim) float32 matrix of UNIT vectors.

    The vectors are L2-normalized, which means cosine similarity between any two of
    them is just their dot product. That lets retrieval score the whole corpus with a
    single fast matrix multiply (see retrieve.py).

    Texts are sent in batches so we make a handful of requests instead of one per
    document — much faster for a few hundred documents.
    """
    if not texts:
        raise ValueError("embed_texts called with no texts")

    client = _get_client()
    vectors: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(model=config.EMBEDDING_MODEL, input=batch)
        # The API guarantees one embedding per input, in order.
        vectors.extend(item.embedding for item in response.data)

    matrix = np.asarray(vectors, dtype=np.float32)
    return _normalize(matrix)


def _normalize(matrix: np.ndarray) -> np.ndarray:
    """Scale each row to unit length. Guards against divide-by-zero on empty vectors."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # avoid NaN if a vector is all zeros
    return matrix / norms
