"""
Generate — the "G" in RAG. Turn retrieved calendar excerpts + a question into a grounded answer.

The whole idea of RAG: instead of asking the LLM to answer from memory (where it may
hallucinate), we hand it real excerpts from the UBC Academic Calendar as context and
instruct it to answer *from that context*. The model becomes a reader/synthesizer over
retrieved facts.

`generate_answer` returns a string and never prints. That keeps it usable both from the
CLI (which prints the return value) and, later, from the Phase 3 eval loop (which runs
100 questions and must not spew to stdout).

Two backends produce the answer, selected by `config.LLM_BACKEND`:
  - "anthropic": Claude via the Anthropic API (the default, so the app runs without a
    local model server).
  - "local": any OpenAI-compatible local server (LM Studio, llama.cpp, vLLM, Ollama's
    OpenAI shim) via `/v1/chat/completions`.

Both paths take the same (system prompt, user turn) and return a plain string, so the
callers and the eval loop don't care which backend is active.
"""

from __future__ import annotations

from . import config, trace
from .retrieve import Result

# System prompt: defines the assistant's role and the grounding rule.
# The user only sees their question and the final answer — never the retrieved context —
# so the answer must read as standalone advice and must not point back at the numbered
# excerpt blocks. Two calendar-specific twists: (1) the calendar is authoritative and
# changes yearly, so the answer should hand the user the official page URL(s) carried on
# each excerpt; (2) the corpus deliberately contains colliding editions (2026/27 live vs
# 2025/26 archive) and cohort-split requirement pages, so the model must disambiguate.
SYSTEM_PROMPT = (
    "You are a UBC academic advisor. Answer the user's question using ONLY the excerpts "
    "from the UBC Vancouver Academic Calendar provided as context, but write the answer "
    "as if you simply know it. Do NOT mention or number the excerpts: the user cannot "
    'see them, so phrases like "Excerpt 3" are meaningless to them. You SHOULD, however, '
    "point the user to the official calendar page URL(s) shown with the excerpts for the "
    "authoritative and most current wording. Excerpts may come from different calendar "
    "editions (e.g. 2026/27 vs 2025/26) or different student cohorts — answer for the "
    "edition and cohort the question asks about, defaulting to the current 2026/27 "
    "calendar, and note when requirements differ between them. Keep the answer concise "
    "and focused directly on what was asked. If the excerpts do not contain enough "
    "information to answer, say so plainly rather than inventing requirements."
)

# Closed-book prompt: the "no-RAG" baseline for the ablation. The model answers from its
# own parametric memory with no retrieved context. We push it to commit to concrete
# specifics (rather than refuse) so its answer makes measurable claims to score for
# hallucination against the gold calendar excerpt.
CLOSED_BOOK_SYSTEM = (
    "You are a UBC academic advisor. Answer the user's question about UBC Vancouver "
    "courses, programs, and policies from your own knowledge, with concrete specifics "
    "(course codes, credit counts, requirements), kept concise. Give your single best "
    "answer; do not refuse or say you lack access to the official calendar."
)

# Both clients are created lazily and cached, so importing this module is cheap and only
# the backend actually in use gets constructed.
_openai_client = None
_anthropic_client = None


def _get_openai_client():
    """The OpenAI client pointed at the local server (LLM_BACKEND == 'local')."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(
            base_url=config.OPENAI_BASE_URL,
            api_key=config.OPENAI_API_KEY,
        )
    return _openai_client


def _get_anthropic_client():
    """The Anthropic client (LLM_BACKEND == 'anthropic'); reads ANTHROPIC_API_KEY."""
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def format_context(results: list[Result]) -> str:
    """Render retrieved calendar excerpts into a readable, numbered context block for the
    prompt. Each chunk's `text` already leads with its page title + section breadcrumb;
    the header line and Source URL make the excerpt scannable and citable."""
    blocks = []
    for n, r in enumerate(results, start=1):
        chunk = r.recipe  # engine-wide name for "the document record"
        blocks.append(
            f"[Excerpt {n}] {chunk['title']}\n"
            f"Source: {chunk['url']}\n"
            f"{chunk['text']}"
        )
    return "\n\n".join(blocks)


def build_user_turn(query: str, results: list[Result]) -> str:
    """Render the grounded user turn: the retrieved excerpts followed by the question."""
    context = format_context(results)
    return (
        f"Here are some excerpts from the UBC Vancouver Academic Calendar that may be "
        f"relevant:\n\n{context}\n\n"
        f"Question: {query}"
    )


def complete(system: str, user: str) -> str:
    """One-shot completion via the configured backend, for callers that build their own
    prompt (the Phase-4 router and agent) rather than the grounded calendar turn."""
    return _complete(system, user)


def _complete(system: str, user: str) -> str:
    """Dispatch one (system, user) turn to the configured backend and return the text.

    Every LLM call in the project funnels through here, so this is the one place that traces
    the exact prompt sent to the API (when tracing is on; a no-op otherwise).
    """
    model = config.ANTHROPIC_MODEL if config.LLM_BACKEND == "anthropic" else config.CHAT_MODEL
    trace.prompt(system, user, model)
    if config.LLM_BACKEND == "anthropic":
        text = _complete_anthropic(system, user)
    else:
        text = _complete_local(system, user)
    trace.response(text)
    return text


def _complete_local(system: str, user: str) -> str:
    """OpenAI-compatible local server via /v1/chat/completions."""
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_TOKENS,
    )
    return (response.choices[0].message.content or "").strip()


def _complete_anthropic(system: str, user: str) -> str:
    """Claude via the Anthropic API. `system` is a top-level arg, not a message.

    Note: current Claude models don't take sampling params (no `temperature`/`top_p`),
    so grounding is steered by SYSTEM_PROMPT rather than by config.TEMPERATURE.
    """
    client = _get_anthropic_client()
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def generate_answer(query: str, results: list[Result]) -> str:
    """Answer the question grounded in the retrieved calendar excerpts."""
    return _complete(SYSTEM_PROMPT, build_user_turn(query, results))


def generate_answer_closed_book(query: str) -> str:
    """Answer with NO retrieved context — the no-RAG baseline for the ablation harness."""
    return _complete(CLOSED_BOOK_SYSTEM, query)
