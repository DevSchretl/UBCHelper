"""Render pipeline trace events as HTML, for the Gradio Space.

The page shows a run as four connected stages: Plan, Search, Rank and Answer. A row of stage
cards fills in as the pipeline moves, and one panel per stage sits underneath. This module
turns the trace event stream into that markup on the server, because Gradio owns the page and
there is nowhere to hang a client-side renderer. `web/static/app.js` builds the same markup in
the browser for the FastAPI and static builds, so `web/static/panels.css` styles both and
`web/static/stages.js` handles the clicking in both.

`Renderer` is fed events one at a time and can emit its current HTML after each, which is what
makes the cards animate as the pipeline runs rather than appearing all at once. It never knows
which stage a visitor is looking at. That choice lives in the browser (stages.js), so a live
update can never pull someone away from the stage they opened.
"""

from __future__ import annotations

import re
import uuid
from html import escape as _e

STAGES = ("plan", "search", "rank", "answer")
_NAMES = {"plan": "Plan", "search": "Search", "rank": "Rank", "answer": "Answer"}
_BLURBS = {
    "plan": "The router decides how to search",
    "search": "Vector and keyword search",
    "rank": "Fuse, rerank, keep the best",
    "answer": "Claude writes it up",
}

# Chips worth surfacing on a result card, in display order. `edition_year` and
# `cohort_qualifier` come first because they are the whole point of this corpus: they are
# what separates the near-identical twins that naive top-k RAG confuses.
_CHIP_FIELDS = ("page_type", "faculty", "program", "subject_code")

# Stroke icons on a 24px grid, inlined so the page needs no icon font or extra request.
_PATHS = {
    "plan": '<path d="M12 20v-7"/><path d="M12 13 6.5 7.5"/><path d="m12 13 5.5-5.5"/>'
            '<path d="M6 11V7h4"/><path d="M18 11V7h-4"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5"/>',
    "rank": '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
    "answer": '<path d="M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-7l-4 3.5V16H5a1 1 0 0 1-1-1V6'
              'a1 1 0 0 1 1-1z"/><path d="M8 9.5h8M8 12.5h5"/>',
    "check": '<path d="m5 12.5 4.2 4.2L19 7"/>',
    "left": '<path d="M19 12H5"/><path d="m11 6-6 6 6 6"/>',
    "right": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
}


