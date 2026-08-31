"""
Tier 1 — retrieval metrics. Deterministic, no LLM, instant, free.

This is the fast inner loop for tuning retrieval: it asks "did the retriever surface the
right excerpt?" purely by comparing the ids it returned against the gold ids in the test
set. No judge model, no embeddings beyond the query embedding the retriever already does.

Three standard metrics, each computed per question over the ranked list of returned ids,
then averaged across all questions:

    hit@k     did ANY gold id land in the top-k?            (1 or 0)  -> mean
    recall@k  what FRACTION of gold ids landed in the top-k?           -> mean
    MRR       1 / rank of the FIRST gold hit (0 if none)               -> mean

Run it (needs LM Studio for the query embeddings + a built index):
    python -m eval.retrieval_metrics
    python -m eval.retrieval_metrics --k 3 --limit 5
"""

from __future__ import annotations

import argparse
import json

from src import config, retrieve

# ----------------------------------------------------------------------------------------
# Pure metric functions. These take plain lists of ids, so they are fully deterministic
# and unit-testable with no LM Studio, no index, no network.
# ----------------------------------------------------------------------------------------


def hit_at_k(retrieved_ids: list[int], gold_ids: list[int], k: int) -> float:
    """1.0 if at least one gold id appears in the top-k retrieved ids, else 0.0."""
    top_k = set(retrieved_ids[:k])
    return 1.0 if top_k & set(gold_ids) else 0.0


def recall_at_k(retrieved_ids: list[int], gold_ids: list[int], k: int) -> float:
    """Fraction of the gold ids that appear in the top-k retrieved ids."""
    if not gold_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    found = top_k & set(gold_ids)
    return len(found) / len(gold_ids)


def reciprocal_rank(retrieved_ids: list[int], gold_ids: list[int]) -> float:
    """1 / (rank of the first gold hit). 0.0 if no gold id is in the list.

    Averaging this across questions gives MRR (Mean Reciprocal Rank).
    """
    gold = set(gold_ids)
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in gold:
            return 1.0 / rank
    return 0.0


# ----------------------------------------------------------------------------------------
# Runner: drive the retriever over the test set and aggregate the metrics above.
# (This part DOES need LM Studio — to embed each query — and a built index.)
# ----------------------------------------------------------------------------------------


def load_testset(path=config.TESTSET_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["items"]


def evaluate_retrieval(testset: list[dict], k: int) -> dict:
    """Run retrieval for every question and return aggregate + per-item metrics.

    `k` controls both how many excerpts we retrieve and the @k in the metrics, so the eval
    measures retrieval at the depth it reports.
    """
    per_item = []
    for item in testset:
        results = retrieve.retrieve(item["question"], top_k=k)
        retrieved_ids = [r.id for r in results]
        gold_ids = item["gold_ids"]
        per_item.append(
            {
                "id": item["id"],
                "gold_ids": gold_ids,
                "retrieved_ids": retrieved_ids,
                "hit": hit_at_k(retrieved_ids, gold_ids, k),
                "recall": recall_at_k(retrieved_ids, gold_ids, k),
                "rr": reciprocal_rank(retrieved_ids, gold_ids),
            }
        )

    n = len(per_item) or 1  # avoid divide-by-zero on an empty test set
    aggregate = {
        "k": k,
        "num_questions": len(per_item),
        f"hit@{k}": sum(x["hit"] for x in per_item) / n,
        f"recall@{k}": sum(x["recall"] for x in per_item) / n,
        "mrr": sum(x["rr"] for x in per_item) / n,
    }
    return {"aggregate": aggregate, "per_item": per_item}


def _print_report(report: dict) -> None:
    agg = report["aggregate"]
    k = agg["k"]
    hit = agg[f"hit@{k}"]
    recall = agg[f"recall@{k}"]
    print(f"\nRetrieval metrics over {agg['num_questions']} questions (k={k}):")
    print(f"  hit@{k}    : {hit:.3f}")
    print(f"  recall@{k} : {recall:.3f}")
    print(f"  MRR       : {agg['mrr']:.3f}")

    print("\nPer-question ([+] = a gold id was retrieved):")
    for x in report["per_item"]:
        mark = "[+]" if x["hit"] else "[ ]"
        print(
            f"  {mark} {x['id']}  gold={x['gold_ids']}  "
            f"retrieved={x['retrieved_ids']}  rr={x['rr']:.3f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Tier-1 retrieval metrics.")
    parser.add_argument("--k", type=int, default=config.EVAL_K, help="retrieval depth / @k")
    parser.add_argument("--limit", type=int, default=None, help="only the first N questions")
    args = parser.parse_args()

    testset = load_testset()
    if args.limit:
        testset = testset[: args.limit]

    report = evaluate_retrieval(testset, k=args.k)
    _print_report(report)


if __name__ == "__main__":
    main()
