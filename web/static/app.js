/* UBC Calendar RAG demo — event-stream renderer.
 *
 * The page is driven entirely by the pipeline's own trace events, which arrive in the order
 * they happen. Every mode below emits the same frames, so there is exactly one rendering
 * path — `handle()` does not know or care where its events came from.
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
 * EventSource cannot read the body of a non-200 response — and the rate-limit and
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
  examples: $('examples'), noMatch: $('no-match'), trace: $('trace'), traceEmpty: $('trace-empty'),
  retrieval: $('retrieval'), retrievalEmpty: $('retrieval-empty'),
  answerSection: $('answer-section'), answer: $('answer'), answerRoute: $('answer-route'),
  sources: $('sources'), statusDot: $('status-dot'), statusText: $('status-text'),
};

let running = false;
let abort = null;

// ---------------------------------------------------------------- run state
const state = {
  step: null,        // the <li> currently being filled in
  hop: null,         // the retrieval block currently being filled in
  hopCount: 0,
  question: '',
  docs: new Map(),   // id -> full document record, across every hop
  order: [],         // final grounding order (merge order, or the single hop's finals)
};

function resetRun(question) {
  state.step = null;
  state.hop = null;
  state.hopCount = 0;
  state.question = question;
  state.docs = new Map();
  state.order = [];
  el.trace.innerHTML = '';
  el.retrieval.innerHTML = '';
  el.traceEmpty.hidden = true;
  el.retrievalEmpty.hidden = true;
  el.answerSection.hidden = true;
  el.answer.textContent = '';
  el.sources.innerHTML = '';
  el.notice.hidden = true;
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

// ---------------------------------------------------------------- trace pane
function addStep(title) {
  if (state.step) state.step.classList.replace('active', 'done');
  const li = document.createElement('li');
  li.className = 'active';
  li.innerHTML = `<div class="step-title">${esc(prettyStep(title))}</div>`;
  el.trace.appendChild(li);
  state.step = li;
  return li;
}

/* The trace titles are written for a terminal ("AGENT - decompose into sub-questions").
 * Keep the substance, drop the shouting. */
function prettyStep(title) {
  const cleaned = title.replace(/^([A-Z]+) - /, (_, stage) => `${stage[0]}${stage.slice(1).toLowerCase()}: `);
  return cleaned.length > 150 ? cleaned.slice(0, 149) + '…' : cleaned;
}

function stepMeta(html) {
  if (!state.step) addStep('PIPELINE - running');
  const div = document.createElement('div');
  div.className = 'step-meta';
  div.innerHTML = html;
  state.step.appendChild(div);
  return div;
}

function addPromptDetails(call) {
  if (!state.step) return;
  const details = document.createElement('details');
  details.className = 'prompt';
  details.innerHTML =
    `<summary>prompt and reply · ${esc(call.model)} · ${call.ms} ms</summary>
     <div class="prompt-body">
       <h4>System</h4><pre>${esc(call.system)}</pre>
       <h4>User</h4><pre>${esc(call.user)}</pre>
       <h4>Reply</h4><pre>${esc(call.reply)}</pre>
     </div>`;
  state.step.appendChild(details);
}

// ---------------------------------------------------------------- retrieval pane
function startHop(query) {
  state.hopCount += 1;
  const isSub = query.trim() !== state.question.trim();
  const label = isSub ? `Sub-question ${state.hopCount}` : 'Single query';

  const block = document.createElement('div');
  block.className = 'hop';
  block.innerHTML =
    `<div class="hop-head"><strong>${esc(label)}:</strong> <span class="q"></span></div>
     <div class="columns">
       <div class="column dense"><h3>Vector <span></span></h3><ul class="cand-list"></ul></div>
       <div class="column bm25"><h3>Keyword <span></span></h3><ul class="cand-list"></ul></div>
       <div class="column rrf"><h3>Fused <span></span></h3><ul class="cand-list"></ul></div>
     </div>
     <p class="cand-legend">
       <span class="swatch sl"></span><b>shortlisted</b> for reranking &nbsp;·&nbsp;
       <span class="swatch sv"></span><b>kept</b> in the final results
     </p>
     <div class="finals"></div>`;
  block.querySelector('.q').textContent = query;
  el.retrieval.appendChild(block);
  state.hop = block;
}

