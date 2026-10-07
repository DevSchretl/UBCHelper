"""
Agent eval (Phase 4) — does the adaptive path actually earn its keep?

eval/run_eval.py and eval/run_ablation.py both call `retrieve.retrieve()` directly, so the
router and the agent have never been measured: every number in eval/reports/history.csv is
the single-shot path. This runner fixes that by going through `pipeline.answer()` with the
route FORCED, which is the same code the CLI and the web demo run.

Three retrieval arms per question, plus a router pass:

    agent           pipeline.answer(route="complex")  decompose -> multi-hop -> merge
    simple          pipeline.answer(route="simple")   the shipped single-shot path
    simple_matched  pipeline.answer(route="simple", top_k=M) where M = len(agent's merge)
    router          router.classify(q) scored against each item's `expected_route`

`simple_matched` is a CONTROL, not a shipped configuration. The agent returns up to
AGENT_MAX_SUBQ x AGENT_SUBQ_TOP_K excerpts and the simple path returns TOP_K, so a raw
comparison confounds "smarter decomposition" with "simply got more excerpts". Two things
answer that confound: every comparative metric is scored at the SAME depth k on all arms,
and simple_matched asks the separate question "would just retrieving M in one shot have
done as well?". Note that its generation side is not a production configuration -- it puts
M excerpts in the prompt, which the shipped simple path never does -- so read its retrieval
numbers and treat its generation numbers as advisory.

Run (needs an index; the judge needs a local LM Studio server -- see config.JUDGE_MODEL):
    python -m eval.run_agent_eval --selftest                  # pure helpers, no network
    python -m eval.run_agent_eval --limit 2 --mode dense --no-judge --name smoke
    python -m eval.run_agent_eval --name agent-v1 --router-votes 3 --pace 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from statistics import mean

from src import config, generate, pipeline, retrieve, router, trace
from eval import judge
from eval import retrieval_metrics as rm
from eval.run_ablation import _load_items

# Imported rather than copied a third time: run_ablation already carries its own duplicate
# of _fmt, and a third would be the one that drifts.
from eval.run_eval import _fmt, _mean_or_none, append_history_row

ARMS = ("agent", "simple", "simple_matched")
RETRIEVAL_ARMS = ("simple", "simple_matched", "agent")  # report order: cheapest first
POLICIES = ("always_simple", "always_complex", "router", "oracle")
GEN_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

# Which trace events correspond to a paid API call, and the operator-facing price of each.
# The canonical copy lives at web/limits.py:PAID_EVENT_KINDS / PRICES. It is duplicated
# here rather than imported because requirements-web.txt keeps the engine's dependency list
# to "exactly what ask.py and the eval harness need", and eval/ importing web/ would invert
# that layering. _selftest asserts the two stay in step when the web extras are installed.
PAID_EVENT_KINDS = {"llm_call": "llm", "retrieval_start": "embed", "shortlist": "rerank"}
PRICES = {"llm": 0.0015, "embed": 0.000001, "rerank": 0.002}

# Buckets every metric is rolled up over. "specific"/"general" exist so the simple arm can
# be cross-checked against the existing history.csv ledger, which only covers testset.json.
BUCKETS = (
    "overall", "specific", "general",
    "code-lookup", "multi-hop", "collision", "policy",
    "expected=simple", "expected=complex",
)


# ========================================================================================
# Pure helpers. No network, no index, no keys -- all covered by --selftest.
# ========================================================================================

def _score(ids: list[int], gold_ids: list[int], k: int) -> dict:
    """hit/recall/rr over the first `k` ids. Always slice before calling.

    rm.reciprocal_rank deliberately takes no `k` and scans the whole list
    (eval/retrieval_metrics.py:49), so it MUST be handed a pre-sliced list. Passing the
    agent's full 12-item merge here while the simple arm passes 4 would hand the agent
    three times the lottery tickets -- the single easiest way to fake a win in this file.
    """
    top = ids[:k]
    return {
        "hit": rm.hit_at_k(top, gold_ids, k),
        "recall": rm.recall_at_k(top, gold_ids, k),
        "rr": rm.reciprocal_rank(top, gold_ids),
    }


def _infer_route(item: dict) -> str:
    """Fallback gold route when --infer-routes is passed. Advisory, never a measurement."""
    return "complex" if item.get("category") == "multi-hop" else "simple"


def _slim(event: dict) -> dict | None:
    """Keep only the fields the report reads; drop the rest.

    An `llm_call` carries the full system+user prompt and reply (~15 KB for an 8-excerpt
    synthesis) and `candidates` carries 50 scored rows per stage per retrieval. Retaining
    raw events for 16 questions x 3 arms is tens of megabytes for no reason.
    """
    kind = event.get("kind")
    if kind == "llm_call":
        return {"kind": kind, "purpose": event.get("purpose"), "ms": event.get("ms")}
    if kind == "route":
        return {"kind": kind, "decision": event.get("decision"),
                "raw_reply": event.get("raw_reply")}
    if kind == "subquestions":
        return {"kind": kind, "items": event.get("items", [])}
    if kind == "merge":
        return {"kind": kind, "order": event.get("order", []),
                "per_hop": event.get("per_hop", []), "dropped": event.get("dropped")}
    if kind == "retrieval_start":
        return {"kind": kind, "query": event.get("query")}
    if kind == "shortlist":
        return {"kind": kind, "ids": event.get("ids", [])}
    if kind == "candidates":
        return {"kind": kind, "stage": event.get("stage"), "n": len(event.get("items", []))}
    return None  # step / detail / results / retrieval_final -- printing only


def _tally(counts: dict, event: dict) -> None:
    """Fold one trace event into a {llm, embed, rerank} tally, in place."""
    bucket = PAID_EVENT_KINDS.get(event.get("kind"))
    if bucket:
        counts[bucket] = counts.get(bucket, 0) + 1


def _cost_usd(counts: dict) -> float:
    return round(sum(PRICES[b] * n for b, n in counts.items() if b in PRICES), 4)


def _llm_ms_by_purpose(events: list[dict]) -> dict:
    out: dict[str, int] = {}
    for e in events:
        if e.get("kind") == "llm_call" and e.get("ms") is not None:
            out[e.get("purpose") or "?"] = out.get(e.get("purpose") or "?", 0) + int(e["ms"])
    return out


def _first(events: list[dict], kind: str) -> dict | None:
    return next((e for e in events if e.get("kind") == kind), None)


def _per_hop_gold(per_hop: list[list[int]], gold_ids: list[int]) -> list[list[int]]:
    """Which gold ids each hop surfaced, hop-indexed."""
    gold = set(gold_ids)
    return [sorted(set(hop) & gold) for hop in per_hop]


def _hop_attribution(per_hop: list[list[int]], gold_ids: list[int]) -> dict:
    """gold id -> index (1-based) of the FIRST hop that found it, or None."""
    found: dict[int, int | None] = {}
    for g in gold_ids:
        found[g] = next((i for i, hop in enumerate(per_hop, start=1) if g in hop), None)
    return found


def _policy_pick(record: dict, policy: str) -> str:
    """Which arm a routing policy would have used for this question."""
    if policy == "always_simple":
        return "simple"
    if policy == "always_complex":
        return "agent"
    if policy == "router":
        decision = (record.get("router") or {}).get("decision", "simple")
        return "agent" if decision == "complex" else "simple"
    if policy == "oracle":
        return "agent" if record["expected_route"] == "complex" else "simple"
    raise ValueError(f"unknown policy: {policy}")


def _in_bucket(record: dict, bucket: str) -> bool:
    if bucket == "overall":
        return True
    if bucket in ("specific", "general"):
        return record["type"] == bucket
    if bucket.startswith("expected="):
        return record["expected_route"] == bucket.split("=", 1)[1]
    return record["category"] == bucket


# ========================================================================================
# Running one arm. Everything below here talks to the network.
# ========================================================================================

def _assert_arm_shape(arm: str, events: list[dict], item_id: str) -> None:
    """Refuse to score an arm that did not take the path it claims.

    src/pipeline.py:30 dispatches on the literal string "complex" and treats everything
    else as simple, with no error. If route forcing ever breaks, this eval would quietly
    measure the simple arm twice and report that the agent ties it.
    """
    has_subq = _first(events, "subquestions") is not None
    has_merge = _first(events, "merge") is not None
    if arm == "agent" and not (has_subq and has_merge):
        raise SystemExit(
            f"{item_id}: the 'agent' arm produced no subquestions/merge event, so it did "
            f"not take the complex path. Route forcing in src/pipeline.py is broken."
        )
    if arm != "agent" and (has_subq or has_merge):
        raise SystemExit(
            f"{item_id}: the '{arm}' arm produced agent trace events, so it took the "
            f"complex path. Route forcing in src/pipeline.py is broken."
        )


def _safe_groundedness(answer: str, gold_texts: list[str]) -> dict:
    """run_ablation._groundedness, but a judge parse failure degrades the item, not the run.

    run_ablation calls judge.supported_claims uncaught, so one bad parse kills a whole
    30-minute run. Same bug is worth fixing there.
    """
    try:
        supported, total = judge.supported_claims(answer, gold_texts)
    except (judge.JudgeParseError, KeyError, TypeError, ValueError, IndexError) as exc:
        return {"score": None, "supported": None, "total": None, "error": type(exc).__name__}
    score = 1.0 if total == 0 else supported / total
    return {"score": round(score, 4), "supported": supported, "total": total, "error": None}


def _run_arm(arm: str, item: dict, *, k: int, mode: str | None, top_k: int | None,
             chunk_by_id: dict, do_judge: bool, full_judge: bool, dump_fh) -> dict:
    """Run one arm end to end through pipeline.answer() and score it."""
    route = "complex" if arm == "agent" else "simple"
    events: list[dict] = []
    counts = {"llm": 0, "embed": 0, "rerank": 0}

    def sink(ev: dict) -> None:
        _tally(counts, ev)
        if dump_fh is not None:
            dump_fh.write(json.dumps({"item": item["id"], "arm": arm, **ev},
                                     ensure_ascii=False, default=str) + "\n")
        slim = _slim(ev)
        if slim is not None:
            events.append(slim)

    started = time.perf_counter()
    with trace.collect(sink):
        out = pipeline.answer(item["question"], top_k=top_k, mode=mode, route=route)
    wall_ms = round((time.perf_counter() - started) * 1000)
    _assert_arm_shape(arm, events, item["id"])

    results = out["results"]
    ids = [r.id for r in results]
    gold_ids = item["gold_ids"]

    # Only the first SYNTH_CONTEXT_K merged excerpts reach the model (src/agent.py:73), so
    # anything generation-side must be scored against those and no more.
    prompt_depth = min(len(ids), config.SYNTH_CONTEXT_K) if arm == "agent" else len(ids)
    prompt_ids = ids[:prompt_depth]

    record = {
        "retrieved_ids": ids,
        "retrieved_titles": [r.recipe["title"] for r in results],
        "depth": len(ids),
        "prompt_depth": prompt_depth,
        "at_k": _score(ids, gold_ids, k),
        "at_full": _score(ids, gold_ids, len(ids)),
        "prompt_recall": rm.recall_at_k(prompt_ids, gold_ids, len(prompt_ids)),
        "answer": out["answer"],
        "groundedness": None,
        "judge": None,
        "trace": {
            "api_calls": counts,
            "queries": [e["query"] for e in events if e.get("kind") == "retrieval_start"],
            "subquestions": (_first(events, "subquestions") or {}).get("items", []),
            "llm_ms": _llm_ms_by_purpose(events),
            "wall_ms": wall_ms,
        },
        "flags": {},
    }

    merge = _first(events, "merge")
    if merge is not None:
        per_hop = merge.get("per_hop", [])
        record["trace"]["per_hop"] = per_hop
        record["trace"]["per_hop_gold"] = _per_hop_gold(per_hop, gold_ids)
        record["trace"]["hop_attribution"] = _hop_attribution(per_hop, gold_ids)
        record["trace"]["dropped"] = merge.get("dropped")
        # One sub-question means decompose collapsed: the complex arm is then literally the
        # simple arm plus two wasted LLM calls, and it dilutes the measured agent effect.
        record["flags"]["degenerate"] = len(record["trace"]["subquestions"]) <= 1
        record["flags"]["short_merge"] = len(ids) < k

    if do_judge:
        gold_texts = [chunk_by_id[g]["text"] for g in gold_ids if g in chunk_by_id]
        record["groundedness"] = _safe_groundedness(out["answer"], gold_texts)
        if full_judge:
            contexts = [r.recipe["text"] for r in results[:prompt_depth]]
            record["judge"] = judge.judge_item(
                item["question"], out["answer"], contexts, item["reference_answer"]
            )
    return record


def _classify_arm(item: dict, votes: int) -> dict:
    """Run router.classify() `votes` times; majority wins, disagreement is recorded."""
    decisions, replies, ms, calls = [], [], 0, 0
    for _ in range(votes):
        events: list[dict] = []

        def sink(ev: dict, bucket: list = events) -> None:
            slim = _slim(ev)
            if slim is not None:
                bucket.append(slim)

        with trace.collect(sink):
            decisions.append(router.classify(item["question"]))
        route_ev = _first(events, "route")
        replies.append((route_ev or {}).get("raw_reply", ""))
        ms += sum(int(e.get("ms") or 0) for e in events if e.get("kind") == "llm_call")
        calls += sum(1 for e in events if e.get("kind") == "llm_call")
    decision = Counter(decisions).most_common(1)[0][0]
    return {
        "votes": decisions,
        "raw_replies": replies,
        "decision": decision,
        "correct": decision == item["expected_route"],
        "stable": len(set(decisions)) == 1,
        "ms": ms,
        "llm_calls": calls,
    }


def _run_item(item: dict, *, k: int, mode: str | None, arms: tuple, router_votes: int,
              chunk_by_id: dict, do_judge: bool, full_judge: bool, dump_fh) -> dict:
    record = {
        "id": item["id"],
        "category": item.get("category") or "general",
        "type": item["type"],
        "question": item["question"],
        "reference_answer": item.get("reference_answer", ""),
        "gold_ids": item["gold_ids"],
        "expected_route": item["expected_route"],
        "router": None,
        "arms": {},
    }
    if router_votes > 0:
        record["router"] = _classify_arm(item, router_votes)

    # The agent runs first so its merge depth M is known before simple_matched needs it.
    if "agent" in arms:
        record["arms"]["agent"] = _run_arm(
            "agent", item, k=k, mode=mode, top_k=None, chunk_by_id=chunk_by_id,
            do_judge=do_judge, full_judge=full_judge, dump_fh=dump_fh)
    matched_k = record["arms"].get("agent", {}).get("depth", k)
    if "simple" in arms:
        record["arms"]["simple"] = _run_arm(
            "simple", item, k=k, mode=mode, top_k=k, chunk_by_id=chunk_by_id,
            do_judge=do_judge, full_judge=full_judge, dump_fh=dump_fh)
    if "simple_matched" in arms:
        record["arms"]["simple_matched"] = _run_arm(
            "simple_matched", item, k=k, mode=mode, top_k=matched_k,
            chunk_by_id=chunk_by_id, do_judge=do_judge, full_judge=full_judge,
            dump_fh=dump_fh)

    record["delta"] = _item_delta(record, k)
    return record


def _item_delta(record: dict, k: int) -> dict | None:
    """agent - simple at depth k, plus which golds each arm uniquely found."""
    agent, simple = record["arms"].get("agent"), record["arms"].get("simple")
    if not agent or not simple:
        return None
    gold = set(record["gold_ids"])
    a_hit = set(agent["retrieved_ids"][:k]) & gold
    s_hit = set(simple["retrieved_ids"][:k]) & gold
    ag, sg = agent.get("groundedness") or {}, simple.get("groundedness") or {}
    return {
        "hit": round(agent["at_k"]["hit"] - simple["at_k"]["hit"], 4),
        "recall": round(agent["at_k"]["recall"] - simple["at_k"]["recall"], 4),
        "rr": round(agent["at_k"]["rr"] - simple["at_k"]["rr"], 4),
        "groundedness": (round(ag["score"] - sg["score"], 4)
                         if ag.get("score") is not None and sg.get("score") is not None
                         else None),
        # Two different mechanisms can lose a gold the simple arm had: round-robin
        # interleaving pushing it below the cutoff, or -- on a one-hop (degenerate) run --
        # decompose's rephrasing of the question simply retrieving something else. Check
        # the item's subquestions to tell which; `degenerate` distinguishes them.
        "golds_gained": sorted(a_hit - s_hit),
        "golds_lost": sorted(s_hit - a_hit),
        "extra_llm_calls": agent["trace"]["api_calls"]["llm"] - simple["trace"]["api_calls"]["llm"],
        "extra_rerank_calls": (agent["trace"]["api_calls"]["rerank"]
                               - simple["trace"]["api_calls"]["rerank"]),
        "extra_ms": agent["trace"]["wall_ms"] - simple["trace"]["wall_ms"],
    }


# ========================================================================================
# Aggregation
# ========================================================================================

def _summarize_arm(rows: list[dict], arm: str) -> dict | None:
    """One bucket's numbers for one arm. None when the bucket is empty for this arm."""
    cells = [r["arms"][arm] for r in rows if arm in r["arms"]]
    if not cells:
        return None
    ground = [c["groundedness"]["score"] for c in cells
              if c.get("groundedness") and c["groundedness"]["score"] is not None]
    out = {
        "n": len(cells),
        "hit@k": round(mean(c["at_k"]["hit"] for c in cells), 4),
        "recall@k": round(mean(c["at_k"]["recall"] for c in cells), 4),
        "mrr": round(mean(c["at_k"]["rr"] for c in cells), 4),
        "recall@full": round(mean(c["at_full"]["recall"] for c in cells), 4),
        "prompt_recall": round(mean(c["prompt_recall"] for c in cells), 4),
        "depth": round(mean(c["depth"] for c in cells), 2),
        "groundedness": round(mean(ground), 4) if ground else None,
        "groundedness_n": len(ground),
        "llm_calls_per_q": round(mean(c["trace"]["api_calls"]["llm"] for c in cells), 2),
        "rerank_calls_per_q": round(mean(c["trace"]["api_calls"]["rerank"] for c in cells), 2),
        "ms_per_q": round(mean(c["trace"]["wall_ms"] for c in cells)),
    }
    for metric in GEN_METRICS:
        vals = [c["judge"][metric] for c in cells if c.get("judge")]
        out[metric] = _mean_or_none(vals) if vals else None
    return out


