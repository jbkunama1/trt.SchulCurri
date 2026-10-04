// Globale Helfer (CSP: kein Inline-JS, daher Event-Delegation)
function csrf() { return document.querySelector('meta[name="csrf-token"]').content; }

async function api(url, data) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf() },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

function setTheme(t) {
  document.documentElement.dataset.theme = t;
  document.querySelectorAll('.theme-card').forEach(b => b.classList.toggle('active', b.dataset.setTheme === t));
  try { localStorage.setItem('theme', t); } catch (e) { /* ignorieren */ }
  if (document.body.dataset.auth) api('/api/theme', { theme: t }).catch(() => {});
}

document.addEventListener('click', e => {
  const t = e.target.closest('[data-set-theme]');
  if (t) { setTheme(t.dataset.setTheme); return; }
  if (e.target.closest('[data-print]')) window.print();
});

document.addEventListener('submit', e => {
  const msg = e.target.dataset.confirm;
  if (msg && !window.confirm(msg)) e.preventDefault();
});

if (!document.body.dataset.auth) {
  try {
    const saved = localStorage.getItem('theme');
    if (saved) document.documentElement.dataset.theme = saved;
  } catch (e) { /* ignorieren */ }
}
