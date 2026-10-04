/* UBC Calendar RAG demo: event-stream renderer.
 *
 * The page is driven entirely by the pipeline's own trace events, which arrive in the order
 * they happen. Every mode below emits the same frames, so there is exactly one rendering
 * path: `handle()` does not know or care where its events came from.
 *
 * A run is drawn as four connected stages (Plan, Search, Rank, Answer): a row of stage cards
 * and one panel per stage. `Renderer` below is a port of web/render.py, which draws the same
 * markup server-side for the Gradio Space, so panels.css styles both builds and stages.js
 * (which keeps track of the open stage) serves both. Keep the two renderers in step.
 *
 * Two delivery modes share this file:
 *
 *   server   FastAPI is present (`uvicorn web.app:app`). Live questions stream over SSE and
 *            cached runs replay from /api/replay. This is the full pipeline, using your keys.
 *   static   No backend at all (the Hugging Face static Space). `runs.js` defines
 *            window.DEMO_RUNS and every run replays straight from memory. No keys exist, so
 *            arbitrary questions are impossible; the ask box filters the cached set instead.
 *
 * SSE is consumed via fetch + a hand-rolled parser rather than EventSource, because
 * EventSource cannot read the body of a non-200 response, and the rate-limit and
 * budget-exhausted messages are precisely the ones a visitor needs to see.
 */
'use strict';

// Set by runs.js, which only the static build emits.
const STATIC = typeof window.DEMO_RUNS !== 'undefined';

// Replay pacing, mirrored from web/replay.py so both modes animate identically.
const FRAME_DELAY_MS = 60;
const STAGE_DELAY_MS = 250;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const el = {
  form: $('ask-form'), question: $('question'), submit: $('submit-btn'),
  mode: $('mode'), route: $('route'), budget: $('budget'), notice: $('notice'),
  examples: $('example-chips'), noMatch: $('no-match'),
  bar: $('stage-bar'), plan: $('panel-plan'), search: $('panel-search'), rank: $('panel-rank'),
  head: $('answer-head'), answer: $('answer-md'), side: $('answer-side'), nav: $('answer-nav'),
  statusDot: $('status-dot'), statusText: $('status-text'),
};

let running = false;
let abort = null;
let site = { chunks: null, model: '' };   // filled in from /api/health or runs.js

// ---------------------------------------------------------------- the stage renderer
const STAGES = ['plan', 'search', 'rank', 'answer'];
const NAMES = { plan: 'Plan', search: 'Search', rank: 'Rank', answer: 'Answer' };
const BLURBS = {
  plan: 'The router decides how to search',
  search: 'Vector and keyword search',
  rank: 'Fuse, rerank, keep the best',
  answer: 'Claude writes it up',
};
// Chips worth surfacing on a result card, after the edition and cohort chips.
const CHIP_FIELDS = ['page_type', 'faculty', 'program', 'subject_code'];
const PATHS = {
  plan: '<path d="M12 20v-7"/><path d="M12 13 6.5 7.5"/><path d="m12 13 5.5-5.5"/><path d="M6 11V7h4"/><path d="M18 11V7h-4"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5"/>',
  rank: '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
  answer: '<path d="M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-7l-4 3.5V16H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z"/><path d="M8 9.5h8M8 12.5h5"/>',
  check: '<path d="m5 12.5 4.2 4.2L19 7"/>',
  left: '<path d="M19 12H5"/><path d="m11 6-6 6 6 6"/>',
  right: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
};
const icon = (name, cls = '') => `<svg class="st-i ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" `
  + `stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name]}</svg>`;
const fmt = (value, places = 3) => Number(value).toFixed(places);
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const badge = (part) => `<span class="part-badge p${part + 1}" title="Part ${part + 1}">${part + 1}</span>`;

