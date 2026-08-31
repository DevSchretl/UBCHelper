"""
Tier 2 — RAGAS-style generation metrics, judged by the local LLM.

These four metrics follow the RAGAS definitions, but instead of pulling in the heavy
RAGAS + LangChain dependency tree (which fights hard on new Python interpreters), each
metric is a small, self-contained prompt to the judge model via the same OpenAI client we
use everywhere. Fully transparent, works on Python 3.14, no extra dependencies.

    faithfulness       fraction of the ANSWER's claims that are supported by the
                       retrieved excerpts.  Hallucination rate = 1 - faithfulness.
    answer_relevancy   how well the answer actually addresses the question (RAGAS trick:
                       generate questions the answer fits, embed them, compare to the real
                       question via cosine similarity).
    context_precision  of the retrieved excerpts, what fraction were relevant — rank-aware,
                       so relevant excerpts ranked higher score better.
    context_recall     does the retrieved context contain what's needed to reproduce the
                       reference answer (fraction of reference claims it supports).

Every score is in [0, 1], higher is better. The judge runs at temperature 0 for
determinism, and bad/unparseable JSON from the model degrades one metric to None for that
question rather than crashing the whole run.

NOTE: these are *directionally faithful* to canonical RAGAS, not numerically identical —
ideal for tracking relative change as you tune the system, which is the point.
"""

from __future__ import annotations

import json
import re
import time

import numpy as np
from openai import APIError, OpenAI

from src import config, embed

# Judge settings. Temperature 0 -> as deterministic as the model allows.
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 1536  # headroom so long claim arrays don't truncate into invalid JSON
RELEVANCY_NUM_QUESTIONS = 3  # how many questions to reverse-generate for answer_relevancy

_JSON_SYSTEM = "You are a strict evaluator. Respond with ONLY valid JSON — no prose, no markdown, no code fences."

# LM Studio constrains generation to a JSON *schema* (OpenAI "structured outputs" style),
# which guarantees both valid JSON and the exact shape each metric expects — so the model
# can't emit prose, fences, trailing commas, or the wrong keys. One schema per output shape.
def _claims_schema(verdict_key: str) -> dict:
    """Schema for {"claims": [{"claim": str, <verdict_key>: bool}, ...]} (faithfulness/recall)."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "claim": {"type": "string"},
                        verdict_key: {"type": "boolean"},
                    },
                    "required": ["claim", verdict_key],
                },
            }
        },
        "required": ["claims"],
    }


_QUESTIONS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
    "required": ["questions"],
}

_VERDICTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"verdicts": {"type": "array", "items": {"type": "boolean"}}},
    "required": ["verdicts"],
}

_client: OpenAI | None = None


class JudgeParseError(Exception):
    """Raised when the judge's reply can't be parsed into the expected JSON."""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=config.OPENAI_BASE_URL, api_key=config.OPENAI_API_KEY)
    return _client


def _extract_json(text: str):
    """Best-effort JSON extraction from a chat reply.

    Local models often wrap JSON in ```code fences``` or add a sentence around it, so we
    try a direct parse, then strip fences, then fall back to the outermost {...} or [...].
    """
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start, end = s.find(open_ch), s.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise JudgeParseError(text)


def _with_retries(fn, attempts: int = 3, base_delay: float = 1.0):
    """Call fn(), retrying transient LM Studio API errors with linear backoff.

    LM Studio can JIT-unload an idle model and return a transient 400 "Model unloaded"
    (an APIError); the next call reloads it. Without this, one blip sinks a long run.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except APIError:
            if attempt == attempts:
                raise
            time.sleep(base_delay * attempt)


