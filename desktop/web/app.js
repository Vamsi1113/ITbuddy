/* Tobi desktop chat: messenger-style conversation, live view drawer, agents / connectors / tools sheets. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const api = () => (window.pywebview && window.pywebview.api) || null;
  async function call(name, ...args) {
    const a = api();
    if (!a || !a[name]) return null;
    try { return await a[name](...args); } catch (e) { console.error(name, e); return null; }
  }

  const I = (d) => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
  const ICON = {
    agents: I('<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17.5" cy="9" r="2.4"/><path d="M16.5 14.2c2.6.2 4.5 2.3 4.5 5"/>'),
    connectors: I('<path d="M9 3v5M15 3v5M7 8h10v3a5 5 0 0 1-10 0V8zM12 16v5"/>'),
    tools: I('<path d="M14.5 5.5a4.5 4.5 0 0 0-5.6 5.6L3.5 16.5a2 2 0 0 0 2.8 2.8l5.4-5.4a4.5 4.5 0 0 0 5.6-5.6l-3 3-2.5-.5-.5-2.5z"/>'),
    gear: I('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9L7 7M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>'),
    pin: I('<path d="M9 3h6l-1 6 3 3v2H7v-2l3-3-1-6zM12 14v7"/>'),
    min: I('<path d="M5 12h14"/>'),
    close: I('<path d="M6 6l12 12M18 6L6 18"/>'),
    send: I('<path d="M21 3L10 14M21 3l-7 18-4-7-7-4 18-7z"/>'),
    chevron: I('<path d="M15 5l-7 7 7 7"/>'),
  };

  const state = { busy: false, steps: [], liveOpen: false, side: 'left', lastWho: null, lastRow: null, userMsgs: 0,
                  catalog: null, logo: '', typingRow: null, ticks: null, feedCount: 0, reportShown: false };

  // ------------------------------------------------------------------ text helpers
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  const hhmm = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

  /** A small, safe markdown renderer: bold, italic, code, code blocks, quotes, lists, links. Input is escaped first. */
  function md(src) {
    const blocks = [];
    let text = esc(src).replace(/```([\s\S]*?)```/g, (_, c) => { blocks.push(`<pre><code>${c.replace(/^\n/, '')}</code></pre>`); return `\u0000${blocks.length - 1}\u0000`; });
    const inline = (t) => t
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(/(^|[^*])\*([^*\s][^*]*)\*(?!\*)/g, '$1<i>$2</i>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2">$1</a>')
      .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2">$2</a>');
    const out = []; let list = null;
    const flush = () => { if (list) { out.push(`<${list.tag}>${list.items.join('')}</${list.tag}>`); list = null; } };
    for (const line of text.split('\n')) {
      let m;
      if ((m = line.match(/^\s*[-•]\s+(.*)/))) { if (!list || list.tag !== 'ul') { flush(); list = { tag: 'ul', items: [] }; } list.items.push(`<li>${inline(m[1])}</li>`); }
      else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (!list || list.tag !== 'ol') { flush(); list = { tag: 'ol', items: [] }; } list.items.push(`<li>${inline(m[1])}</li>`); }
      else if ((m = line.match(/^&gt;\s?(.*)/))) { flush(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); }
      else if (/^\s*$/.test(line)) { flush(); }
      else { flush(); out.push(`<p>${inline(line)}</p>`); }
    }
    flush();
    return out.join('').replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[+i]);
  }

  // ------------------------------------------------------------------ conversation
  const stream = $('#stream');
  const scroll = () => { stream.scrollTop = stream.scrollHeight; };

  function addRow({ who, html, meta = true, cls = '', wide = false }) {
    const first = state.lastWho !== who;
    if (state.lastRow) state.lastRow.classList.remove('last');
    const row = document.createElement('div');
    row.className = `row ${who} first last ${cls}`.replace(' first', first ? ' first' : '');
    if (who === 'in') row.insertAdjacentHTML('beforeend', `<div class="av">${state.logo ? `<img src="${state.logo}" alt="">` : ''}</div>`);
    const b = document.createElement('div');
    b.className = `bubble${wide ? ' wide' : ''}`;
    b.innerHTML = html + (meta ? `<span class="meta">${hhmm()}${who === 'out' ? ' <span class="ticks">✓</span>' : ''}</span>` : '');
    row.appendChild(b);
    stream.appendChild(row);
    state.lastWho = who; state.lastRow = row;
    scroll();
    return row;
  }
  function addSys(text) { stream.insertAdjacentHTML('beforeend', `<div class="sys">${esc(text)}</div>`); state.lastWho = null; state.lastRow = null; scroll(); }

  function setStatus(text, typing) {
    const el = $('#status');
    el.textContent = text; el.classList.toggle('typing', !!typing);
    $('.avatar .dot').style.background = typing ? '#5B91A3' : '#2F8F6B';
  }
  function typingOn(caption) {
    if (!state.typingRow) {
      state.typingRow = addRow({ who: 'in', html: '<i></i><i></i><i></i>', meta: false, cls: 'typing' });
    }
    setStatus(caption ? `typing… ${caption}` : 'typing…', true);
    scroll();
  }
  function typingOff() {
    if (state.typingRow) { const r = state.typingRow; state.typingRow = null; r.remove(); if (stream.lastElementChild) state.lastRow = stream.lastElementChild.classList.contains('row') ? stream.lastElementChild : null; state.lastWho = state.lastRow ? (state.lastRow.classList.contains('out') ? 'out' : 'in') : null; if (state.lastRow) state.lastRow.classList.add('last'); }
    setStatus('online', false);
  }

  function chunks(report) {
    const parts = String(report || '').split(/\n{2,}/).map((s) => s.trim()).filter(Boolean);
    const merged = [];
    for (const p of parts) {                         // keep a heading line together with the list that follows it
      const prev = merged[merged.length - 1];
      if (prev && (prev.length < 46 || /^\*\*[^*]+\*\*$/.test(prev) || /:\s*$/.test(prev))) merged[merged.length - 1] = `${prev}\n${p}`;
      else merged.push(p);
    }
    while (merged.length > 4) { const last = merged.pop(); merged[merged.length - 1] += `\n\n${last}`; }
    return merged.length ? merged : [''];
  }

  const OUTCOME = {
    fixed: ['ok', 'Done and verified'], done: ['ok', 'Done'], no_action: ['warn', 'Answered, nothing changed'],
    escalated: ['warn', 'Ticket opened for IT'], not_fixed: ['warn', 'Problem remains, ticket opened'],
    rejected: ['bad', 'You declined, nothing changed'], refused: ['bad', 'Blocked by the safety policy'],
    unsupported: ['warn', 'I need a little more detail'], error: ['bad', 'Stopped with an error'],
  };

  async function deliver(e) {
    const parts = chunks(e.report);
    const [kind, label] = OUTCOME[e.outcome] || ['warn', e.outcome || 'Done'];
    const chat = e.outcome === 'chat';
    for (let i = 0; i < parts.length; i++) {
      if (i > 0) { typingOn(); await wait(Math.min(1300, 380 + parts[i].length * 8)); typingOff(); }
      const last = i === parts.length - 1;
      let html = '';
      if (i === 0 && !chat) html += `<span class="pill ${kind}">${esc(label)}</span>`;
      html += md(parts[i]);
      if (last && e.comparison && e.comparison.length) {
        html += `<table class="cmp"><tr><th>Check</th><th>Before</th><th>After</th></tr>${e.comparison.map((r) => `<tr><td>${esc(r.metric)}</td><td>${esc(r.before)}</td><td>${esc(r.after)}</td></tr>`).join('')}</table>`;
      }
      if (last && state.steps.length) html += `<div><button class="steps-toggle" data-steps>${state.steps.length} step${state.steps.length > 1 ? 's' : ''}</button></div>`;
      addRow({ who: 'in', html });
    }
  }

  function addApproval(e) {
    const a = e.approval || {};
    const steps = (a.steps || []).map((s, i) => `<li>${esc(s)}</li>`).join('');
    const risk = ({ 1: 'Low-impact change', 2: 'Medium change, cannot be undone' })[a.risk] || 'Change';
    const row = addRow({ who: 'in', wide: true, cls: 'card-row', html:
      `<div class="card"><span class="risk">${esc(risk)}</span><h4>${esc(a.summary || 'Approval needed')}</h4>` +
      (a.diagnosis ? md(a.diagnosis) : '') +
      `<div class="lbl">What will change</div>${md(a.what_changes || '')}` +
      (steps ? `<div class="lbl">Planned steps</div><ol>${steps}</ol>` : '') +
      `<div class="actions"><button class="btn go" data-act="1">Approve</button><button class="btn no" data-act="0">Reject</button></div></div>` });
    row.querySelector('.bubble').classList.add('card');
    row.dataset.task = e.task_id;
  }

  async function decide(btn) {
    const row = btn.closest('.row');
    const approved = btn.dataset.act === '1';
    const box = row.querySelector('.actions');
    box.outerHTML = `<div class="decided">${approved ? '✓ Approved' : '✕ Rejected'}</div>`;
    state.busy = true; state.steps = state.steps.slice(); setBusy(true);
    typingOn(approved ? 'working on it' : '');
    const r = await call('resume', row.dataset.task, approved);
    if (r && r.ok === false) { typingOff(); setBusy(false); addRow({ who: 'in', html: md('I am still busy with the last step. Try again in a moment.') }); }
  }

  // ------------------------------------------------------------------ live view
  const FEED_ICON = { open_website: '🌐', web_search: '🔎', read_webpage: '🌐', open_folder: '📁', list_folder: '📁', read_text_file: '📄', write_text_file: '✍️',
    run_powershell: '⌨️', install_software: '📦', open_application: '🖱️', open_in_notepad: '📝', start_password_reset: '🔑', diagnose_printing: '🖨️',
    clear_print_queue: '🖨️', mail_send: '✉️', raise_ticket: '🎫' };
  function feedIcon(e) {
    const t = e.text || '';
    if (t.startsWith('Done:')) return '✅';
    if (/failed|blocked/i.test(t)) return '⚠️';
    if (/approval/i.test(t)) return '⏸️';
    return FEED_ICON[e.tool] || '⚙️';
  }
  function addFeed(e) {
    const feed = $('#live-feed');
    feed.insertAdjacentHTML('afterbegin', `<div class="fe"><span class="t">${esc((e.t || '').slice(0, 5) || hhmm())}</span><span>${feedIcon(e)}</span><span class="x"><b>${esc(e.agent || '')}</b> ${esc(e.text || '')}</span></div>`);
    while (feed.children.length > 60) feed.lastElementChild.remove();
    if (e.image) {
      const shot = $('#live-shot');
      shot.classList.remove('empty'); shot.innerHTML = `<img src="${e.image}" alt="Latest screenshot">`;
      if (!state.liveOpen) $('#pull').classList.add('alert');
    }
  }
  function liveBadge(on) { const b = $('#live-badge'); b.className = `badge ${on ? 'live' : 'idle'}`; b.textContent = on ? 'Live' : 'Last run'; }
  async function toggleLive(force) {
    const want = force === undefined ? !state.liveOpen : force;
    if (state.liveBusy || want === state.liveOpen) return;
    state.liveBusy = true;
    const app = $('#app'), LIVE = 340;
    // while the window slides, the layout keeps its final width and is pinned to the edge that does not move,
    // so the panel is revealed (or covered) by the moving window edge instead of squeezing the chat
    app.style.setProperty('--anim-w', (window.innerWidth + (want ? LIVE : 0)) + 'px');
    app.dataset.side = state.side; app.classList.add('anim'); app.dataset.live = 'open';
    $('#pull').classList.remove('alert');
    const r = await call('set_live', want);
    state.liveBusy = false;
    app.classList.remove('anim');
    if (r === null) { app.dataset.live = 'closed'; return; }          // no window bridge (browser preview)
    state.liveOpen = r.open; state.side = r.side || state.side;
    app.dataset.live = r.open ? 'open' : 'closed'; app.dataset.side = state.side;
    $('#pull').title = r.open ? 'Hide live view' : 'Show live view';
    setTimeout(scroll, 60);
  }

  // ------------------------------------------------------------------ events from Python
  window.ib = {
    onEvent(e) {
      if (e.type === 'status') {
        state.steps.push(e);
        if (state.ticks) { state.ticks.textContent = '✓✓'; state.ticks.classList.add('read'); state.ticks = null; }
        if (!state.typingRow) typingOn();
        setStatus(`typing… ${String(e.text || '').slice(0, 30)}`, true);
        addFeed(e); liveBadge(true);
      } else if (e.type === 'approval') {
        typingOff(); liveBadge(false); setBusy(false); addApproval(e);
      } else if (e.type === 'done') {
        typingOff(); liveBadge(false);
        deliver(e).then(() => { setBusy(false); state.steps = []; });
      } else if (e.type === 'error') {
        typingOff(); liveBadge(false); setBusy(false);
        addRow({ who: 'in', html: `<span class="pill bad">Something went wrong</span>${md(e.message || '')}` });
      }
    },
  };

  // ------------------------------------------------------------------ composer
  const input = $('#input'), sendBtn = $('#send');
  function setBusy(b) { state.busy = b; sendBtn.disabled = b || !input.value.trim(); input.placeholder = b ? 'Tobi is working…' : 'Message Tobi'; }
  function autosize() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 110) + 'px'; sendBtn.disabled = state.busy || !input.value.trim(); }
  async function submit(text) {
    text = (text || input.value).trim();
    if (!text || state.busy) return;
    input.value = ''; autosize();
    $('#suggest').innerHTML = '';
    state.userMsgs++;
    const row = addRow({ who: 'out', html: md(text) });
    state.ticks = row.querySelector('.ticks');
    state.steps = []; setBusy(true); typingOn();
    const r = await call('send', text);
    if (r && r.ok === false) { typingOff(); setBusy(false); addRow({ who: 'in', html: md('I am still working on your last request. One moment.') }); }
    else if (r === null) { typingOff(); setBusy(false); addRow({ who: 'in', html: md('I cannot reach my engine from this preview.') }); }
  }
  input.addEventListener('input', autosize);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } });
  sendBtn.addEventListener('click', () => submit());

  // ------------------------------------------------------------------ sheets
  const SHEETS = { agents: '#sheet-agents', connectors: '#sheet-connectors', tools: '#sheet-tools' };
  const pill = (s) => `<span class="st ${s === 'ready' ? 'ready' : s === 'needs setup' ? 'setup' : 'off'}">${s === 'ready' ? 'Ready' : s === 'needs setup' ? 'Needs setup' : 'Off'}</span>`;
  function sheetHead(title, count) { return `<div class="sheet-head"><div><h3>${title}</h3><div class="count">${count}</div></div><button class="icon" data-close title="Close">${ICON.close}</button></div>`; }
  function buildSheets(c) {
    const groups = ['Special agents', 'Specialists'];
    $('#sheet-agents').innerHTML = sheetHead('Agents', `${c.agents.length} ready to help`) + `<div class="sheet-body">` + groups.map((g) =>
      `<div class="group-title">${g}</div>` + c.agents.filter((a) => a.group === g).map((a) =>
        `<div class="item"><div class="top"><div class="ic">${esc(a.icon)}</div><div class="nm">${esc(a.name)}</div>${pill(a.status)}</div>
         <div class="ds">${esc(a.purpose)}</div><div class="try">${a.examples.map((x) => `<button class="chip" data-try="${esc(x)}">${esc(x)}</button>`).join('')}</div></div>`).join('')).join('') + `</div>`;
    $('#sheet-connectors').innerHTML = sheetHead('Connectors', `${c.connectors.filter((x) => x.status === 'ready').length} of ${c.connectors.length} ready`) + `<div class="sheet-body">` + c.connectors.map((k) =>
      `<div class="item"><div class="top"><div class="ic">🔌</div><div class="nm">${esc(k.name)}</div>${pill(k.status)}</div><div class="ds">${esc(k.description)}</div>` +
      (k.status === 'needs setup' ? `<div class="warn-note">Missing in .env: ${esc(k.missing.join(', '))}. ${esc(k.setup)}</div>` : '') + `</div>`).join('') + `</div>`;
    $('#sheet-tools').innerHTML = sheetHead('Tools', `${c.tools.length} tools`) + `<input class="search" id="tool-search" placeholder="Search tools" autocomplete="off"><div class="sheet-body" id="tool-list"></div>`;
    renderTools('');
    $('#tool-search').addEventListener('input', (ev) => renderTools(ev.target.value));
  }
  function renderTools(q) {
    q = q.toLowerCase();
    $('#tool-list').innerHTML = state.catalog.tools.filter((t) => !q || `${t.name} ${t.description} ${t.connector}`.toLowerCase().includes(q)).slice(0, 80).map((t) =>
      `<div class="item"><div class="top"><div class="nm">${esc(t.name)}</div><span class="tier r${t.risk}" style="margin-left:auto">R${t.risk}</span></div><div class="ds">${esc(t.description)}</div></div>`).join('') || '<div class="ds" style="padding:10px">No tool matches.</div>';
  }
  async function openSheet(name) {
    $('#menu').hidden = true;
    if (!state.catalog) { state.catalog = await call('catalog'); if (!state.catalog) return; buildSheets(state.catalog); }
    const sheet = $(SHEETS[name]); const was = sheet.classList.contains('open');
    $$('.sheet').forEach((s) => s.classList.remove('open')); $$('[data-sheet]').forEach((b) => b.classList.remove('on'));
    if (!was) { sheet.classList.add('open'); $(`[data-sheet="${name}"]`).classList.add('on'); }
  }
  const closeSheets = () => { $$('.sheet').forEach((s) => s.classList.remove('open')); $$('[data-sheet]').forEach((b) => b.classList.remove('on')); };

  // ------------------------------------------------------------------ wiring
  document.addEventListener('click', async (e) => {
    const t = e.target.closest('button, a, [data-sheet], [data-close], [data-try], [data-act]') || e.target;
    if (t.tagName === 'A' && t.getAttribute('href')) { e.preventDefault(); call('open_url', t.getAttribute('href')); return; }
    if (t.dataset && t.dataset.sheet) return openSheet(t.dataset.sheet);
    if (t.hasAttribute && t.hasAttribute('data-close')) return closeSheets();
    if (t.dataset && t.dataset.try) { closeSheets(); input.value = t.dataset.try; autosize(); return submit(); }
    if (t.dataset && t.dataset.act !== undefined) return decide(t);
    if (t.hasAttribute && t.hasAttribute('data-steps')) {
      const b = t.closest('.bubble'); let box = b.querySelector('.steps');
      if (box) { box.remove(); return; }
      b.insertAdjacentHTML('beforeend', `<div class="steps">${state.lastSteps.map((s) => `<div><b>${esc(s.agent || '')}</b> ${esc(s.text || '')}</div>`).join('')}</div>`); scroll(); return;
    }
    if (!e.target.closest('#menu') && !e.target.closest('#btn-menu')) $('#menu').hidden = true;
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeSheets(); $('#menu').hidden = true; } });

  /** Fonts are an enhancement: load them after the page is visible, so a slow network can never leave the window blank. */
  function loadFonts() {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Figtree:wght@400;500;600;700&display=swap';
    document.head.appendChild(link);
  }

  async function init() {
    if (state.initDone) return; state.initDone = true;
    setTimeout(loadFonts, 400);
    for (const [id, name] of [['btn-menu', 'gear'], ['btn-pin', 'pin'], ['btn-min', 'min'], ['btn-close', 'close'], ['send', 'send'], ['pull', 'chevron']]) $(`#${id}`).innerHTML = ICON[name];
    $$('[data-sheet]').forEach((b) => { b.innerHTML = ICON[b.dataset.sheet]; });
    // everything in the header that is not a button drags the window (pywebview drag region)
    $$('.head, .head *').forEach((el) => { if (!el.closest('button')) el.classList.add('pywebview-drag-region'); });

    $('#btn-close').onclick = () => call('close');
    $('#btn-min').onclick = () => call('minimize');
    $('#btn-pin').onclick = async (e) => { const on = !e.currentTarget.classList.contains('on'); e.currentTarget.classList.toggle('on', on); call('pin', on); };
    $('#btn-menu').onclick = () => { closeSheets(); $('#menu').hidden = !$('#menu').hidden; };
    $('#pull').onclick = () => toggleLive();
    $('#opt-autopilot').onchange = (e) => call('set_options', e.target.checked, null, null);
    $('#opt-live').onchange = (e) => call('set_options', null, e.target.checked, null);
    $('#opt-readonly').onchange = (e) => call('set_options', null, null, e.target.checked);
    $('#opt-quit').onclick = () => call('quit');
    $('#opt-console').onclick = () => { $('#menu').hidden = true; call('open_console'); };
    $('#opt-new').onclick = () => { $('#menu').hidden = true; call('new_chat'); stream.innerHTML = ''; state.lastWho = state.lastRow = null; greet(); };

    const info = (await call('info')) || { name: 'Tobi', model: '', logo: '' };
    state.logo = info.logo || ''; if (info.side) state.side = info.side;
    if (state.logo) { $('#logo').src = state.logo; }
    $('#opt-autopilot').checked = !!info.autopilot; $('#opt-readonly').checked = !!info.readOnly;
    $('#status').title = info.model || '';
    greet();
  }

  const SUGGEST = ['My computer is slow', 'My printer is not printing', 'Open YouTube in Chrome', 'Install 7-Zip', 'How do I connect to the VPN?', 'I forgot my password'];
  function greet() {
    const h = new Date().getHours();
    addSys('Today');
    addRow({ who: 'in', html: md(`${h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'}! I'm **Tobi**. Tell me what is not working. I check your computer, ask before I change anything, and show you what I did.`) });
    $('#suggest').innerHTML = SUGGEST.map((s) => `<button class="chip" data-try="${esc(s)}">${esc(s)}</button>`).join('');
  }
  // remember the steps of the last run for the "N steps" chip
  const origOnEvent = window.ib.onEvent;
  window.ib.onEvent = (e) => { if (e.type === 'done') state.lastSteps = state.steps.slice(); origOnEvent(e); };
  state.lastSteps = [];

  if (window.pywebview) init(); else window.addEventListener('pywebviewready', init);
  setTimeout(() => { if (!state.initDone) init(); }, 1500);       // plain browser preview: no bridge, still render
})();