def _summarize_policy(rows: list[dict], policy: str, k: int) -> dict | None:
    """Score a routing policy by picking one arm per question. No extra API calls."""
    picks = [(r, _policy_pick(r, policy)) for r in rows]
    # A policy scored over only the questions whose chosen arm happens to be available is
    # not comparable to one scored over all of them -- with --arms simple, `oracle` would
    # silently drop every complex question and report an inflated recall. All or nothing.
    if not picks or any(a not in r["arms"] for r, a in picks):
        return None
    ground = [r["arms"][a]["groundedness"]["score"] for r, a in picks
              if r["arms"][a].get("groundedness")
              and r["arms"][a]["groundedness"]["score"] is not None]
    counts = {b: sum(r["arms"][a]["trace"]["api_calls"][b] for r, a in picks)
              for b in ("llm", "embed", "rerank")}
    return {
        "n": len(picks),
        "complex_share": round(sum(1 for _, a in picks if a == "agent") / len(picks), 4),
        "hit@k": round(mean(r["arms"][a]["at_k"]["hit"] for r, a in picks), 4),
        "recall@k": round(mean(r["arms"][a]["at_k"]["recall"] for r, a in picks), 4),
        "mrr": round(mean(r["arms"][a]["at_k"]["rr"] for r, a in picks), 4),
        "groundedness": round(mean(ground), 4) if ground else None,
        "llm_calls_per_q": round(counts["llm"] / len(picks), 2),
        "rerank_calls_per_q": round(counts["rerank"] / len(picks), 2),
        "ms_per_q": round(mean(r["arms"][a]["trace"]["wall_ms"] for r, a in picks)),
        "est_cost_usd": _cost_usd(counts),
    }


