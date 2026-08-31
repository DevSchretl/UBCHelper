"""
make_testset — generate a corpus-grounded test set from the indexed calendar chunks.

A test set is only meaningful if its gold ids point at chunks that are actually in the
index. So instead of hand-writing questions, we sample real indexed chunks and ask the
local LLM to write, for each one, a specific question that chunk answers plus a concise
reference answer grounded in it. The chunk's own id becomes the gold id — which is what
makes the deterministic retrieval metrics (hit@k etc.) work.

Landing pages and tiny fragments make useless questions, so sampling skips chunks with
page_type == "landing" or very short text.

This produces *candidates*. The intended workflow is to then CURATE by hand — delete vague
or wrong questions, fix wording, and (for near-duplicate chunks, e.g. the same requirement
in the 2025/26 vs 2026/27 edition or across cohort pages) add sibling ids to gold_ids —
and commit the frozen result. Start small and grow.

Run (needs a built index; uses the local LM Studio backend — see config.CHAT_MODEL):
    python -m eval.make_testset --num 15 --out eval/testset.json
"""

from __future__ import annotations

import argparse
import json
import random

from openai import OpenAI

from src import config, retrieve
from eval.judge import _extract_json, JudgeParseError  # reuse robust JSON parsing

_MIN_CHUNK_CHARS = 300  # too little text to ground a specific question + answer

_SYSTEM = (
    "You write evaluation data for a UBC academic-calendar question-answering system. "
    "Respond with ONLY valid JSON — no prose, no markdown, no code fences."
)


def _prompt(chunk: dict) -> str:
    return (
        "Given the CALENDAR EXCERPT below, write ONE specific question that a UBC student "
        "might ask and that THIS excerpt answers well, plus a concise reference answer "
        "grounded only in the excerpt. The question should be specific (name the course, "
        "program, or policy it is about — and the student cohort or calendar year when the "
        "excerpt is cohort- or edition-specific) and answerable from the excerpt.\n\n"
        f"EXCERPT TITLE: {chunk['title']}\n"
        f"SOURCE URL: {chunk['url']}\n"
        f"EXCERPT TEXT: {chunk['text']}\n\n"
        'Return JSON: {"question": "<question>", "reference_answer": "<answer>"}'
    )


def _eligible(chunk: dict) -> bool:
    return chunk.get("page_type") != "landing" and len(chunk.get("text", "")) >= _MIN_CHUNK_CHARS


def generate(num: int, seed: int) -> list[dict]:
    """Sample `num` eligible indexed chunks and turn each into a test item."""
    _, chunks = retrieve._load_index()  # the indexed corpus (id-aligned metadata)
    pool = [c for c in chunks if _eligible(c)]
    print(f"Sampling from {len(pool)} eligible chunks (of {len(chunks)} indexed).")
    if num > len(pool):
        num = len(pool)
    sampled = random.Random(seed).sample(pool, num)

    client = OpenAI(base_url=config.OPENAI_BASE_URL, api_key=config.OPENAI_API_KEY)
    items: list[dict] = []
    for chunk in sampled:
        response = client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _prompt(chunk)},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        try:
            parsed = _extract_json(response.choices[0].message.content or "")
            question = parsed["question"].strip()
            reference_answer = parsed["reference_answer"].strip()
        except (JudgeParseError, KeyError, AttributeError, TypeError):
            print(f"  skipped chunk {chunk['id']} ({chunk['title']!r}): bad JSON")
            continue

        items.append(
            {
                "id": f"q{len(items) + 1:03d}",
                "question": question,
                "reference_answer": reference_answer,
                "gold_ids": [chunk["id"]],
                "source_chunk_id": chunk["id"],
            }
        )
        print(f"  [{len(items)}] id={chunk['id']:<4} {chunk['title']}")
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a corpus-grounded eval test set.")
    parser.add_argument("--num", type=int, default=15, help="how many questions to generate")
    parser.add_argument("--seed", type=int, default=42, help="sampling seed (reproducible)")
    parser.add_argument("--out", default=str(config.TESTSET_PATH), help="output JSON path")
    args = parser.parse_args()

    print(f"Generating {args.num} questions from the indexed corpus "
          f"(model={config.CHAT_MODEL}) ...")
    items = generate(args.num, args.seed)

    payload = {
        "description": (
            "Auto-generated, corpus-grounded test set (eval/make_testset.py). Each gold id "
            "points at an indexed calendar chunk. REVIEW AND CURATE before trusting the "
            "numbers: delete vague/wrong items, fix wording, add sibling ids to gold_ids "
            "for near-duplicate chunks (edition/cohort twins)."
        ),
        "items": items,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(items)} questions to {args.out}")


if __name__ == "__main__":
    main()
