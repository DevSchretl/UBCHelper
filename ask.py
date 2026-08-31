"""
ask.py — the tiny CLI that runs the whole naive-RAG loop for one question.

    retrieve(question)  ->  generate_answer(question, excerpts)  ->  print

Usage (from the project root, with the venv active):
    python ask.py "What are the prerequisites for CPSC 210?"
    python ask.py --top-k 6 "How many credits does the B.Sc. require?"
    python ask.py --show-context "What is the academic standing policy?"

Prerequisites:
    1. Keys in `.env` (copy `.env.example`): OPENAI_API_KEY for query embeddings and
       ANTHROPIC_API_KEY for generation (the default backend).
    2. The index built once:  python -m src.ingest
"""

from __future__ import annotations

import argparse

from src import config, generate, pipeline, retrieve, trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the UBC academic-calendar RAG advisor a question.")
    parser.add_argument("question", help="your calendar question (wrap it in quotes)")
    parser.add_argument(
        "--top-k",
        type=int,
        default=config.TOP_K,
        help=f"how many calendar excerpts to retrieve (default: {config.TOP_K})",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="also print the full text of the calendar excerpts sent to the model",
    )
    parser.add_argument(
        "--mode",
        choices=["dense", "hybrid", "hybrid_rerank"],
        default=config.RETRIEVAL_MODE,
        help=f"retrieval pipeline to use (default: {config.RETRIEVAL_MODE})",
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="route the question (Phase 4): simple -> fast retriever, complex -> agent",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="print every internal step and the exact prompts sent to the APIs "
             "(most informative with --adaptive)",
    )
    args = parser.parse_args()

    if args.trace:
        trace.enable()

    # 1. RETRIEVE (+ optionally route). --adaptive sends the question through the Phase-4
    # pipeline, which classifies it and picks the simple or agentic path; otherwise we run
    # the plain retrieve -> generate loop with the chosen --mode.
    if args.adaptive:
        print("\nThinking ...\n")
        result = pipeline.answer(args.question, top_k=args.top_k, mode=args.mode)
        results, answer = result["results"], result["answer"]
        print(f"Route: {result['route']}")
    else:
        results = retrieve.retrieve(args.question, top_k=args.top_k, mode=args.mode)
        answer = None

    # Show which excerpts grounded the answer (titles + similarity scores). This makes
    # the retrieval step visible, which is the whole point of the learning exercise.
    print("\nRetrieved excerpts:")
    for r in results:
        print(f"  [{r.score:.3f}] (id={r.id}) {r.recipe['title']}")

    if args.show_context:
        print("\n--- context sent to the model ---")
        print(generate.format_context(results))
        print("--- end context ---")

    # 2. GENERATE — have the LLM answer, grounded in those excerpts (the adaptive path
    # already produced the answer above).
    if answer is None:
        print("\nThinking ...\n")
        answer = generate.generate_answer(args.question, results)

    print("\nAnswer:")
    print(answer)


if __name__ == "__main__":
    main()
