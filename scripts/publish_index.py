"""Upload the built index and demo cache to a private Hugging Face Dataset repo.

The demo container pulls these at startup (web/bootstrap.py) instead of carrying them in
the image. The repo must be **private**: `index/metadata.json` holds the full text of all
chunks, and `.gitignore` already excludes the crawl on the grounds that UBC's Terms of Use
don't permit redistributing it. A demo that quotes excerpts and links to the official page
is attribution; a public bulk download is not.

    python scripts/publish_index.py --repo your-username/ubchelper-index

Prints the commit sha at the end — pin it as DEMO_INDEX_REVISION. Chunk ids are positional,
so a later re-ingest renumbers them. The test sets survive that (they resolve gold_keys at load
time), but the cached demo runs hold raw ids, so an unpinned deployment would let a re-ingest
silently desync the recorded runs from the index.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.getenv("DEMO_INDEX_REPO", ""),
                        help="target dataset repo, e.g. your-username/ubchelper-index")
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    parser.add_argument("--public", action="store_true",
                        help="create the repo public (see the module docstring first)")
    args = parser.parse_args()

    if not args.repo:
        sys.exit("Pass --repo or set DEMO_INDEX_REPO.")
    if not args.token:
        sys.exit("Pass --token or set HF_TOKEN (needs write access).")

    from huggingface_hub import HfApi

    cache = config.PROJECT_ROOT / "web" / "cache" / "demo_runs.json"
    uploads = [config.EMBEDDINGS_PATH, config.METADATA_PATH]
    missing = [p.name for p in uploads if not p.exists()]
    if missing:
        sys.exit(f"Missing {', '.join(missing)} — build the index with `python -m src.ingest`.")
    if not cache.exists():
        print(f"note: {cache.name} not found — the demo will start with no free examples. "
              f"Build it with `python scripts/build_demo_cache.py`.", file=sys.stderr)
    else:
        uploads.append(cache)

    api = HfApi(token=args.token)
    api.create_repo(args.repo, repo_type="dataset", private=not args.public, exist_ok=True)

    for path in uploads:
        size_mb = path.stat().st_size / 1e6
        print(f"uploading {path.name} ({size_mb:.1f} MB) ...", flush=True)
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo=path.name,
            repo_id=args.repo,
            repo_type="dataset",
        )

    sha = api.dataset_info(args.repo).sha
    print(f"\nDone. Set these on the Space:\n"
          f"  DEMO_INDEX_REPO={args.repo}\n"
          f"  DEMO_INDEX_REVISION={sha}")


if __name__ == "__main__":
    main()
