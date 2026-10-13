/* Hover citations.

   Prose carries <cite data-r="key1 key2">; this turns each into a small
   superscript marker and shows the entry on hover or focus. The entries come
   from the paper's own bibliography (refs.json), so the page and the paper
   cannot drift apart. */
(() => {
  const marks = [...document.querySelectorAll('cite[data-r]')];
  if (!marks.length) return;

  let card = null, hideT = 0;
  const make = () => {
    card = document.createElement('div');
    card.className = 'refcard';
    card.setAttribute('role', 'tooltip');
    card.addEventListener('pointerenter', () => clearTimeout(hideT));
    card.addEventListener('pointerleave', hide);
    document.body.appendChild(card);
  };
  const hide = () => { hideT = setTimeout(() => card && card.classList.remove('on'), 120); };

  fetch('refs.json').then((r) => r.json()).then((R) => {
    // number the references in reading order, the way a paper does
    const num = new Map();
    marks.forEach((m) => m.dataset.r.split(/\s+/).forEach((k) => {
      if (R[k] && !num.has(k)) num.set(k, num.size + 1);
    }));

    marks.forEach((m) => {
      const keys = m.dataset.r.split(/\s+/).filter((k) => R[k]);
      if (!keys.length) { m.remove(); return; }
      m.textContent = keys.map((k) => num.get(k)).join(',');
      m.tabIndex = 0;
      const show = () => {
        if (!card) make();
        clearTimeout(hideT);
        card.innerHTML = keys.map((k) => {
          const e = R[k];
          return `<div class="refrow"><span class="refn">${num.get(k)}</span>` +
                 `<span><span class="reft">${e.t}</span>` +
                 `<span class="refm">${e.a} · ${e.v} ${e.y}</span></span></div>`;
        }).join('');
        card.classList.add('on');
        const r = m.getBoundingClientRect();
        const w = Math.min(380, window.innerWidth - 32);
        card.style.width = `${w}px`;
        let x = r.left + r.width / 2 - w / 2;
        x = Math.max(16, Math.min(x, window.innerWidth - w - 16));
        card.style.left = `${x}px`;
        const below = r.bottom + 10 + card.offsetHeight < window.innerHeight;
        card.style.top = `${window.scrollY +
          (below ? r.bottom + 9 : r.top - card.offsetHeight - 9)}px`;
      };
      m.addEventListener('pointerenter', show);
      m.addEventListener('focus', show);
      m.addEventListener('pointerleave', hide);
      m.addEventListener('blur', hide);
    });
  }).catch(() => {});
})();
