/**
 * AGPL-3.0 §13 source offer.
 *
 * This service is licensed AGPL-3.0 (see THIRD_PARTY.md for why — three of the
 * bundled detectors are Ultralytics-architecture YOLO models). Section 13 asks
 * one concrete thing of a hosted service: people interacting with it over a
 * network must be offered its source. This puts that offer in the navbar of
 * every page the Space serves.
 *
 * Kept in its own file rather than folded into common.js for two reasons.
 * Compliance code should be one findable unit — someone auditing this should
 * not have to locate a function inside a utilities module — and common.js is
 * at 368 of the project's 400-line limit, so adding it there would spend the
 * remaining budget on something unrelated to what that file does.
 *
 * Loaded from index.html, eda.html and vision.html on the same source line as
 * common.js. Not stylistic: all three are pinned in .file-length-baseline at
 * their exact current length, so a new line in any of them fails CI.
 */
const _SOURCE_URL = 'https://github.com/ramleo/ML-Unified';

document.addEventListener('DOMContentLoaded', () => {
  const nav = document.querySelector('nav.nav');
  if (!nav || nav.querySelector('[data-source-offer]')) return;

  const a = document.createElement('a');
  a.href = _SOURCE_URL;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.dataset.sourceOffer = '1';
  a.title = 'Source code for this service — AGPL-3.0';
  // Matches the "Home" pill beside it rather than introducing a second style.
  a.style.cssText =
    'font-size:0.75rem;color:var(--text3);text-decoration:none;display:flex;' +
    'align-items:center;gap:0.3rem;padding:0.3rem 0.65rem;border:1px solid var(--border2);' +
    'border-radius:9999px;transition:color 0.15s,border-color 0.15s;white-space:nowrap';
  a.onmouseover = () => { a.style.color = 'var(--text)';  a.style.borderColor = 'var(--text3)';  };
  a.onmouseout  = () => { a.style.color = 'var(--text3)'; a.style.borderColor = 'var(--border2)'; };
  a.innerHTML =
    '<svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">' +
    '<path d="M8 0a8 8 0 00-2.53 15.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.4 7.4 0 014 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8 8 0 008 0z"/>' +
    '</svg>Source · AGPL-3.0';

  const picker = nav.querySelector('#themePickerWrap');
  picker ? nav.insertBefore(a, picker) : nav.appendChild(a);
});