function firstLine(markdown) {
  for (const line of String(markdown).split('\n')) {
    const text = line.replace(/[#>*_`]+/g, '').trim();
    if (text) return text;
  }
  return '';
}

class Renderer {
  constructor(question, chunks = null, model = '') {
    this.question = question;
    this.chunks = chunks;
    this.model = model;
    this.runId = Math.random().toString(16).slice(2, 10);
    this.started = false;
    this.state = Object.fromEntries(STAGES.map((s) => [s, 'idle']));
    this.status = '';
    this.route = '';
    this.forced = false;
    this.merging = false;
    this.parts = [];
    this.calls = {};
    this.hops = [];
    this.merge = null;
    this.docs = new Map();
    this.order = [];
    this.notes = Object.fromEntries(STAGES.map((s) => [s, []]));
    this.flow = null;
    this.answerText = '';
    this.error = '';
  }

  // ------------------------------------------------------------ ingest
  feed(ev) {
    const handler = this[`on_${ev.kind}`];
    if (handler) handler.call(this, ev);
  }

  partNote(i) {
    return this.parts.length > 1 ? ` for part ${i + 1} of ${this.parts.length}` : '';
  }

  current() {
    const active = STAGES.find((s) => this.state[s] === 'active');
    if (active) return active;
    const reached = STAGES.filter((s) => this.state[s] !== 'idle');
    return reached.length ? reached[reached.length - 1] : 'plan';
  }

  planDone() {
    if (this.state.plan !== 'done') {
      this.state.plan = 'done';
      this.flow = ['plan', 0];
    }
  }

  searchDone() {
    const i = this.hops.length - 1;
    const more = this.parts.length > 1 && i < this.parts.length - 1;
    this.state.search = more ? 'waiting' : 'done';
    this.flow = ['search', i];
  }

  on_step(ev) {
    const title = String(ev.title || '');
    if (title.startsWith('PIPELINE - answer')) {
      this.started = true;
      this.state.plan = 'active';
      this.status = 'Reading your question';
    } else if (title.startsWith('ROUTE')) {
      this.state.plan = 'active';
      this.status = 'Deciding whether this needs one search or several';
    } else if (title.startsWith('AGENT - decompose')) {
      if (!this.route) { this.route = 'complex'; this.forced = true; }
      this.state.plan = 'active';
      this.status = 'Splitting your question into parts';
    } else if (title.startsWith('RETRIEVE - simple route')) {
      if (!this.route) { this.route = 'simple'; this.forced = true; }
      this.planDone();
    } else if (title.startsWith('AGENT - merge')) {
      this.merging = true;
      this.state.rank = 'active';
      this.status = 'Combining what the searches found';
    } else if (title.startsWith('GENERATE') || title.startsWith('AGENT - synthesize')) {
      ['plan', 'search', 'rank'].forEach((s) => { this.state[s] = 'done'; });
      this.merging = false;
      this.state.answer = 'active';
      this.status = 'Writing the answer';
      this.flow = ['rank', -1];
    }
  }

  on_route(ev) {
    this.route = String(ev.decision || 'simple');
    if (this.route !== 'complex') this.planDone();
  }

  on_subquestions(ev) {
    this.parts = (ev.items || []).map(String);
    this.planDone();
  }

  on_llm_call(ev) {
    this.calls[String(ev.purpose || 'complete')] = ev;
  }

  on_detail(ev) {
    const label = String(ev.label || '');
    const value = String(ev.value ?? '');
    if (label === 'decision' || label.startsWith('sub-question')) return;
    this.notes[this.current()].push(value ? `${label}: ${value}` : label);
  }

  on_retrieval_start(ev) {
    const i = this.hops.length;
    this.hops.push({
      query: String(ev.query || ''), mode: String(ev.mode || ''),
      dense: [], bm25: [], rrf: [], shortlist: [], finals: [],
    });
    this.planDone();
    if (this.state.rank === 'active') this.state.rank = 'waiting';
    this.state.search = 'active';
    this.status = `Searching the calendar${this.partNote(i)}`;
    if (i > 0) this.flow = ['plan', i];
  }

  on_candidates(ev) {
    const stage = String(ev.stage || '');
    if (!this.hops.length || !['dense', 'bm25', 'rrf'].includes(stage)) return;
    this.hops[this.hops.length - 1][stage] = ev.items || [];
    if (stage === 'rrf') {
      this.searchDone();
      this.state.rank = 'active';
      this.status = `Ranking the results${this.partNote(this.hops.length - 1)}`;
    }
  }

  on_shortlist(ev) {
    if (!this.hops.length) return;
    const ids = ev.ids || [];
    this.hops[this.hops.length - 1].shortlist = ids;
    this.state.rank = 'active';
    this.status = `Reranking the top ${ids.length}${this.partNote(this.hops.length - 1)}`;
  }

  on_retrieval_final(ev) {
    const items = ev.items || [];
    items.forEach((doc) => this.docs.set(doc.id, doc));
    if (!this.hops.length) return;
    this.hops[this.hops.length - 1].finals = items;
    if (this.state.search === 'active') this.searchDone();
    if (this.route === 'complex') {
      this.state.rank = 'waiting';
    } else {
      this.state.rank = 'done';
      this.order = items.map((doc) => doc.id);
    }
  }

  on_merge(ev) {
    this.merge = ev;
    this.order = ev.order || [];
    this.state.rank = 'done';
  }

  settle() {
    if (this.answerText && !this.error) {
      STAGES.forEach((s) => { this.state[s] = 'done'; });
    } else if (this.started) {
      // The run ended early: nothing still to come is "waiting" any more.
      STAGES.forEach((s) => { if (this.state[s] !== 'done') this.state[s] = 'stopped'; });
    }
    this.status = '';
    this.merging = false;
  }

  // ------------------------------------------------------------ render: all outputs
  panels(isRunning = false) {
    if (!isRunning) this.settle();
    const out = {
      bar: this.barHtml(isRunning), plan: this.planHtml(), search: this.searchHtml(),
      rank: this.rankHtml(), head: this.answerHeadHtml(isRunning), answer: this.answerText.trim(),
      side: this.answerSideHtml(), nav: navHtml('answer'),
    };
    if (this.error) out.answer = '';
    this.flow = null;
    return out;
  }

  // ------------------------------------------------------------ render: the bar
  barHtml(isRunning) {
    let runState = this.answerText ? 'done' : 'idle';
    if (this.error) runState = 'error';
    else if (isRunning) runState = 'running';
    const cards = [];
    STAGES.forEach((stage, i) => {
      cards.push(this.card(stage));
      if (i < STAGES.length - 1) cards.push(this.arrow(stage));
    });
    return '<div class="stage-top"><h2 class="stage-title">How this answer was found</h2>'
      + '<p class="stage-hint"><span class="hint-touch">Tap a stage to look inside</span>'
      + '<span class="hint-mouse">Click a stage to look inside, or use the arrow keys</span></p></div>'
      + `<div class="stage-bar" role="tablist" aria-label="Pipeline stages" data-run="${this.runId}" `
      + `data-state="${runState}">${cards.join('')}</div>`;
  }

  card(stage) {
    const selected = stage === 'answer';
    return `<button type="button" class="stage-card is-${this.state[stage]}" role="tab" `
      + `id="stage-tab-${stage}" data-stage="${stage}" aria-controls="panel-${stage}" `
      + `aria-selected="${selected}" tabindex="${selected ? 0 : -1}">`
      + `<span class="stage-icon">${icon(stage)}</span>`
      + `<span class="stage-label">${NAMES[stage]}</span>`
      + `<span class="stage-count">${icon('check', 'stage-tick')}${esc(this.count(stage))}</span>`
      + `<span class="stage-blurb">${BLURBS[stage]}</span>`
      + `<span class="stage-mini mini-${stage}" aria-hidden="true">${this.mini(stage)}</span>`
      + '<span class="stage-unseen" aria-hidden="true"></span></button>';
  }

  found() {
    return this.hops.reduce((n, hop) => n + hop.dense.length + hop.bm25.length, 0);
  }

  kept() {
    return this.order.length ? this.order.length : this.hops.reduce((n, hop) => n + hop.finals.length, 0);
  }

  count(stage) {
    const state = this.state[stage];
    if (!this.started) return '';
    if (state === 'idle') return 'waiting';
    if (state === 'stopped') return 'stopped';
    const many = this.parts.length > 1;
    const part = many ? `part ${this.hops.length} of ${this.parts.length}…` : '';
    if (stage === 'plan') {
      if (state === 'active') return this.route === 'complex' ? 'splitting…' : 'thinking…';
      return many ? plural(this.parts.length, 'part') : '1 search';
    }
    if (stage === 'search') {
      if (state === 'active') return part || 'searching…';
      return state === 'waiting' ? `${this.found()} so far` : `${this.found()} found`;
    }
    if (stage === 'rank') {
      if (state === 'active') return this.merging ? 'merging…' : (part || 'ranking…');
      return state === 'waiting' ? `${this.kept()} kept so far` : `${this.kept()} kept`;
    }
    return state === 'active' ? 'writing…' : 'ready';
  }

  mini(stage) {
    if (stage === 'plan') {
      if (this.route === 'complex' && this.parts.length) return this.parts.map((_, k) => `<i class="p${k + 1}"></i>`).join('');
      if (this.route === 'simple') return '<i class="one"></i>';
      return '<i class="wait"></i>';
    }
    if (stage === 'search') {
      const n = Math.max(this.parts.length, 1);
      const dense = Math.min(this.hops.filter((hop) => hop.dense.length).length / n, 1);
      const bm25 = Math.min(this.hops.filter((hop) => hop.bm25.length).length / n, 1);
      return `<i class="md" style="--v:${dense.toFixed(2)}"></i><i class="mk" style="--v:${bm25.toFixed(2)}"></i>`;
    }
    if (stage === 'rank') {
      const found = this.found();
      const fused = this.hops.reduce((n, hop) => n + hop.rrf.length, 0);
      const short = this.hops.reduce((n, hop) => n + hop.shortlist.length, 0);
      const kept = this.hops.some((hop) => hop.finals.length) ? this.kept() : 0;
      return [[found, 1, ''], [fused, 0.87, ''], [short, 0.5, ''], [kept, 0.04, ' k']].map(([value, nominal, keep]) => {
        const width = found && value ? value / found : nominal;
        return `<i class="${value ? 'on' : ''}${keep}" style="--w:${width.toFixed(3)}"></i>`;
      }).join('');
    }
    return this.answerText && !this.error ? esc(firstLine(this.answerText)) : '';
  }

  arrow(stage) {
    const filled = {
      plan: this.state.plan === 'done',
      search: this.hops.some((hop) => hop.rrf.length || hop.finals.length),
      rank: this.state.rank === 'done',
    }[stage];
    let classes = `stage-arrow${filled ? ' is-filled' : ''}`;
    if (this.flow && this.flow[0] === stage) {
      classes += ' is-flowing';
      if (this.flow[1] >= 0 && this.parts.length > 1) classes += ` part${this.flow[1] + 1}`;
    }
    return `<span class="${classes}" aria-hidden="true">${icon('right')}</span>`;
  }

  // ------------------------------------------------------------ render: the panels
  planHtml() {
    const what = 'A quick model call reads the question and decides how much searching it needs. '
      + 'Simple questions get one search. Comparisons and prerequisite chains are split '
      + 'into parts, and each part is searched on its own.';
    if (!this.started) return panelHtml('plan', what, waitHtml("Ask a question and the router's decision shows up here."));
    const body = [`<div class="sp-quote">${esc(this.question)}</div>`];
    if (this.state.plan === 'active') body.push(statusHtml(this.status));
    if (this.route) {
      const isComplex = this.route === 'complex';
      let why = isComplex
        ? 'It needs more than one calendar page, so it is split into parts and each part gets its own search.'
        : 'One calendar page should answer it, so it gets a single search.';
      if (this.forced) {
        why = `Search settings set the route to always ${isComplex ? 'multi-step' : 'single-shot'}, so the router was skipped.`;
      }
      body.push(`<div class="sp-decision"><span class="sp-pill">${isComplex ? 'Complex' : 'Simple'}</span><span>${why}</span></div>`);
    }
    if (this.calls.route) body.push(promptHtml(this.calls.route, 'Router prompt and reply'));
    if (this.parts.length) {
      body.push(`<ol class="sp-parts">${this.parts.map((part, k) => `<li>${badge(k)}<span>${esc(part)}</span></li>`).join('')}</ol>`);
    }
    if (this.calls.decompose) body.push(promptHtml(this.calls.decompose, 'Splitting prompt and reply'));
    body.push(this.notesHtml('plan'));
    return panelHtml('plan', what, body.join(''));
  }

  laneHead(i) {
    const query = i < this.parts.length ? this.parts[i] : this.hops[i].query;
    return `<div class="sp-lane-head">${badge(i)}<span>${esc(query)}</span></div>`;
  }

  searchHtml() {
    const corpus = this.chunks ? `all ${Number(this.chunks).toLocaleString('en-US')} calendar excerpts` : 'every calendar excerpt';
    const what = `Two searches run side by side. Vector search compares the meaning of the question with ${corpus}. `
      + 'Keyword search (BM25) looks for the exact words, which is how a course code like CPSC 210 gets found.';
    if (!this.hops.length) {
      return panelHtml('search', what, waitHtml(this.started ? 'Waiting for Plan.' : 'Ask a question and the two searches show up here.'));
    }
    const many = this.parts.length > 1;
    const lanes = [];
    for (let i = 0; i < Math.max(this.parts.length, this.hops.length); i += 1) {
      const head = many ? this.laneHead(i) : '';
      if (i >= this.hops.length) {
        lanes.push(`<section class="sp-lane">${head}${waitHtml(`Part ${i + 1} is searched after part ${i} has been ranked.`)}</section>`);
      } else {
        lanes.push(`<section class="sp-lane" data-lane="${i}">${head}${searchListsHtml(this.hops[i])}</section>`);
      }
    }
    const status = this.state.search === 'active' ? statusHtml(this.status) : '';
    const first = this.hops[0];
    let tech = '';
    if (first.bm25.length) {
      tech = `Each search returns its top ${first.dense.length}. Pages that both searches found are marked <b>both</b>, `
        + 'and the ones that made the final cut are marked <b>kept</b>.';
    } else if (first.dense.length) {
      tech = `Vector search returns its top ${first.dense.length}, and those are what Rank keeps.`;
    }
    return panelHtml('search', what, status + lanes.join('') + (tech ? `<p class="sp-tech">${tech}</p>` : '') + this.notesHtml('search'));
  }

  rankHtml() {
    const first = this.hops[0] || { mode: '', shortlist: [], finals: [] };
    const kept = first.finals.length || 4;
    const fuse = 'The two lists are fused into one ranking (reciprocal rank fusion), so a page that both searches found rises to the top.';
    let what;
    if (first.mode === 'dense') what = `Vector search only, so there is nothing to fuse: the ${kept} closest excerpts are kept.`;
    else if (first.mode === 'hybrid') what = `${fuse} The best ${kept} are kept. This search mode skips the reranker.`;
    else {
      what = `${fuse} The top ${first.shortlist.length || 50} go to a reranker (Cohere) that reads each excerpt `
        + `against the question, and the best ${kept} are kept.`;
    }
    const many = this.parts.length > 1;
    if (many) what += ' Each part is ranked on its own, then the parts are merged.';
    if (!this.hops.some((hop) => hop.rrf.length || hop.finals.length)) {
      const status = this.state.rank === 'active' ? statusHtml(this.status) : '';
      return panelHtml('rank', what, status + waitHtml(this.started ? 'Waiting for Search.' : 'Ask a question and the ranking shows up here.'));
    }
    const lanes = [];
    for (let i = 0; i < Math.max(this.parts.length, this.hops.length); i += 1) {
      const head = many ? this.laneHead(i) : '';
      const hop = this.hops[i];
      if (!hop || !(hop.rrf.length || hop.finals.length)) {
        lanes.push(`<section class="sp-lane">${head}${waitHtml(`Part ${i + 1} is ranked after it has been searched.`)}</section>`);
        continue;
      }
      let cards = hop.finals.map((doc) => docCardHtml(doc, hop, many ? i : null)).join('');
      if (cards) cards = `<div class="sp-cards">${cards}</div>`;
      lanes.push(`<section class="sp-lane">${head}${funnelHtml(hop)}${cards}${fusedHtml(hop)}</section>`);
    }
    const status = this.state.rank === 'active' ? statusHtml(this.status) : '';
    return panelHtml('rank', what, status + lanes.join('') + (this.merge ? this.mergeHtml() : '') + this.notesHtml('rank'));
  }

  mergeHtml() {
    const perHop = this.merge.per_hop || [];
    const seen = new Set();
    const steps = [];
    const depth = Math.max(0, ...perHop.map((ids) => ids.length));
    for (let rank = 0; rank < depth; rank += 1) {
      perHop.forEach((ids, part) => {
        if (rank >= ids.length) return;
        const id = ids[rank];
        const title = esc((this.docs.get(id) || {}).title || `Excerpt ${id}`);
        if (seen.has(id)) {
          steps.push(`<li class="is-drop">${badge(part)}<span class="sp-strike">${title}</span> (already in)</li>`);
        } else {
          seen.add(id);
          steps.push(`<li>${badge(part)}<span>${title}</span></li>`);
        }
      });
    }
    const dropped = Number(this.merge.dropped || 0);
    return `<section class="sp-merge"><h4>Merging the ${plural(perHop.length, 'part')}</h4>`
      + "<p class=\"sp-tech\">Each part's best excerpt goes in first, then each part's second best, and so on. "
      + `Repeats are dropped. That leaves ${plural(this.order.length, 'excerpt')}, with ${plural(dropped, 'repeat')} dropped.</p>`
      + `<ol>${steps.join('')}</ol></section>`;
  }

  answerHeadHtml(isRunning) {
    const model = String((this.calls.answer || {}).model || this.model || '');
    let who = esc(model) || 'The model';
    if (model.includes('claude')) who = `Claude (${esc(model)})`;
    const what = `${who} writes the answer using only the kept excerpts, and points you to the official calendar pages.`;
    let body;
    if (this.error) body = `<div class="notice">${esc(this.error)}</div>`;
    else if (this.answerText) body = `<p class="sp-answer-meta"><span class="sp-badge">${this.route === 'complex' ? 'multi-step' : 'single-shot'}</span></p>`;
    else if (isRunning || this.started) body = statusHtml(this.status || 'Reading your question');
    else body = waitHtml('Your answer will show up here, with links to the calendar pages it came from.');
    return '<div class="stage-panel" role="tabpanel" aria-labelledby="stage-tab-answer">'
      + `${headHtml('answer', what)}<div class="sp-body">${body}</div></div>`;
  }

  sources() {
    const perHop = ((this.merge || {}).per_hop || []).map((ids) => new Set(ids));
    const many = this.parts.length > 1;
    const pages = new Map();
    for (const id of (this.order.length ? this.order : [...this.docs.keys()])) {
      const doc = this.docs.get(id);
      if (!doc || !doc.url) continue;
      const parts = many ? perHop.map((ids, k) => (ids.has(id) ? k : -1)).filter((k) => k >= 0) : [];
      if (pages.has(doc.url)) parts.forEach((k) => pages.get(doc.url).parts.add(k));
      else pages.set(doc.url, { title: String(doc.title || doc.url), parts: new Set(parts) });
    }
    return [...pages].map(([url, page]) => ({ url, title: page.title, parts: [...page.parts].sort() }));
  }

  answerSideHtml() {
    if (this.error || !this.answerText) return '';
    const sources = this.sources();
    let side = '';
    if (sources.length) {
      const items = sources.map((s) => `<li><span class="sp-badges">${s.parts.map(badge).join('')}</span>`
        + `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a></li>`).join('');
      side += `<section class="sp-sources"><h4>Based on ${plural(sources.length, 'calendar page')}</h4><ul>${items}</ul></section>`;
    }
    if (this.calls.answer) side += promptHtml(this.calls.answer, 'Answer prompt and reply');
    return `<div class="sp-answer-side">${side}</div>`;
  }

  notesHtml(stage) {
    const lines = this.notes[stage];
    if (!lines.length) return '';
    return `<details class="prompt sp-notes"><summary>Raw trace, ${plural(lines.length, 'line')}</summary>`
      + `<div class="prompt-body"><pre>${esc(lines.join('\n'))}</pre></div></details>`;
  }
}

// ---------------------------------------------------------------- panel pieces
function panelHtml(stage, what, body) {
  return `<div class="stage-panel" role="tabpanel" aria-labelledby="stage-tab-${stage}">`
    + `${headHtml(stage, what)}<div class="sp-body">${body}</div>${navHtml(stage)}</div>`;
}

function headHtml(stage, what) {
  return `<div class="sp-head"><span class="sp-icon">${icon(stage)}</span><div>`
    + `<p class="sp-eyebrow">Stage ${STAGES.indexOf(stage) + 1} of 4</p>`
    + `<h3 class="sp-title">${NAMES[stage]}</h3></div></div><p class="sp-what">${what}</p>`;
}

function navHtml(stage) {
  const i = STAGES.indexOf(stage);
  const back = i ? `<button type="button" class="sp-btn" data-go="${STAGES[i - 1]}">${icon('left')}${NAMES[STAGES[i - 1]]}</button>` : '';
  const next = i < STAGES.length - 1
    ? `<button type="button" class="sp-btn sp-next" data-go="${STAGES[i + 1]}">Next: ${NAMES[STAGES[i + 1]]}${icon('right')}</button>`
    : '<button type="button" class="sp-btn sp-next" data-go="plan">See how it was found: start at Plan</button>';
  return `<div class="sp-nav">${back}${next}</div>`;
}

const statusHtml = (text) => `<div class="sp-status"><span class="sp-dot" aria-hidden="true"></span><span>${esc(text)}</span></div>`;
const waitHtml = (text) => `<div class="sp-wait">${text}</div>`;

function promptHtml(call, label) {
  return '<details class="prompt">'
    + `<summary>${esc(label)}<span class="prompt-meta">${esc(call.model || '')} · ${call.ms || 0} ms</span></summary>`
    + `<div class="prompt-body"><h4>System</h4><pre>${esc(call.system)}</pre>`
    + `<h4>User</h4><pre>${esc(call.user)}</pre><h4>Reply</h4><pre>${esc(call.reply)}</pre></div></details>`;
}

function searchListsHtml(hop) {
  if (!hop.dense.length) return waitHtml('Searching…');
  const vectorOnly = hop.mode === 'dense';
  let both = new Set();
  if (hop.bm25.length) {
    const denseIds = new Set(hop.dense.map((c) => c.id));
    both = new Set(hop.bm25.map((c) => c.id).filter((id) => denseIds.has(id)));
  }
  const kept = new Set(hop.finals.map((doc) => doc.id));
  const lists = [candListHtml('dense', 'Vector search', hop.dense, both, kept, 4)];
  if (vectorOnly) {
    lists.push('<div class="sp-list bm25"><div class="sp-list-head">Keyword search</div><div class="sp-wait">Off in this search mode.</div></div>');
  } else {
    lists.push(candListHtml('bm25', 'Keyword search', hop.bm25, both, kept, 2));
  }
  const keyword = hop.bm25.length ? `Keyword ${hop.bm25.length}` : 'Keyword off';
  const toggle = '<div class="sp-toggle" role="group" aria-label="Which list to show">'
    + `<button type="button" data-pick="dense" aria-pressed="true">Vector ${hop.dense.length}</button>`
    + `<button type="button" data-pick="bm25" aria-pressed="false">${keyword}</button></div>`;
  return `${toggle}<div class="sp-lists">${lists.join('')}</div>`;
}

function candRowHtml(cand, both, kept, places, cut = false) {
  let flags = '';
  if (both.has(cand.id)) flags += '<span class="sp-flag both" title="Found by both searches">both</span>';
  if (kept.has(cand.id)) flags += '<span class="sp-flag kept" title="Kept for the answer">kept</span>';
  if (cut) flags += '<span class="sp-flag cut" title="Not sent to the reranker">cut</span>';
  const title = esc(cand.title || '');
  const classes = `sp-row${kept.has(cand.id) ? ' is-kept' : ''}${cut ? ' is-cut' : ''}`;
  return `<li class="${classes}"><span class="sp-rid">${cand.id}</span>`
    + `<span class="sp-rtitle" title="${title}">${title}</span><span class="sp-flags">${flags}</span>`
    + `<span class="sp-rscore">${fmt(cand.score, places)}</span></li>`;
}

function candListHtml(kind, name, items, both, kept, places) {
  const rows = items.map((c) => candRowHtml(c, both, kept, places));
  const more = rows.length > 5
    ? `<details class="sp-more"><summary>Show all ${rows.length}</summary><ol class="sp-rows">${rows.slice(5).join('')}</ol></details>`
    : '';
  return `<div class="sp-list ${kind}"><div class="sp-list-head">${name}<span class="sp-n">top ${items.length}</span></div>`
    + `<ol class="sp-rows">${rows.slice(0, 5).join('')}</ol>${more}</div>`;
}

function funnelHtml(hop) {
  const found = hop.dense.length + hop.bm25.length;
  if (!found) return '';
  const split = `<i class="d" style="flex-grow:${hop.dense.length}"></i><i class="k" style="flex-grow:${hop.bm25.length}"></i>`;
  const rows = [['Candidates', found, 'split', split]];
  if (hop.rrf.length) rows.push(['After fusing', hop.rrf.length, '', '']);
  if (hop.shortlist.length) rows.push(['Sent to reranker', hop.shortlist.length, '', '']);
  if (hop.finals.length) rows.push(['Kept', hop.finals.length, 'keep', '']);
  return '<div class="sp-funnel">' + rows.map(([label, value, cls, inner]) =>
    `<div class="fn-row"><span class="fn-label">${label}</span><span class="fn-track">`
    + `<span class="fn-bar ${cls}" style="--w:${(value / found).toFixed(4)}">${inner}</span></span>`
    + `<span class="fn-val">${value}</span></div>`).join('') + '</div>';
}

function fusedHtml(hop) {
  if (!hop.rrf.length) return '';
  const kept = new Set(hop.finals.map((doc) => doc.id));
  const short = new Set(hop.shortlist);
  const rows = hop.rrf.map((c) => candRowHtml(c, new Set(), kept, 4, short.size > 0 && !short.has(c.id))).join('');
  return `<details class="prompt sp-fused"><summary>The fused ranking, all ${hop.rrf.length}`
    + '<span class="prompt-meta">RRF</span></summary>'
    + `<div class="sp-list fused"><ol class="sp-rows sp-scroll">${rows}</ol></div></details>`;
}

function docCardHtml(doc, hop, part) {
  const chips = [];
  if (doc.edition_year) chips.push(`<span class="tag edition">${esc(doc.edition_year)}</span>`);
  if (doc.cohort_qualifier) chips.push('<span class="tag cohort">cohort-specific</span>');
  CHIP_FIELDS.forEach((field) => { if (doc[field]) chips.push(`<span class="tag">${esc(doc[field])}</span>`); });
  const foundBy = [];
  [['dense', 'vector', 'dv'], ['bm25', 'keyword', 'kw']].forEach(([kind, label, css]) => {
    if (!hop[kind].length) return;
    const rank = hop[kind].findIndex((c) => c.id === doc.id) + 1;
    foundBy.push(rank ? `<span class="${css}">${label} #${rank}</span>` : `not in the ${label} top ${hop[kind].length}`);
  });
  const section = doc.section ? `<p class="doc-section">${esc(doc.section)}</p>` : '';
  const chipRow = chips.length ? `<div class="doc-chips">${chips.join('')}</div>` : '';
  const provenance = foundBy.length ? `<p class="doc-prov">Found by ${foundBy.join(' · ')}</p>` : '';
  const link = doc.url
    ? `<div class="doc-actions"><a href="${esc(doc.url)}" target="_blank" rel="noopener noreferrer">Official page ↗</a></div>`
    : '';
  return '<article class="doc">'
    + `<div class="doc-head">${part !== null ? badge(part) : ''}<span class="doc-title">${esc(doc.title)}</span>`
    + `<span class="doc-score" title="Relevance score">id ${doc.id} · ${fmt(doc.score)}</span></div>`
    + `${section}${chipRow}${provenance}${link}`
    + `<details class="excerpt"><summary>Excerpt</summary><div class="doc-text">${esc(doc.text)}</div></details></article>`;
}

// ---------------------------------------------------------------- painting
let renderer = new Renderer('');
let paintQueued = false;

/* Repaint every output from the renderer. Unchanged outputs are left alone, so a stage
 * someone is reading (an open "Show all" list, a scrolled excerpt) is not reset by an update
 * to a different stage. */
const painted = {};
function paint(isRunning) {
  const out = renderer.panels(isRunning);
  const targets = { bar: el.bar, plan: el.plan, search: el.search, rank: el.rank, head: el.head, side: el.side, nav: el.nav };
  Object.entries(targets).forEach(([key, node]) => {
    if (painted[key] !== out[key]) { node.innerHTML = out[key]; painted[key] = out[key]; }
  });
  if (painted.answer !== out.answer) { el.answer.textContent = out.answer; painted.answer = out.answer; }
}

// Events can arrive dozens at a time; paint at most once a frame while a run is going.
function schedulePaint() {
  if (paintQueued) return;
  paintQueued = true;
  requestAnimationFrame(() => { paintQueued = false; paint(running); });
}

// ---------------------------------------------------------------- SSE plumbing
async function streamSSE(url, onEvent) {
  abort = new AbortController();
  const response = await fetch(url, { signal: abort.signal, headers: { Accept: 'text/event-stream' } });

  if (!response.ok) {
    let body = {};
    try { body = await response.json(); } catch (_) { /* non-JSON error page */ }
    const err = new Error(body.error || `Request failed (${response.status})`);
    err.status = response.status;
    err.budgetExhausted = !!body.budget_exhausted;
    throw err;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let split;
    while ((split = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      if (!block.trim() || block.startsWith(':')) continue;   // heartbeat comment

      let name = 'message', data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) name = line.slice(6).trim();
        else if (line.startsWith('data:')) data += line.slice(5).trim();
      }
      if (data) {
        try { onEvent(name, JSON.parse(data)); }
        catch (_) { /* a malformed frame must not kill the stream */ }
      }
    }
  }
}

// ---------------------------------------------------------------- dispatch
function handle(name, data) {
  switch (name) {
    case 'accepted':
      renderer = new Renderer(data.question, site.chunks, site.model);
      el.question.value = data.question;
      el.notice.hidden = true;
      // In static mode the standing note above the chips already says everything is a
      // recording, so flashing a banner on every click would just be noise.
      if (data.replay && !STATIC) {
        note('Playing back a saved run. No API calls, nothing metered.');
      }
      break;

    case 'answer':
      renderer.answerText = String(data.text || '');
      renderer.route = data.route || renderer.route;
      break;

    case 'done':
      if (!data.replay && data.api_calls) {
        const c = data.api_calls;
        note(`Done in ${(data.ms / 1000).toFixed(1)}s using ${c.llm} model call${c.llm === 1 ? '' : 's'}, `
             + `${c.embed} embedding${c.embed === 1 ? '' : 's'}, ${c.rerank} rerank${c.rerank === 1 ? '' : 's'}.`);
      }
      refreshUsage();
      break;

    case 'error':
      renderer.error = data.message;
      break;

    default:
      // Every trace event the pipeline emits: step, route, candidates, and the rest.
      renderer.feed({ ...data, kind: data.kind || name });
  }
  schedulePaint();
}

function note(message) {
  el.notice.textContent = message;
  el.notice.hidden = false;
}

// ---------------------------------------------------------------- static replay
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function staticRun(slug) {
  return (window.DEMO_RUNS.runs || []).find((r) => r.slug === slug);
}

/* Walk a cached run's frames with the same pacing the server uses, so the stage cards animate
 * rather than appearing all at once. Emits the identical event shapes `handle()` expects. */
async function replayLocal(slug) {
  const runData = staticRun(slug);
  if (!runData) {
    handle('error', { message: 'That saved run is not available.' });
    return;
  }
  handle('accepted', {
    question: runData.question,
    mode: runData.mode || 'hybrid_rerank',
    route: runData.forced_route || 'auto',
    replay: true,
  });
  for (const event of runData.events) {
    await sleep(event.kind === 'step' ? STAGE_DELAY_MS : FRAME_DELAY_MS);
    handle(event.kind, event);
  }
  handle('answer', { text: runData.answer, route: runData.route });
  handle('done', {
    route: runData.route,
    excerpts: runData.excerpts || 0,
    ms: runData.ms || 0,
    replay: true,
  });
}

// ---------------------------------------------------------------- driving
async function run(target, question) {
  if (running) return;
  running = true;
  el.submit.disabled = true;
  el.submit.textContent = 'Working…';
  renderer = new Renderer(question, site.chunks, site.model);
  schedulePaint();

  try {
    if (target.slug) await replayLocal(target.slug);
    else await streamSSE(target.url, handle);
  } catch (err) {
    if (err.name !== 'AbortError') {
      renderer.error = err.budgetExhausted
        ? err.message + ' Pick one of the saved runs above to see the whole thing work.'
        : err.message;
    }
  } finally {
    running = false;
    el.submit.disabled = false;
    el.submit.textContent = STATIC ? 'Filter' : 'Ask';
    paint(false);
    refreshUsage();
  }
}

/* In static mode there is no backend to ask, so the input filters the cached questions
 * instead of pretending to run one. Filtering as you type is honest about what the page can
 * do, and still lets someone hunt for the question they had in mind. */
function filterExamples(term) {
  const needle = term.trim().toLowerCase();
  let visible = 0;
  el.examples.querySelectorAll('.chip').forEach((chip) => {
    const match = !needle || chip.dataset.question.toLowerCase().includes(needle)
      || (chip.dataset.category || '').toLowerCase().includes(needle);
    chip.hidden = !match;
    if (match) visible += 1;
  });
  el.noMatch.hidden = visible > 0;
  el.examples.dispatchEvent(new Event('scroll'));   // let the row's arrows catch up
}

el.form.addEventListener('submit', (ev) => {
  ev.preventDefault();
  const question = el.question.value.trim();
  if (!question) return;
  if (STATIC) {
    filterExamples(question);
    return;
  }
  const params = new URLSearchParams({ q: question, mode: el.mode.value, route: el.route.value });
  run({ url: `/api/ask/stream?${params}` }, question);
});

if (STATIC) el.question.addEventListener('input', () => filterExamples(el.question.value));

// ---------------------------------------------------------------- bootstrap
function renderExamples(examples) {
  // One row that scrolls sideways, so a long question is cut short on its chip; the full
  // text is in the tooltip and fills the box when the run starts.
  el.examples.innerHTML = examples.map((ex) =>
    `<button class="chip" type="button" data-slug="${esc(ex.slug)}"
             data-question="${esc(ex.question)}" data-category="${esc(ex.category || '')}"
             title="${esc(ex.question)}">${ex.category ? `<span class="chip-cat">${esc(ex.category)}</span>` : ''}<span class="chip-q">${esc(ex.question)}</span></button>`).join('');

  el.examples.querySelectorAll('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const question = chip.dataset.question;
      run(STATIC ? { slug: chip.dataset.slug }
                 : { url: `/api/replay/${encodeURIComponent(chip.dataset.slug)}` }, question);
    });
  });
}

