"""
Orchestrator — run the whole evaluation and record the result.

For every question in the frozen test set it does ONE retrieval pass, then (unless
--retrieval-only) generates an answer and judges it, computing both metric tiers:

    Tier 1 (retrieval) : hit@k, recall@k, MRR        -- deterministic, from eval/retrieval_metrics
    Tier 2 (generation): faithfulness, answer_relevancy, context_precision/recall  -- eval/judge

It writes two things to eval/reports/:
    report.md     ONE self-contained doc: summary metrics + every question's full test
                  data (question, reference answer, retrieved excerpts, answer, scores).
                  Overwritten each run.
    history.csv   ONE row per run -- the cross-run performance ledger (kept so you can
                  compare runs, e.g. phase1 vs phase2, since report.md only holds the last).

Run (needs an index built; the judge defaults to a local LM Studio server — see
config.JUDGE_MODEL):
    python -m eval.run_eval --name phase1-dense
    python -m eval.run_eval --retrieval-only        # fast: skip generation + judge
    python -m eval.run_eval --limit 3               # quick smoke test
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from statistics import mean

from src import config, generate, retrieve
from eval import judge
from eval import retrieval_metrics as rm

GEN_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def _mean_or_none(values: list[float]):
    vals = [v for v in values if v is not None]
    return round(mean(vals), 4) if vals else None


def run(testset: list[dict], k: int, do_judge: bool) -> dict:
    """Evaluate every test item and return the full report dict."""
    per_item = []
    for n, item in enumerate(testset, start=1):
        # --- Tier 1: retrieve once, score deterministically -----------------------------
        results = retrieve.retrieve(item["question"], top_k=k)
        retrieved_ids = [r.id for r in results]
        gold_ids = item["gold_ids"]
        record = {
            "id": item["id"],
            "question": item["question"],
            "reference_answer": item.get("reference_answer", ""),
            "gold_ids": gold_ids,
            "retrieved_ids": retrieved_ids,
            "retrieved_titles": [r.recipe["title"] for r in results],
            "retrieval": {
                "hit": rm.hit_at_k(retrieved_ids, gold_ids, k),
                "recall": rm.recall_at_k(retrieved_ids, gold_ids, k),
                "rr": rm.reciprocal_rank(retrieved_ids, gold_ids),
            },
        }

        # --- Tier 2: generate an answer, then judge it ----------------------------------
        if do_judge:
            contexts = [r.recipe["text"] for r in results]
            answer = generate.generate_answer(item["question"], results)
            record["answer"] = answer
            record["judge"] = judge.judge_item(
                item["question"], answer, contexts, item["reference_answer"]
            )
            faith = record["judge"]["faithfulness"]
            print(
                f"  [{n}/{len(testset)}] {item['id']}  hit={record['retrieval']['hit']:.0f}"
                f"  faithfulness={'-' if faith is None else f'{faith:.2f}'}"
            )
        else:
            print(f"  [{n}/{len(testset)}] {item['id']}  hit={record['retrieval']['hit']:.0f}")

        per_item.append(record)

    return _aggregate(per_item, k, do_judge)


def _aggregate(per_item: list[dict], k: int, do_judge: bool) -> dict:
    n = len(per_item) or 1
    retrieval = {
        "hit@k": round(sum(x["retrieval"]["hit"] for x in per_item) / n, 4),
        "recall@k": round(sum(x["retrieval"]["recall"] for x in per_item) / n, 4),
        "mrr": round(sum(x["retrieval"]["rr"] for x in per_item) / n, 4),
    }

    generation = None
    hallucination_rate = None
    if do_judge:
        generation = {
            m: _mean_or_none([x["judge"][m] for x in per_item]) for m in GEN_METRICS
        }
        if generation["faithfulness"] is not None:
            hallucination_rate = round(1.0 - generation["faithfulness"], 4)

    return {
        "run": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "k": k,
            "num_questions": len(per_item),
            "judged": do_judge,
            "retrieval_mode": config.RETRIEVAL_MODE,
            "chat_model": config.CHAT_MODEL,
            "judge_model": config.JUDGE_MODEL,
            "embedding_model": config.EMBEDDING_MODEL,
            "corpus_size": len(retrieve._load_index()[1]),  # indexed chunk count
        },
        "aggregate": {
            "retrieval": retrieval,
            "generation": generation,
            "hallucination_rate": hallucination_rate,
        },
        "per_item": per_item,
    }


# ----------------------------------------------------------------------------------------
# Output: a single, self-contained markdown report, plus the history.csv ledger.
# ----------------------------------------------------------------------------------------

HISTORY_COLUMNS = [
    "timestamp", "name", "k", "num_questions", "judged",
    "chat_model", "judge_model",
    "hit@k", "recall@k", "mrr",
    "faithfulness", "answer_relevancy", "context_precision", "context_recall",
    "hallucination_rate",
]


def _fmt(value) -> str:
    return "-" if value is None else f"{value:.3f}"


def write_report(report: dict, name: str):
    """Write the single markdown report and append one row to the history ledger."""
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORT_PATH.write_text(_render_markdown(report, name), encoding="utf-8")
    _append_history(report, name)
    return config.REPORT_PATH


def _render_markdown(report: dict, name: str) -> str:
    """One concise markdown doc: a summary table, then every question's full test data."""
    run = report["run"]
    agg = report["aggregate"]
    ret = agg["retrieval"]
    gen = agg["generation"]
    k = run["k"]

    # --- header + summary metric table ---
    lines = [
        f"# UBCHelper eval — {name}",
        "",
        f"{run['timestamp']} · {run['num_questions']} questions · k={k} · "
        f"judge {'on' if run['judged'] else 'off'}",
        "",
        f"Models: chat=`{run['chat_model']}`, judge=`{run['judge_model']}`, "
        f"embed=`{run['embedding_model']}` · corpus={run['corpus_size']} · "
        f"retrieval={run['retrieval_mode']}",
        "",
        "## Summary",
        "",
        "| metric | score |",
        "|--------|-------|",
        f"| hit@{k} | {_fmt(ret['hit@k'])} |",
        f"| recall@{k} | {_fmt(ret['recall@k'])} |",
        f"| MRR | {_fmt(ret['mrr'])} |",
    ]
    if gen is not None:
        lines += [
            f"| faithfulness | {_fmt(gen['faithfulness'])} |",
            f"| answer_relevancy | {_fmt(gen['answer_relevancy'])} |",
            f"| context_precision | {_fmt(gen['context_precision'])} |",
            f"| context_recall | {_fmt(gen['context_recall'])} |",
            f"| **hallucination_rate** | **{_fmt(agg['hallucination_rate'])}** |",
        ]

    # --- per-question detail: all test data, one block each ---
    lines += ["", "## Questions", ""]
    for x in report["per_item"]:
        r = x["retrieval"]
        marker = "hit" if r["hit"] else "miss"
        retrieved = " · ".join(
            f"[{i}] {t}" for i, t in zip(x["retrieved_ids"], x["retrieved_titles"])
        )
        lines += [
            f"### {x['id']} — {marker} — gold {x['gold_ids']}",
            "",
            f"**Q:** {x['question']}",
            "",
            f"**Reference:** {x['reference_answer']}",
            "",
            f"**Retrieved:** {retrieved}",
        ]
        if "judge" in x:
            j = x["judge"]
            lines += [
                "",
                f"**Answer:** {x['answer']}",
                "",
                f"**Scores:** rr {r['rr']:.2f} · faithfulness {_fmt(j['faithfulness'])} "
                f"· answer_relevancy {_fmt(j['answer_relevancy'])} "
                f"· context_precision {_fmt(j['context_precision'])} "
                f"· context_recall {_fmt(j['context_recall'])}"
                + (f" · parse-failed: {', '.join(j['errors'])}" if j["errors"] else ""),
            ]
        else:
            lines += ["", f"**Scores:** rr {r['rr']:.2f}"]
        lines.append("")

    return "\n".join(lines) + "\n"