def _chat_json(prompt: str, schema: dict, name: str):
    """Send one judging prompt and return the parsed JSON, shape-constrained by `schema`.

    response_format=json_schema makes LM Studio grammar-constrain the output to that exact
    schema, so the judge can't emit prose/fences/trailing commas or the wrong keys. We keep
    _extract_json as a defensive fallback.
    """
    client = _get_client()
    response = _with_retries(
        lambda: client.chat.completions.create(
            model=config.JUDGE_MODEL,
            messages=[
                {"role": "system", "content": _JSON_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=JUDGE_TEMPERATURE,
            max_tokens=JUDGE_MAX_TOKENS,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
        )
    )
    return _extract_json(response.choices[0].message.content or "")


def _join_contexts(contexts: list[str]) -> str:
    """Number the retrieved excerpts so the judge can refer to them by position."""
    return "\n\n".join(f"[{i}] {c}" for i, c in enumerate(contexts, start=1))


# ----------------------------------------------------------------------------------------
# The four metrics. Each returns a float in [0, 1]; each may raise JudgeParseError (or a
# KeyError/TypeError on an unexpected JSON shape), which judge_item turns into a None.
# ----------------------------------------------------------------------------------------


def supported_claims(answer: str, contexts: list[str]) -> tuple[int, int]:
    """Decompose ANSWER into atomic claims and count how many CONTEXT supports.

    Returns (supported, total). The ablation harness uses the raw counts (so an empty
    answer -> 0/0 is visible) while faithfulness just takes the ratio.
    """
    prompt = (
        "Break the ANSWER into atomic factual claims. For each claim decide whether it is "
        "supported by the CONTEXT (the retrieved calendar excerpts). A claim is supported only if "
        "the CONTEXT contains information that backs it up.\n\n"
        f"CONTEXT:\n{_join_contexts(contexts)}\n\n"
        f"ANSWER:\n{answer}\n\n"
        'Return JSON: {"claims": [{"claim": "<text>", "supported": true|false}, ...]}. '
        'If the answer makes no factual claims, return {"claims": []}.'
    )
    claims = _chat_json(prompt, _claims_schema("supported"), "faithfulness")["claims"]
    supported = sum(1 for c in claims if c.get("supported"))
    return supported, len(claims)


def faithfulness(answer: str, contexts: list[str]) -> float:
    """supported_claims / total_claims. Hallucination rate = 1 - this."""
    supported, total = supported_claims(answer, contexts)
    if total == 0:
        return 1.0  # nothing asserted -> nothing unfaithful
    return supported / total


def answer_relevancy(question: str, answer: str) -> float:
    """Mean cosine similarity between the real question and questions the answer fits.

    If the answer truly addresses the question, questions reverse-generated from it should
    look a lot like the original question in embedding space.
    """
    prompt = (
        f"Given the ANSWER below, generate {RELEVANCY_NUM_QUESTIONS} distinct questions "
        "that this answer would directly and completely answer.\n\n"
        f"ANSWER:\n{answer}\n\n"
        'Return JSON: {"questions": ["...", "..."]}.'
    )
    generated = _chat_json(prompt, _QUESTIONS_SCHEMA, "answer_relevancy")["questions"]
    if not generated:
        return 0.0
    vecs = embed.embed_texts([question] + list(generated))  # unit vectors
    sims = vecs[1:] @ vecs[0]  # cosine == dot, since normalized
    return float(np.clip(np.mean(sims), 0.0, 1.0))


def context_precision(question: str, reference_answer: str, contexts: list[str]) -> float:
    """Rank-aware precision: were relevant excerpts retrieved, and ranked near the top?"""
    prompt = (
        "For each retrieved CONTEXT, decide whether it is useful for answering the "
        "QUESTION, given the REFERENCE ANSWER. Output true if the context contains "
        "information useful to produce the reference answer, false otherwise.\n\n"
        f"QUESTION: {question}\n"
        f"REFERENCE ANSWER: {reference_answer}\n\n"
        f"CONTEXTS:\n{_join_contexts(contexts)}\n\n"
        'Return JSON: {"verdicts": [true|false, ...]} with one entry per context, in order.'
    )
    verdicts = [bool(v) for v in _chat_json(prompt, _VERDICTS_SCHEMA, "context_precision")["verdicts"]]
    total_relevant = sum(verdicts)
    if total_relevant == 0:
        return 0.0
    # Average precision: average of precision@i taken at each relevant rank i.
    hits = 0
    weighted = 0.0
    for i, relevant in enumerate(verdicts, start=1):
        if relevant:
            hits += 1
            weighted += hits / i
    return weighted / total_relevant


def context_recall(reference_answer: str, contexts: list[str]) -> float:
    """Fraction of the reference answer's claims that the retrieved context supports."""
    prompt = (
        "Break the REFERENCE ANSWER into atomic claims. For each claim decide whether it "
        "can be attributed to (is supported by) the CONTEXT.\n\n"
        f"CONTEXT:\n{_join_contexts(contexts)}\n\n"
        f"REFERENCE ANSWER:\n{reference_answer}\n\n"
        'Return JSON: {"claims": [{"claim": "<text>", "attributed": true|false}, ...]}.'
    )
    claims = _chat_json(prompt, _claims_schema("attributed"), "context_recall")["claims"]
    if not claims:
        return 1.0
    attributed = sum(1 for c in claims if c.get("attributed"))
    return attributed / len(claims)


# Maps metric name -> a zero-arg callable, so judge_item can run each in a uniform
# try/except and record which ones failed without aborting the whole evaluation.
def judge_item(
    question: str, answer: str, contexts: list[str], reference_answer: str
) -> dict:
    """Run all four metrics for one (question, answer, contexts) triple.

    Returns a dict of {metric: float|None, ..., "errors": [names that failed to parse]}.
    A None means the judge's reply for that metric couldn't be parsed — recorded, not
    fatal, so a single bad response never sinks a long run.
    """
    metrics = {
        "faithfulness": lambda: faithfulness(answer, contexts),
        "answer_relevancy": lambda: answer_relevancy(question, answer),
        "context_precision": lambda: context_precision(question, reference_answer, contexts),
        "context_recall": lambda: context_recall(reference_answer, contexts),
    }
    scores: dict = {}
    errors: list[str] = []
    for name, fn in metrics.items():
        try:
            scores[name] = round(float(fn()), 4)
        except (JudgeParseError, KeyError, TypeError, ValueError, IndexError):
            scores[name] = None
            errors.append(name)
    scores["errors"] = errors
    return scores
