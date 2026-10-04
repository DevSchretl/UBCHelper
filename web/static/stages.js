/* Stage cards for "Ask the UBC Academic Calendar".
 *
 * The page draws a run as four cards (Plan, Search, Rank, Answer) above four panels. The
 * server (web/render.py) or app.js renders the cards and the panels; this script only keeps
 * track of which stage the visitor has open and shows that panel, by setting data-selected on
 * #pipe (panels.css hides the others). The choice lives here in the browser, so live updates
 * can redraw the cards during a run without moving anyone off the stage they are reading.
 *
 * It also marks the stages a visitor has not opened since the last run, remembers which list
 * (vector or keyword) each search shows on a phone, gives the examples row arrow buttons on a
 * laptop, and closes the phone keyboard after a question is asked.
 *
 * Shared by the Gradio Space (loaded through launch(head=...), so it can run before the page
 * exists) and web/static/index.html.
 */
(() => {
  'use strict';

  const STAGES = ['plan', 'search', 'rank', 'answer'];
  let selected = 'answer';
  let opened = new Set(['answer']);
  let run = null;
  let focusedCard = null;     // the card holding keyboard focus, so a redraw can hand it on
  let barElement = null;      // the card row last seen; every live update replaces it
  let barScroll = 0;          // how far the visitor has scrolled the card row, on a phone
  let barTouched = false;     // whether they scrolled it themselves during this run
  let lastActive = null;
  const picks = new Map();    // `${run}:${lane}` -> 'dense' or 'bm25', the list a phone shows
  const smooth = () => (window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth');

  function paint() {
    const pipe = document.getElementById('pipe');
    if (pipe && pipe.dataset.selected !== selected) pipe.dataset.selected = selected;

    const bar = document.querySelector('.stage-bar');
    if (bar) {
      if (bar.dataset.run !== run) {
        run = bar.dataset.run;
        opened = new Set([selected]);
        barTouched = false;
        lastActive = null;
      }
      // On a phone the card row scrolls sideways. A redraw would reset it to the start, so
      // carry the scroll position over, then bring the running stage into view unless the
      // visitor has been scrolling the row themselves.
      if (bar !== barElement) {
        barElement = bar;
        if (barScroll) bar.scrollLeft = barScroll;
        bar.addEventListener('scroll', () => { barScroll = bar.scrollLeft; }, { passive: true });
      }
      const running = bar.querySelector('.stage-card.is-active');
      const activeStage = running ? running.dataset.stage : null;
      // Instant, not smooth: the next redraw would cut a smooth scroll off halfway.
      if (activeStage && activeStage !== lastActive && !barTouched) reveal(activeStage, false);
      if (activeStage) lastActive = activeStage;
      const finished = bar.dataset.state === 'done';
      bar.querySelectorAll('.stage-card').forEach((card) => {
        const on = card.dataset.stage === selected;
        if (card.getAttribute('aria-selected') !== String(on)) card.setAttribute('aria-selected', String(on));
        if (card.tabIndex !== (on ? 0 : -1)) card.tabIndex = on ? 0 : -1;
        card.classList.toggle('unseen', finished && !opened.has(card.dataset.stage));
      });
      // A redraw replaces the cards. If it took away the card that had keyboard focus, give
      // focus to its replacement; if the visitor moved on, leave focus alone.
      const active = document.activeElement;
      if (focusedCard && !focusedCard.isConnected && (!active || active === document.body)) {
        const card = bar.querySelector(`.stage-card[data-stage="${selected}"]`);
        if (card) {
          focusedCard = card;
          card.focus({ preventScroll: true });
        }
      }
    }

    document.querySelectorAll('.sp-lane[data-lane]').forEach((lane) => {
      const pick = picks.get(`${run}:${lane.dataset.lane}`) || 'dense';
      lane.classList.toggle('show-bm25', pick === 'bm25');
      lane.querySelectorAll('[data-pick]').forEach((button) => {
        const on = String(button.dataset.pick === pick);
        if (button.getAttribute('aria-pressed') !== on) button.setAttribute('aria-pressed', on);
      });
    });

    setupExamples();
  }

  // Scroll the card row sideways, if it scrolls at all, so this stage's card is in view.
  function reveal(stage, smoothly = true) {
    const bar = document.querySelector('.stage-bar');
    const card = bar && bar.querySelector(`.stage-card[data-stage="${stage}"]`);
    if (!card || bar.scrollWidth <= bar.clientWidth + 1) return;
    const row = bar.getBoundingClientRect();
    const box = card.getBoundingClientRect();
    const behavior = smoothly ? smooth() : 'auto';
    if (box.left < row.left) bar.scrollBy({ left: box.left - row.left - 8, behavior });
    else if (box.right > row.right) bar.scrollBy({ left: box.right - row.right + 8, behavior });
    barScroll = bar.scrollLeft;
  }

  function select(stage, focus) {
    if (!STAGES.includes(stage)) return;
    selected = stage;
    opened.add(stage);
    paint();
    reveal(stage);
    if (focus) {
      const card = document.querySelector(`.stage-card[data-stage="${stage}"]`);
      if (card) card.focus({ preventScroll: true });
    }
  }

  // The examples row scrolls sideways. A phone swipes it; a laptop gets arrow buttons, since
  // a mouse wheel cannot scroll sideways. Gradio draws the row, so the arrows are added here.
  function setupExamples() {
    const box = document.getElementById('examples');
    const row = box && box.querySelector(':scope > .gallery');
    if (!row || row.dataset.arrows) return;
    row.dataset.arrows = 'on';
    box.querySelectorAll(':scope > .ex-arrow').forEach((old) => old.remove());
    const arrow = (dir) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `ex-arrow ex-${dir}`;
      button.setAttribute('aria-label', dir === 'prev' ? 'Scroll examples left' : 'Scroll examples right');
      button.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${dir === 'prev' ? 'm15 6-6 6 6 6' : 'm9 6 6 6-6 6'}"/></svg>`;
      button.addEventListener('click', () => {
        row.scrollBy({ left: (dir === 'prev' ? -0.8 : 0.8) * row.clientWidth, behavior: smooth() });
      });
      return button;
    };
    const prev = arrow('prev');
    const next = arrow('next');
    row.before(prev);
    row.after(next);
    const update = () => {
      const max = row.scrollWidth - row.clientWidth;
      prev.disabled = row.scrollLeft <= 2;
      next.disabled = row.scrollLeft >= max - 2;
      box.classList.toggle('fade-left', !prev.disabled);
      box.classList.toggle('fade-right', !next.disabled);
    };
    row.addEventListener('scroll', update, { passive: true });
    if (window.ResizeObserver) new ResizeObserver(update).observe(row);
    update();
  }

  document.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const card = target.closest('.stage-card');
    if (card) {
      select(card.dataset.stage);
      return;
    }

    const go = target.closest('[data-go]');
    if (go) {
      select(go.dataset.go);
      const bar = document.querySelector('.stage-bar');
      if (bar && bar.getBoundingClientRect().top < 0) bar.scrollIntoView({ block: 'start', behavior: smooth() });
      const next = document.querySelector(`.stage-card[data-stage="${go.dataset.go}"]`);
      if (next) next.focus({ preventScroll: true });
      return;
    }

    const pick = target.closest('[data-pick]');
    if (pick) {
      const lane = pick.closest('.sp-lane[data-lane]');
      if (lane) {
        picks.set(`${run}:${lane.dataset.lane}`, pick.dataset.pick);
        paint();
      }
      return;
    }

    // On a phone, close the keyboard once the question is asked so it does not cover the answer.
    if (target.closest('#ask-btn, #submit-btn') && window.matchMedia('(pointer: coarse)').matches) {
      const active = document.activeElement;
      if (active && typeof active.blur === 'function') active.blur();
    }
  });

  document.addEventListener('keydown', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (event.key === 'Enter' && !event.shiftKey && target.closest('#question')
        && window.matchMedia('(pointer: coarse)').matches) {
      setTimeout(() => target.blur(), 0);
      return;
    }
    if (!target.closest('.stage-card')) return;
    const i = STAGES.indexOf(selected);
    const j = { ArrowRight: (i + 1) % 4, ArrowLeft: (i + 3) % 4, Home: 0, End: 3 }[event.key];
    if (j === undefined) return;
    event.preventDefault();
    select(STAGES[j], true);
  });

  document.addEventListener('focusin', (event) => {
    const card = event.target instanceof Element ? event.target.closest('.stage-card') : null;
    focusedCard = card;
  });
  document.addEventListener('pointerdown', (event) => {
    if (!(event.target instanceof Element) || !event.target.closest('.stage-card')) focusedCard = null;
    if (event.target instanceof Element && event.target.closest('.stage-bar')) barTouched = true;
  });
  document.addEventListener('wheel', (event) => {
    if (event.target instanceof Element && event.target.closest('.stage-bar')) barTouched = true;
  }, { passive: true });

  // Live updates replace the cards and panels; repaint the selection after each one, before
  // the browser draws the frame.
  const start = () => {
    new MutationObserver(paint).observe(document.body, { childList: true, subtree: true });
    paint();
  };
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start);
})();