def _summarize_router(rows: list[dict]) -> dict | None:
    scored = [r for r in rows if r.get("router")]
    if not scored:
        return None
    tp = sum(1 for r in scored if r["expected_route"] == "complex"
             and r["router"]["decision"] == "complex")
    fp = sum(1 for r in scored if r["expected_route"] == "simple"
             and r["router"]["decision"] == "complex")
    tn = sum(1 for r in scored if r["expected_route"] == "simple"
             and r["router"]["decision"] == "simple")
    fn = sum(1 for r in scored if r["expected_route"] == "complex"
             and r["router"]["decision"] == "simple")
    return {
        "n": len(scored),
        "accuracy": round((tp + tn) / len(scored), 4),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision_complex": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "recall_complex": round(tp / (tp + fn), 4) if (tp + fn) else None,
        "stability": round(sum(1 for r in scored if r["router"]["stable"]) / len(scored), 4),
        "disagreements": [
            {"id": r["id"], "expected": r["expected_route"],
             "got": r["router"]["decision"], "raw_replies": r["router"]["raw_replies"]}
            for r in scored if not r["router"]["correct"]
        ],
    }


def _agent_diagnostics(rows: list[dict], k: int) -> dict | None:
    cells = [(r, r["arms"]["agent"]) for r in rows if "agent" in r["arms"]]
    if not cells:
        return None
    subq = [len(c["trace"]["subquestions"]) for _, c in cells]
    hops: Counter = Counter()
    for r, c in cells:
        for _gold, hop in (c["trace"].get("hop_attribution") or {}).items():
            hops[f"hop{hop}" if hop else "none"] += 1
    return {
        "mean_subq": round(mean(subq), 2), "min_subq": min(subq), "max_subq": max(subq),
        "mean_merge_depth": round(mean(c["depth"] for _, c in cells), 2),
        "mean_dropped": round(mean((c["trace"].get("dropped") or 0) for _, c in cells), 2),
        "degenerate_items": [r["id"] for r, c in cells if c["flags"].get("degenerate")],
        "short_merge_items": [r["id"] for r, c in cells if c["flags"].get("short_merge")],
        "hop_gold_attribution": dict(sorted(hops.items())),
        # recall the merge found but ranked below the cutoff: large means the ordering,
        # not the retrieval, is what is losing the golds.
        "mean_recall_buried_below_k": round(
            mean(c["at_full"]["recall"] - c["at_k"]["recall"] for _, c in cells), 4),
        "golds_only_agent_found": {r["id"]: r["delta"]["golds_gained"] for r in rows
                                   if r.get("delta") and r["delta"]["golds_gained"]},
        "golds_only_simple_found": {r["id"]: r["delta"]["golds_lost"] for r in rows
                                    if r.get("delta") and r["delta"]["golds_lost"]},
    }


