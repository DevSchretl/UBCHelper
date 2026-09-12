"""
Central configuration — every tunable lives here, nothing is hard-coded elsewhere.

Ported from RAGChef. The retrieval / generation / eval knobs are domain-agnostic and kept
as-is (just re-prefixed UBCAL_); the recipe-CSV corpus block is replaced by the calendar
scrape/chunk block below. Environment overrides can live in a `.env` at the project root
(copy `.env.example`).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
# PROJECT_ROOT is this file's grandparent:  <root>/src/config.py -> <root>
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env before reading settings (real env vars still win — load_dotenv won't override).
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
PAGES_DIR = DATA_DIR / "pages"          # raw crawl (gitignored): one JSON record per page
MANIFEST_PATH = PAGES_DIR / "manifest.json"   # url -> current snapshot (conditional-GET state)
COURSES_PATH = DATA_DIR / "courses.jsonl"     # optional structured course/prereq table
INDEX_DIR = PROJECT_ROOT / "index"      # built by ingest.py; gitignored

# Where ingest.py writes the index (the "vector store"). Two small files:
EMBEDDINGS_PATH = INDEX_DIR / "embeddings.npy"   # float32 matrix, shape (N, dim)
METADATA_PATH = INDEX_DIR / "metadata.json"      # list of N chunk records (id-aligned)

# ======================================================================================
# Data layer: scraping the UBC Vancouver Academic Calendar
# ======================================================================================
# The corpus is built to be hard for naive top-k RAG:
#   - concurrent editions (2026/27 live + a 2025/26 archive slice), and
#   - cohort-split requirement pages disambiguated only by page title.
# See docs / the scrape plan for the reasoning behind the scope below.

CALENDAR_BASE_URL = os.getenv("UBCAL_BASE_URL", "https://vancouver.calendar.ubc.ca")
ARCHIVE_BASE_URL = os.getenv("UBCAL_ARCHIVE_BASE_URL", "https://archive.calendar.ubc.ca")

# Sitemap index (6 sub-sitemaps of readable aliases) — primary URL discovery for the live site.
SITEMAP_URL = CALENDAR_BASE_URL + "/sitemap.xml"

# Editions. The live site serves 2026/27; the 2025/26 edition is a frozen static mirror of the
# same Drupal theme under this archive subdirectory.
LIVE_EDITION_YEAR = "2026/27"
ARCHIVE_EDITION_YEAR = "2025/26"
ARCHIVE_EDITION_DIR = "vancouver/2526"          # archive.calendar.ubc.ca/vancouver/2526/<path>/index.html

# Which editions to crawl (comma-separated): "live", "archive", or both.
EDITIONS = os.getenv("UBCAL_EDITIONS", "live,archive").split(",")

# --- Scope: LIVE 2026/27 = every faculty/college/school + campus-wide policies (+ the course
# subjects below). A live URL is in scope if its path starts with one of these prefixes (or
# exactly matches a course-subject path).
#
# This used to name the Faculty of Science subtree plus the five cohort-split programs
# individually. Widening to the whole chapter picks up the remaining faculties (Applied Science,
# Medicine, Education, Land & Food Systems, and the rest) without having to enumerate them, and
# the cohort-split programs it used to list are all children of it anyway.
LIVE_SCOPE_PREFIXES = [
    "faculties-colleges-and-schools",
    "campus-wide-policies-and-regulations",
]

# --- Scope: ARCHIVE 2025/26 = NARROW collision slice. Only the requirement-bearing subtrees
# where editions collide (general B.Sc. + CS + the cohort programs + course subjects). Derived
# from the live path_keys that match these prefixes (the archive has no sitemap).
ARCHIVE_SCOPE_PREFIXES = [
    "faculties-colleges-and-schools/faculty-science/bachelor-science",
    "faculties-colleges-and-schools/faculty-science/bachelor-computer-science",
    "faculties-colleges-and-schools/faculty-arts/bachelor-arts",
    "faculties-colleges-and-schools/faculty-arts/bachelor-media-studies",
    "faculties-colleges-and-schools/faculty-commerce-and-business-administration/bachelor-commerce",
    "faculties-colleges-and-schools/vancouver-school-economics/bachelor-international-economics",
    "faculties-colleges-and-schools/faculty-forestry-and-environmental-stewardship/bsc-natural-resources-students-starting-september-2024",
    "faculties-colleges-and-schools/faculty-forestry-and-environmental-stewardship/bsc-degrees-students-who-started-prior-september-2024",
]

# The index page that lists every subject, which enumerate_subjects() reads. Note this is the
# "Courses by Subject" sub-page, not the /course-descriptions chapter landing page, which links
# only to its own table of contents.
COURSE_SUBJECT_INDEX_PATH = "course-descriptions/courses-subject"

# Course descriptions: one page per subject (exact-path match). These are taxonomy-term pages
# the sitemap omits, so scrape.enumerate_subjects() discovers the full live set from the
# course-descriptions index at crawl time; this list is the fallback if that fetch fails.
COURSE_SUBJECT_PATHS = [
    "course-descriptions/subject/cpscv",
    "course-descriptions/subject/mathv",
    "course-descriptions/subject/statv",
]

# The ARCHIVE edition deliberately mirrors only these three subjects, not every subject the live
# crawl finds. The archive exists to create edition collisions on requirement-bearing pages (see
# ARCHIVE_SCOPE_PREFIXES below); mirroring ~200 more subject pages would double the crawl and
# blunt that trap into general near-duplicate noise without testing anything new.
ARCHIVE_SUBJECT_PATHS = [
    "course-descriptions/subject/cpscv",
    "course-descriptions/subject/mathv",
    "course-descriptions/subject/statv",
]

# Robots.txt Disallow prefixes we must never fetch (belt-and-suspenders; the sitemap won't
# list these anyway).
ROBOTS_DISALLOW_PREFIXES = [
    "admin/", "search", "user/", "node/add", "comment/reply", "filter/tips", "media/oembed",
]

# Path segments excluded from the live crawl even though they sit inside a scope prefix.
# `academic-staff` is a per-faculty roster of people (114 pages; one of them is a single
# 159,000-character list of names). Nothing a student asks about courses, programs or policies
# is answered by a staff directory, so these pages would only add retrieval distractors, and
# the largest of them are individually too big for the embedding model to accept.
EXCLUDE_PATH_SEGMENTS = [
    s for s in os.getenv("UBCAL_EXCLUDE_PATH_SEGMENTS", "academic-staff").split(",") if s
]

# A handful of structurally different pages for the extraction smoke test (`scrape --sample`):
# a CS requirements page (15 tables), both B.A. cohort pages, a policy page, and a course page.
SAMPLE_PATHS = [
    "faculties-colleges-and-schools/faculty-science/bachelor-science/computer-science",
    "faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202324-or-earlier",
    "faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later",
    "campus-wide-policies-and-regulations/academic-standing",
    "course-descriptions/subject/cpscv",
]

# --- Politeness (the site's robots.txt asks for Crawl-delay: 10) ---
CRAWL_DELAY = float(os.getenv("UBCAL_CRAWL_DELAY", "10"))     # seconds between requests
REQUEST_TIMEOUT = float(os.getenv("UBCAL_REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("UBCAL_MAX_RETRIES", "3"))        # on 429 / 5xx
BACKOFF_BASE = float(os.getenv("UBCAL_BACKOFF_BASE", "10"))   # exponential: base * 2**attempt
USER_AGENT = os.getenv(
    "UBCAL_USER_AGENT",
    "UBCHelper-RAG-demo/0.1 (educational, non-commercial; respects robots.txt)",
)

# --- Chunking (calendar pages are long/heterogeneous, unlike one-recipe-one-doc) ---
CHUNK_MAX_CHARS = int(os.getenv("UBCAL_CHUNK_MAX_CHARS", "1800"))
CHUNK_OVERLAP = int(os.getenv("UBCAL_CHUNK_OVERLAP", "150"))
CHUNK_MIN_CHARS = int(os.getenv("UBCAL_CHUNK_MIN_CHARS", "120"))  # merge tiny trailing chunks

# Hard ceiling, enforced even on blocks that are otherwise kept whole (requirement tables).
# text-embedding-3-small rejects any input over 8192 tokens, and a single oversized chunk kills
# the whole ingest mid-batch with nothing saved. Calendar text tokenizes densely (tables, codes,
# names), so this is set well under 8192 * 4 chars to stay safe on the worst-tokenizing pages.
CHUNK_HARD_MAX_CHARS = int(os.getenv("UBCAL_CHUNK_HARD_MAX_CHARS", "16000"))

# ======================================================================================
# Retrieval / generation / eval knobs (domain-agnostic; used once the engine is copied in)
# ======================================================================================
TOP_K = int(os.getenv("UBCAL_TOP_K", "4"))

RETRIEVAL_MODE = os.getenv("UBCAL_RETRIEVAL_MODE", "hybrid_rerank")  # dense | hybrid | hybrid_rerank

# Stage-1 recall width. These were 20/20/20; measured at 50 on the 12-question test set,
# hit@4 went 0.667 -> 0.833 and MRR 0.542 -> 0.667, at both the 3,770- and 16,576-chunk corpus
# sizes. The win is the reranker getting a deeper shortlist to work with: the golds it was
# missing sat at stage-1 ranks 20-50, where it never saw them. Cost is unchanged in API calls
# (rerank takes the shortlist in one request), only the documents per request go up.
DENSE_K = int(os.getenv("UBCAL_DENSE_K", "50"))
SPARSE_K = int(os.getenv("UBCAL_SPARSE_K", "50"))
RRF_K = int(os.getenv("UBCAL_RRF_K", "60"))
RERANK_CANDIDATES = int(os.getenv("UBCAL_RERANK_CANDIDATES", "50"))
RERANKER_MODEL = os.getenv("UBCAL_RERANKER_MODEL", "rerank-v3.5")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")

LLM_BACKEND = os.getenv("UBCAL_LLM_BACKEND", "anthropic")            # anthropic | local
ANTHROPIC_MODEL = os.getenv("UBCAL_ANTHROPIC_MODEL", "claude-haiku-4-5")

OPENAI_BASE_URL = os.getenv("UBCAL_BASE_URL_LLM", "http://localhost:1234/v1")
OPENAI_API_KEY = os.getenv("UBCAL_API_KEY", "lm-studio")
CHAT_MODEL = os.getenv("UBCAL_CHAT_MODEL", "google/gemma-4-e4b")

# Embeddings — hosted OpenAI API. The SAME model must embed documents (ingest) and queries.
EMBED_BASE_URL = os.getenv("UBCAL_EMBED_BASE_URL")   # None -> real OpenAI endpoint
EMBED_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("UBCAL_EMBED_MODEL", "text-embedding-3-small")

# Per-request timeout for the hosted APIs. The SDK defaults are 300-600 s, which on a demo
# serving one run at a time means a single stalled call holds the only slot for ten minutes.
# Real calls take 1-5 s, so a minute is generous.
API_TIMEOUT = float(os.getenv("UBCAL_API_TIMEOUT", "60"))

TEMPERATURE = float(os.getenv("UBCAL_TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("UBCAL_MAX_TOKENS", "1024"))

AGENT_MAX_SUBQ = int(os.getenv("UBCAL_AGENT_MAX_SUBQ", "3"))
AGENT_SUBQ_TOP_K = int(os.getenv("UBCAL_AGENT_SUBQ_TOP_K", str(TOP_K)))
SYNTH_CONTEXT_K = int(os.getenv("UBCAL_SYNTH_CONTEXT_K", "8"))

EVAL_DIR = PROJECT_ROOT / "eval"
TESTSET_PATH = EVAL_DIR / "testset.json"
GENERAL_TESTSET_PATH = EVAL_DIR / "testset.general.json"
REPORTS_DIR = EVAL_DIR / "reports"
REPORT_PATH = REPORTS_DIR / "report.md"
ABLATION_REPORT_PATH = REPORTS_DIR / "ablation.md"
HISTORY_PATH = REPORTS_DIR / "history.csv"
EVAL_K = int(os.getenv("UBCAL_EVAL_K", str(TOP_K)))
JUDGE_MODEL = os.getenv("UBCAL_JUDGE_MODEL", CHAT_MODEL)
