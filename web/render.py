"""Render pipeline trace events as HTML, for the Gradio Space.

The FastAPI build streams raw trace events to the browser and lets `web/static/app.js`
build the DOM. ZeroGPU — the free tier that can actually run Python — is Gradio-SDK-only,
and Gradio owns the page, so there is nowhere to hang that JS. This module does the same
job server-side: same event stream in, the same markup out, so `web/static/styles.css`
styles both without a single change.

`Renderer` is fed events one at a time and can emit its current HTML after each, which is
what makes the stepper animate as the pipeline runs rather than appearing all at once.
"""

from __future__ import annotations

from html import escape as _e

# Chips worth surfacing on a result card, in display order. `edition_year` and
# `cohort_qualifier` come first because they are the whole point of this corpus: they are
# what separates the near-identical twins that naive top-k RAG confuses.
_CHIP_FIELDS = ("page_type", "faculty", "program", "subject_code")


def _fmt(value: float, places: int = 3) -> str:
    return f"{float(value):.{places}f}"


class Renderer:
    """Accumulates trace events and renders the three panels."""

    def __init__(self, question: str) -> None:
        self.question = question
        self.steps: list[dict] = []      # {title, meta: [html], extras: [html]}
        self.hops: list[dict] = []       # {query, columns, shortlist, finals}
        self.docs: dict[int, dict] = {}
        self.order: list[int] = []
        self.answer_text = ""
        self.route = ""
        self.error = ""
        # Paid-API call counts, tallied straight off the event stream. Every paid call
        # announces itself — one `llm_call` per generation, one `retrieval_start` per query
        # embedding, one `shortlist` per Cohere rerank — so this stays correct on its own if
        # the pipeline's shape ever changes.
        self.calls = {"llm": 0, "embed": 0, "rerank": 0}

    # ---------------------------------------------------------------- ingest
    def feed(self, event: dict) -> None:
        kind = event.get("kind")
        handler = getattr(self, f"_on_{kind}", None)
        if handler:
            handler(event)

    def _step(self) -> dict:
        if not self.steps:
            self.steps.append({"title": "Running", "meta": [], "extras": []})
        return self.steps[-1]

    def _on_step(self, ev: dict) -> None:
        self.steps.append({"title": _pretty_step(ev["title"]), "meta": [], "extras": []})

    def _on_detail(self, ev: dict) -> None:
        self._step()["meta"].append(
            f"{_e(str(ev['label']))}: <code>{_e(str(ev['value']))}</code>"
        )

    def _on_route(self, ev: dict) -> None:
        decision = ev["decision"]
        tail = ("decomposed and retrieved per sub-question."
                if decision == "complex" else "answered from a single retrieval.")
        self._step()["meta"].append(
            f"Classified as <strong>{_e(decision)}</strong> — {tail}"
        )

    def _on_subquestions(self, ev: dict) -> None:
        items = "".join(f"<li>{_e(s)}</li>" for s in ev["items"])
        self._step()["extras"].append(f'<ol class="subq">{items}</ol>')

    def _on_llm_call(self, ev: dict) -> None:
        self.calls["llm"] += 1
        self._step()["extras"].append(
            '<details class="prompt">'
            f'<summary>prompt &amp; reply — {_e(ev["model"])} · {ev["ms"]} ms</summary>'
            '<div class="prompt-body">'
            f'<h4>System</h4><pre>{_e(ev["system"])}</pre>'
            f'<h4>User</h4><pre>{_e(ev["user"])}</pre>'
            f'<h4>Reply</h4><pre>{_e(ev["reply"])}</pre>'
            "</div></details>"
        )

    def _on_merge(self, ev: dict) -> None:
        self.order = ev["order"]
        dropped = ev["dropped"]
        self._step()["meta"].append(
            f"Interleaved {len(ev['per_hop'])} rankings round-robin → "
            f"<strong>{len(ev['order'])}</strong> unique excerpts "
            f"({dropped} duplicate{'' if dropped == 1 else 's'} dropped)."
        )

    def _on_retrieval_start(self, ev: dict) -> None:
        self.calls["embed"] += 1
        self.hops.append({
            "query": ev["query"], "columns": {}, "shortlist": set(), "finals": [],
        })

    def _on_candidates(self, ev: dict) -> None:
        if self.hops:
            self.hops[-1]["columns"][ev["stage"]] = ev["items"]

    def _on_shortlist(self, ev: dict) -> None:
        self.calls["rerank"] += 1
        if self.hops:
            self.hops[-1]["shortlist"] = set(ev["ids"])

    def _on_retrieval_final(self, ev: dict) -> None:
        if self.hops:
            self.hops[-1]["finals"] = ev["items"]
        for doc in ev["items"]:
            self.docs[doc["id"]] = doc
        if not self.order:
            self.order = [d["id"] for d in ev["items"]]

    # ---------------------------------------------------------------- render
    def trace_html(self, running: bool = False) -> str:
        if not self.steps:
            return '<div class="empty">Ask a question to watch the pipeline execute.</div>'
        rows = []
        for i, step in enumerate(self.steps):
            last = i == len(self.steps) - 1
            state = "active" if (running and last) else "done"
            meta = "".join(f'<div class="step-meta">{m}</div>' for m in step["meta"])
            rows.append(
                f'<li class="{state}"><div class="step-title">{_e(step["title"])}</div>'
                f'{meta}{"".join(step["extras"])}</li>'
            )
        return f'<ol class="trace">{"".join(rows)}</ol>'

    def retrieval_html(self) -> str:
        if not self.hops:
            return '<div class="empty">Candidate documents will appear here.</div>'
        blocks = []
        for i, hop in enumerate(self.hops, start=1):
            multi = len(self.hops) > 1 or hop["query"].strip() != self.question.strip()
            label = f"Sub-question {i}" if multi else "Single query"
            survivors = {d["id"] for d in hop["finals"]}
            columns = "".join(
                _column(name, css, hop["columns"].get(key, []), hop["shortlist"], survivors)
                for key, name, css in (
                    ("dense", "Dense", "dense"),
                    ("bm25", "BM25", "bm25"),
                    ("rrf", "RRF fused", "rrf"),
                )
            )
            finals = ""
            if hop["finals"]:
                finals = (
                    '<div class="finals">'
                    f'<h3 class="finals-head">Final top-{len(hop["finals"])}</h3>'
                    + "".join(_doc_card(d) for d in hop["finals"]) + "</div>"
                )
            blocks.append(
                f'<div class="hop"><div class="hop-head"><strong>{_e(label)}</strong> — '
                f'<span class="q">{_e(hop["query"])}</span></div>'
                f'<div class="columns">{columns}</div>'
                '<p class="cand-legend"><span class="swatch sl"></span><b>shortlisted</b> '
                'for reranking &nbsp;·&nbsp; <span class="swatch sv"></span><b>survived</b> '
                "into the final top-k</p>"
                f"{finals}</div>"
            )
        return "".join(blocks)

    def answer_html(self) -> str:
        if self.error:
            return f'<div class="notice">{_e(self.error)}</div>'
        if not self.answer_text:
            return ""
        badge = "agentic route" if self.route == "complex" else "simple route"
        seen, links = set(), []
        for doc_id in self.order or list(self.docs):
            doc = self.docs.get(doc_id)
            if not doc or not doc.get("url") or doc["url"] in seen:
                continue
            seen.add(doc["url"])
            links.append(
                f'<li><a href="{_e(doc["url"])}" target="_blank" rel="noopener noreferrer">'
                f'{_e(doc["title"])}</a></li>'
            )
        sources = ""
        if links:
            plural = "s" if len(links) > 1 else ""
            sources = (f'<div class="sources"><h3>Grounded in {len(links)} calendar '
                       f'page{plural}</h3><ul>{"".join(links)}</ul></div>')
        return (
            f'<div class="answer-section"><h2>Answer '
            f'<span class="route-badge">{_e(badge)}</span></h2>'
            f'<div class="answer">{_e(self.answer_text)}</div>{sources}</div>'
        )

    def panels(self, running: bool = False) -> tuple[str, str, str]:
        return self.trace_html(running), self.retrieval_html(), self.answer_html()