def _aggregate(per_item: list[dict], *, k: int, mode: str, name: str, arms: tuple,
               judged: bool, full_judge: bool, routes_inferred: bool, router_votes: int,
               wall_seconds: float, failures: list) -> dict:
    counts = {"llm": 0, "embed": 0, "rerank": 0}
    for r in per_item:
        for cell in r["arms"].values():
            for b, n in cell["trace"]["api_calls"].items():
                counts[b] += n
        counts["llm"] += (r.get("router") or {}).get("llm_calls", 0)

    by_arm = {arm: {b: _summarize_arm([r for r in per_item if _in_bucket(r, b)], arm)
                    for b in BUCKETS} for arm in arms}
    deltas = {}
    for b in BUCKETS:
        a, s = by_arm.get("agent", {}).get(b), by_arm.get("simple", {}).get(b)
        if a and s:
            deltas[b] = {
                "n": a["n"],
                "recall@k": round(a["recall@k"] - s["recall@k"], 4),
                "hit@k": round(a["hit@k"] - s["hit@k"], 4),
                "mrr": round(a["mrr"] - s["mrr"], 4),
                "groundedness": (round(a["groundedness"] - s["groundedness"], 4)
                                 if a["groundedness"] is not None
                                 and s["groundedness"] is not None else None),
            }

    return {
        "run": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "name": name, "k": k, "num_questions": len(per_item),
            "n_specific": sum(1 for r in per_item if r["type"] == "specific"),
            "n_general": sum(1 for r in per_item if r["type"] == "general"),
            "arms": list(arms), "judged": judged, "full_judge": full_judge,
            "routes_inferred": routes_inferred, "router_votes": router_votes,
            "retrieval_mode": mode, "chat_model": generate.active_model(),
            "judge_model": config.JUDGE_MODEL, "embedding_model": config.EMBEDDING_MODEL,
            "corpus_size": len(retrieve._load_index()[1]),
            "agent_max_subq": config.AGENT_MAX_SUBQ,
            "agent_subq_top_k": config.AGENT_SUBQ_TOP_K,
            "synth_context_k": config.SYNTH_CONTEXT_K,
            "wall_seconds": round(wall_seconds, 1),
            "api_calls": counts, "estimated_cost_usd": _cost_usd(counts),
            "failures": failures,
        },
        "arms": by_arm,
        "delta": deltas,
        "policies": {p: _summarize_policy(per_item, p, k) for p in POLICIES},
        "router": _summarize_router(per_item),
        "agent_diagnostics": _agent_diagnostics(per_item, k),
        "judge_failures": {
            arm: sum(1 for r in per_item if arm in r["arms"]
                     and (r["arms"][arm].get("groundedness") or {}).get("error"))
            for arm in arms
        },
        "per_item": per_item,
    }