function fillColumn(stage, items) {
  if (!state.hop) return;
  const selector = { dense: '.column.dense', bm25: '.column.bm25', rrf: '.column.rrf' }[stage];
  const column = state.hop.querySelector(selector);
  if (!column) return;
  column.querySelector('h3 span').textContent = `(${items.length})`;
  column.querySelector('.cand-list').innerHTML = items.map((c) =>
    `<li class="cand" data-id="${c.id}" title="${esc(c.title)}">
       <span class="cid">${c.id}</span><span>${c.score.toFixed(4)}</span>
     </li>`).join('');
}

function markCandidates(ids, className) {
  if (!state.hop) return;
  const wanted = new Set(ids);
  state.hop.querySelectorAll('.cand').forEach((node) => {
    if (wanted.has(Number(node.dataset.id))) node.classList.add(className);
  });
}

function renderFinals(items) {
  if (!state.hop) return;
  state.hop.querySelector('.finals').innerHTML =
    `<h3 class="column"><span style="font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--final)">
       Final ${items.length}</span></h3>` + items.map(docCard).join('');
  markCandidates(items.map((d) => d.id), 'survivor');
}

function docCard(doc) {
  const chips = [];
  if (doc.edition_year) chips.push(`<span class="tag edition">${esc(doc.edition_year)}</span>`);
  if (doc.cohort_qualifier) chips.push(`<span class="tag cohort">cohort-specific</span>`);
  if (doc.page_type) chips.push(`<span class="tag">${esc(doc.page_type)}</span>`);
  if (doc.faculty) chips.push(`<span class="tag">${esc(doc.faculty)}</span>`);
  if (doc.subject_code) chips.push(`<span class="tag">${esc(doc.subject_code)}</span>`);

  return `<div class="doc">
    <div class="doc-head">
      <span class="doc-title">${esc(doc.title)}</span>
      <span class="doc-score">id ${doc.id} · ${Number(doc.score).toFixed(3)}</span>
    </div>
    ${doc.section ? `<div class="doc-section">${esc(doc.section)}</div>` : ''}
    <div class="doc-chips">${chips.join('')}</div>
    <div class="doc-actions">
      <a href="#" data-toggle="${doc.id}">show excerpt</a>
      ${doc.url ? `<a href="${esc(doc.url)}" target="_blank" rel="noopener noreferrer">official page ↗</a>` : ''}
    </div>
    <div class="doc-text" id="text-${doc.id}" hidden>${esc(doc.text)}</div>
  </div>`;
}

el.retrieval.addEventListener('click', (ev) => {
  const link = ev.target.closest('a[data-toggle]');
  if (!link) return;
  ev.preventDefault();
  const body = $(`text-${link.dataset.toggle}`);
  if (!body) return;
  body.hidden = !body.hidden;
  link.textContent = body.hidden ? 'show excerpt' : 'hide excerpt';
});

// ---------------------------------------------------------------- answer
function renderAnswer(text, route) {
  el.answerSection.hidden = false;
  el.answer.textContent = text;
  el.answerRoute.textContent = route === 'complex' ? 'multi-step' : 'single-shot';

  const ids = state.order.length ? state.order : [...state.docs.keys()];
  const seen = new Set();
  const links = [];
  for (const id of ids) {
    const doc = state.docs.get(id);
    if (!doc || !doc.url || seen.has(doc.url)) continue;
    seen.add(doc.url);
    links.push(`<li><a href="${esc(doc.url)}" target="_blank" rel="noopener noreferrer">${esc(doc.title)}</a></li>`);
  }
  el.sources.innerHTML = links.length
    ? `<h3>Based on ${links.length} calendar page${links.length > 1 ? 's' : ''}</h3><ul>${links.join('')}</ul>`
    : '';
}

