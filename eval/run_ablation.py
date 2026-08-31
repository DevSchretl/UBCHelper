"""
Ablation — how much is the RAG actually helping?

Answers every test question two ways and scores both with the SAME metric:

    RAG     : retrieve relevant excerpts ->  grounded generation   (the real pipeline)
    no-RAG  : closed-book, no context    ->  the model answers from memory   (the baseline)

Both answers are judged for GROUNDEDNESS against the question's *gold excerpt* — the fraction
of the answer's atomic claims that the true excerpt supports (reusing judge.supported_claims).
Hallucination rate = 1 - groundedness. Because the judge compares against the gold excerpt (not
the retrieved context), the metric is well-defined for the no-RAG arm too, so the two are
directly comparable. The gap between the arms is the value retrieval adds.

The test set is the frozen specific-source questions (eval/testset.json) plus a few broad
general calendar questions (eval/testset.general.json); results are broken down by type, since
RAG helps most on specific-source questions and least on general knowledge.

NOTE: "hallucination" here means "unsupported by the gold excerpt", so a closed-book answer
that gives plausible but *different* requirements still counts as unsupported. That is intended
for specific-source questions; it is why general questions are reported separately.

Run (needs an index built; the judge defaults to a local LM Studio server — see
config.JUDGE_MODEL):
    python -m eval.run_ablation
    python -m eval.run_ablation --limit 2        # quick smoke test
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from statistics import mean

from src import config, generate, retrieve
from eval import judge


def _load_items(path, kind: str) -> list[dict]:
    """Load a test set file and tag every item with its `type` (specific/general)."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["items"]
    for it in items:
        it["type"] = kind
    return items


def _groundedness(answer: str, gold_texts: list[str]) -> dict:
    """Score one answer against the gold excerpt(s). Returns score + raw claim counts.

    For near-dup questions with several valid golds, a claim supported by ANY gold counts —
    so the answer is judged against the union of all gold excerpts.
    """
    supported, total = judge.supported_claims(answer, gold_texts)
    score = 1.0 if total == 0 else supported / total
    return {"score": round(score, 4), "supported": supported, "total": total}


def run(items: list[dict], k: int) -> dict:
    """Run both arms for every item and return the full ablation report dict."""
    _, metadata = retrieve._load_index()
    chunk_by_id = {r["id"]: r for r in metadata}

    per_item = []
    for n, item in enumerate(items, start=1):
        gold_ids = item["gold_ids"]
        golds = [chunk_by_id[g] for g in gold_ids if g in chunk_by_id]
        if not golds:
            print(f"  [{n}/{len(items)}] {item['id']}  SKIPPED — no gold ids {gold_ids} in index")
            continue
        gold_texts = [g["text"] for g in golds]
        gold_title = golds[0]["title"] + (f" (+{len(golds) - 1} more)" if len(golds) > 1 else "")
        question = item["question"]

        # Arm A: RAG (retrieve -> grounded generation). Arm B: closed-book (no context).
        rag_answer = generate.generate_answer(question, retrieve.retrieve(question, top_k=k))
        cb_answer = generate.generate_answer_closed_book(question)

        rag = _groundedness(rag_answer, gold_texts)
        cb = _groundedness(cb_answer, gold_texts)

        per_item.append({
            "id": item["id"],
            "type": item["type"],
            "question": question,
            "reference_answer": item.get("reference_answer", ""),
            "gold_id": gold_ids,
            "gold_title": gold_title,
            "rag": {"answer": rag_answer, **rag},
            "no_rag": {"answer": cb_answer, **cb},
        })
        print(
            f"  [{n}/{len(items)}] {item['id']} ({item['type']})  "
            f"RAG ground={rag['score']:.2f} ({rag['supported']}/{rag['total']})  "
            f"no-RAG ground={cb['score']:.2f} ({cb['supported']}/{cb['total']})"
        )

    return _aggregate(per_item, k)


def _aggregate(per_item: list[dict], k: int) -> dict:
    def summarize(rows: list[dict]) -> dict | None:
        if not rows:
            return None
        rag_g = mean(r["rag"]["score"] for r in rows)
        cb_g = mean(r["no_rag"]["score"] for r in rows)
        return {
            "n": len(rows),
            "rag_groundedness": round(rag_g, 4),
            "no_rag_groundedness": round(cb_g, 4),
            "rag_hallucination": round(1.0 - rag_g, 4),
            "no_rag_hallucination": round(1.0 - cb_g, 4),
            "hallucination_delta": round((1.0 - rag_g) - (1.0 - cb_g), 4),  # neg = RAG helps
        }

    by_type = {
        "overall": summarize(per_item),
        "specific": summarize([r for r in per_item if r["type"] == "specific"]),
        "general": summarize([r for r in per_item if r["type"] == "general"]),
    }
    return {
        "run": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "k": k,
            "num_questions": len(per_item),
            "chat_model": config.CHAT_MODEL,
            "judge_model": config.JUDGE_MODEL,
            "embedding_model": config.EMBEDDING_MODEL,
            "corpus_size": len(retrieve._load_index()[1]),  # indexed chunk count
        },
        "summary": by_type,
        "per_item": per_item,
    }