# ========================================================================================
# Report
# ========================================================================================

def write_report(report: dict, name: str):
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    config.AGENT_REPORT_PATH.write_text(_render_markdown(report, name), encoding="utf-8")
    _append_history(report, name)
    return config.AGENT_REPORT_PATH


AGENT_HISTORY_COLUMNS = [
    "timestamp", "name", "k", "num_questions", "judged", "routes_inferred", "router_votes",
    "retrieval_mode", "corpus_size", "chat_model", "judge_model",
    "agent_max_subq", "synth_context_k",
    "simple_hit@k", "simple_recall@k", "simple_mrr", "simple_groundedness",
    "agent_hit@k", "agent_recall@k", "agent_mrr", "agent_groundedness", "agent_recall@full",
    "matched_recall@k", "recall_delta", "groundedness_delta",
    "multihop_recall_delta", "expected_complex_recall_delta",
    "router_accuracy", "router_stability",
    "policy_router_recall", "policy_oracle_recall",
    "llm_calls", "embed_calls", "rerank_calls", "wall_seconds", "est_cost_usd",
]


def _append_history(report: dict, name: str) -> None:
    run, arms, delta = report["run"], report["arms"], report["delta"]
    s = (arms.get("simple") or {}).get("overall") or {}
    a = (arms.get("agent") or {}).get("overall") or {}
    m = (arms.get("simple_matched") or {}).get("overall") or {}
    pol, rt = report["policies"], report["router"] or {}
    row = {
        "timestamp": run["timestamp"], "name": name, "k": run["k"],
        "num_questions": run["num_questions"], "judged": run["judged"],
        "routes_inferred": run["routes_inferred"], "router_votes": run["router_votes"],
        "retrieval_mode": run["retrieval_mode"], "corpus_size": run["corpus_size"],
        "chat_model": run["chat_model"], "judge_model": run["judge_model"],
        "agent_max_subq": run["agent_max_subq"], "synth_context_k": run["synth_context_k"],
        "simple_hit@k": s.get("hit@k"), "simple_recall@k": s.get("recall@k"),
        "simple_mrr": s.get("mrr"), "simple_groundedness": s.get("groundedness"),
        "agent_hit@k": a.get("hit@k"), "agent_recall@k": a.get("recall@k"),
        "agent_mrr": a.get("mrr"), "agent_groundedness": a.get("groundedness"),
        "agent_recall@full": a.get("recall@full"),
        "matched_recall@k": m.get("recall@k"),
        "recall_delta": (delta.get("overall") or {}).get("recall@k"),
        "groundedness_delta": (delta.get("overall") or {}).get("groundedness"),
        "multihop_recall_delta": (delta.get("multi-hop") or {}).get("recall@k"),
        "expected_complex_recall_delta": (delta.get("expected=complex") or {}).get("recall@k"),
        "router_accuracy": rt.get("accuracy"), "router_stability": rt.get("stability"),
        "policy_router_recall": (pol.get("router") or {}).get("recall@k"),
        "policy_oracle_recall": (pol.get("oracle") or {}).get("recall@k"),
        "llm_calls": run["api_calls"]["llm"], "embed_calls": run["api_calls"]["embed"],
        "rerank_calls": run["api_calls"]["rerank"],
        "wall_seconds": run["wall_seconds"], "est_cost_usd": run["estimated_cost_usd"],
    }
    append_history_row(config.AGENT_HISTORY_PATH, AGENT_HISTORY_COLUMNS, row)


