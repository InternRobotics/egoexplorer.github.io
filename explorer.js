/* Session explorer.

   One <video> holds the four-panel session recording; the four canvases each
   draw a different crop of it, so the streams stay exactly in sync without
   four downloads. Segment times come from sessions.json, which maps the source
   caption timeline onto the accelerated, head-trimmed video. */
(() => {
  // Panels A and D are still crops of the dashboard; B and C now come from
  // their own renders (Blender SMPL-X, and MANO posed from the glove), so each
  // stream has its own source. The dashboard stays the clock.
  const CROP = {
    ego:     [[96, 80, 586, 330]],
    // the two dashboard cards' interiors (borders at x 198-206 | 384-391 | 570-577 | 755-763);
    // the old right crop started inside the skeleton card and cut the hand at x 725
    tactile: [[207, 466, 176, 184], [578, 466, 176, 184]],   // left + right tactile
  };
  // The dashboard draws both tactile hands palm-up as seen from the back, so the left hand's
  // thumb lands on the right and the right hand's on the left. Mirror each hand in place so the
  // left thumb sits on the left and the right thumb on the right, but only the band between the
  // title ("Left tactile") and the "Contact n / 17" readout, which stay readable.
  const MIRROR_BAND = { tactile: [16, 170] };                // source rows [from, to) within a crop
  const OWN = { body: 'body', fingers: 'hands' };            // stream -> asset folder
  const HOME = new Set(['session_G', 'session_H', 'session_I', 'session_J']);
  const ORDER = ['session_A', 'session_B', 'session_C', 'session_D', 'session_E',
                 'session_F', 'session_G', 'session_H', 'session_I', 'session_J'];

  // bumped when the panels are re-rendered, so a visitor who has seen the
  // page before does not keep the previous cut from cache
  const V = '?v=31';

  const $ = (id) => document.getElementById(id);
  const picker = $('task-picker'), video = $('session-video');
  if (!picker || !video) return;

  // one hidden <video> per own-source stream, kept in step with the master
  const extra = {};
  for (const k of Object.keys(OWN)) {
    const v = document.createElement('video');
    v.muted = true; v.playsInline = true; v.preload = 'metadata';
    v.style.display = 'none';
    document.body.appendChild(v);
    extra[k] = v;
  }
  const canvases = [...document.querySelectorAll('.streams canvas')].map((c) => ({
    el: c, ctx: c.getContext('2d'), kind: c.dataset.stream,
    parts: CROP[c.dataset.stream] || null, own: extra[c.dataset.stream] || null,
    band: MIRROR_BAND[c.dataset.stream] || null,
  }));

  let data = null, segs = [], active = -1, raf = 0, order = [], cur = 0;
  let onScreen = false, paused = false;

  const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

  function paint() {
    for (const { el, ctx, parts, own, band } of canvases) {
      const src = own || video;
      if (src.readyState < 2) continue;
      ctx.clearRect(0, 0, el.width, el.height);
      if (!parts) {                       // own render: draw the whole frame
        const sw = src.videoWidth, sh = src.videoHeight;
        if (!sw) continue;
        const s = Math.min(el.width / sw, el.height / sh);
        ctx.drawImage(src, 0, 0, sw, sh,
                      (el.width - sw * s) / 2, (el.height - sh * s) / 2, sw * s, sh * s);
        continue;
      }
      const w = el.width / parts.length;
      parts.forEach(([sx, sy, sw, sh], i) => {
        const s = Math.min(w / sw, el.height / sh);
        const dx = i * w + (w - sw * s) / 2, dy = (el.height - sh * s) / 2;
        if (!band) {
          ctx.drawImage(src, sx, sy, sw, sh, dx, dy, sw * s, sh * s);
          return;
        }
        const [b0, b1] = band;
        // title and readout as they are
        ctx.drawImage(src, sx, sy, sw, b0, dx, dy, sw * s, b0 * s);
        ctx.drawImage(src, sx, sy + b1, sw, sh - b1, dx, dy + b1 * s, sw * s, (sh - b1) * s);
        // the hand, flipped about the crop's vertical centre line
        ctx.save();
        ctx.translate(dx + sw * s, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(src, sx, sy + b0, sw, b1 - b0, 0, dy + b0 * s, sw * s, (b1 - b0) * s);
        ctx.restore();
      });
    }
    // the own-source clips drift a little; nudge them back to the master clock
    for (const v of Object.values(extra)) {
      if (v.readyState >= 1 && Math.abs(v.currentTime - video.currentTime) > 0.22) {
        v.currentTime = video.currentTime;
      }
      if (video.paused !== v.paused) { video.paused ? v.pause() : v.play().catch(() => {}); }
    }
    if (segs.length) {
      const t = video.currentTime;
      $('tl-head').style.left = `${(t / (video.duration || 1)) * 100}%`;
      $('tl-time').textContent = mmss(t);
      let k = segs.findIndex((s) => t >= s.t && t < s.e);
      if (k === -1) k = t < segs[0].t ? 0 : segs.length - 1;
      if (k !== active) {
        active = k;
        $('seg-idx').textContent = `SUBTASK ${String(k + 1).padStart(2, '0')}`;
        $('seg-label').textContent = segs[k].label;
        $('seg-text').textContent = segs[k].text;
        [...$('tl-segs').children].forEach((e, i) => e.classList.toggle('on', i === k));
        const list = $('seg-items');
        [...list.children].forEach((e, i) => {
          const on = i === k;
          e.classList.toggle('on', on);
          // scrollIntoView bubbles to ancestor scrollers and creeps the whole
          // page upward; move only this list's own scrollTop
          if (on) {
            const top = e.offsetTop - list.clientHeight / 2 + e.offsetHeight / 2;
            list.scrollTop = Math.max(0, Math.min(top, list.scrollHeight - list.clientHeight));
          }
        });
      }
    }
    raf = requestAnimationFrame(paint);
  }

  function render(id) {
    const d = data[id];
    cur = Math.max(order.indexOf(id), 0);
    segs = d.segments; active = -1;
    [...picker.children].forEach((b) =>
      b.setAttribute('aria-selected', String(b.dataset.id === id)));
    video.src = `assets/sessions/${id}.mp4${V}`;
    video.load();
    for (const [k, folder] of Object.entries(OWN)) {
      extra[k].src = `assets/${folder}/${id}.mp4${V}`;
      extra[k].load();
    }
    $('tl-meta').textContent =
      `${d.task} · ${Math.round(d.source_duration)} s of work at ${d.speed}× · ${segs.length} subtasks`;

    $('tl-segs').innerHTML = '';
    segs.forEach((s) => {
      const i = document.createElement('i');
      i.style.flex = String(Math.max(s.e - s.t, 0.12));
      $('tl-segs').appendChild(i);
    });
    $('seg-count').textContent = `${segs.length} subtasks`;
    $('seg-items').innerHTML = '';
    segs.forEach((s) => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="t">${mmss(s.t)}</span><span class="l">${s.label}</span>`;
      li.addEventListener('click', () => { video.currentTime = s.t + 0.05; video.play(); });
      $('seg-items').appendChild(li);
    });
    if (onScreen) start();
  }

  // the section plays itself: each session runs once, then hands over to the
  // next, so a visitor who just scrolls here still sees every task
  function start() {
    paused = false;
    video.play().catch(() => {});
    for (const v of Object.values(extra)) v.play().catch(() => {});
  }
  function stop() {
    video.pause();
    for (const v of Object.values(extra)) v.pause();
  }
  video.addEventListener('ended', () => {
    render(order[(cur + 1) % order.length]);
  });

  $('pp').addEventListener('click', () => {
    if (video.paused) { start(); } else { paused = true; stop(); }
  });
  const sync = () => $('pp').classList.toggle('playing', !video.paused);
  video.addEventListener('play', sync);
  video.addEventListener('pause', sync);

  $('tl').addEventListener('click', (e) => {
    const r = $('tl').getBoundingClientRect();
    video.currentTime = ((e.clientX - r.left) / r.width) * (video.duration || 0);
  });

  fetch('assets/sessions.json').then((r) => r.json()).then((j) => {
    data = j;
    order = ORDER.filter((id) => j[id]);
    order.forEach((id) => {
      const b = document.createElement('button');
      b.type = 'button'; b.role = 'tab'; b.dataset.id = id;
      if (HOME.has(id)) b.classList.add('home');
      b.setAttribute('aria-selected', 'false');
      b.innerHTML = `<span class="dot"></span>${j[id].task}`;
      b.addEventListener('click', () => render(id));
      picker.appendChild(b);
    });
    render(order[0]);
    raf = requestAnimationFrame(paint);

    const grid = $('streams-grid');
    if (grid && 'IntersectionObserver' in window) {
      new IntersectionObserver((es) => {
        onScreen = es[0].isIntersecting;
        if (onScreen && !paused) start(); else stop();
      }, { threshold: 0.3 }).observe(grid);
    } else {
      onScreen = true; start();
    }
  }).catch(() => { $('seg-text').textContent = 'Could not load the session index.'; });

})();

/* The capture notes follow the camera.

   The figure is one continuous move — whole rig, head, wrist — so the notes
   highlight themselves as it arrives at each, rather than waiting to be
   clicked. Clicking one still seeks the film to that point. Without JS the
   video simply plays and every note stays legible. */
(() => {
  const film = document.getElementById('rig-film');
  const notes = [...document.querySelectorAll('.rig-note')];
  if (!film || notes.length < 2) return;
  document.documentElement.setAttribute('data-rig', '');
  // a note can claim more than one stretch of the film: the camera pulls back
  // to the wide shot at the end, so the first note takes that too
  const marks = [];
  notes.forEach((n, i) => String(n.dataset.at).split(',')
    .forEach((t) => marks.push([parseFloat(t) || 0, i])));
  marks.sort((a, b) => a[0] - b[0]);
  let cur = -1;
  const show = (i) => {
    if (i === cur) return;
    cur = i;
    notes.forEach((n, k) => n.classList.toggle('on', k === i));
  };
  film.addEventListener('timeupdate', () => {
    let i = marks[0][1];
    for (const [t, k] of marks) if (film.currentTime >= t) i = k;
    show(i);
  });
  notes.forEach((n, i) => {
    n.tabIndex = 0;
    const first = marks.find(([, k]) => k === i);
    const go = () => {
      film.currentTime = (first ? first[0] : 0) + 0.05;
      film.play().catch(() => {});
      show(i);
    };
    n.addEventListener('click', go);
    n.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); }
    });
  });
  show(0);
  // only run while it is on screen
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((es) => {
      if (es[0].isIntersecting) film.play().catch(() => {}); else film.pause();
    }, { threshold: 0.25 }).observe(film);
  }
})();
