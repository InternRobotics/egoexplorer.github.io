/* Motion: reveals, a scroll-spy nav, a progress rail and counting stats.

   Everything here is additive and reversible — the page is complete without
   it. It switches itself off under prefers-reduced-motion, and the whole
   layer goes away by deleting <html data-motion>.

   Visibility is driven by a plain geometry sweep rather than an
   IntersectionObserver. An observer does not fire in a background tab, and
   anything that hides content with CSS and reveals it from script has to fail
   open: if the sweep never runs, a watchdog reveals everything. */
(() => {
  const root = document.documentElement;
  if (!root.hasAttribute('data-motion')) return;
  if (window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    root.removeAttribute('data-motion');
    return;
  }

  const GROUPS = [
    ['.prose > h2, .prose > p, .prose > ul, .prose > .spec, .prose > pre', 0],
    ['.chapter-head > *', 1],
    ['.figure, .rig-figure, .chapter-stage, .pointcloud-viewer, .picker,' +
     ' .streams, .transport, .seg-row, .tile-key, .ch-stats, .duo, .ch-steps', 0],
  ];
  let pending = [];
  for (const [sel, stagger] of GROUPS) {
    document.querySelectorAll(sel).forEach((el) => {
      el.classList.add('rv');
      pending.push(el);
      if (stagger) {
        const sibs = [...el.parentElement.children];
        el.style.setProperty('--rvd', `${sibs.indexOf(el) * 70}ms`);
      }
    });
  }

  // ── stats count up, once, when their block is reached ──────────────────
  const counters = [...document.querySelectorAll('.ch-stats .n')].map((el) => {
    // a trailing element (the live "+" on the hours stat) is kept, only the digits count
    const tail = el.querySelector('i');
    if (tail) tail.remove();
    const raw = el.textContent.trim();
    const target = parseFloat(raw.replace(/,/g, ''));
    if (!isFinite(target)) return null;
    el.style.minWidth = `${el.getBoundingClientRect().width}px`;
    const fmt = (v) => raw.includes(',')
      ? Math.round(v).toLocaleString('en-US') : String(Math.round(v));
    const put = (txt) => { el.textContent = txt; if (tail) el.appendChild(tail); };
    // The real number stays in the DOM until the count-up actually starts.
    // Zeroing it here instead meant anything that reads the page without
    // scrolling -- a crawler, a share preview, reader mode, a screenshot --
    // saw "0 body joints, in physics", which reads as a result rather than an
    // animation that has not run yet.
    return { el, target, fmt, put, done: false };
  }).filter(Boolean);

  // stepped on a timer, not rAF: a throttled tab starves rAF and the number
  // would sit at zero forever
  const run = (c) => {
    c.done = true;
    c.put(c.fmt(0));                       // start from zero only now
    const t0 = Date.now(), D = 1100;
    const id = setInterval(() => {
      const u = Math.min((Date.now() - t0) / D, 1);
      c.put(c.fmt(c.target * (1 - Math.pow(1 - u, 3))));
      if (u >= 1) { clearInterval(id); c.el.classList.add('counted'); }
    }, 16);
  };

  const revealAll = () => {
    pending.forEach((el) => el.classList.add('in'));
    pending = [];
    counters.forEach((c) => { if (!c.done) { c.done = true; c.put(c.fmt(c.target)); c.el.classList.add('counted'); } });
  };

  // ── the rail, and the nav that says where you are ──────────────────────
  const rail = document.createElement('div');
  rail.className = 'read-rail';
  rail.innerHTML = '<i></i>';
  document.body.appendChild(rail);
  const bar = rail.firstElementChild;
  const links = [...document.querySelectorAll('.nav-links a')];
  const targets = links
    .map((a) => [a, document.querySelector(a.getAttribute('href'))])
    .filter(([, t]) => t);
  // measured against the document, not an offsetParent that may be positioned
  const docTop = (el) => el.getBoundingClientRect().top + window.scrollY;

  let swept = false, last = 0;
  function sweep() {
    swept = true;
    const vh = window.innerHeight;
    if (pending.length) {
      const keep = [];
      for (const el of pending) {
        // anything at or above the fold is revealed, including what a jump
        // scrolled straight past — requiring it to be *in* the viewport leaves
        // skipped elements invisible for the rest of the session
        if (el.getBoundingClientRect().top < vh * 0.92) el.classList.add('in');
        else keep.push(el);
      }
      pending = keep;
    }
    for (const c of counters) {
      if (c.done) continue;
      if (c.el.getBoundingClientRect().top < vh * 0.85) run(c);
    }
    const h = document.documentElement.scrollHeight - vh;
    bar.style.transform = `scaleX(${h > 0 ? window.scrollY / h : 0})`;
    const mid = window.scrollY + vh * 0.34;
    let cur = null;
    for (const [a, t] of targets) {
      if (docTop(t) <= mid) cur = a;
    }
    links.forEach((a) => a.classList.toggle('here', a === cur));
  }

  // throttled on the clock rather than on a frame, for the same reason
  let queued = 0;
  const onScroll = () => {
    const now = Date.now();
    if (now - last >= 60) { last = now; sweep(); return; }
    if (!queued) {
      queued = setTimeout(() => { queued = 0; last = Date.now(); sweep(); }, 60);
    }
  };
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', onScroll);
  addEventListener('load', onScroll);
  document.addEventListener('visibilitychange', onScroll);
  sweep();
  // fail open: if the sweep has somehow not run, nothing stays hidden
  setTimeout(() => { if (!swept) revealAll(); }, 2500);
})();

/* The nav inverts over the dark chapters and the hero.

   Not part of the motion layer: this runs whether or not <html data-motion>
   is set, because a white bar sitting on a black chapter is a design fault
   rather than an embellishment. */
(() => {
  const nav = document.querySelector('.nav');
  if (!nav) return;
  const dark = [...document.querySelectorAll('.hero, .chapter')];
  if (!dark.length) return;
  let last = 0, queued = 0;
  const test = () => {
    // the nav is sticky and sits in flow, so it never overlaps anything;
    // what matters is what is directly underneath it
    const edge = nav.getBoundingClientRect().bottom + 2;
    const on = dark.some((s) => {
      const r = s.getBoundingClientRect();
      return r.top <= edge && r.bottom >= edge;
    });
    nav.classList.toggle('on-dark', on);
  };
  const onScroll = () => {
    const now = Date.now();
    if (now - last >= 60) { last = now; test(); return; }
    if (!queued) {
      queued = setTimeout(() => { queued = 0; last = Date.now(); test(); }, 60);
    }
  };
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', onScroll);
  addEventListener('load', onScroll);
  test();
})();