def _render_markdown(report: dict, name: str) -> str:
    run, arms = report["run"], report["arms"]
    k = run["k"]
    L = [
        f"# UBCHelper agent eval — {name}",
        "",
        f"{run['timestamp']} · {run['num_questions']} questions "
        f"({run['n_specific']} specific + {run['n_general']} general) · k={k} · "
        f"mode={run['retrieval_mode']} · judge {'on' if run['judged'] else 'off'}"
        f"{' (full RAGAS)' if run['full_judge'] else ''}",
        "",
        f"Models: chat=`{run['chat_model']}`, judge=`{run['judge_model']}`, "
        f"embed=`{run['embedding_model']}` · corpus={run['corpus_size']} · "
        f"agent knobs: max_subq={run['agent_max_subq']}, "
        f"subq_top_k={run['agent_subq_top_k']}, synth_context_k={run['synth_context_k']}",
        "",
    ]
    if run["routes_inferred"]:
        L += ["> **Router accuracy below is ADVISORY.** `expected_route` was inferred from "
              "`category`, not hand-labelled, so a 'router error' may just be a "
              "disagreement about the label.", ""]
    if run["failures"]:
        L += [f"> **{len(run['failures'])} question(s) failed and are excluded**: "
              + ", ".join(f"`{i}` ({e})" for i, e in run["failures"]), ""]

    L += [
        "## How to read this",
        "",
        f"- Both arms run the real `pipeline.answer()` with the route forced, not a "
        f"reimplementation — that bypass is the bug this eval exists to fix.",
        f"- **Every comparative metric is at depth k={k} on all arms.** The agent retrieves "
        f"up to {run['agent_max_subq'] * run['agent_subq_top_k']} excerpts; scoring it "
        f"deeper than the simple arm would be a gift, not a comparison.",
        f"- `recall@full` and `prompt_recall` are diagnostics, not comparisons. "
        f"`prompt_recall` counts only the excerpts that actually reached the model "
        f"(the agent's first {run['synth_context_k']}).",
        "- `simple_matched` is a control: a one-shot retrieve at the agent's own merge "
        "depth. It answers \"would just retrieving more have worked?\" Its generation is "
        "not a shipped configuration.",
        "- Groundedness is scored against the **gold** excerpt, so it is arm-invariant. "
        "`context_precision`/`context_recall` are depth-sensitive — read them within an "
        "arm over time, not across arms.",
        f"- n={run['num_questions']}, and `decompose` is nondeterministic (no temperature "
        f"is sent to Anthropic), so a delta smaller than "
        f"{1 / max(run['num_questions'], 1):.3f} is not a result.",
        "",
        "## Routing policies",
        "",
        "What each routing strategy would have scored, from the arms already run.",
        "",
        "| policy | n | % complex | hit@k | recall@k | MRR | grounded | LLM/q | rerank/q | s/q | est $ |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p in POLICIES:
        row = report["policies"].get(p)
        if row:
            L.append(
                f"| `{p}` | {row['n']} | {row['complex_share']:.0%} | {_fmt(row['hit@k'])} | "
                f"{_fmt(row['recall@k'])} | {_fmt(row['mrr'])} | "
                f"{_fmt(row['groundedness'])} | {row['llm_calls_per_q']} | "
                f"{row['rerank_calls_per_q']} | {row['ms_per_q'] / 1000:.1f} | "
                f"{row['est_cost_usd']:.3f} |")

    L += ["", "## Arms by bucket", "",
          "| bucket | n | arm | depth | hit@k | recall@k | MRR | recall@full | grounded |",
          "|---|---|---|---|---|---|---|---|---|"]
    for b in BUCKETS:
        for arm in RETRIEVAL_ARMS:
            row = arms.get(arm, {}).get(b)
            if row:
                L.append(
                    f"| {b} | {row['n']} | `{arm}` | {row['depth']} | {_fmt(row['hit@k'])} | "
                    f"{_fmt(row['recall@k'])} | {_fmt(row['mrr'])} | "
                    f"{_fmt(row['recall@full'])} | {_fmt(row['groundedness'])} |")

    L += ["", "### agent − simple (depth k, the comparable number)", "",
          "| bucket | n | Δ hit@k | Δ recall@k | Δ MRR | Δ grounded |",
          "|---|---|---|---|---|---|"]
    for b, d in report["delta"].items():
        ground = "-" if d["groundedness"] is None else f"{d['groundedness']:+.3f}"
        L.append(f"| {b} | {d['n']} | {d['hit@k']:+.3f} | {d['recall@k']:+.3f} | "
                 f"{d['mrr']:+.3f} | {ground} |")

    rt = report["router"]
    if rt:
        c = rt["confusion"]
        L += ["", "## Router accuracy", "",
              f"Accuracy **{rt['accuracy']:.3f}** over {rt['n']} questions "
              f"({run['router_votes']} vote(s) each, stability {rt['stability']:.3f}). "
              f"Positive class = `complex`; precision {_fmt(rt['precision_complex'])}, "
              f"recall {_fmt(rt['recall_complex'])}.",
              "",
              "A bare accuracy figure flatters the router here: only "
              f"{c['tp'] + c['fn']} of {rt['n']} questions are genuinely complex, so "
              f"\"always simple\" would score "
              f"{(c['tn'] + c['fp']) / rt['n']:.3f}. The errors are not symmetric either — "
              "a false `complex` wastes two LLM calls and two reranks, a false `simple` "
              "silently loses recall.",
              "",
              "| | predicted simple | predicted complex |",
              "|---|---|---|",
              f"| **actually simple** | {c['tn']} | {c['fp']} |",
              f"| **actually complex** | {c['fn']} | {c['tp']} |"]
        if rt["disagreements"]:
            L += ["", "Disagreements (raw model replies shown, since the parse at "
                  "`src/router.py:36` is substring containment):", ""]
            for d in rt["disagreements"]:
                L.append(f"- `{d['id']}` expected **{d['expected']}**, got "
                         f"**{d['got']}** — replies: {d['raw_replies']}")

    diag = report["agent_diagnostics"]
    if diag:
        L += ["", "## Agent diagnostics", "",
              f"- Sub-questions per item: mean {diag['mean_subq']} "
              f"(min {diag['min_subq']}, max {diag['max_subq']})",
              f"- Merge depth: mean {diag['mean_merge_depth']}, "
              f"mean deduped away {diag['mean_dropped']}",
              f"- Which hop first surfaced each gold: {diag['hop_gold_attribution']}",
              f"- Recall found but ranked below k: "
              f"{diag['mean_recall_buried_below_k']:.4f}",
              f"- Golds only the agent found: {diag['golds_only_agent_found'] or 'none'}",
              f"- Golds only the simple arm found (the agent lost them — to merge ordering "
              f"on a multi-hop item, or to decompose's rephrasing on a degenerate one): "
              f"{diag['golds_only_simple_found'] or 'none'}"]
        if diag["degenerate_items"]:
            L.append(f"- **Degenerate** (decompose returned one sub-question, so the agent "
                     f"arm is the simple arm plus wasted calls): "
                     f"{diag['degenerate_items']}")
        if diag["short_merge_items"]:
            L.append(f"- Short merge (fewer than k results after dedup): "
                     f"{diag['short_merge_items']}")

    jf = report["judge_failures"]
    L += ["", "## Cost", "",
          f"- API calls: {run['api_calls']} · estimated **${run['estimated_cost_usd']:.3f}**",
          f"- Wall clock: {run['wall_seconds']:.0f} s",
          f"- Judge parse failures by arm: {jf}"]
    if run["judged"] and any(v > 0 for v in jf.values()):
        L.append("- **Caveat:** groundedness means are taken over the items that parsed. "
                 "If the arms failed at different rates the comparison is biased; see "
                 "`groundedness_n` per bucket.")

    L += ["", "## Questions", ""]
    for r in report["per_item"]:
        route_line = f"expected **{r['expected_route']}**"
        if r.get("router"):
            mark = "correct" if r["router"]["correct"] else "WRONG"
            route_line += f", router said **{r['router']['decision']}** ({mark})"
        L += [f"### {r['id']} — {r['category']} — gold {r['gold_ids']}", "",
              f"**Q:** {r['question']}", "", f"**Reference:** {r['reference_answer']}", "",
              f"**Route:** {route_line}", ""]
        agent_cell = r["arms"].get("agent")
        if agent_cell and agent_cell["trace"]["subquestions"]:
            L += ["**Sub-questions** (nondeterministic — this is what to diff between runs):",
                  ""]
            L += [f"  {i}. {s}" for i, s in
                  enumerate(agent_cell["trace"]["subquestions"], start=1)]
            L += ["", f"**Per-hop ids:** {agent_cell['trace'].get('per_hop')} → merged "
                      f"{agent_cell['retrieved_ids']} "
                      f"(deduped away {agent_cell['trace'].get('dropped')})", ""]
        for arm in RETRIEVAL_ARMS:
            cell = r["arms"].get(arm)
            if not cell:
                continue
            g = cell.get("groundedness") or {}
            L += [f"**`{arm}`** — depth {cell['depth']}, hit {cell['at_k']['hit']:.0f}, "
                  f"recall@{k} {cell['at_k']['recall']:.3f}, rr {cell['at_k']['rr']:.3f}, "
                  f"grounded {_fmt(g.get('score'))}"
                  + (f" ({g['supported']}/{g['total']})" if g.get("total") is not None else "")
                  + (f" · judge parse failed: {g['error']}" if g.get("error") else ""),
                  "",
                  "  " + " · ".join(f"[{i}] {t}" for i, t in
                                    zip(cell["retrieved_ids"], cell["retrieved_titles"])),
                  "", f"  {cell['answer']}", ""]
        if r.get("delta"):
            d = r["delta"]
            L += [f"**Δ agent−simple:** recall {d['recall']:+.3f}, "
                  f"gained {d['golds_gained'] or '[]'}, lost {d['golds_lost'] or '[]'}, "
                  f"+{d['extra_llm_calls']} LLM calls, +{d['extra_ms']} ms", ""]
    return "\n".join(L) + "\n"


def _print_summary(report: dict) -> None:
    run = report["run"]
    print("\n=== Routing policies ===")
    for p in POLICIES:
        row = report["policies"].get(p)
        if row:
            print(f"  {p:<15} n={row['n']:<3} recall@k={_fmt(row['recall@k'])}  "
                  f"hit@k={_fmt(row['hit@k'])}  grounded={_fmt(row['groundedness'])}  "
                  f"{row['llm_calls_per_q']} LLM/q  ${row['est_cost_usd']:.3f}")
        else:
            print(f"  {p:<15} - (needs an arm this run did not include)")
    print("\n=== agent - simple (depth k) ===")
    for b in ("overall", "multi-hop", "expected=complex"):
        d = report["delta"].get(b)
        if d:
            print(f"  {b:<18} n={d['n']:<3} recall {d['recall@k']:+.3f}  "
                  f"hit {d['hit@k']:+.3f}  mrr {d['mrr']:+.3f}")
    rt = report["router"]
    if rt:
        print(f"\nRouter: accuracy={rt['accuracy']:.3f} stability={rt['stability']:.3f} "
              f"confusion={rt['confusion']}")
    print(f"\nAPI calls {run['api_calls']}  est ${run['estimated_cost_usd']:.3f}  "
          f"{run['wall_seconds']:.0f}s")


# ========================================================================================
# Preflight, selftest, CLI
# ========================================================================================

def _check_routes(items: list[dict], allow_infer: bool) -> bool:
    """Ensure every item carries a gold `expected_route`. Returns routes_inferred."""
    missing = [it["id"] for it in items if not it.get("expected_route")]
    if not missing:
        return False
    if not allow_infer:
        raise SystemExit(
            f"These test items have no expected_route: {missing}\n"
            f"Router accuracy needs a hand-labelled gold route ('complex' iff a complete "
            f"answer needs two or more DISTINCT pages; two editions of one page count as "
            f"one). Add it, or pass --infer-routes to derive it from `category` and have "
            f"the number reported as advisory."
        )
    for it in items:
        it.setdefault("expected_route", _infer_route(it))
    return True


def _preflight(mode: str, arms: tuple, do_judge: bool) -> None:
    """Fail before spending money, not twenty minutes in."""
    bad = [a for a in arms if a not in ARMS]
    if bad:
        # pipeline.answer treats any non-"complex" route as simple with no error, so a
        # typo'd arm would silently measure the simple arm twice.
        raise SystemExit(f"unknown arm(s) {bad}; valid arms are {list(ARMS)}")
    if mode not in ("dense", "hybrid", "hybrid_rerank"):
        raise SystemExit(f"unknown --mode {mode!r}; retrieve.retrieve() would sys.exit()")
    if mode == "hybrid_rerank" and not config.COHERE_API_KEY:
        raise SystemExit("mode hybrid_rerank needs COHERE_API_KEY; or pass --mode hybrid")
    if config.LLM_BACKEND == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("UBCAL_LLM_BACKEND=anthropic but ANTHROPIC_API_KEY is unset")
    print(f"Warming the index ... {retrieve.warmup()} chunks")
    if do_judge:
        try:
            judge.supported_claims("The sky is blue.", ["The sky is blue."])
        except Exception as exc:
            raise SystemExit(
                f"The judge is not reachable at {config.OPENAI_BASE_URL} "
                f"(model {config.JUDGE_MODEL}): {type(exc).__name__}: {exc}\n"
                f"Start LM Studio and load the judge model, or pass --no-judge."
            )


def _selftest() -> None:
    """Exercise the pure helpers on synthetic data. No index, no keys, no network."""
    assert _score([1, 2, 3, 9], [9], 4) == {"hit": 1.0, "recall": 1.0, "rr": 0.25}
    assert _score([1, 2, 3, 9], [9], 3) == {"hit": 0.0, "recall": 0.0, "rr": 0.0}, \
        "rr must be computed on the sliced list, or a deep arm gets free credit"
    assert _score([5, 6], [5, 7], 2)["recall"] == 0.5
    assert _infer_route({"category": "multi-hop"}) == "complex"
    assert _infer_route({"category": "collision"}) == "simple"
    assert _slim({"kind": "step", "title": "x"}) is None
    assert _slim({"kind": "llm_call", "purpose": "route", "ms": 5, "system": "x" * 9999}) \
        == {"kind": "llm_call", "purpose": "route", "ms": 5}
    counts = {"llm": 0, "embed": 0, "rerank": 0}
    for ev in ({"kind": "llm_call"}, {"kind": "llm_call"}, {"kind": "retrieval_start"},
               {"kind": "shortlist"}, {"kind": "step"}):
        _tally(counts, ev)
    assert counts == {"llm": 2, "embed": 1, "rerank": 1}, counts
    assert _llm_ms_by_purpose([{"kind": "llm_call", "purpose": "route", "ms": 10},
                               {"kind": "llm_call", "purpose": "route", "ms": 5}]) \
        == {"route": 15}
    assert _per_hop_gold([[1, 2], [3]], [2, 3]) == [[2], [3]]
    assert _hop_attribution([[1], [2]], [2, 9]) == {2: 2, 9: None}
    rec = {"router": {"decision": "complex"}, "expected_route": "simple"}
    assert _policy_pick(rec, "router") == "agent"
    assert _policy_pick(rec, "oracle") == "simple"
    assert _policy_pick(rec, "always_simple") == "simple"
    assert _policy_pick(rec, "always_complex") == "agent"
    r = {"type": "specific", "category": "multi-hop", "expected_route": "complex"}
    assert _in_bucket(r, "overall") and _in_bucket(r, "multi-hop")
    assert _in_bucket(r, "expected=complex") and not _in_bucket(r, "general")
    assert _cost_usd({"llm": 2, "rerank": 1}) == round(2 * 0.0015 + 0.002, 4)
    try:  # the duplicated paid-call table must not drift from the web layer's copy
        from web import limits as _limits
        assert PAID_EVENT_KINDS == _limits.PAID_EVENT_KINDS, "drifted from web/limits.py"
        assert PRICES == _limits.PRICES, "prices drifted from web/limits.py"
    except ImportError:
        pass
    print("selftest: all pure helpers OK")


def run(items: list[dict], *, k: int, mode: str, arms: tuple, router_votes: int,
        do_judge: bool, full_judge: bool, pace: float, dump_fh) -> tuple[list, list]:
    chunk_by_id = {r["id"]: r for r in retrieve._load_index()[1]}
    per_item, failures = [], []
    for n, item in enumerate(items, start=1):
        started = time.perf_counter()
        try:
            record = _run_item(item, k=k, mode=mode, arms=arms, router_votes=router_votes,
                               chunk_by_id=chunk_by_id, do_judge=do_judge,
                               full_judge=full_judge, dump_fh=dump_fh)
        except SystemExit:
            raise                        # a broken harness must not be swallowed as a datum
        except Exception as exc:
            failures.append((item["id"], f"{type(exc).__name__}: {exc}"))
            print(f"  [{n}/{len(items)}] {item['id']}  FAILED — {type(exc).__name__}: {exc}")
            continue
        per_item.append(record)
        d = record.get("delta") or {}
        print(f"  [{n}/{len(items)}] {item['id']} ({record['category']})  "
              f"d_recall={d.get('recall', 0):+.3f}  "
              f"route={(record.get('router') or {}).get('decision', '-')}"
              f"/{record['expected_route']}  "
              f"{time.perf_counter() - started:.1f}s")
        if pace:
            time.sleep(pace)
    return per_item, failures


def main() -> None:
    p = argparse.ArgumentParser(description="Run the agent-vs-simple eval (Phase 4).")
    p.add_argument("--name", default="agent-vs-simple", help="label for this run")
    p.add_argument("--k", type=int, default=config.EVAL_K, help="retrieval depth / @k")
    p.add_argument("--limit", type=int, default=None, help="only the first N questions")
    p.add_argument("--mode", default=config.RETRIEVAL_MODE,
                   help="dense | hybrid | hybrid_rerank (dense/hybrid make NO Cohere calls)")
    p.add_argument("--arms", default=",".join(ARMS), help=f"comma list of {list(ARMS)}")
    p.add_argument("--no-general", action="store_true", help="skip testset.general.json")
    p.add_argument("--no-judge", action="store_true", help="skip groundedness and the judge")
    p.add_argument("--full-judge", action="store_true",
                   help="also run judge_item's four RAGAS metrics (slow, local)")
    p.add_argument("--router-votes", type=int, default=config.AGENT_EVAL_ROUTER_VOTES,
                   help="classify() calls per question; >1 measures stability")
    p.add_argument("--no-router", action="store_true", help="skip the router pass entirely")
    p.add_argument("--infer-routes", action="store_true",
                   help="derive expected_route from category instead of failing")
    p.add_argument("--pace", type=float, default=config.AGENT_EVAL_PACE_SECONDS,
                   help="seconds to sleep between questions (Cohere is 10 rerank/min)")
    p.add_argument("--dump-traces", nargs="?", const=str(config.AGENT_TRACE_DUMP_PATH),
                   default=None, help="write the unslimmed event stream as JSONL")
    p.add_argument("--selftest", action="store_true", help="pure helpers only, then exit")
    args = p.parse_args()

    # Provider error strings and calendar text can carry non-ASCII, and a cp1252 Windows
    # console raises on them mid-run -- after the paid calls are already spent. Same guard
    # src/trace.py:enable() uses, for the same reason.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if args.selftest:
        _selftest()
        return

    arms = tuple(a.strip() for a in args.arms.split(",") if a.strip())
    do_judge = not args.no_judge
    votes = 0 if args.no_router else max(1, args.router_votes)

    items = _load_items(config.TESTSET_PATH, "specific")
    if not args.no_general:
        items += _load_items(config.GENERAL_TESTSET_PATH, "general")
    if args.limit:
        items = items[: args.limit]
    routes_inferred = _check_routes(items, args.infer_routes)
    _preflight(args.mode, arms, do_judge)

    print(f"Running '{args.name}' over {len(items)} questions "
          f"(k={args.k}, mode={args.mode}, arms={list(arms)}, "
          f"judge={'on' if do_judge else 'off'}, router_votes={votes}, pace={args.pace}s) ...")

    dump_fh = None
    if args.dump_traces:
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        dump_fh = open(args.dump_traces, "w", encoding="utf-8")
    started = time.perf_counter()
    try:
        per_item, failures = run(items, k=args.k, mode=args.mode, arms=arms,
                                 router_votes=votes, do_judge=do_judge,
                                 full_judge=args.full_judge, pace=args.pace,
                                 dump_fh=dump_fh)
    finally:
        if dump_fh is not None:
            dump_fh.close()

    if not per_item:
        raise SystemExit("every question failed; nothing to report")

    report = _aggregate(per_item, k=args.k, mode=args.mode, name=args.name, arms=arms,
                        judged=do_judge, full_judge=args.full_judge,
                        routes_inferred=routes_inferred, router_votes=votes,
                        wall_seconds=time.perf_counter() - started, failures=failures)
    _print_summary(report)
    path = write_report(report, args.name)
    print(f"\nWrote:\n  {path}\n  {config.AGENT_HISTORY_PATH}")
    if failures:
        # Keep the paid data, but never let a degraded run look clean.
        raise SystemExit(f"\n{len(failures)} question(s) failed: "
                         + ", ".join(i for i, _ in failures))


if __name__ == "__main__":
    main()