function renderUsage(usage) {
  if (!usage) return;
  el.budget.textContent = usage.budget_exhausted
    ? 'out of model calls for today, saved runs still work'
    : `${usage.llm_calls_remaining}/${usage.llm_calls_limit} model calls left today · ` +
      `${usage.per_ip_hour}/hour per visitor`;
}

async function refreshUsage() {
  if (STATIC) return;   // nothing is metered when nothing is spent
  try {
    const health = await (await fetch('/api/health')).json();
    renderUsage(health.usage);
    site = { chunks: health.chunks, model: health.model };
    const ok = health.status === 'ok';
    el.statusDot.className = 'dot ' + (ok ? (health.usage.budget_exhausted ? 'warn' : 'ok') : 'err');
    el.statusText.textContent = ok
      ? `${health.chunks.toLocaleString()} chunks · ${health.retrieval_mode} · ${health.model}`
      : 'index unavailable';
  } catch (_) {
    el.statusDot.className = 'dot err';
    el.statusText.textContent = 'offline';
  }
}

function initStatic() {
  const meta = window.DEMO_RUNS;
  document.body.classList.add('static-mode');
  site = { chunks: meta.chunks || null, model: meta.model || '' };

  el.question.placeholder = `Filter ${meta.runs.length} saved runs…`;
  el.submit.textContent = 'Filter';
  el.budget.textContent = 'no API keys, nothing metered';
  el.statusDot.className = 'dot ok';
  el.statusText.textContent =
    `${(meta.chunks || 0).toLocaleString()} chunks · ${meta.retrieval_mode || 'hybrid_rerank'} · ${meta.model || ''}`;

  renderExamples(meta.runs.map((r) => ({
    slug: r.slug, question: r.question, category: r.category, cached: true,
  })));
}

async function initServer() {
  refreshUsage();
  try {
    const data = await (await fetch('/api/examples')).json();
    if (data.examples.length) renderExamples(data.examples);
    else el.examples.closest('.examples-wrap').hidden = true;
  } catch (_) {
    el.examples.closest('.examples-wrap').hidden = true;
  }
}

(function init() {
  if (STATIC) initStatic();
  else initServer();
  renderer = new Renderer('', site.chunks, site.model);
  paint(false);
})();
