/* Copy buttons: <button class="copy-btn" data-copy="#id"> copies that element's text.
   The button turns green with a check for a moment on success. The Clipboard API needs a
   secure context (https or localhost); elsewhere it falls back to a hidden textarea. */
(() => {
  const fallback = (text) => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:-1000px;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  };
  document.querySelectorAll('.copy-btn[data-copy]').forEach((btn) => {
    const label = btn.querySelector('.copy-label');
    let timer = 0;
    const show = (cls, text) => {
      clearTimeout(timer);
      btn.classList.remove('copied', 'failed');
      btn.classList.add(cls);
      if (label) label.textContent = text;
      timer = setTimeout(() => {
        btn.classList.remove(cls);
        if (label) label.textContent = 'Copy';
      }, 1800);
    };
    btn.addEventListener('click', async () => {
      const src = document.querySelector(btn.dataset.copy);
      if (!src) return;
      const text = src.textContent;
      let ok = false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
          ok = true;
        }
      } catch (e) { ok = false; }
      if (!ok) ok = fallback(text);
      show(ok ? 'copied' : 'failed', ok ? 'Copied' : 'Press ⌘C');
      if (!ok) {
        const r = document.createRange();
        r.selectNodeContents(src);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(r);
      }
    });
  });
})();
