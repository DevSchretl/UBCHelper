"""
Scrape — build the local page cache the index is later ingested from.

Pipeline:
    sitemap.xml  ->  filter to in-scope subtrees  ->  polite HTTP GET  ->  data/pages/

The UBC Vancouver Academic Calendar is server-rendered Drupal 11, so a plain GET returns the
full page — no headless browser. Enumeration is sitemap-driven (the site exposes a 6-page
sitemap of readable aliases), filtered to the target subtrees in config; the 2025/26 archive
edition (a static mirror of the same theme) has no sitemap, so its URLs are derived from the
in-scope live path_keys.

Each fetched page is stored as one JSON record under data/pages/<source>/<hash>.json, holding
the raw HTML plus provenance (canonical url, path_key, edition, fetch time, content hash). The
filename is the content hash, so a page that changes mid-year writes a NEW file and the old
snapshot is retained. data/pages/manifest.json maps each url to its current snapshot and drives
conditional GETs on re-runs.

Politeness: the site's robots.txt asks for Crawl-delay: 10, so requests are spaced 10s apart
(single-threaded) with a descriptive User-Agent and exponential backoff on 429/5xx.

Run from the project root:
    python -m src.scrape --dry-run                 # enumerate only; print in-scope counts
    python -m src.scrape --sample --delay 6        # fetch the ~5 representative sample pages
    python -m src.scrape --editions live,archive   # full in-scope crawl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from . import config

SOURCE_LABELS = {"live": "live-2627", "archive": "archive-2526"}


# --------------------------------------------------------------------------------------
# URL / scope helpers
# --------------------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def path_key_of(url: str) -> str:
    """The logical path of a URL, minus host and surrounding slashes. For archive URLs we also
    strip the /vancouver/2526/ edition prefix and a trailing /index.html so a page's key matches
    its live twin (this is what pairs the two editions for collision questions)."""
    path = urlparse(url).path.strip("/")
    if path.startswith(config.ARCHIVE_EDITION_DIR):
        path = path[len(config.ARCHIVE_EDITION_DIR):].strip("/")
    if path.endswith("/index.html"):
        path = path[: -len("/index.html")]
    elif path.endswith("index.html"):
        path = path[: -len("index.html")].strip("/")
    return path


def _prefix_match(path: str, prefixes: list[str]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def _disallowed(path: str) -> bool:
    return any(path == d.rstrip("/") or path.startswith(d) for d in config.ROBOTS_DISALLOW_PREFIXES)


def in_scope_live(path: str) -> bool:
    if _disallowed(path):
        return False
    return _prefix_match(path, config.LIVE_SCOPE_PREFIXES) or path in config.COURSE_SUBJECT_PATHS


def in_scope_archive(path: str) -> bool:
    return _prefix_match(path, config.ARCHIVE_SCOPE_PREFIXES) or path in config.COURSE_SUBJECT_PATHS


def archive_url_for(path_key: str) -> str:
    return f"{config.ARCHIVE_BASE_URL}/{config.ARCHIVE_EDITION_DIR}/{path_key}/index.html"


# --------------------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------------------
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT})
    return s


def fetch(session: requests.Session, url: str, extra_headers: dict | None = None) -> requests.Response | None:
    """GET with retry/backoff on 429/5xx (honoring Retry-After). Returns the final Response
    (including 304 / 404 for the caller to handle) or None if the request never completed."""
    headers = dict(extra_headers or {})
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            resp = session.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT, allow_redirects=True)
        except requests.RequestException as exc:
            if attempt >= config.MAX_RETRIES:
                print(f"  ! request error, giving up: {url}  ({exc})")
                return None
            wait = config.BACKOFF_BASE * (2 ** attempt)
            print(f"  . request error ({exc}); retry in {wait:.0f}s")
            time.sleep(wait)
            continue
        if resp.status_code in (429, 500, 502, 503, 504):
            if attempt >= config.MAX_RETRIES:
                print(f"  ! HTTP {resp.status_code}, giving up: {url}")
                return resp
            retry_after = resp.headers.get("Retry-After", "")
            wait = float(retry_after) if retry_after.isdigit() else config.BACKOFF_BASE * (2 ** attempt)
            print(f"  . HTTP {resp.status_code}; retry in {wait:.0f}s")
            time.sleep(wait)
            continue
        return resp
    return None


# --------------------------------------------------------------------------------------
# Enumeration
# --------------------------------------------------------------------------------------
def _locs(xml_text: str) -> list[str]:
    return [m.strip() for m in re.findall(r"<loc>\s*(.*?)\s*</loc>", xml_text, re.I | re.S)]


def enumerate_live(session: requests.Session, delay: float) -> dict[str, str]:
    """Walk the sitemap index -> sub-sitemaps -> content aliases, keep the in-scope ones.
    Returns {path_key: url}."""
    index = fetch(session, config.SITEMAP_URL)
    if index is None or index.status_code != 200:
        sys.exit(f"Could not fetch sitemap index: {config.SITEMAP_URL}")
    sub_sitemaps = _locs(index.text)
    print(f"Sitemap index lists {len(sub_sitemaps)} sub-sitemaps.")

    in_scope: dict[str, str] = {}
    for sub in sub_sitemaps:
        time.sleep(delay)
        r = fetch(session, sub)
        if r is None or r.status_code != 200:
            print(f"  ! skipping sub-sitemap (HTTP {getattr(r, 'status_code', '??')}): {sub}")
            continue
        for url in _locs(r.text):
            pk = path_key_of(url)
            if in_scope_live(pk):
                in_scope.setdefault(pk, url)
    return in_scope


def archive_targets(live_path_keys: list[str]) -> dict[str, str]:
    """Derive in-scope archive URLs from the live path_keys (the archive has no sitemap)."""
    return {pk: archive_url_for(pk) for pk in live_path_keys if in_scope_archive(pk)}


def build_worklist(session, editions: list[str], sample: bool, delay: float) -> list[dict]:
    """Return a list of {url, path_key, edition, source} to fetch."""
    work: list[dict] = []

    if sample:
        live_pks = {pk: config.CALENDAR_BASE_URL + "/" + pk for pk in config.SAMPLE_PATHS}
    elif "live" in editions:
        live_pks = enumerate_live(session, delay)
        # Course-subject pages are taxonomy-term pages the sitemap omits — add them explicitly.
        for pk in config.COURSE_SUBJECT_PATHS:
            live_pks.setdefault(pk, config.CALENDAR_BASE_URL + "/" + pk)
    else:
        live_pks = {}

    if "live" in editions:
        for pk, url in sorted(live_pks.items()):
            work.append({"url": url, "path_key": pk, "edition": config.LIVE_EDITION_YEAR, "source": SOURCE_LABELS["live"]})

    if "archive" in editions:
        for pk, url in sorted(archive_targets(list(live_pks)).items()):
            work.append({"url": url, "path_key": pk, "edition": config.ARCHIVE_EDITION_YEAR, "source": SOURCE_LABELS["archive"]})

    return work


# --------------------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------------------
def _load_manifest() -> dict:
    if config.MANIFEST_PATH.exists():
        return json.loads(config.MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _save_manifest(manifest: dict) -> None:
    config.PAGES_DIR.mkdir(parents=True, exist_ok=True)
    config.MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def _canonical(html: str, fallback: str) -> str:
    # Only trust an ABSOLUTE canonical. The static archive mirror emits a relative
    # <link rel=canonical href="index.html">, which is useless as a dedup/citation key.
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](https?://[^"\']+)["\']', html, re.I)
    return m.group(1) if m else fallback


def save_page(record: dict) -> str:
    """Write one page record to data/pages/<source>/<hash16>.json (content-addressed, so a
    changed page yields a new file and old snapshots survive). Returns the project-relative path."""
    out_dir = config.PAGES_DIR / record["source"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{record['content_hash'][:16]}.json"
    if not path.exists():
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return str(path.relative_to(config.PROJECT_ROOT)).replace("\\", "/")


# --------------------------------------------------------------------------------------
# Crawl
# --------------------------------------------------------------------------------------
def crawl(editions: list[str], limit: int, delay: float, dry_run: bool, sample: bool) -> None:
    session = make_session()
    work = build_worklist(session, editions, sample, delay)

    if limit and limit > 0:
        work = work[:limit]

    print(f"\nIn scope: {len(work)} pages "
          f"({sum(w['source'] == SOURCE_LABELS['live'] for w in work)} live, "
          f"{sum(w['source'] == SOURCE_LABELS['archive'] for w in work)} archive).")
    _print_breakdown(work)

    if dry_run:
        print("\n[dry-run] Sample of in-scope URLs:")
        for w in work[:15]:
            print(f"  {w['edition']}  {w['url']}")
        return

    manifest = _load_manifest()
    fetched = skipped = failed = 0

    for i, item in enumerate(work, 1):
        url = item["url"]
        prior = manifest.get(url, {})
        cond = {}
        if prior.get("etag"):
            cond["If-None-Match"] = prior["etag"]
        if prior.get("last_modified"):
            cond["If-Modified-Since"] = prior["last_modified"]

        if i > 1:
            time.sleep(delay)
        print(f"[{i}/{len(work)}] {url}")
        resp = fetch(session, url, cond)

        if resp is None:
            failed += 1
            continue
        if resp.status_code == 304:
            print("  = 304 not modified (kept cached copy)")
            skipped += 1
            continue
        if resp.status_code != 200:
            print(f"  ! HTTP {resp.status_code} (skipped)")
            failed += 1
            continue

        html = resp.text
        record = {
            "url": url,
            "canonical_url": _canonical(html, str(resp.url)),
            "path_key": item["path_key"],
            "edition_year": item["edition"],
            "source": item["source"],
            "http_status": resp.status_code,
            "fetched_at": _now_iso(),
            "content_hash": hashlib.sha256(html.encode("utf-8", "replace")).hexdigest(),
            "last_modified": resp.headers.get("Last-Modified"),
            "etag": resp.headers.get("ETag"),
            "raw_html": html,
        }
        json_path = save_page(record)
        manifest[url] = {k: record[k] for k in
                         ("path_key", "edition_year", "source", "http_status",
                          "fetched_at", "content_hash", "last_modified", "etag")}
        manifest[url]["json_path"] = json_path
        fetched += 1

    _save_manifest(manifest)
    print(f"\nDone. fetched={fetched} unchanged={skipped} failed={failed}. "
          f"Manifest: {config.MANIFEST_PATH}")


def _print_breakdown(work: list[dict]) -> None:
    chapters: dict[str, int] = {}
    for w in work:
        if w["source"] != SOURCE_LABELS["live"]:
            continue
        top = w["path_key"].split("/", 1)[0] or "(root)"
        chapters[top] = chapters.get(top, 0) + 1
    if chapters:
        print("Live pages by chapter:")
        for name, count in sorted(chapters.items(), key=lambda kv: -kv[1]):
            print(f"  {count:4d}  {name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Scrape the UBC Vancouver Academic Calendar into data/pages/.")
    ap.add_argument("--editions", default=",".join(config.EDITIONS),
                    help="comma-separated: live, archive (default from config).")
    ap.add_argument("--limit", type=int, default=0, help="cap number of pages fetched (0 = no cap).")
    ap.add_argument("--delay", type=float, default=config.CRAWL_DELAY, help="seconds between requests.")
    ap.add_argument("--dry-run", action="store_true", help="enumerate + print counts only; fetch nothing.")
    ap.add_argument("--sample", action="store_true", help="fetch only the representative SAMPLE_PATHS.")
    args = ap.parse_args()

    editions = [e.strip() for e in args.editions.split(",") if e.strip()]
    crawl(editions, args.limit, args.delay, args.dry_run, args.sample)


if __name__ == "__main__":
    main()
