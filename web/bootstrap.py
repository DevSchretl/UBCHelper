"""Fetch the built index at startup.

`index/` is gitignored and must stay that way. `index/metadata.json` carries the full text
of all 16,576 chunks, so committing it to a public Space repo would republish the UBC
corpus in bulk — exactly what .gitignore avoids for `data/pages/`, citing UBC's Terms of
Use. The demo quoting excerpts with a link back to the official page is ordinary
attribution; shipping the corpus as a downloadable artifact is not.

So the index lives in a **private** Hugging Face Dataset repo and is pulled at container
start with a token held as a Space secret. Upload it with `scripts/publish_index.py`.

`DEMO_INDEX_REVISION` should be pinned. Chunk ids are positional, so a re-ingest renumbers
them: the test sets survive that because they carry `gold_keys` and resolve them at load time
(eval/retrieval_metrics.py), but the cached demo runs hold raw ids and do not, so an unpinned
repo would let a re-ingest silently desync the recorded runs from the index.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from src import config

INDEX_REPO = os.getenv("DEMO_INDEX_REPO", "")
INDEX_REVISION = os.getenv("DEMO_INDEX_REVISION", "main")
HF_TOKEN = os.getenv("HF_TOKEN", "")

# The demo cache ships alongside the index, for the same licensing reason: it embeds the
# excerpt text of every cached run.
CACHE_PATH = Path(os.getenv("DEMO_CACHE_PATH", str(config.PROJECT_ROOT / "web" / "cache" / "demo_runs.json")))


def ensure_index() -> str:
    """Make sure `index/` exists locally. Returns a short status string for the log.

    A local index always wins: that keeps `uvicorn web.app:app` working on a dev machine
    with no HF credentials at all.
    """
    if config.EMBEDDINGS_PATH.exists() and config.METADATA_PATH.exists():
        return f"index present at {config.INDEX_DIR}"

    if not INDEX_REPO:
        raise RuntimeError(
            "No index found and DEMO_INDEX_REPO is unset. Either build it locally with "
            "`python -m src.ingest`, or set DEMO_INDEX_REPO/HF_TOKEN to pull the "
            "prebuilt index."
        )

    from huggingface_hub import snapshot_download

    local = snapshot_download(
        repo_id=INDEX_REPO,
        repo_type="dataset",
        revision=INDEX_REVISION,
        token=HF_TOKEN or None,
    )
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("embeddings.npy", "metadata.json"):
        src_file = Path(local) / name
        if not src_file.exists():
            raise RuntimeError(f"{INDEX_REPO} is missing {name}")
        shutil.copy2(src_file, config.INDEX_DIR / name)

    # The demo cache is optional — the site works without it, just with no free examples.
    cached = Path(local) / "demo_runs.json"
    if cached.exists():
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached, CACHE_PATH)

    return f"index pulled from {INDEX_REPO}@{INDEX_REVISION}"
