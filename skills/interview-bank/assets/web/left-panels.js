'use strict';
// Only the existing .sidebar and .library are decorated/reorganized.
// Reading uses the original app.js renderer, toolbar, collapse logic and CSS.
(function organizeLeftPanels() {
  const byId = id => document.getElementById(id);
  const library = document.querySelector('.library');
  const side = byId('sidebar');
  const labels = {
    'zh-CN': { directory: '来源与目录', notes: '资料筛选', bank: '题目筛选',
      conditions: '{n} 个条件', all: '全部条件', materials: '全部资料' },
    en: { directory: 'Sources & contents', notes: 'Material filters', bank: 'Question filters',
      conditions: '{n} filters', all: 'All filters', materials: 'All materials' }
  };
  const label = (key, n) => (labels[lang] || labels['zh-CN'])[key].replace('{n}', n);
  const paths = {
    all: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
    due: '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
    weak: '<path d="m12 3 9 9-9 9-9-9z"/>',
    unseen: '<circle cx="12" cy="12" r="7"/>',
    list: '<path d="M8 6h12M8 12h12M8 18h12M4 6h.1M4 12h.1M4 18h.1"/>',
    filters: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2.5"/><circle cx="15" cy="17" r="2.5"/>',
    collapse: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m7-12-3 4 3 4"/>',
    book: '<path d="M4 4h7l1 2 1-2h7v15h-7l-1 2-1-2H4zM12 6v15"/>'
  };
  function svg(name) {
    const wrapper = document.createElement('span');
    wrapper.innerHTML = '<svg class="lb-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + (paths[name] || paths.list) + '</svg>';
    return wrapper.firstChild;
  }
  function text(tag, cls, value) {
    const node = document.createElement(tag);
    node.className = cls;
    if (value !== undefined) node.textContent = value;
    return node;
  }
  function panel(id, title, glyph, node) {
    const details = text('details', 'lb-panel');
    details.id = id;
    const summary = document.createElement('summary');
    const heading = text('span', '', label(title));
    summary.append(svg(glyph), heading);
    const value = text('span', 'lb-summary-value');
    summary.append(value);
    details.append(summary, node);
    return { details, value, heading, title };
  }
  const head = text('div', 'lb-list-head');
  head.append(byId('result-count'));
  const collapse = text('button', 'lb-collapse-list');
  collapse.type = 'button';
  collapse.setAttribute('aria-label', t('hide_list'));
  collapse.title = t('hide_list');
  collapse.append(svg('collapse'));
  collapse.addEventListener('click', () => byId('toggle-list').click());
  head.append(collapse);
  const search = byId('search').closest('label');
  library.insertBefore(head, search);
  const panels = text('div', 'lb-panels');
  library.insertBefore(panels, search.nextSibling);
  const navigation = byId('notes-navigation');
  // Public accounts use a global topic/date catalogue; advanced study filters remain collapsible.
  navigation.append(byId('notes-experience-filters'));
  const noteFilters = byId('notes-filters');
  const scopeLabel = byId('notes-search-scope').closest('label');
  const scope = text('div', 'lb-scope');
  scope.append(scopeLabel);
  panels.after(scope);
  const directory = panel('lb-directory', 'directory', 'book', navigation);
  const notesFilter = panel('lb-notes-filter', 'notes', 'filters', noteFilters);
  const bankFilter = panel('lb-bank-filter', 'bank', 'filters', byId('inline-filters'));
  panels.append(directory.details, notesFilter.details, bankFilter.details);
  bankFilter.details.addEventListener('toggle', () => {
    if (roomy.matches) byId('inline-filters').hidden = !bankFilter.details.open;
  });
  byId('open-filters').addEventListener('click', () => {
    if (roomy.matches) bankFilter.details.open = !byId('inline-filters').hidden;
  });
  // Existing controls keep their original listeners and data model.
  byId('hide-side').replaceChildren(svg('collapse'));
  function decorateViews() {
    for (const control of document.querySelectorAll('.modes [data-mode]')) {
      if (!control.querySelector('.lb-icon')) control.prepend(svg(control.dataset.mode === 'bank' ? 'all' :
        control.dataset.section === 'experiences' ? 'due' : control.dataset.section === 'learning' ? 'list' : 'book'));
    }
    for (const control of side.querySelectorAll('[data-view]')) {
      const first = control.querySelector('span');
      if (first && !first.querySelector('.lb-icon')) first.prepend(svg(control.dataset.view));
    }
  }
  function groupSourceNavigation() {
    const root = byId('side-notes');
    if (!root || root.querySelector(':scope > .lb-tree')) return;
    const headings = [...root.children].filter(n => n.classList.contains('side-title'));
    for (const heading of headings) {
      const details = text('details', 'lb-tree');
      const title = heading.textContent;
      details.open = ![t('notes_other_sources'), t('notes_sources')].includes(title);
      const summary = document.createElement('summary');
      summary.textContent = title;
      const body = text('div', 'lb-tree-body');
      heading.before(details);
      details.append(summary, body);
      let node = heading.nextSibling;
      while (node && !(node.nodeType === 1 && node.classList.contains('side-title'))) {
        const next = node.nextSibling;
        body.append(node);
        node = next;
      }
      heading.remove();
    }
  }
  function setLabel(node, value) {
    if (node.textContent !== value) node.textContent = value;
  }
  function sync() {
    for (const item of [directory, notesFilter, bankFilter]) setLabel(item.heading,
      item === directory && state.notes.section === 'experiences' ? t('notes_public_group') : label(item.title));
    collapse.setAttribute('aria-label', t('hide_list'));
    collapse.title = t('hide_list');
    // placeFilters() moves the original controls between the dialog and the list on resize.
    if (roomy.matches) byId('inline-filters').hidden = !bankFilter.details.open;
    const isNotes = document.body.classList.contains('notes-mode');
    const isHome = document.body.classList.contains('notes-home');
    directory.details.hidden = !isNotes || isHome || navigation.hidden;
    notesFilter.details.hidden = !isNotes || isHome || noteFilters.hidden;
    scope.hidden = !isNotes || isHome || ['experiences', 'learning'].includes(state.notes.section);
    bankFilter.details.hidden = isNotes || !roomy.matches;
    const activeBank = filters.filter(name => byId(name).value).length
      + (byId('view').value !== 'all') + (byId('sort').value !== 'frequency');
    setLabel(bankFilter.value, activeBank ? label('conditions', activeBank) : label('all'));
    const directoryText = byId('notes-source-name').textContent;
    const topic = byId('notes-topic');
    const selected = topic.selectedOptions[0]?.textContent || '';
    setLabel(directory.value, isNotes ? (topic.value ? selected : directoryText) : '');
    const activeNotes = ['notes-tag', 'notes-verification', 'notes-experience-company', 'notes-experience-year', 'notes-experience-domain',
      'notes-question-type', 'notes-connection'].filter(id => byId(id).value).length
      + (byId('notes-kind').value && byId('notes-kind').value !== 'study' ? 1 : 0)
      + (byId('notes-learning').value !== 'all' ? 1 : 0);
    setLabel(notesFilter.value, activeNotes ? label('conditions', activeNotes) : label('materials'));
    collapse.disabled = byId('reader').hidden;
    offerContinue();
    decorateViews();
    if (isNotes) groupSourceNavigation();
  }
  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; sync(); });
  }
  const observer = new MutationObserver(schedule);
  for (const target of [byId('side-notes'), byId('views'), byId('result-count'), byId('notes-source-name'), byId('notes-topic')]) {
    observer.observe(target, { childList: true, subtree: true });
  }
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  observer.observe(navigation, { attributes: true, attributeFilter: ['hidden'] });
  observer.observe(noteFilters, { attributes: true, attributeFilter: ['hidden'] });
  observer.observe(byId('reader'), { attributes: true, attributeFilter: ['hidden'] });
  observer.observe(byId('question-list'), { attributes: true, subtree: true, attributeFilter: ['class'] });
  library.addEventListener('change', schedule);
  roomy.addEventListener('change', schedule);
  sync();
}());