// ---------------------------------------------------------------- dispatch
function handle(name, data) {
  switch (name) {
    case 'accepted':
      resetRun(data.question);
      el.question.value = data.question;
      // In static mode the standing note above the chips already says everything is a
      // recording, so flashing a banner on every click would just be noise.
      if (data.replay && !STATIC) {
        note('Playing back a saved run. No API calls, nothing metered.');
      }
      break;

    case 'step':
      addStep(data.title);
      break;

    case 'detail':
      stepMeta(`${esc(data.label)}: <code>${esc(data.value)}</code>`);
      break;

    case 'route':
      stepMeta(`Classified as <strong>${esc(data.decision)}</strong>, so it gets ` +
               (data.decision === 'complex'
                 ? 'split into sub-questions and searched one at a time.'
                 : 'answered from a single search.'));
      break;

    case 'subquestions': {
      const list = document.createElement('ol');
      list.className = 'subq';
      list.innerHTML = data.items.map((s) => `<li>${esc(s)}</li>`).join('');
      if (state.step) state.step.appendChild(list);
      break;
    }

    case 'llm_call':
      addPromptDetails(data);
      break;

    case 'retrieval_start':
      startHop(data.query);
      break;

    case 'candidates':
      fillColumn(data.stage, data.items);
      break;

    case 'shortlist':
      markCandidates(data.ids, 'shortlisted');
      break;

    case 'retrieval_final':
      data.items.forEach((d) => state.docs.set(d.id, d));
      state.order = data.items.map((d) => d.id);   // superseded by `merge` on the agentic route
      renderFinals(data.items);
      break;

    case 'merge':
      state.order = data.order;
      stepMeta(`Interleaved ${data.per_hop.length} rankings to give ` +
               `<strong>${data.order.length}</strong> unique excerpts ` +
               `(${data.dropped} duplicate${data.dropped === 1 ? '' : 's'} dropped).`);
      break;

    case 'answer':
      renderAnswer(data.text, data.route);
      break;

    case 'done':
      if (state.step) state.step.classList.replace('active', 'done');
      state.step = null;
      if (!data.replay && data.api_calls) {
        const c = data.api_calls;
        note(`Done in ${(data.ms / 1000).toFixed(1)}s using ${c.llm} model call${c.llm === 1 ? '' : 's'}, ` +
             `${c.embed} embedding${c.embed === 1 ? '' : 's'}, ${c.rerank} rerank${c.rerank === 1 ? '' : 's'}.`);
      }
      refreshUsage();
      break;

    case 'error':
      note(data.message);
      break;
  }
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

/* Walk a cached run's frames with the same pacing the server uses, so the stepper animates
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
  resetRun(question);

  try {
    if (target.slug) await replayLocal(target.slug);
    else await streamSSE(target.url, handle);
  } catch (err) {
    if (err.name !== 'AbortError') {
      note(err.budgetExhausted
        ? err.message + ' Pick one of the saved runs above to see the whole thing work.'
        : err.message);
    }
  } finally {
    running = false;
    el.submit.disabled = false;
    el.submit.textContent = STATIC ? 'Filter' : 'Ask';
    if (state.step) state.step.classList.replace('active', 'done');
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
  el.examples.innerHTML = examples.map((ex) =>
    `<button class="chip" type="button" data-slug="${esc(ex.slug)}"
             data-question="${esc(ex.question)}" data-category="${esc(ex.category || '')}">
       ${esc(ex.question)}${ex.category ? `<span class="chip-cat">${esc(ex.category)}</span>` : ''}
     </button>`).join('');

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
    else el.examples.closest('.examples').hidden = true;
  } catch (_) {
    el.examples.closest('.examples').hidden = true;
  }
}

(function init() {
  if (STATIC) initStatic();
  else initServer();
})();
