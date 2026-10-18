# Собирает самодостаточный index.html (все заметки внутри) для базы знаний.
# Usage: python -I build_ui.py <brain_dir>
import json, sys
from pathlib import Path

B = Path(sys.argv[1])
GROUPS = [('Старт', ['00-Начни-здесь', '01-Роадмап', '02-Чеклист', '03-Что-дальше']), ('Уроки', 'Уроки'), ('Каталоги', 'Каталоги'),
          ('Сообщество', ['Проекты-участников']), ('Расшифровки видео', 'Транскрипты')]
notes, nav = {}, []
for title, src in GROUPS:
    files = [B / f'{n}.md' for n in src] if isinstance(src, list) else sorted((B / src).glob('*.md'))
    items = []
    for f in files:
        text = f.read_text(encoding='utf-8')
        h1 = next((l[2:].strip() for l in text.splitlines() if l.startswith('# ')), f.stem)
        notes[f.stem] = {'title': h1, 'md': text}
        items.append(f.stem)
    nav.append({'title': title, 'items': items, 'collapsed': title == 'Расшифровки видео'})

DATA = json.dumps({'notes': notes, 'nav': nav}, ensure_ascii=False).replace('</', '<\\/')

HTML = r'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ИИнженер: база знаний</title>
<style>
:root{--bg:#f7f7f5;--panel:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e6e6e2;--accent:#5b5bd6;--accent-soft:#ececfb;--code:#f1f1ee}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--panel:#1c1c1f;--fg:#ececee;--muted:#9a9aa2;--line:#2c2c31;--accent:#8f8fff;--accent-soft:#25254a;--code:#26262b}}
:root[data-theme="dark"]{--bg:#141416;--panel:#1c1c1f;--fg:#ececee;--muted:#9a9aa2;--line:#2c2c31;--accent:#8f8fff;--accent-soft:#25254a;--code:#26262b}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex}
aside{width:300px;flex-shrink:0;background:var(--panel);border-right:1px solid var(--line);height:100vh;overflow-y:auto;position:sticky;top:0;padding:18px 14px}
.brand{font-weight:800;font-size:18px;margin:0 6px 4px}.sub{color:var(--muted);font-size:12px;margin:0 6px 14px}
#q{width:100%;padding:9px 12px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--fg);font-size:14px;outline:none}
#q:focus{border-color:var(--accent)}
.grp{margin-top:16px}.grp>button{all:unset;cursor:pointer;display:block;width:100%;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:4px 6px}
.grp a{display:block;padding:5px 8px;border-radius:8px;color:var(--fg);text-decoration:none;font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.grp a:hover{background:var(--bg)}.grp a.on{background:var(--accent-soft);color:var(--accent);font-weight:600}
.grp.closed .items{display:none}
main{flex:1;min-width:0;height:100vh;overflow-y:auto}
article{max-width:860px;margin:0 auto;padding:36px 32px 80px}
article h1{font-size:30px;line-height:1.25;margin:0 0 18px}article h2{margin-top:34px;padding-top:8px;border-top:1px solid var(--line);font-size:21px}article h3{font-size:17px;margin-top:22px}
article a{color:var(--accent)}article blockquote{margin:14px 0;padding:10px 16px;background:var(--accent-soft);border-radius:10px}article blockquote p{margin:4px 0}
article code{background:var(--code);padding:1px 6px;border-radius:5px;font-size:13px}article pre{background:var(--code);padding:14px;border-radius:10px;overflow-x:auto;white-space:pre-wrap}article pre code{padding:0;background:none}
article table{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow-x:auto}article th,article td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}article th{background:var(--bg)}
article li{margin:3px 0}article ul.contains-task-list,article li.task{list-style:none}
article input[type=checkbox]{width:17px;height:17px;accent-color:var(--accent);vertical-align:-3px;margin-right:6px;cursor:pointer}
article hr{border:none;border-top:1px solid var(--line);margin:28px 0}
.progress{position:sticky;top:0;z-index:2;background:var(--bg);padding:10px 0 12px;margin:-10px 0 10px}
.bar{height:8px;background:var(--line);border-radius:6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--accent);transition:width .3s}
.ptext{font-size:13px;color:var(--muted);margin-bottom:5px}
.watch{display:inline-block;margin:0 8px 8px 0;padding:9px 16px;border-radius:10px;background:#e33;color:#fff!important;text-decoration:none;font-weight:600}
.res{padding:12px 14px;border:1px solid var(--line);border-radius:10px;margin-bottom:10px;background:var(--panel);cursor:pointer}.res:hover{border-color:var(--accent)}
.res b{display:block;margin-bottom:3px}.res span{font-size:13px;color:var(--muted)}.res mark{background:var(--accent-soft);color:var(--accent)}
.top{display:flex;justify-content:flex-end;gap:8px;padding:12px 18px 0}
.top button,#menu{border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:8px;padding:6px 10px;cursor:pointer;font-size:13px}
#menu{display:none}
@media (max-width:820px){body{display:block}aside{position:fixed;inset:0 auto 0 0;z-index:5;transform:translateX(-100%);transition:transform .2s;width:84%;max-width:320px}
aside.open{transform:none;box-shadow:0 0 40px rgba(0,0,0,.3)}main{height:auto}#menu{display:inline-block}.top{justify-content:space-between}article{padding:20px 16px 60px}}
</style></head><body>
<aside id="side"><div class="brand">🧠 ИИнженер 1.0</div><div class="sub">База знаний курса</div>
<input id="q" placeholder="Поиск по всем урокам…" autocomplete="off"><nav id="nav"></nav></aside>
<main id="main"><div class="top"><button id="menu">☰ Меню</button><button id="theme" title="Тема">🌓</button></div><article id="doc"></article></main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const store = { get(k){ try{ return JSON.parse(localStorage.getItem(k)) }catch(e){ return null } }, set(k,v){ try{ localStorage.setItem(k, JSON.stringify(v)) }catch(e){} } };
const $ = s => document.querySelector(s);
const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// Theme toggle (remembered per viewer).
const savedTheme = store.get('theme'); if (savedTheme) document.documentElement.dataset.theme = savedTheme;
$('#theme').onclick = () => { const dark = matchMedia('(prefers-color-scheme: dark)').matches;
  const cur = document.documentElement.dataset.theme || (dark ? 'dark' : 'light'); const nx = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = nx; store.set('theme', nx); };
$('#menu').onclick = () => $('#side').classList.toggle('open');

// Sidebar.
const nav = $('#nav');
D.nav.forEach(g => {
  const closed = store.get('grp:' + g.title) ?? g.collapsed;
  const el = document.createElement('div'); el.className = 'grp' + (closed ? ' closed' : '');
  el.innerHTML = `<button>${g.title} ▾</button><div class="items">` + g.items.map(id =>
    `<a href="#/${encodeURIComponent(id)}" data-id="${esc(id)}">${esc(D.notes[id].title.replace(/^Расшифровка: /,''))}</a>`).join('') + '</div>';
  el.querySelector('button').onclick = () => { el.classList.toggle('closed'); store.set('grp:' + g.title, el.classList.contains('closed')); };
  nav.appendChild(el);
});

// Markdown → HTML: strip frontmatter, turn [[wiki|links]] into hash routes.
function toHtml(md) {
  md = md.replace(/^---\n[\s\S]*?\n---\n/, '');
  md = md.replace(/\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\\?\|([^\]]+))?\]\]/g, (m, t, label) => {
    t = t.trim(); const known = D.notes[t];
    return `[${(label || (known ? known.title : t)).trim()}](#/${encodeURIComponent(t)})`;
  });
  return marked.parse(md, { gfm: true });
}

