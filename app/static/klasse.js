// Autosave fuer Checkliste, Bewertung und Reflexion
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const stamp = () => new Date().toLocaleString('de-DE');

document.querySelectorAll('.item').forEach(card => {
  const note = card.querySelector('.note');
  const meta = card.querySelector('.meta');
  const save = () => api('/api/checklist', { id: card.dataset.id, status: card.dataset.status, note: note.value })
    .then(() => { meta.textContent = '💾 gespeichert ' + stamp(); })
    .catch(() => { meta.textContent = '⚠️ Speichern fehlgeschlagen. Bitte neu laden und erneut versuchen.'; });
  card.querySelectorAll('.status-btn').forEach(btn => btn.addEventListener('click', () => {
    card.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    card.dataset.status = btn.dataset.status;
    save();
  }));
  note.addEventListener('input', debounce(save, 700));
});

document.querySelectorAll('.eval').forEach(card => {
  const btn = card.querySelector('.done-btn');
  const res = card.querySelector('.result');
  let done = btn.dataset.done === '1';
  const save = () => api('/api/evaluation', { id: card.dataset.id, done, result: res.value }).catch(() => {});
  btn.addEventListener('click', () => { done = !done; btn.textContent = done ? '✅' : '⬜'; save(); });
  res.addEventListener('input', debounce(save, 700));
});

const saved = document.getElementById('saved');
document.querySelectorAll('.ref').forEach(ta => {
  ta.addEventListener('input', debounce(() => {
    api('/api/reflection', { year_id: document.body.dataset.year, stage: document.body.dataset.stage, qkey: ta.dataset.qkey, answer: ta.value })
      .then(() => { saved.textContent = '💾 Reflexion gespeichert ' + stamp(); })
      .catch(() => { saved.textContent = '⚠️ Speichern fehlgeschlagen'; });
  }, 800));
});