def _column(name: str, css: str, items: list[dict], shortlist: set, survivors: set) -> str:
    rows = []
    for cand in items:
        classes = ["cand"]
        if cand["id"] in shortlist:
            classes.append("shortlisted")
        if cand["id"] in survivors:
            classes.append("survivor")
        rows.append(
            f'<li class="{" ".join(classes)}" title="{_e(cand["title"])}">'
            f'<span class="cid">{cand["id"]}</span><span>{_fmt(cand["score"], 4)}</span></li>'
        )
    count = f"({len(items)})" if items else ""
    return (f'<div class="column {css}"><h3>{name} <span>{count}</span></h3>'
            f'<ul class="cand-list">{"".join(rows)}</ul></div>')


def _doc_card(doc: dict) -> str:
    chips = []
    if doc.get("edition_year"):
        chips.append(f'<span class="tag edition">{_e(doc["edition_year"])}</span>')
    if doc.get("cohort_qualifier"):
        chips.append('<span class="tag cohort">cohort-specific</span>')
    for field in _CHIP_FIELDS:
        if doc.get(field):
            chips.append(f'<span class="tag">{_e(str(doc[field]))}</span>')

    section = (f'<div class="doc-section">{_e(doc["section"])}</div>'
               if doc.get("section") else "")
    link = (f'<a href="{_e(doc["url"])}" target="_blank" rel="noopener noreferrer">'
            f"official page ↗</a>") if doc.get("url") else ""
    return (
        '<div class="doc"><div class="doc-head">'
        f'<span class="doc-title">{_e(doc["title"])}</span>'
        f'<span class="doc-score">id {doc["id"]} · {_fmt(doc["score"])}</span></div>'
        f'{section}<div class="doc-chips">{"".join(chips)}</div>'
        f'<div class="doc-actions">{link}</div>'
        f'<details class="excerpt"><summary>excerpt</summary>'
        f'<div class="doc-text">{_e(doc.get("text", ""))}</div></details></div>'
    )


def _pretty_step(title: str) -> str:
    """"AGENT - decompose ..." -> "Agent: decompose ...". Keeps the substance, drops the shouting."""
    parts = title.split(" - ", 1)
    if len(parts) == 2 and parts[0].isupper():
        title = f"{parts[0][0]}{parts[0][1:].lower()}: {parts[1]}"
    return title if len(title) <= 150 else title[:149] + "…"