# ----------------------------------------------------------------------------------------
# Report: a single self-contained markdown doc (summary table + every answer side by side).
# ----------------------------------------------------------------------------------------

def _fmt(v) -> str:
    return "-" if v is None else f"{v:.3f}"


def write_report(report: dict, name: str):
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    config.ABLATION_REPORT_PATH.write_text(_render_markdown(report, name), encoding="utf-8")
    return config.ABLATION_REPORT_PATH


def _render_markdown(report: dict, name: str) -> str:
    run = report["run"]
    s = report["summary"]
    n_specific = sum(1 for r in report["per_item"] if r["type"] == "specific")
    n_general = sum(1 for r in report["per_item"] if r["type"] == "general")

    lines = [
        f"# UBCHelper ablation — {name}",
        "",
        f"{run['timestamp']} · {run['num_questions']} questions "
        f"({n_specific} specific + {n_general} general) · k={run['k']}",
        "",
        f"Models: chat=`{run['chat_model']}`, judge=`{run['judge_model']}`, "
        f"embed=`{run['embedding_model']}` · corpus={run['corpus_size']}",
        "",
        "Groundedness = fraction of the answer's claims supported by the gold excerpt "
        "(higher is better). Hallucination = 1 - groundedness. Both arms are judged against "
        "the same gold excerpt, so a closed-book answer that gives plausible but *different* "
        "requirements still counts as unsupported — which is why general questions are listed "
        "separately.",
        "",
        "## Summary — RAG vs no-RAG",
        "",
        "| set | n | RAG groundedness | no-RAG groundedness | RAG halluc. | no-RAG halluc. | halluc. delta (RAG-noRAG) |",
        "|-----|---|------------------|---------------------|-------------|----------------|---------------------------|",
    ]
    for label in ("overall", "specific", "general"):
        row = s.get(label)
        if row is None:
            continue
        lines.append(
            f"| {label} | {row['n']} | {_fmt(row['rag_groundedness'])} | "
            f"{_fmt(row['no_rag_groundedness'])} | {_fmt(row['rag_hallucination'])} | "
            f"{_fmt(row['no_rag_hallucination'])} | {_fmt(row['hallucination_delta'])} |"
        )

    lines += ["", "## Questions", ""]
    for x in report["per_item"]:
        rag, cb = x["rag"], x["no_rag"]
        lines += [
            f"### {x['id']} — {x['type']} — gold {x['gold_id']} {x['gold_title']}",
            "",
            f"**Q:** {x['question']}",
            "",
            f"**Reference:** {x['reference_answer']}",
            "",
            f"**RAG answer** — groundedness {rag['score']:.3f} "
            f"({rag['supported']}/{rag['total']} claims):",
            "",
            rag["answer"],
            "",
            f"**No-RAG answer** — groundedness {cb['score']:.3f} "
            f"({cb['supported']}/{cb['total']} claims):",
            "",
            cb["answer"],
            "",
        ]
    return "\n".join(lines) + "\n"


def _print_summary(report: dict) -> None:
    print("\n=== RAG vs no-RAG (groundedness, higher is better) ===")
    for label in ("overall", "specific", "general"):
        row = report["summary"].get(label)
        if row is None:
            continue
        print(
            f"{label:<9} (n={row['n']:>2}): "
            f"RAG={_fmt(row['rag_groundedness'])}  no-RAG={_fmt(row['no_rag_groundedness'])}  "
            f"| halluc RAG={_fmt(row['rag_hallucination'])} vs no-RAG={_fmt(row['no_rag_hallucination'])}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RAG vs no-RAG ablation.")
    parser.add_argument("--name", default="rag-vs-norag", help="label for this run")
    parser.add_argument("--k", type=int, default=config.EVAL_K, help="retrieval depth for the RAG arm")
    parser.add_argument("--limit", type=int, default=None, help="only the first N questions")
    args = parser.parse_args()

    items = _load_items(config.TESTSET_PATH, "specific") + _load_items(
        config.GENERAL_TESTSET_PATH, "general"
    )
    if args.limit:
        items = items[: args.limit]

    print(f"Running ablation '{args.name}' over {len(items)} questions "
          f"(RAG k={args.k} + closed-book) ...")
    report = run(items, k=args.k)

    _print_summary(report)
    report_path = write_report(report, args.name)
    print(f"\nWrote:\n  {report_path}")


if __name__ == "__main__":
    main()