function render(id) {
  const n = D.notes[id] || D.notes['00-Начни-здесь']; id = D.notes[id] ? id : '00-Начни-здесь';
  const doc = $('#doc'); doc.innerHTML = toHtml(n.md);
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.id === id));
  document.title = n.title + ' · ИИнженер';
  // Lessons: big "watch" buttons for the YouTube recordings.
  if (id.startsWith('Урок-')) {
    const vids = [...doc.querySelectorAll('h2')].find(h => h.textContent.includes('Видео'));
    const links = vids ? [...vids.nextElementSibling.querySelectorAll('a[href*="youtu"]')] : [];
    if (links.length) { const box = document.createElement('div');
      box.innerHTML = links.map(a => `<a class="watch" target="_blank" rel="noopener" href="${a.href}">▶ ${esc(a.textContent)}</a>`).join('');
      doc.querySelector('h1').after(box); }
  }
  doc.querySelectorAll('a[href^="http"]').forEach(a => { a.target = '_blank'; a.rel = 'noopener'; });
  // Checkboxes: interactive, saved per note.
  const boxes = [...doc.querySelectorAll('input[type=checkbox]')];
  if (boxes.length) {
    const key = 'chk:' + id, state = store.get(key) || {};
    const prog = document.createElement('div'); prog.className = 'progress';
    const upd = () => { const done = boxes.filter(b => b.checked).length;
      prog.innerHTML = `<div class="ptext">Прогресс: ${done} из ${boxes.length}</div><div class="bar"><i style="width:${100*done/boxes.length}%"></i></div>`; };
    boxes.forEach((b, i) => { b.disabled = false; b.checked = !!state[i]; b.closest('li')?.classList.add('task');
      b.onchange = () => { state[i] = b.checked; store.set(key, state); upd(); }; });
    upd(); doc.querySelector('h1').after(prog);
  }
  doc.querySelectorAll('pre code.language-mermaid').forEach(c => { const d = document.createElement('div'); d.className = 'mermaid'; d.textContent = c.textContent; c.parentElement.replaceWith(d); });
  if (window.mermaid && doc.querySelector('.mermaid')) { mermaid.initialize({ startOnLoad:false, theme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'default' }); mermaid.run(); }
  $('#main').scrollTop = 0; $('#side').classList.remove('open');
}

