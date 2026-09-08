"""Spend and abuse controls for the public demo.

The demo answers unauthenticated questions using three paid APIs (OpenAI embeddings,
Cohere rerank, Anthropic generation), so the guiding rule is that the worst case has to be
*degradation*, never a surprise bill. Two independent limits enforce that:

    per-IP     a sliding window (hour + day) so one visitor cannot monopolise the demo
    global     a hard daily ceiling on paid API calls; once hit, live querying is refused
               and the UI falls back to the precomputed example runs. The site stays up.

The global ceiling counts **API calls, not dollars**. A call count is exact and knowable
up front (a simple-route run is 2 LLM calls + 1 embed + 1 rerank; a complex run is 3 LLM
calls and up to 3 of each retrieval call), whereas a dollar figure drifts every time a
provider changes its price list. Money is shown to the operator as an estimate derived
from PRICES below, but it is never what the limiter enforces.

IP addresses are stored only as salted SHA-256. The limiter needs to recognise a repeat
visitor, which a hash does exactly as well as an address — so the demo keeps no PII.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------------------
# Knobs (all overridable in the environment; the defaults suit a free-tier portfolio demo)
# --------------------------------------------------------------------------------------
DB_PATH = Path(os.getenv("DEMO_DB_PATH", "/tmp/ubchelper-demo.sqlite3"))
IP_SALT = os.getenv("DEMO_IP_SALT", "change-me-in-production")

DAILY_LLM_CALLS = int(os.getenv("DEMO_DAILY_LLM_CALLS", "400"))
IP_PER_HOUR = int(os.getenv("DEMO_IP_PER_HOUR", "6"))
IP_PER_DAY = int(os.getenv("DEMO_IP_PER_DAY", "20"))

MAX_QUESTION_CHARS = int(os.getenv("DEMO_MAX_QUESTION_CHARS", "300"))
MIN_QUESTION_CHARS = 3

# USD per call, for the operator-facing estimate only — never used for enforcement.
# Refresh these from the providers' current pricing; being stale costs nothing but accuracy.
PRICES = {
    "llm": float(os.getenv("DEMO_PRICE_LLM", "0.0015")),      # one Haiku call, ~2.5k tokens
    "embed": float(os.getenv("DEMO_PRICE_EMBED", "0.000001")),  # one short query embedding
    "rerank": float(os.getenv("DEMO_PRICE_RERANK", "0.002")),   # one Cohere rerank search
}

HOUR = 3600
DAY = 86400

# Which trace events correspond to a paid API call, and which counter each feeds. Every paid
# call announces itself in the stream, so tallying these is exact rather than estimated — and
# it stays correct on its own if the pipeline's shape changes. Shared by every delivery mode
# so the three of them cannot drift apart on what counts as spend.
PAID_EVENT_KINDS = {
    "llm_call": "llm",          # one generation (route, decompose, or answer)
    "retrieval_start": "embed",  # one query embedding
    "shortlist": "rerank",       # one Cohere rerank (hybrid_rerank mode only)
}


def tally(counts: dict, event: dict) -> None:
    """Fold one trace event into a {llm, embed, rerank} tally, in place."""
    bucket = PAID_EVENT_KINDS.get(event.get("kind"))
    if bucket:
        counts[bucket] = counts.get(bucket, 0) + 1


@dataclass
class Decision:
    """The outcome of a limit check. `retry_after` is seconds, 0 when not applicable."""

    allowed: bool
    reason: str = ""
    retry_after: int = 0
    # True when the *global* budget is what blocked this, so the UI can switch to
    # cached-examples-only mode rather than telling the visitor to slow down.
    budget_exhausted: bool = False


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{IP_SALT}:{ip}".encode()).hexdigest()


def client_ip(request) -> str:
    """The visitor's address, accounting for the reverse proxy in front of the app.

    Hugging Face Spaces (like any hosted platform) terminates TLS upstream, so
    `request.client.host` is the proxy for every visitor. Reading the first hop of
    X-Forwarded-For is what separates per-visitor limits from one global limit applied to
    everybody — getting this wrong silently rate-limits the whole internet as one IP.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init() -> None:
    """Create the tables. Safe to call on every startup."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS usage ("
            "  day TEXT PRIMARY KEY, runs INT DEFAULT 0, llm INT DEFAULT 0,"
            "  embed INT DEFAULT 0, rerank INT DEFAULT 0)"
        )
        conn.execute("CREATE TABLE IF NOT EXISTS hits (ip_hash TEXT, ts REAL)")
        conn.execute("CREATE INDEX IF NOT EXISTS hits_ts ON hits(ts)")


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def validate_question(raw: str) -> tuple[str, str]:
    """Clean and bounds-check a question. Returns (question, error) — error empty if OK.

    Runs before any paid call, so a junk request costs nothing.
    """
    question = "".join(ch for ch in (raw or "") if ch.isprintable()).strip()
    if len(question) < MIN_QUESTION_CHARS:
        return "", "Please enter a question."
    if len(question) > MAX_QUESTION_CHARS:
        return "", f"Questions are limited to {MAX_QUESTION_CHARS} characters."
    return question, ""


def check(ip_hash: str) -> Decision:
    """Decide whether this visitor may run a live query right now."""
    now = time.time()
    with closing(_connect()) as conn, conn:
        # Age out anything older than the widest window; keeps the table small forever.
        conn.execute("DELETE FROM hits WHERE ts < ?", (now - DAY,))

        spent = conn.execute(
            "SELECT llm FROM usage WHERE day = ?", (_today(),)
        ).fetchone()
        if spent and spent[0] >= DAILY_LLM_CALLS:
            # Kept neutral about what else is on offer: the FastAPI and static builds can
            # fall back to precomputed runs, the Gradio build has none, and this module is
            # shared by all three.
            return Decision(
                allowed=False,
                reason="The demo's daily API budget is used up. The live pipeline resets "
                       "at 00:00 UTC.",
                budget_exhausted=True,
            )

        hour_count = conn.execute(
            "SELECT COUNT(*) FROM hits WHERE ip_hash = ? AND ts > ?", (ip_hash, now - HOUR)
        ).fetchone()[0]
        if hour_count >= IP_PER_HOUR:
            oldest = conn.execute(
                "SELECT MIN(ts) FROM hits WHERE ip_hash = ? AND ts > ?",
                (ip_hash, now - HOUR),
            ).fetchone()[0]
            wait = max(1, int(oldest + HOUR - now))
            return Decision(
                allowed=False,
                reason=f"Rate limit: {IP_PER_HOUR} live questions per hour. "
                       f"Try again in about {max(1, round(wait / 60))} minutes.",
                retry_after=wait,
            )

        day_count = conn.execute(
            "SELECT COUNT(*) FROM hits WHERE ip_hash = ? AND ts > ?", (ip_hash, now - DAY)
        ).fetchone()[0]
        if day_count >= IP_PER_DAY:
            return Decision(
                allowed=False,
                reason=f"Rate limit: {IP_PER_DAY} live questions per day.",
                retry_after=DAY,
            )

    return Decision(allowed=True)


def reserve(ip_hash: str) -> None:
    """Record that this visitor started a run (counts against their window immediately).

    Charged on start rather than on success so that a run which errors out — or a visitor
    who reloads mid-stream — still consumes their slot. The paid calls were made either way.
    """
    with closing(_connect()) as conn, conn:
        conn.execute("INSERT INTO hits (ip_hash, ts) VALUES (?, ?)", (ip_hash, time.time()))


def record(llm: int = 0, embed: int = 0, rerank: int = 0) -> None:
    """Add one finished run's actual API call counts to today's global total."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO usage (day, runs, llm, embed, rerank) VALUES (?, 1, ?, ?, ?) "
            "ON CONFLICT(day) DO UPDATE SET runs = runs + 1, llm = llm + ?, "
            "embed = embed + ?, rerank = rerank + ?",
            (_today(), llm, embed, rerank, llm, embed, rerank),
        )


def snapshot() -> dict:
    """Today's usage, for /api/health and the UI's budget badge."""
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT runs, llm, embed, rerank FROM usage WHERE day = ?", (_today(),)
        ).fetchone()
    runs, llm, embed, rerank = row if row else (0, 0, 0, 0)
    return {
        "day": _today(),
        "runs": runs,
        "llm_calls": llm,
        "llm_calls_limit": DAILY_LLM_CALLS,
        "llm_calls_remaining": max(0, DAILY_LLM_CALLS - llm),
        "budget_exhausted": llm >= DAILY_LLM_CALLS,
        "estimated_cost_usd": round(
            llm * PRICES["llm"] + embed * PRICES["embed"] + rerank * PRICES["rerank"], 4
        ),
        "per_ip_hour": IP_PER_HOUR,
        "per_ip_day": IP_PER_DAY,
    }
