"""
Ingest — build the index from the cached calendar pages. Run after `python -m src.scrape`.

Pipeline:
    data/pages/  ->  chunk.py records  ->  embeddings  ->  index/ (numpy matrix + JSON metadata)

Keeps RAGChef's index format: a float32 embeddings matrix (index/embeddings.npy) plus an
id-aligned list of chunk records (index/metadata.json). `id` is the global position of a chunk
across all pages, assigned here so the eval's gold_ids stay stable.

Run from the project root:
    python -m src.ingest                 # chunk + embed all cached pages
    python -m src.ingest --no-embed      # build/save metadata only (no OpenAI key needed)
    python -m src.ingest --limit 20      # only the first 20 cached pages (dev)
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from . import chunk, config, embed


def build_chunks(limit_pages: int = 0) -> list[dict]:
    """Chunk every cached page (or the first `limit_pages`) and assign global ids."""
    chunks: list[dict] = []
    for i, record in enumerate(chunk.iter_page_records()):
        if limit_pages and i >= limit_pages:
            break
        chunks.extend(chunk.page_record_to_chunks(record))
    for idx, c in enumerate(chunks):
        c["id"] = idx  # stable global position; the eval matches gold_ids on this
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the index from data/pages/.")
    ap.add_argument("--limit", type=int, default=0, help="cap number of pages chunked (0 = all).")
    ap.add_argument("--no-embed", action="store_true",
                    help="write metadata.json only, skip embeddings (no OpenAI key needed).")
    args = ap.parse_args()

    if not config.MANIFEST_PATH.exists():
        sys.exit("No cached pages found. Run `python -m src.scrape` first.")

    print("Chunking cached pages ...")
    chunks = build_chunks(args.limit)
    if not chunks:
        sys.exit("No chunks produced — is data/pages empty?")
    print(f"Built {len(chunks)} chunks.")

    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)

    if args.no_embed:
        with open(config.METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)
        print(f"[--no-embed] Wrote metadata only: {config.METADATA_PATH}")
        return

    print(f"Embedding {len(chunks)} chunks via {config.EMBEDDING_MODEL} "
          f"at {config.EMBED_BASE_URL or 'OpenAI API'} ...")
    embeddings = embed.embed_texts([c["text"] for c in chunks])  # (N, dim) unit vectors
    print(f"Got embeddings of shape {embeddings.shape}.")

    np.save(config.EMBEDDINGS_PATH, embeddings)
    with open(config.METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    print(f"Saved index:\n  {config.EMBEDDINGS_PATH}\n  {config.METADATA_PATH}\nDone.")


if __name__ == "__main__":
    main()