def _append_history(report: dict, name: str) -> None:
    run = report["run"]
    ret = report["aggregate"]["retrieval"]
    gen = report["aggregate"]["generation"] or {}
    row = {
        "timestamp": run["timestamp"],
        "name": name,
        "k": run["k"],
        "num_questions": run["num_questions"],
        "judged": run["judged"],
        "chat_model": run["chat_model"],
        "judge_model": run["judge_model"],
        "hit@k": ret["hit@k"],
        "recall@k": ret["recall@k"],
        "mrr": ret["mrr"],
        "faithfulness": gen.get("faithfulness"),
        "answer_relevancy": gen.get("answer_relevancy"),
        "context_precision": gen.get("context_precision"),
        "context_recall": gen.get("context_recall"),
        "hallucination_rate": report["aggregate"]["hallucination_rate"],
    }
    is_new = not config.HISTORY_PATH.exists()
    with open(config.HISTORY_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def _print_summary(report: dict) -> None:
    agg = report["aggregate"]
    ret = agg["retrieval"]
    k = report["run"]["k"]
    print("\n=== Summary ===")
    print(f"Retrieval : hit@{k}={_fmt(ret['hit@k'])}  "
          f"recall@{k}={_fmt(ret['recall@k'])}  mrr={_fmt(ret['mrr'])}")
    gen = agg["generation"]
    if gen is not None:
        print(f"Generation: faithfulness={_fmt(gen['faithfulness'])}  "
              f"answer_relevancy={_fmt(gen['answer_relevancy'])}")
        print(f"            context_precision={_fmt(gen['context_precision'])}  "
              f"context_recall={_fmt(gen['context_recall'])}")
        print(f"Hallucination rate (1 - faithfulness): "
              f"{_fmt(agg['hallucination_rate'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the UBCHelper evaluation harness.")
    parser.add_argument("--name", default="run", help="label for this run (e.g. phase1-dense)")
    parser.add_argument("--k", type=int, default=config.EVAL_K, help="retrieval depth / @k")
    parser.add_argument("--limit", type=int, default=None, help="only the first N questions")
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="skip generation + the LLM judge (fast, deterministic, no chat model needed)",
    )
    args = parser.parse_args()

    testset = rm.load_testset()
    if args.limit:
        testset = testset[: args.limit]

    print(f"Running '{args.name}' over {len(testset)} questions (k={args.k}, "
          f"mode={config.RETRIEVAL_MODE}, judge={'off' if args.retrieval_only else 'on'}) ...")
    report = run(testset, k=args.k, do_judge=not args.retrieval_only)

    _print_summary(report)
    report_path = write_report(report, args.name)
    print(f"\nWrote:\n  {report_path}\n  {config.HISTORY_PATH}")


if __name__ == "__main__":
    main()
