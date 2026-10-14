'use strict';
// Browser-local shelf preferences. Source files, note IDs and learning records are never reordered.
const sourceShelf = (() => {
  function normalize(value, names) {
    const known = new Set(names);
    const clean = items => [...new Set((Array.isArray(items) ? items : []).filter(id => known.has(id)))];
    const saved = value && value.version === 1 ? value : {};
    const order = clean(saved.order);
    return { version: 1, order: [...order, ...names.filter(id => !order.includes(id))], expanded: clean(saved.expanded) };
  }
  function move(names, id, position) {
    if (!names.includes(id) || !Number.isInteger(position)) return [...names];
    const result = names.filter(name => name !== id);
    result.splice(Math.max(0, Math.min(position, result.length)), 0, id);
    return result;
  }

  const memory = new Map();
  let originals = [], prefs, key, drag, menu, ignoreClickUntil = 0, installed = false;
  const root = () => $('source-cards');
  const cards = () => [...root().querySelectorAll(':scope > .source-card')];
  const names = () => cards().map(card => card.dataset.source);
  function announce(value) { $('source-shelf-status').textContent = value; }
  function persist() {
    memory.set(key, prefs);
    try { localStorage.setItem(key, JSON.stringify(prefs)); }
    catch (_) { announce(t('shelf_session_only')); }
    syncTools();
  }
  function syncTools() {
    if (!prefs) return;
    $('shelf-expand-all').disabled = prefs.expanded.length === originals.length;
    $('shelf-collapse-all').disabled = !prefs.expanded.length;
    $('shelf-reset-order').disabled = prefs.order.every((name, i) => name === originals[i]);
  }
  function closeMenu(focus = false) {
    if (!menu) return;
    const previous = menu;
    menu = null;
    previous.node.remove();
    previous.handle.setAttribute('aria-expanded', 'false');
    if (focus) previous.handle.focus({ preventScroll: true });
  }
  function applyOrder(order, handle) {
    const byName = new Map(cards().map(card => [card.dataset.source, card]));
    for (const id of order) root().append(byName.get(id));
    prefs.order = [...order];
    persist();
    handle?.focus({ preventScroll: true });
    const source = handle?.closest('.source-card');
    if (source) announce(t('shelf_moved', { title: source.dataset.title, n: order.indexOf(source.dataset.source) + 1, total: order.length }));
  }
  function showMenu(handle) {
    if (menu?.handle === handle) { closeMenu(true); return; }
    closeMenu();
    const card = handle.closest('.source-card');
    const id = card.dataset.source, order = names(), index = order.indexOf(id);
    const node = el('div', 'source-move-menu');
    node.id = 'shelf-menu-' + id;
    node.setAttribute('role', 'menu');
    node.setAttribute('aria-label', t('shelf_move', { title: card.dataset.title }));
    for (const [label, position] of [['shelf_first', 0], ['shelf_previous', index - 1], ['shelf_next', index + 1], ['shelf_last', order.length - 1]]) {
      const action = button(t(label), '', () => {
        closeMenu();
        applyOrder(move(names(), id, position), handle);
      });
      action.setAttribute('role', 'menuitem');
      action.disabled = position < 0 || position >= order.length || position === index;
      node.append(action);
    }
    card.append(node);
    handle.setAttribute('aria-expanded', 'true');
    menu = { node, handle };
    node.querySelector('button:not(:disabled)')?.focus({ preventScroll: true });
    node.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); closeMenu(true); }
      else if (event.key === 'Tab') closeMenu(true);
      else if (['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
        const items = [...node.querySelectorAll('button:not(:disabled)')];
        const current = items.indexOf(document.activeElement);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 :
          (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items[next]?.focus();
      }
    });
  }
  function setExpanded(card, on, save = true) {
    card.classList.toggle('is-open', on);
    card.querySelector('.source-card-toggle').setAttribute('aria-expanded', String(on));
    card.querySelector('.source-card-body').hidden = !on;
    const expanded = new Set(prefs.expanded);
    if (on) expanded.add(card.dataset.source); else expanded.delete(card.dataset.source);
    prefs.expanded = [...expanded];
    if (save) persist();
  }
  function prepare(sources) {
    finish(false);
    closeMenu();
    originals = sources.map(source => source.name);
    key = 'ibank-source-shelf:' + (state.data?.account || state.data?.name || 'local');
    prefs = normalize(memory.get(key) || stored(key, {}), originals);
    syncTools();
    const byName = new Map(sources.map(source => [source.name, source]));
    return prefs.order.map(name => byName.get(name));
  }
  function decorate(card, source, content, done) {
    card.dataset.source = source.name;
    card.dataset.title = source.title;
    const head = el('div', 'source-card-header');
    const heading = el('h2', 'source-card-heading');
    const toggle = button('', 'source-card-toggle', () => setExpanded(card, !card.classList.contains('is-open')));
    toggle.id = 'shelf-toggle-' + source.name;
    toggle.setAttribute('aria-controls', 'shelf-panel-' + source.name);
    const monogram = el('span', 'source-monogram', source.title.includes('Java') ? 'J' : source.title.includes('RAG') ? 'R' :
      source.title.includes('LLM') ? 'L' : source.title.includes('前端') ? 'F' : 'A');
    monogram.setAttribute('aria-hidden', 'true');
    const copy = el('span', 'source-card-copy');
    copy.append(el('span', 'source-card-title', source.title), el('span', 'source-card-caption',
      t('shelf_count', { n: source.content_total }) + (source.metadata.language ? ' · ' + languageLabel(source.metadata.language) : '')));
    const chevron = el('span', 'source-card-chevron', '⌄');
    chevron.setAttribute('aria-hidden', 'true');
    toggle.append(monogram, copy, chevron);
    heading.append(toggle);
    const handle = button('', 'source-drag-handle', () => showMenu(handle));
    handle.setAttribute('aria-label', t('shelf_move', { title: source.title }));
    handle.title = t('shelf_handle_hint');
    handle.setAttribute('aria-haspopup', 'menu');
    handle.setAttribute('aria-expanded', 'false');
    handle.setAttribute('aria-controls', 'shelf-menu-' + source.name);
    handle.setAttribute('aria-describedby', 'source-shelf-hint');
    const dots = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    dots.setAttribute('viewBox', '0 0 16 20');
    dots.setAttribute('aria-hidden', 'true');
    for (const x of [5, 11]) for (const y of [4, 10, 16]) {
      const dot = document.createElementNS(dots.namespaceURI, 'circle');
      dot.setAttribute('cx', x); dot.setAttribute('cy', y); dot.setAttribute('r', '1.4');
      dots.append(dot);
    }
    handle.append(dots);
    head.append(heading, handle);
    const progress = el('div', 'source-card-progress');
    progress.append(el('small', '', t('notes_progress', { r: done, n: source.content_total })));
    const track = el('div', 'source-progress-track');
    const fill = el('span');
    fill.style.transform = 'scaleX(' + (source.content_total ? done / source.content_total : 0) + ')';
    track.append(fill);
    progress.append(track);
    const panel = el('div', 'source-card-body');
    panel.id = 'shelf-panel-' + source.name;
    panel.setAttribute('aria-labelledby', toggle.id);
    panel.append(...content);
    card.append(head, progress, panel);
    setExpanded(card, prefs.expanded.includes(source.name), false);
  }

  function clearTarget() {
    root().querySelectorAll('[data-drop]').forEach(card => delete card.dataset.drop);
  }
  function targetAt(x, y) {
    const bounds = root().getBoundingClientRect();
    if (x < bounds.left - 12 || x > bounds.right + 12 || y < bounds.top - 20 || y > bounds.bottom + 20) return null;
    const candidates = cards().filter(card => card !== drag.card);
    let target, best = Infinity;
    for (const card of candidates) {
      const r = card.getBoundingClientRect();
      const dx = Math.max(r.left - x, 0, x - r.right), dy = Math.max(r.top - y, 0, y - r.bottom);
      const distance = dx * dx + dy * dy;
      if (distance < best) { target = card; best = distance; }
    }
    if (!target) return null;
    const r = target.getBoundingClientRect();
    const before = drag.single ? y < r.top + r.height / 2 : x < r.left + r.width / 2;
    return { card: target, before };
  }
  function updateTarget() {
    clearTarget();
    drag.target = targetAt(drag.x, drag.y);
    if (drag.target) drag.target.card.dataset.drop = drag.target.before ? 'before' : 'after';
    const box = drag.preview.getBoundingClientRect();
    const pane = root().closest('.library').getBoundingClientRect();
    const x = Math.max(pane.left + 8, Math.min(innerWidth - box.width - 8, drag.x - drag.offsetX));
    const y = Math.max(8, Math.min(innerHeight - box.height - 8, drag.y - drag.offsetY));
    drag.preview.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
  }
  function scrollFrame() {
    if (!drag?.active) return;
    const library = root().closest('.library');
    const scroller = wide.matches ? library : document.scrollingElement;
    const r = wide.matches ? library.getBoundingClientRect() : { top: 0, bottom: innerHeight, left: 0, right: innerWidth };
    const speed = drag.x < r.left || drag.x > r.right ? 0 : drag.y < r.top + 56 ? -Math.min(16, (r.top + 56 - drag.y) / 3) :
      drag.y > r.bottom - 56 ? Math.min(16, (drag.y - r.bottom + 56) / 3) : 0;
    if (speed) { scroller.scrollTop += speed; updateTarget(); }
    drag.frame = requestAnimationFrame(scrollFrame);
  }
  function start(event) {
    const handle = event.target.closest('.source-drag-handle');
    if (!handle || event.button !== 0 || !event.isPrimary || cards().length < 2) return;
    const card = handle.closest('.source-card'), r = card.getBoundingClientRect();
    drag = { handle, card, pointerId: event.pointerId, x: event.clientX, y: event.clientY,
      startX: event.clientX, startY: event.clientY, offsetX: event.clientX - r.left, offsetY: event.clientY - r.top };
  }
  function pointerMove(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag.x = event.clientX; drag.y = event.clientY;
    if (!drag.active) {
      if (Math.hypot(drag.x - drag.startX, drag.y - drag.startY) < 6) return;
      closeMenu();
      drag.active = true;
      root().setPointerCapture(drag.pointerId);
      const all = cards().map(card => card.getBoundingClientRect());
      drag.single = all.length < 2 || Math.abs(all[0].left - all[1].left) < 2;
      root().dataset.shelfLayout = drag.single ? 'single' : 'grid';
      root().classList.add('is-reordering');
      drag.card.classList.add('is-dragging');
      const preview = drag.card.cloneNode(true);
      preview.classList.remove('is-dragging', 'is-open');
      preview.classList.add('source-drag-preview');
      preview.setAttribute('aria-hidden', 'true');
      preview.inert = true;
      for (const node of [preview, ...preview.querySelectorAll('[id], [aria-controls], [aria-labelledby]')]) {
        node.removeAttribute('id'); node.removeAttribute('aria-controls'); node.removeAttribute('aria-labelledby');
      }
      preview.querySelector('.source-card-body').hidden = true;
      preview.style.width = drag.card.getBoundingClientRect().width + 'px';
      root().closest('.library').append(preview);
      drag.preview = preview;
      drag.frame = requestAnimationFrame(scrollFrame);
    }
    event.preventDefault();
    updateTarget();
  }
  function finish(commit) {
    if (!drag) return;
    const previous = drag;
    drag = null;
    if (!previous.active) return;
    cancelAnimationFrame(previous.frame);
    previous.preview.remove();
    previous.card.classList.remove('is-dragging');
    clearTarget();
    root().classList.remove('is-reordering');
    if (root().hasPointerCapture(previous.pointerId)) root().releasePointerCapture(previous.pointerId);
    ignoreClickUntil = performance.now() + 250;
    if (commit && previous.target) {
      const order = names(), id = previous.card.dataset.source;
      const remaining = order.filter(name => name !== id);
      const position = remaining.indexOf(previous.target.card.dataset.source) + (previous.target.before ? 0 : 1);
      applyOrder(move(order, id, position), previous.handle);
    } else {
      previous.handle.focus({ preventScroll: true });
      announce(t('shelf_cancelled'));
    }
  }
  function install() {
    if (installed) return;
    installed = true;
    root().addEventListener('pointerdown', start);
    window.addEventListener('pointermove', pointerMove, { passive: false });
    window.addEventListener('pointerup', event => {
      if (!drag || event.pointerId !== drag.pointerId) return;
      if (drag.active) { drag.x = event.clientX; drag.y = event.clientY; updateTarget(); }
      finish(true);
    });
    window.addEventListener('pointercancel', event => { if (drag && event.pointerId === drag.pointerId) finish(false); });
    root().addEventListener('lostpointercapture', () => finish(false));
    window.addEventListener('blur', () => finish(false));
    window.addEventListener('resize', () => finish(false));
    document.addEventListener('visibilitychange', () => { if (document.hidden) finish(false); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && drag?.active) { event.preventDefault(); finish(false); } });
    document.addEventListener('pointerdown', event => { if (menu && !menu.node.contains(event.target) && !menu.handle.contains(event.target)) closeMenu(); });
    root().addEventListener('click', event => {
      if (performance.now() < ignoreClickUntil) { event.preventDefault(); event.stopPropagation(); }
    }, true);
    root().addEventListener('click', event => {
      if (event.target.closest('button, a, input, .source-card-body, .source-move-menu')) return;
      const card = event.target.closest('.source-card');
      card?.querySelector('.source-card-toggle').click();
    });
    for (const [id, on] of [['shelf-expand-all', true], ['shelf-collapse-all', false]]) {
      $(id).addEventListener('click', () => { closeMenu(); cards().forEach(card => setExpanded(card, on, false)); persist(); });
    }
    $('shelf-reset-order').addEventListener('click', () => { finish(false); closeMenu(); applyOrder(originals); announce(t('shelf_reset_done')); });
    window.addEventListener('storage', event => {
      if (event.key !== key) return;
      memory.delete(key);
      if (state.mode === 'notes' && state.notes.home && state.notesData) renderSourceCards(state.notesData);
    });
  }
  return { prepare, decorate, install, model: { normalize, move } };
})();