def _icon(name: str, cls: str = "") -> str:
    return (f'<svg class="st-i {cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f"{_PATHS[name]}</svg>")


def _fmt(value: float, places: int = 3) -> str:
    return f"{float(value):.{places}f}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _badge(part: int) -> str:
    """The numbered dot that follows one sub-question through every stage."""
    return f'<span class="part-badge p{part + 1}" title="Part {part + 1}">{part + 1}</span>'


def _first_line(markdown: str) -> str:
    """The answer's opening line without Markdown marks, for the Answer card's preview."""
    for line in markdown.splitlines():
        text = re.sub(r"[#>*_`]+", "", line).strip()
        if text:
            return text
    return ""


class Renderer:
    """Accumulates trace events and renders the stage bar and the four stage panels."""

    def __init__(self, question: str, chunks: int | None = None, model: str = "") -> None:
        self.question = question
        self.chunks = chunks
        self.model = model
        self.run_id = uuid.uuid4().hex[:8]
        self.started = False
        # Per stage: idle, active, waiting (done for now, more parts to come), done, stopped.
        self.state = dict.fromkeys(STAGES, "idle")
        self.status = ""
        self.route = ""          # "simple" or "complex", once known
        self.forced = False      # True when Search settings fixed the route and the router was skipped
        self.merging = False
        self.parts: list[str] = []
        self.calls: dict[str, dict] = {}     # the llm_call events, by purpose: route, decompose, answer
        self.hops: list[dict] = []           # one per search, so one per part on the complex route
        self.merge: dict | None = None
        self.docs: dict[int, dict] = {}
        self.order: list[int] = []
        self.notes: dict[str, list[str]] = {stage: [] for stage in STAGES}
        self.flow: tuple[str, int] | None = None   # (stage, part): the arrow that animates next paint
        self.answer_text = ""
        self.error = ""

    # ---------------------------------------------------------------- ingest
    def feed(self, event: dict) -> None:
        handler = getattr(self, f"_on_{event.get('kind')}", None)
        if handler:
            handler(event)

    def _part_note(self, i: int) -> str:
        return f" for part {i + 1} of {len(self.parts)}" if len(self.parts) > 1 else ""

    def _current(self) -> str:
        """The stage a trace line belongs to: the running one, else the latest one reached."""
        for stage in STAGES:
            if self.state[stage] == "active":
                return stage
        reached = [stage for stage in STAGES if self.state[stage] != "idle"]
        return reached[-1] if reached else "plan"

    def _plan_done(self) -> None:
        if self.state["plan"] != "done":
            self.state["plan"] = "done"
            self.flow = ("plan", 0)

    def _search_done(self) -> None:
        i = len(self.hops) - 1
        more = len(self.parts) > 1 and i < len(self.parts) - 1
        self.state["search"] = "waiting" if more else "done"
        self.flow = ("search", i)

    def _on_step(self, ev: dict) -> None:
        title = str(ev.get("title", ""))
        if title.startswith("PIPELINE - answer"):
            self.started = True
            self.state["plan"] = "active"
            self.status = "Reading your question"
        elif title.startswith("ROUTE"):
            self.state["plan"] = "active"
            self.status = "Deciding whether this needs one search or several"
        elif title.startswith("AGENT - decompose"):
            if not self.route:     # no router call came first, so the route was set by hand
                self.route, self.forced = "complex", True
            self.state["plan"] = "active"
            self.status = "Splitting your question into parts"
        elif title.startswith("RETRIEVE - simple route"):
            if not self.route:
                self.route, self.forced = "simple", True
            self._plan_done()
        elif title.startswith("AGENT - merge"):
            self.merging = True
            self.state["rank"] = "active"
            self.status = "Combining what the searches found"
        elif title.startswith(("GENERATE", "AGENT - synthesize")):
            for stage in ("plan", "search", "rank"):
                self.state[stage] = "done"
            self.merging = False
            self.state["answer"] = "active"
            self.status = "Writing the answer"
            self.flow = ("rank", -1)

    def _on_route(self, ev: dict) -> None:
        self.route = str(ev.get("decision") or "simple")
        if self.route != "complex":
            self._plan_done()

    def _on_subquestions(self, ev: dict) -> None:
        self.parts = [str(item) for item in ev.get("items", [])]
        self._plan_done()

    def _on_llm_call(self, ev: dict) -> None:
        self.calls[str(ev.get("purpose") or "complete")] = ev

    def _on_detail(self, ev: dict) -> None:
        label, value = str(ev.get("label", "")), str(ev.get("value", ""))
        # The router's decision and the sub-questions already have a place in the Plan panel.
        if label == "decision" or label.startswith("sub-question"):
            return
        self.notes[self._current()].append(f"{label}: {value}" if value else label)

    def _on_retrieval_start(self, ev: dict) -> None:
        i = len(self.hops)
        self.hops.append({
            "query": str(ev.get("query", "")), "mode": str(ev.get("mode", "")),
            "dense": [], "bm25": [], "rrf": [], "shortlist": [], "finals": [],
        })
        self._plan_done()
        if self.state["rank"] == "active":
            self.state["rank"] = "waiting"
        self.state["search"] = "active"
        self.status = f"Searching the calendar{self._part_note(i)}"
        if i > 0:
            self.flow = ("plan", i)

    def _on_candidates(self, ev: dict) -> None:
        stage = str(ev.get("stage", ""))
        if not self.hops or stage not in ("dense", "bm25", "rrf"):
            return
        self.hops[-1][stage] = list(ev.get("items", []))
        if stage == "rrf":
            self._search_done()
            self.state["rank"] = "active"
            self.status = f"Ranking the results{self._part_note(len(self.hops) - 1)}"

    def _on_shortlist(self, ev: dict) -> None:
        if not self.hops:
            return
        ids = list(ev.get("ids", []))
        self.hops[-1]["shortlist"] = ids
        self.state["rank"] = "active"
        self.status = f"Reranking the top {len(ids)}{self._part_note(len(self.hops) - 1)}"

    def _on_retrieval_final(self, ev: dict) -> None:
        items = list(ev.get("items", []))
        for doc in items:
            self.docs[doc["id"]] = doc
        if not self.hops:
            return
        self.hops[-1]["finals"] = items
        if self.state["search"] == "active":   # vector-only mode fuses nothing, so Search ends here
            self._search_done()
        if self.route == "complex":
            self.state["rank"] = "waiting"     # the merge finishes it
        else:
            self.state["rank"] = "done"
            self.order = [doc["id"] for doc in items]

    def _on_merge(self, ev: dict) -> None:
        self.merge = ev
        self.order = list(ev.get("order", []))
        self.state["rank"] = "done"

    def _settle(self) -> None:
        """Final card states once a run has stopped, whether or not it finished."""
        if self.answer_text and not self.error:
            for stage in STAGES:
                self.state[stage] = "done"
        elif self.started:
            # The run ended early: nothing still to come is "waiting" any more.
            for stage in STAGES:
                if self.state[stage] != "done":
                    self.state[stage] = "stopped"
        self.status = ""
        self.merging = False

    # ---------------------------------------------------------------- render: all outputs
    def panels(self, running: bool = False) -> tuple[str, ...]:
        """Every output, in page order: the stage bar, the Plan, Search and Rank panels, then
        the four pieces of the Answer panel (heading and status, answer text, sources, Back and
        Next). The answer text is Markdown, for a gr.Markdown component; the rest is HTML."""
        if not running:
            self._settle()
        out = (
            self.bar_html(running), self.plan_html(), self.search_html(), self.rank_html(),
            self.answer_head_html(running), self.answer_markdown(), self.answer_side_html(),
            self.answer_nav_html(),
        )
        self.flow = None    # an arrow animates for one paint only
        return out

    # ---------------------------------------------------------------- render: the bar
    def bar_html(self, running: bool = False) -> str:
        if self.error:
            run_state = "error"
        elif running:
            run_state = "running"
        else:
            run_state = "done" if self.answer_text else "idle"
        cards = []
        for i, stage in enumerate(STAGES):
            cards.append(self._card(stage))
            if i < len(STAGES) - 1:
                cards.append(self._arrow(stage))
        return (
            '<div class="stage-top"><h2 class="stage-title">How this answer was found</h2>'
            '<p class="stage-hint"><span class="hint-touch">Tap a stage to look inside</span>'
            '<span class="hint-mouse">Click a stage to look inside, or use the arrow keys</span></p>'
            '</div>'
            f'<div class="stage-bar" role="tablist" aria-label="Pipeline stages" '
            f'data-run="{self.run_id}" data-state="{run_state}">{"".join(cards)}</div>'
        )

    def _card(self, stage: str) -> str:
        # The server always marks Answer selected; stages.js moves the selection to whatever the
        # visitor picked before the browser paints.
        selected = stage == "answer"
        return (
            f'<button type="button" class="stage-card is-{self.state[stage]}" role="tab" '
            f'id="stage-tab-{stage}" data-stage="{stage}" aria-controls="panel-{stage}" '
            f'aria-selected="{"true" if selected else "false"}" tabindex="{0 if selected else -1}">'
            f'<span class="stage-icon">{_icon(stage)}</span>'
            f'<span class="stage-label">{_NAMES[stage]}</span>'
            f'<span class="stage-count">{_icon("check", "stage-tick")}{_e(self._count(stage))}</span>'
            f'<span class="stage-blurb">{_BLURBS[stage]}</span>'
            f'<span class="stage-mini mini-{stage}" aria-hidden="true">{self._mini(stage)}</span>'
            '<span class="stage-unseen" aria-hidden="true"></span></button>'
        )

    def _found(self) -> int:
        return sum(len(hop["dense"]) + len(hop["bm25"]) for hop in self.hops)

    def _kept(self) -> int:
        return len(self.order) if self.order else sum(len(hop["finals"]) for hop in self.hops)

    def _count(self, stage: str) -> str:
        state = self.state[stage]
        if not self.started:
            return ""
        if state in ("idle", "stopped"):
            return "waiting" if state == "idle" else "stopped"
        many = len(self.parts) > 1
        part = f"part {len(self.hops)} of {len(self.parts)}…" if many else ""
        if stage == "plan":
            if state == "active":
                return "splitting…" if self.route == "complex" else "thinking…"
            return _plural(len(self.parts), "part") if many else "1 search"
        if stage == "search":
            if state == "active":
                return part or "searching…"
            return f"{self._found()} so far" if state == "waiting" else f"{self._found()} found"
        if stage == "rank":
            if state == "active":
                return "merging…" if self.merging else (part or "ranking…")
            return f"{self._kept()} kept so far" if state == "waiting" else f"{self._kept()} kept"
        return "writing…" if state == "active" else "ready"

    def _mini(self, stage: str) -> str:
        """The small live picture on each card."""
        if stage == "plan":
            if self.route == "complex" and self.parts:
                return "".join(f'<i class="p{k + 1}"></i>' for k in range(len(self.parts)))
            if self.route == "simple":
                return '<i class="one"></i>'
            return '<i class="wait"></i>'
        if stage == "search":
            n = max(len(self.parts), 1)
            dense = min(sum(1 for hop in self.hops if hop["dense"]) / n, 1)
            bm25 = min(sum(1 for hop in self.hops if hop["bm25"]) / n, 1)
            return f'<i class="md" style="--v:{dense:.2f}"></i><i class="mk" style="--v:{bm25:.2f}"></i>'
        if stage == "rank":
            found = self._found()
            fused = sum(len(hop["rrf"]) for hop in self.hops)
            short = sum(len(hop["shortlist"]) for hop in self.hops)
            kept = self._kept() if any(hop["finals"] for hop in self.hops) else 0
            bars = []
            # Until results arrive the funnel is a faint outline, at typical proportions.
            for value, nominal, keep in ((found, 1, ""), (fused, 0.87, ""), (short, 0.5, ""), (kept, 0.04, " k")):
                width = value / found if found and value else nominal
                bars.append(f'<i class="{"on" if value else ""}{keep}" style="--w:{width:.3f}"></i>')
            return "".join(bars)
        # The card's count already says "writing…" while the answer is on its way.
        if self.answer_text and not self.error:
            return _e(_first_line(self.answer_text))
        return ""

    def _arrow(self, stage: str) -> str:
        filled = {
            "plan": self.state["plan"] == "done",
            "search": any(hop["rrf"] or hop["finals"] for hop in self.hops),
            "rank": self.state["rank"] == "done",
        }[stage]
        classes = "stage-arrow" + (" is-filled" if filled else "")
        if self.flow and self.flow[0] == stage:
            classes += " is-flowing"
            if self.flow[1] >= 0 and len(self.parts) > 1:
                classes += f" part{self.flow[1] + 1}"
        return f'<span class="{classes}" aria-hidden="true">{_icon("right")}</span>'

    # ---------------------------------------------------------------- render: the panels
    def plan_html(self) -> str:
        what = ("A quick model call reads the question and decides how much searching it needs. "
                "Simple questions get one search. Comparisons and prerequisite chains are split "
                "into parts, and each part is searched on its own.")
        if not self.started:
            return _panel("plan", what, _wait("Ask a question and the router's decision shows up here."))
        # A div, not a blockquote: Gradio forces margins onto blockquotes in its HTML blocks.
        body = [f'<div class="sp-quote">{_e(self.question)}</div>']
        if self.state["plan"] == "active":
            body.append(_status(self.status))
        if self.route:
            is_complex = self.route == "complex"
            if self.forced:
                why = (f"Search settings set the route to always "
                       f"{'multi-step' if is_complex else 'single-shot'}, so the router was skipped.")
            elif is_complex:
                why = ("It needs more than one calendar page, so it is split into parts and each "
                       "part gets its own search.")
            else:
                why = "One calendar page should answer it, so it gets a single search."
            body.append(f'<div class="sp-decision"><span class="sp-pill">'
                        f'{"Complex" if is_complex else "Simple"}</span><span>{why}</span></div>')
        if "route" in self.calls:
            body.append(_prompt(self.calls["route"], "Router prompt and reply"))
        if self.parts:
            items = "".join(f"<li>{_badge(k)}<span>{_e(part)}</span></li>"
                            for k, part in enumerate(self.parts))
            body.append(f'<ol class="sp-parts">{items}</ol>')
        if "decompose" in self.calls:
            body.append(_prompt(self.calls["decompose"], "Splitting prompt and reply"))
        body.append(self._notes("plan"))
        return _panel("plan", what, "".join(body))

    def _lane_head(self, i: int) -> str:
        query = self.parts[i] if i < len(self.parts) else self.hops[i]["query"]
        return f'<div class="sp-lane-head">{_badge(i)}<span>{_e(query)}</span></div>'

    def search_html(self) -> str:
        corpus = f"all {self.chunks:,} calendar excerpts" if self.chunks else "every calendar excerpt"
        what = (f"Two searches run side by side. Vector search compares the meaning of the question "
                f"with {corpus}. Keyword search (BM25) looks for the exact words, which is how a "
                "course code like CPSC 210 gets found.")
        if not self.hops:
            empty = "Waiting for Plan." if self.started else "Ask a question and the two searches show up here."
            return _panel("search", what, _wait(empty))
        many = len(self.parts) > 1
        lanes = []
        for i in range(max(len(self.parts), len(self.hops))):
            head = self._lane_head(i) if many else ""
            if i >= len(self.hops):
                lanes.append(f'<section class="sp-lane">{head}'
                             f'{_wait(f"Part {i + 1} is searched after part {i} has been ranked.")}</section>')
            else:
                lanes.append(f'<section class="sp-lane" data-lane="{i}">{head}'
                             f'{_search_lists(self.hops[i])}</section>')
        status = _status(self.status) if self.state["search"] == "active" else ""
        first = self.hops[0]
        tech = ""
        if first["bm25"]:
            tech = (f"Each search returns its top {len(first['dense'])}. Pages that both searches "
                    "found are marked <b>both</b>, and the ones that made the final cut are marked <b>kept</b>.")
        elif first["dense"]:
            tech = f"Vector search returns its top {len(first['dense'])}, and those are what Rank keeps."
        tech = f'<p class="sp-tech">{tech}</p>' if tech else ""
        return _panel("search", what, status + "".join(lanes) + tech + self._notes("search"))

    def rank_html(self) -> str:
        first = self.hops[0] if self.hops else {"mode": "", "shortlist": [], "finals": []}
        kept = len(first["finals"]) or 4
        fuse = ("The two lists are fused into one ranking (reciprocal rank fusion), so a page that "
                "both searches found rises to the top.")
        if first["mode"] == "dense":
            what = f"Vector search only, so there is nothing to fuse: the {kept} closest excerpts are kept."
        elif first["mode"] == "hybrid":
            what = f"{fuse} The best {kept} are kept. This search mode skips the reranker."
        else:
            short = len(first["shortlist"]) or 50
            what = (f"{fuse} The top {short} go to a reranker (Cohere) that reads each excerpt "
                    f"against the question, and the best {kept} are kept.")
        many = len(self.parts) > 1
        if many:
            what += " Each part is ranked on its own, then the parts are merged."
        if not any(hop["rrf"] or hop["finals"] for hop in self.hops):
            empty = "Waiting for Search." if self.started else "Ask a question and the ranking shows up here."
            status = _status(self.status) if self.state["rank"] == "active" else ""
            return _panel("rank", what, status + _wait(empty))
        lanes = []
        for i in range(max(len(self.parts), len(self.hops))):
            head = self._lane_head(i) if many else ""
            hop = self.hops[i] if i < len(self.hops) else None
            if hop is None or not (hop["rrf"] or hop["finals"]):
                lanes.append(f'<section class="sp-lane">{head}'
                             f'{_wait(f"Part {i + 1} is ranked after it has been searched.")}</section>')
                continue
            cards = "".join(_doc_card(doc, hop, i if many else None) for doc in hop["finals"])
            if cards:
                cards = f'<div class="sp-cards">{cards}</div>'
            lanes.append(f'<section class="sp-lane">{head}{_funnel(hop)}{cards}{_fused(hop)}</section>')
        status = _status(self.status) if self.state["rank"] == "active" else ""
        merge = self._merge_html() if self.merge else ""
        return _panel("rank", what, status + "".join(lanes) + merge + self._notes("rank"))

    def _merge_html(self) -> str:
        per_hop = [list(ids) for ids in self.merge.get("per_hop", [])]
        seen: set[int] = set()
        steps = []
        for rank in range(max((len(ids) for ids in per_hop), default=0)):
            for part, ids in enumerate(per_hop):
                if rank >= len(ids):
                    continue
                title = _e(str(self.docs.get(ids[rank], {}).get("title", f"Excerpt {ids[rank]}")))
                if ids[rank] in seen:
                    steps.append(f'<li class="is-drop">{_badge(part)}<span class="sp-strike">{title}</span> (already in)</li>')
                else:
                    seen.add(ids[rank])
                    steps.append(f"<li>{_badge(part)}<span>{title}</span></li>")
        dropped = int(self.merge.get("dropped", 0))
        return (f'<section class="sp-merge"><h4>Merging the {_plural(len(per_hop), "part")}</h4>'
                "<p class=\"sp-tech\">Each part's best excerpt goes in first, then each part's second "
                f"best, and so on. Repeats are dropped. That leaves {_plural(len(self.order), 'excerpt')}, "
                f"with {_plural(dropped, 'repeat')} dropped.</p><ol>{''.join(steps)}</ol></section>")

    def answer_head_html(self, running: bool = False) -> str:
        model = str(self.calls.get("answer", {}).get("model") or self.model)
        who = f"Claude ({_e(model)})" if "claude" in model else (_e(model) or "The model")
        what = (f"{who} writes the answer using only the kept excerpts, and points you to the "
                "official calendar pages.")
        if self.error:
            body = f'<div class="notice">{_e(self.error)}</div>'
        elif self.answer_text:
            badge = "multi-step" if self.route == "complex" else "single-shot"
            body = f'<p class="sp-answer-meta"><span class="sp-badge">{badge}</span></p>'
        elif running or self.started:
            body = _status(self.status or "Reading your question")
        else:
            body = _wait("Your answer will show up here, with links to the calendar pages it came from.")
        return (f'<div class="stage-panel" role="tabpanel" aria-labelledby="stage-tab-answer">'
                f'{_head("answer", what)}<div class="sp-body">{body}</div></div>')

    def answer_markdown(self) -> str:
        """The answer itself, as Markdown for a gr.Markdown component.

        Markdown rather than HTML because the model writes Markdown: headings, bold and lists
        appear in most recorded answers. Gradio renders (and sanitises) Markdown natively, so
        this needs neither a new dependency nor a hand-rolled converter.
        """
        return "" if self.error else self.answer_text.strip()

    def _sources(self) -> list[tuple[str, str, list[int]]]:
        """(url, title, parts) for each calendar page behind the answer, in grounding order."""
        per_hop = [set(ids) for ids in (self.merge or {}).get("per_hop", [])]
        many = len(self.parts) > 1
        pages: dict[str, tuple[str, set[int]]] = {}
        for doc_id in self.order or list(self.docs):
            doc = self.docs.get(doc_id)
            if not doc or not doc.get("url"):
                continue
            parts = {k for k, ids in enumerate(per_hop) if doc_id in ids} if many else set()
            if doc["url"] in pages:
                pages[doc["url"]][1].update(parts)
            else:
                pages[doc["url"]] = (str(doc.get("title", doc["url"])), parts)
        return [(url, title, sorted(parts)) for url, (title, parts) in pages.items()]

    def answer_side_html(self) -> str:
        if self.error or not self.answer_text:
            return ""
        sources = self._sources()
        side = ""
        if sources:
            items = "".join(
                f'<li><span class="sp-badges">{"".join(_badge(p) for p in parts)}</span>'
                f'<a href="{_e(url)}" target="_blank" rel="noopener noreferrer">{_e(title)}</a></li>'
                for url, title, parts in sources)
            side += (f'<section class="sp-sources"><h4>Based on '
                     f'{_plural(len(sources), "calendar page")}</h4><ul>{items}</ul></section>')
        if "answer" in self.calls:
            side += _prompt(self.calls["answer"], "Answer prompt and reply")
        return f'<div class="sp-answer-side">{side}</div>'

    def answer_nav_html(self) -> str:
        return _nav("answer")

    def _notes(self, stage: str) -> str:
        lines = self.notes[stage]
        if not lines:
            return ""
        return (f'<details class="prompt sp-notes"><summary>Raw trace, {_plural(len(lines), "line")}'
                f'</summary><div class="prompt-body"><pre>{_e(chr(10).join(lines))}</pre></div></details>')


# -------------------------------------------------------------------- panel pieces
def _panel(stage: str, what: str, body: str) -> str:
    return (f'<div class="stage-panel" role="tabpanel" aria-labelledby="stage-tab-{stage}">'
            f'{_head(stage, what)}<div class="sp-body">{body}</div>{_nav(stage)}</div>')


def _head(stage: str, what: str) -> str:
    return (f'<div class="sp-head"><span class="sp-icon">{_icon(stage)}</span><div>'
            f'<p class="sp-eyebrow">Stage {STAGES.index(stage) + 1} of 4</p>'
            f'<h3 class="sp-title">{_NAMES[stage]}</h3></div></div><p class="sp-what">{what}</p>')


def _nav(stage: str) -> str:
    i = STAGES.index(stage)
    back = ""
    if i:
        back = (f'<button type="button" class="sp-btn" data-go="{STAGES[i - 1]}">'
                f'{_icon("left")}{_NAMES[STAGES[i - 1]]}</button>')
    if i < len(STAGES) - 1:
        nxt = (f'<button type="button" class="sp-btn sp-next" data-go="{STAGES[i + 1]}">'
               f'Next: {_NAMES[STAGES[i + 1]]}{_icon("right")}</button>')
    else:
        nxt = ('<button type="button" class="sp-btn sp-next" data-go="plan">'
               "See how it was found: start at Plan</button>")
    return f'<div class="sp-nav">{back}{nxt}</div>'


def _status(text: str) -> str:
    return (f'<div class="sp-status"><span class="sp-dot" aria-hidden="true"></span>'
            f"<span>{_e(text)}</span></div>")


def _wait(text: str) -> str:
    return f'<div class="sp-wait">{text}</div>'


def _prompt(call: dict, label: str) -> str:
    return (
        '<details class="prompt">'
        f'<summary>{_e(label)}<span class="prompt-meta">{_e(str(call.get("model", "")))} · '
        f'{call.get("ms", 0)} ms</span></summary><div class="prompt-body">'
        f'<h4>System</h4><pre>{_e(str(call.get("system", "")))}</pre>'
        f'<h4>User</h4><pre>{_e(str(call.get("user", "")))}</pre>'
        f'<h4>Reply</h4><pre>{_e(str(call.get("reply", "")))}</pre></div></details>'
    )


def _search_lists(hop: dict) -> str:
    if not hop["dense"]:
        return _wait("Searching…")
    vector_only = hop["mode"] == "dense"
    both: set[int] = set()
    if hop["bm25"]:
        both = {c["id"] for c in hop["dense"]} & {c["id"] for c in hop["bm25"]}
    kept = {doc["id"] for doc in hop["finals"]}
    lists = [_cand_list("dense", "Vector search", hop["dense"], both, kept, 4)]
    if vector_only:
        lists.append('<div class="sp-list bm25"><div class="sp-list-head">Keyword search</div>'
                     '<div class="sp-wait">Off in this search mode.</div></div>')
    else:
        lists.append(_cand_list("bm25", "Keyword search", hop["bm25"], both, kept, 2))
    keyword = f"Keyword {len(hop['bm25'])}" if hop["bm25"] else "Keyword off"
    toggle = ('<div class="sp-toggle" role="group" aria-label="Which list to show">'
              f'<button type="button" data-pick="dense" aria-pressed="true">Vector {len(hop["dense"])}</button>'
              f'<button type="button" data-pick="bm25" aria-pressed="false">{keyword}</button></div>')
    return f'{toggle}<div class="sp-lists">{"".join(lists)}</div>'


def _cand_row(cand: dict, both: set[int], kept: set[int], places: int, cut: bool = False) -> str:
    flags = ""
    if cand["id"] in both:
        flags += '<span class="sp-flag both" title="Found by both searches">both</span>'
    if cand["id"] in kept:
        flags += '<span class="sp-flag kept" title="Kept for the answer">kept</span>'
    if cut:
        flags += '<span class="sp-flag cut" title="Not sent to the reranker">cut</span>'
    title = _e(str(cand.get("title", "")))
    classes = "sp-row" + (" is-kept" if cand["id"] in kept else "") + (" is-cut" if cut else "")
    return (f'<li class="{classes}"><span class="sp-rid">{cand["id"]}</span>'
            f'<span class="sp-rtitle" title="{title}">{title}</span><span class="sp-flags">{flags}</span>'
            f'<span class="sp-rscore">{_fmt(cand["score"], places)}</span></li>')


def _cand_list(kind: str, name: str, items: list[dict], both: set[int], kept: set[int], places: int) -> str:
    rows = [_cand_row(c, both, kept, places) for c in items]
    more = ""
    if len(rows) > 5:
        more = (f'<details class="sp-more"><summary>Show all {len(rows)}</summary>'
                f'<ol class="sp-rows">{"".join(rows[5:])}</ol></details>')
    return (f'<div class="sp-list {kind}"><div class="sp-list-head">{name}'
            f'<span class="sp-n">top {len(items)}</span></div>'
            f'<ol class="sp-rows">{"".join(rows[:5])}</ol>{more}</div>')


def _funnel(hop: dict) -> str:
    found = len(hop["dense"]) + len(hop["bm25"])
    if not found:
        return ""
    split = (f'<i class="d" style="flex-grow:{len(hop["dense"])}"></i>'
             f'<i class="k" style="flex-grow:{len(hop["bm25"])}"></i>')
    rows = [("Candidates", found, "split", split)]
    if hop["rrf"]:
        rows.append(("After fusing", len(hop["rrf"]), "", ""))
    if hop["shortlist"]:
        rows.append(("Sent to reranker", len(hop["shortlist"]), "", ""))
    if hop["finals"]:
        rows.append(("Kept", len(hop["finals"]), "keep", ""))
    return '<div class="sp-funnel">' + "".join(
        f'<div class="fn-row"><span class="fn-label">{label}</span><span class="fn-track">'
        f'<span class="fn-bar {cls}" style="--w:{value / found:.4f}">{inner}</span></span>'
        f'<span class="fn-val">{value}</span></div>'
        for label, value, cls, inner in rows) + "</div>"


def _fused(hop: dict) -> str:
    if not hop["rrf"]:
        return ""
    kept = {doc["id"] for doc in hop["finals"]}
    short = set(hop["shortlist"])
    rows = "".join(_cand_row(c, set(), kept, 4, cut=bool(short) and c["id"] not in short)
                   for c in hop["rrf"])
    return (f'<details class="prompt sp-fused"><summary>The fused ranking, all {len(hop["rrf"])}'
            f'<span class="prompt-meta">RRF</span></summary>'
            f'<div class="sp-list fused"><ol class="sp-rows sp-scroll">{rows}</ol></div></details>')


def _doc_card(doc: dict, hop: dict, part: int | None) -> str:
    chips = []
    if doc.get("edition_year"):
        chips.append(f'<span class="tag edition">{_e(str(doc["edition_year"]))}</span>')
    if doc.get("cohort_qualifier"):
        chips.append('<span class="tag cohort">cohort-specific</span>')
    for field in _CHIP_FIELDS:
        if doc.get(field):
            chips.append(f'<span class="tag">{_e(str(doc[field]))}</span>')
    found_by = []
    for kind, label, css in (("dense", "vector", "dv"), ("bm25", "keyword", "kw")):
        if not hop[kind]:
            continue
        rank = next((r for r, c in enumerate(hop[kind], start=1) if c["id"] == doc["id"]), 0)
        found_by.append(f'<span class="{css}">{label} #{rank}</span>' if rank
                        else f"not in the {label} top {len(hop[kind])}")
    section = f'<p class="doc-section">{_e(str(doc["section"]))}</p>' if doc.get("section") else ""
    chip_row = f'<div class="doc-chips">{"".join(chips)}</div>' if chips else ""
    provenance = f'<p class="doc-prov">Found by {" · ".join(found_by)}</p>' if found_by else ""
    link = ""
    if doc.get("url"):
        link = (f'<div class="doc-actions"><a href="{_e(str(doc["url"]))}" target="_blank" '
                'rel="noopener noreferrer">Official page ↗</a></div>')
    badge = _badge(part) if part is not None else ""
    return (
        '<article class="doc">'
        f'<div class="doc-head">{badge}<span class="doc-title">{_e(str(doc.get("title", "")))}</span>'
        f'<span class="doc-score" title="Relevance score">id {doc["id"]} · {_fmt(doc["score"])}</span></div>'
        f"{section}{chip_row}{provenance}{link}"
        '<details class="excerpt"><summary>Excerpt</summary>'
        f'<div class="doc-text">{_e(str(doc.get("text", "")))}</div></details></article>'
    )