// Full-text search over every note (incl. transcripts).
function search(q) {
  q = q.trim().toLowerCase(); if (q.length < 2) return route();
  const hits = [];
  for (const [id, n] of Object.entries(D.notes)) {
    const txt = n.md.replace(/\[\[([^\]|]+)\|?([^\]]*)\]\]/g, '$2'); const low = txt.toLowerCase();
    let i = low.indexOf(q), count = 0, first = i; while (i >= 0 && count < 99) { count++; i = low.indexOf(q, i + q.length); }
    if (count) { const s = Math.max(0, first - 70); const snip = esc(txt.slice(s, first + q.length + 90).replace(/\s+/g, ' '));
      hits.push({ id, count, title: n.title, snip: snip.replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), m => `<mark>${m}</mark>`), tr: id.startsWith('Транскрипт') }); }
  }
  hits.sort((a, b) => (a.tr - b.tr) || (b.count - a.count));
  $('#doc').innerHTML = `<h1>Поиск: «${esc(q)}»</h1><p style="color:var(--muted)">Найдено в ${hits.length} заметках</p>` +
    hits.map(h => `<div class="res" onclick="location.hash='#/${encodeURIComponent(h.id)}'"><b>${esc(h.title)} <small style="color:var(--muted)">· ${h.count}</small></b><span>…${h.snip}…</span></div>`).join('');
}
let t; $('#q').oninput = e => { clearTimeout(t); t = setTimeout(() => search(e.target.value), 200); };

function route() { const id = decodeURIComponent(location.hash.replace(/^#\//, '')) || '00-Начни-здесь'; render(id); }
window.onhashchange = () => { $('#q').value = ''; route(); };
route();
</script></body></html>'''

(B / 'index.html').write_text(HTML.replace('__DATA__', DATA), encoding='utf-8')
print('notes', len(notes), 'size', (B / 'index.html').stat().st_size)
