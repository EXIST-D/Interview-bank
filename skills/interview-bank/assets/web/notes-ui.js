'use strict';
// Source shelves and navigation use separate metadata; published content and links stay intact.

function notesLearningKey() {
  return 'ibank-notes-learning:' + (state.data?.account || state.data?.name || 'local');
}

function notesLearning() {
  return stored(notesLearningKey(), {});
}

function noteLearningState(id) {
  const value = notesLearning()[id]?.state;
  return ['read', 'review', 'mastered'].includes(value) ? value : read.has(id) ? 'read' : 'unread';
}

function recordNoteVisit(id) {
  const values = notesLearning();
  if (!values[id]) values[id] = { state: 'read', at: new Date().toISOString() };
  store(notesLearningKey(), values);
}

function noteLearningControls(note) {
  const box = el('section', 'note-learning-controls');
  const status = el('span', 'note-learning-status', t('notes_learning_' + noteLearningState(note.id)));
  const choices = el('div', 'note-learning-actions');
  const change = value => {
    const values = notesLearning();
    if (value) values[note.id] = { state: value, at: new Date().toISOString() };
    else delete values[note.id];
    store(notesLearningKey(), values);
    status.textContent = t('notes_learning_' + noteLearningState(note.id));
    for (const control of choices.querySelectorAll('[data-learning]')) {
      control.setAttribute('aria-pressed', String(control.dataset.learning === noteLearningState(note.id)));
    }
    toast(t('notes_learning_saved'));
    if (state.notes.learning !== 'all') loadNotes(true);
  };
  for (const value of ['review', 'mastered']) {
    const control = button(t('notes_set_' + value), 'chip-button', () => change(value));
    control.dataset.learning = value;
    control.setAttribute('aria-pressed', String(noteLearningState(note.id) === value));
    choices.append(control);
  }
  choices.append(button(t('notes_reset_learning'), 'link', () => change('')));
  box.append(el('span', 'hint', t('notes_learning') + ' · '), status, choices, el('small', 'hint', t('notes_local_hint')));
  return box;
}

function renderStudyRelations(reading, note) {
  if (note.study_links_incomplete) reading.append(el('p', 'notice', t('notes_relation_incomplete')));
  for (const [key, label, section] of [['study_notes', 'notes_study_related', 'knowledge'],
    ['public_experiences', 'notes_public_related', 'experiences']]) {
    const edges = note[key] || [];
    if (!edges.length) continue;
    const box = el('details', 'source-evidence linked');
    box.append(el('summary', '', t(label, { n: edges.length })), el('p', 'hint', t('notes_relation_hint')));
    const list = el('ul', 'linked-list');
    for (const edge of edges) {
      const row = el('li');
      row.append(el('p', '', edge.question_quote));
      const entry = button('', 'linked-item', () => jump('notes', edge.id, section));
      entry.append(el('span', 'linked-title', edge.title), el('span', 'question-meta',
        [edge.company, edge.interview_time, edge.area_title, edge.topic_title, t('relation_' + edge.relation)].filter(Boolean).join(' · ')));
      const evidence = el('details', 'source-evidence');
      evidence.append(el('summary', '', t('notes_relation_evidence')), el('p', 'hint', edge.reason),
        el('blockquote', '', edge.answer_quote));
      row.append(entry, evidence);
      list.append(row);
    }
    box.append(list);
    reading.append(box);
  }
}

function notesParams(offset = 0) {
  const f = state.notes;
  const words = $('search').value.trim();
  const query = new URLSearchParams({ offset, limit: f.home ? 1 : NOTES_PAGE, sort: f.sort, view: f.view, section: f.section || 'knowledge' });
  const globalSearch = words && f.scope === 'all';
  if (f.collection && !globalSearch) query.set('collection', f.collection);
  if (!words || f.scope === 'topic') {
    if (f.view === 'original' && f.chapter !== '') query.set('chapter', f.chapter);
    if (f.view === 'knowledge') {
      if (f.area) query.set('area', f.area);
      if (f.topic) query.set('topic', f.topic);
    }
  }
  if (words) query.set('query', words);
  for (const key of ['tag', 'kind', 'verification', 'connection']) if (f[key]) query.set(key, f[key]);
  if (f.section !== 'experiences' && f.question_type) query.set('question_type', f.question_type);
  if (f.section === 'experiences') {
    for (const key of ['company', 'year', 'experience_domain']) if (f[key]) query.set(key, f[key]);
    if (f.experience_group === 'domain' && f.sort === 'recent') query.set('sort', 'domain');
  }
  if (f.marked) query.set('marked', '1');
  if (f.asked) query.set('asked', '1');
  return query;
}

async function loadNotes(reset = false) {
  const generation = ++state.load;
  if (reset || state.notes.learning !== 'all') { state.offset = 0; state.questions = []; }
  $('question-list').setAttribute('aria-busy', 'true');
  message('error', '');
  try {
    const data = await api('/api/notes?' + notesParams(state.offset));
    if (generation !== state.load) return;
    const f = state.notes;
    if (f.collection && !data.collections.some(c => c.name === f.collection)) {
      return pickNotes({ home: true, collection: '', chapter: '', area: '', topic: '' });
    }
    const current = data.collections.find(c => c.name === f.collection);
    const recovered = {};
    // A source update can retire remembered directory/filter values; do not strand the reader in an empty list.
    if (current && (!$('search').value.trim() || f.scope === 'topic')) {
      if (f.area && !current.areas.some(a => a.id === f.area)) Object.assign(recovered, { area: '', topic: '' });
      else if (f.topic && !current.areas.some(a => a.topics.some(topic => topic.id === f.topic))) recovered.topic = '';
      if (f.chapter !== '' && !current.chapters.some(c => String(c.index) === String(f.chapter))) recovered.chapter = '';
    }
    if (f.tag && !data.facets.tags.includes(f.tag)) recovered.tag = '';
    if (f.question_type && !(f.question_type in data.facets.question_types)) recovered.question_type = '';
    if (f.kind && !['study', 'info'].includes(f.kind) && !(f.kind in data.facets.kinds)) recovered.kind = 'study';
    if (f.section === 'experiences') {
      if (f.experience_domain && !(f.experience_domain in data.facets.experience_domains)) recovered.experience_domain = '';
      if (f.company && !(f.company === 'unknown' ? data.facets.unknown_company : data.facets.companies.includes(f.company))) recovered.company = '';
      if (f.year && !(f.year === 'unknown' ? data.facets.unknown_year : data.facets.years.includes(f.year))) recovered.year = '';
    }
    if (Object.keys(recovered).length) return pickNotes({ ...recovered, home: f.home });
    let cards = data.notes;
    if (!f.home && f.learning !== 'all') {
      // Learning belongs to the browser. Fetch all matching short cards before filtering, not just one page.
      let offset = cards.length;
      while (offset < data.total) {
        const page = await api('/api/notes?' + notesParams(offset));
        if (generation !== state.load) return;
        if (!page.notes.length) break;
        cards = cards.concat(page.notes);
        offset += page.notes.length;
      }
      cards = cards.filter(n => noteLearningState(n.id) === f.learning);
      data.total = cards.length;
      data.ids = cards.map(n => n.id);
    }
    state.notesData = data;
    state.ids = data.ids;
    state.questions = state.offset ? [...state.questions, ...cards] : cards;
    renderNoteFilters(data);
    $('result-count').textContent = t('notes_count', { n: data.total });
    renderNoteList();
    offerContinue();
    if (state.current && !state.ids.includes(state.current) && wide.matches) closeReader();
    else updateNav();
  } catch (error) {
    message('error', error.message || t('connection'));
  } finally {
    if (generation === state.load) $('question-list').setAttribute('aria-busy', 'false');
  }
}

function pickNotes(changes) {
  const navigation = ['collection', 'chapter', 'area', 'topic', 'view', 'section'];
  if (navigation.some(k => k in changes)) $('search').value = '';
  Object.assign(state.notes, { home: false }, changes);
  syncPrimaryNavigation();
  store('ibank-notes', state.notes);
  if (changes.home) {
    ++state.detail;
    closeReader();
    $('source-search').value = '';
    history.replaceState(null, '', location.pathname);
  }
  return loadNotes(true);
}

function enterNotesSource(source, continueReading = false) {
  const last = stored('ibank-last-note', null);
  return pickNotes({ home: false, collection: source.name, chapter: '', area: '', topic: '', tag: '',
    kind: 'study', company: '', year: '', question_type: '', connection: '', verification: '', learning: 'all', marked: false, asked: false, scope: 'source', sort: 'order' })
    .then(() => {
      if (continueReading && last && source.content_ids.includes(last.id)) return openQuestion(last.id, true);
    });
}

function notesSectionSelection(section, home = true) {
  return { section, home: section === 'experiences' ? false : home, public_navigation: 2,
    experience_domain: '', experience_group: 'year', collection: '', chapter: '', area: '', topic: '', tag: '', kind: 'study',
    company: '', year: '', question_type: '', connection: '', verification: '', learning: 'all', marked: false, asked: false, view: 'knowledge',
    scope: section === 'experiences' || !home ? 'all' : 'source', sort: section === 'experiences' ? 'recent' : 'order' };
}

function selectNotesSection(section, home = true) {
  return pickNotes(notesSectionSelection(section, home));
}

function languageLabel(value) {
  return value === 'zh-CN' ? t('notes_language_zh') : value === 'en' ? t('notes_language_en') :
    value === 'mixed' ? t('notes_language_mixed') : value;
}

function renderSourceCards(data) {
  const root = $('source-cards');
  const experiences = state.notes.section === 'experiences';
  const sources = sourceShelf.prepare(data.collections.filter(c => !experiences || c.content_total > 0));
  root.replaceChildren();
  const total = sources.reduce((n, c) => n + c.content_total, 0);
  const information = data.collections.reduce((n, c) => n + c.information_total, 0);
  $('notes-home-title').textContent = t(experiences ? 'notes_section_experiences' : 'notes_home_title');
  $('notes-home-title').nextElementSibling.textContent = t(experiences ? 'notes_experiences_hint' : 'notes_home_hint');
  $('notes-home-summary').textContent = t(experiences ? 'notes_experiences_summary' : 'notes_home_summary', { s: sources.length, n: total, i: information });
  $('notes-browse-experiences').hidden = !experiences;
  for (const source of sources) {
    const card = el('article', 'source-card');
    const meta = source.metadata;
    const description = el('p', 'source-card-description', meta.description || source.origin || t('notes_no_description'));
    const facts = el('p', 'source-card-facts');
    facts.append(el('strong', '', t('notes_source_split', { k: source.knowledge_total, e: source.experience_total })),
      el('span', '', t('notes_source_linked', { n: source.linked })),
      el('span', '', t(experiences ? 'notes_source_experiences_linked' : 'notes_source_public_linked', { n: source.public_linked })));
    const topics = el('div', 'source-card-topics');
    for (const area of source.areas.filter(a => a.count).slice(0, 4)) topics.append(el('span', 'tag', area.title));
    if (!source.areas.length) topics.append(el('span', 'tag', t('notes_original')));
    const done = source.content_ids.filter(id => noteLearningState(id) !== 'unread').length;
    const footer = el('div', 'source-card-footer');
    const last = stored('ibank-last-note', null);
    const canContinue = last && source.content_ids.includes(last.id);
    footer.append(button(t(canContinue ? 'notes_continue' : 'notes_start') + ' →', 'link source-enter',
      () => enterNotesSource(source, canContinue)),
      button(t('notes_source_info'), 'link', () => showSourceInfo(source)));
    sourceShelf.decorate(card, source, [description, facts, topics, footer], done);
    root.append(card);
  }
}

function notesOptions(select, options, value) {
  select.replaceChildren();
  for (const item of options) {
    const option = el('option', '', item.title);
    option.value = item.id;
    if (item.disabled) option.disabled = true;
    select.append(option);
  }
  select.value = value;
  if (select.selectedIndex < 0) select.selectedIndex = 0;
}

function renderNoteFilters(data) {
  const f = state.notes;
  const home = Boolean(f.home);
  const searchingAll = $('search').value.trim() && f.scope === 'all';
  const current = data.collections.find(c => c.name === f.collection);
  const experiences = f.section === 'experiences';
  document.body.classList.toggle('public-experiences', experiences);
  $('public-directory').hidden = !experiences;
  if (experiences) renderPublicDirectory(data);
  syncPrimaryNavigation();
  $('notes-knowledge-count').textContent = data.section_counts.knowledge;
  $('notes-experience-count').textContent = data.section_counts.experiences;
  $('notes-section-knowledge').setAttribute('aria-pressed', String(!experiences));
  $('notes-section-experiences').setAttribute('aria-pressed', String(experiences));
  document.body.classList.toggle('notes-home', home);
  $('notes-overview').hidden = !home;
  $('notes-navigation').hidden = home;
  $('notes-filters').hidden = home;
  $('collections').replaceChildren();
  $('groups').replaceChildren();
  $('groups').hidden = true;
  $('chapter-intro').hidden = true;
  if (home) {
    renderSourceCards(data);
    $('empty-reader').hidden = true;
  } else {
    const title = experiences ? t('notes_section_experiences') : searchingAll || !current ? t('notes_source_all') : current.title;
    $('notes-home').textContent = t(experiences ? 'notes_public_all' : 'notes_sources');
    $('notes-source-name').textContent = title;
    $('notes-source-title').textContent = title;
    $('notes-source-description').textContent = experiences ? t('notes_public_topic_hint') : searchingAll ? t('notes_search_all_hint') : current?.metadata.description || '';
    $('notes-source-info').hidden = experiences || !current || Boolean(searchingAll);
    $('notes-view-knowledge').setAttribute('aria-pressed', String(f.view === 'knowledge'));
    $('notes-view-original').setAttribute('aria-pressed', String(f.view === 'original'));
    $('notes-view-original').parentElement.hidden = experiences;
    $('notes-area-label').parentElement.hidden = experiences;
    $('notes-area-label').hidden = f.view === 'original' || !current || Boolean(searchingAll);
    $('notes-topic-label').textContent = t(f.view === 'original' ? 'notes_original_chapter' : 'notes_topic');
    $('notes-topic').closest('label').hidden = experiences || !current || Boolean(searchingAll);
    notesOptions($('notes-area'), [{ id: '', title: t('notes_area_all') }, ...(current?.areas || []).filter(a => a.count).map(a =>
      ({ id: a.id, title: a.title + ' · ' + a.count }))], f.area);
    if (f.view === 'original') {
      notesOptions($('notes-topic'), [{ id: '', title: t('all_chapters') }, ...(current?.chapters || []).filter(ch => ch.count).map(ch =>
        ({ id: String(ch.index), title: ch.title + ' · ' + ch.count }))], f.chapter);
    } else {
      const areas = (current?.areas || []).filter(a => !f.area || a.id === f.area);
      notesOptions($('notes-topic'), [{ id: '', title: t('notes_topic_all') }, ...areas.flatMap(a => a.topics.filter(topic => topic.count).map(topic =>
        ({ id: topic.id, title: (f.area ? '' : a.title + ' / ') + topic.title + ' · ' + topic.count })))], f.topic);
    }
    const hasTopic = f.view === 'original' ? f.chapter !== '' : Boolean(f.topic);
    notesOptions($('notes-search-scope'), [
      { id: 'topic', title: t('notes_scope_topic'), disabled: !hasTopic || !current },
      { id: 'source', title: t('notes_scope_source'), disabled: !current },
      { id: 'all', title: t('notes_scope_all') },
    ], current ? (f.scope === 'topic' && !hasTopic ? 'source' : f.scope) : 'all');
    f.scope = $('notes-search-scope').value;
    const disableDirectory = Boolean($('search').value.trim() && f.scope !== 'topic');
    $('notes-area').disabled = $('notes-topic').disabled = disableDirectory;
    notesOptions($('notes-tag'), [{ id: '', title: t('notes_tags_all') }, ...data.facets.tags.map(tag => ({ id: tag, title: tag }))], f.tag);
    $('notes-question-type-field').hidden = experiences;
    notesOptions($('notes-question-type'), [{ id: '', title: t('notes_question_type_all') },
      ...Object.entries(data.facets.question_types).map(([id, count]) => ({ id, title: t('notes_question_type_' + id) + ' · ' + count }))], f.question_type);
    notesOptions($('notes-connection'), [{ id: '', title: t('notes_connection_all') },
      ...['any', 'personal', 'public', 'none'].map(id => ({ id, title: t('notes_connection_' + id) }))], f.connection);
    notesOptions($('notes-kind'), [{ id: 'study', title: t('notes_kind_study') },
      ...Object.entries(data.facets.kinds).filter(([k]) => k !== 'info').map(([id, count]) =>
        ({ id, title: t('notes_kind_' + id) + ' · ' + count })),
      ...(f.kind === 'info' ? [{ id: 'info', title: t('notes_kind_info') }] : [])], f.kind);
    notesOptions($('notes-verification'), [{ id: '', title: t('notes_verification_all') },
      ...Object.keys(data.facets.verification).map(k => ({ id: k, title: t('notes_verification_' + k) }))], f.verification);
    $('notes-learning').value = f.learning;
    $('notes-experience-filters').hidden = !experiences;
    if (experiences) {
      notesOptions($('notes-experience-domain'), [{ id: '', title: t('notes_public_domain_all') },
        ...Object.entries(data.facets.experience_domains).map(([id, count]) =>
          ({ id, title: t('notes_domain_' + id) + ' · ' + count }))], f.experience_domain);
    }
    notesOptions($('notes-experience-company'), [{ id: '', title: t('notes_experience_company_all') },
      ...data.facets.companies.map(company => ({ id: company, title: company })),
      ...(data.facets.unknown_company ? [{ id: 'unknown', title: t('notes_experience_company_unknown') }] : [])], f.company);
    notesOptions($('notes-experience-year'), [{ id: '', title: t('notes_experience_year_all') },
      ...data.facets.years.map(year => ({ id: year, title: year })),
      ...(data.facets.unknown_year ? [{ id: 'unknown', title: t('notes_experience_year_unknown') }] : [])], f.year);
    $('notes-experience-sort').value = f.sort === 'recent' ? 'recent' : 'order';
  }
  for (const [id, on] of [['marked-only', f.marked], ['asked-only', f.asked], ['asked-sort', f.sort === 'asked']]) {
    $(id).setAttribute('aria-pressed', String(on));
  }
  for (const [key, label, value] of [
    ['total', experiences ? 'notes_section_experiences' : 'notes_stat_material', data.collections.reduce((n, c) => n + c.content_total, 0)],
    ['answered', 'stat_asked', data.collections.reduce((n, c) => n + c.linked, 0)],
    ['topics', experiences ? 'notes_public_domain' : 'notes_stat_sources', experiences ?
      Object.keys(data.facets.experience_domains).length : data.collections.filter(c => c.content_total > 0).length],
  ]) {
    $(`stat-${key}`).textContent = value;
    $(`stat-${key}-label`).textContent = t(label);
  }
  const side = $('side-notes');
  side.replaceChildren();
  const entry = (parent, label, count, active, action, cls = '') => {
    const node = button('', 'side-item' + cls + (active ? ' active' : ''), action);
    node.append(el('span', '', label), el('small', '', count === undefined ? '' : String(count)));
    node.setAttribute('aria-current', active ? 'page' : 'false');
    parent.append(node);
  };
  if (experiences) {
    entry(side, t('notes_public_all'), data.section_counts.experiences,
      !f.experience_domain && !f.year && !f.company, () => selectNotesSection('experiences'));
    side.append(el('p', 'side-title', t('notes_public_by_domain')));
    for (const [id, count] of Object.entries(data.facets.experience_domains)) {
      entry(side, t('notes_domain_' + id), count, f.experience_domain === id,
        () => pickNotes({ experience_domain: f.experience_domain === id ? '' : id, collection: '', scope: 'all' }));
    }
    side.append(el('p', 'side-title', t('notes_public_by_year')));
    const years = Object.entries(data.facets.experience_years).sort(([a], [b]) => b.localeCompare(a));
    for (const [id, count] of years.filter(([id]) => id !== 'unknown').concat(years.filter(([id]) => id === 'unknown'))) {
      entry(side, id === 'unknown' ? t('notes_experience_year_unknown') : id, count, f.year === id,
        () => pickNotes({ year: f.year === id ? '' : id, collection: '', scope: 'all' }));
    }
    return;
  }
  entry(side, '← ' + t('notes_sources'), data.collections.length, home,
    () => selectNotesSection(experiences ? 'experiences' : 'knowledge'));
  if (!home && current && !searchingAll) {
    side.append(el('p', 'side-title', current.title));
    entry(side, t('notes_all_source'), current.content_total, !f.area && !f.topic && f.chapter === '',
      () => pickNotes({ area: '', topic: '', chapter: '' }));
    if (f.view === 'knowledge' && current.areas.length) {
      for (const area of current.areas) {
        if (!area.count) continue;
        entry(side, area.title, area.count, f.area === area.id && !f.topic,
          () => pickNotes({ area: area.id, topic: '', chapter: '' }));
        if (f.area !== area.id && !experiences) continue;
        for (const topic of area.topics) {
          if (!topic.count) continue;
          entry(side, topic.title, topic.count, f.topic === topic.id,
            () => pickNotes({ area: area.id, topic: topic.id, chapter: '' }), ' side-sub');
        }
      }
    } else {
      for (const chapter of current.chapters.filter(ch => ch.count)) {
        entry(side, chapter.title, chapter.count, String(f.chapter) === String(chapter.index),
          () => pickNotes({ view: 'original', chapter: String(chapter.index), area: '', topic: '' }), ' side-sub');
      }
    }
  }
  side.append(el('p', 'side-title', t(home ? 'notes_sources' : 'notes_other_sources')));
  for (const source of data.collections) {
    if (experiences && !source.content_total) continue;
    entry(side, source.title, source.content_total, !home && f.collection === source.name,
      () => enterNotesSource(source));
  }
}

function grouped() {
  const f = state.notes;
  if (f.section === 'experiences') return !$('search').value.trim() && f.sort === 'recent';
  return !f.home && f.sort === 'order' && !$('search').value.trim() &&
    !(f.collection && (f.view === 'original' ? f.chapter !== '' : Boolean(f.topic)));
}

function renderNoteList() {
  const list = $('question-list');
  list.replaceChildren();
  const groups = grouped();
  $('group-tools').hidden = !groups || !state.questions.length;
  if (state.notes.home) { $('more').hidden = true; return; }
  let head = null;
  for (const n of state.questions) {
    const knowledge = state.notes.view === 'knowledge';
    const experience = n.experience;
    const byDomain = state.notes.experience_group === 'domain';
    const key = experience ? 'public:' + (byDomain ? experience.domain : experience.year || 'unknown') :
      `${n.collection}:${knowledge ? n.area + ':' + n.topic : n.chapter}`;
    const topic = knowledge ? n.topic_title || n.area_title || n.chapter_title : n.chapter_title;
    if (groups && head?.dataset.group !== key) {
      head = el('li', 'group');
      head.dataset.group = key;
      head.dataset.label = experience ? byDomain ? t('notes_domain_' + experience.domain) :
        experience.year || t('notes_experience_year_unknown') : state.notes.collection ? topic : n.collection_title + ' › ' + topic;
      head.append(button('', 'group-head', () => { setFolded('list:' + key, !folded.has('list:' + key)); syncGroup(key); }));
      list.append(head);
    }
    const meta = el('span', 'question-meta');
    const crossSource = !state.notes.collection || ($('search').value.trim() && state.notes.scope === 'all');
    meta.append(el('span', '', experience ? t('notes_domain_' + experience.domain) + ' · ' + topic :
      (crossSource ? n.collection_title + ' · ' : '') + topic));
    if (n.experience) meta.append(el('span', '', [n.experience.company || t('notes_experience_company_unknown'),
      n.experience.interview_time || (n.kind === 'interview' ? t('notes_experience_time_unknown') : '')].filter(Boolean).join(' · ')));
    if (n.marked) meta.append(el('span', 'mark', t('marked')));
    if (!experience) meta.append(el('span', '', t('notes_kind_' + n.kind)));
    if (n.question_type) meta.append(el('span', '', t('notes_question_type_' + n.question_type)));
    if (n.public_experience_count) meta.append(el('span', '', t('notes_public_count', { n: n.public_experience_count })));
    if (n.study_note_count) meta.append(el('span', '', t('notes_study_count', { n: n.study_note_count })));
    if (n.asked) meta.append(el('span', 'has-answer', t('asked_times', { n: n.asked })));
    if (experience) meta.append(el('span', 'public-provenance', t('notes_public_source') + '：' + n.collection_title));
    const item = listRow(n.id, n.title, meta);
    if (groups) item.dataset.member = key;
    list.append(item);
  }
  for (const node of list.querySelectorAll('li.group')) syncGroup(node.dataset.group);
  if (!state.questions.length) list.append(el('li', 'empty', t('empty_notes')));
  $('more').hidden = state.notes.learning !== 'all' || state.questions.length >= (state.notesData?.total || 0);
}

function showSourceInfo(source) {
  const body = $('source-info-body');
  body.replaceChildren();
  $('source-info-title').textContent = source.title;
  body.append(el('p', 'source-info-description', source.metadata.description || source.origin));
  const facts = el('dl', 'source-info-facts');
  const fields = [
    ['notes_source_author', source.metadata.author], ['notes_source_license', source.metadata.license],
    ['notes_source_version', source.metadata.version], ['notes_source_language', languageLabel(source.metadata.language)],
    ['notes_source_upstream_updated', date(source.metadata.updated_at)],
    ['notes_source_imported', date(source.imported_at)], ['notes_source_updated', date(source.organization_updated_at)],
  ];
  for (const [key, value] of fields) facts.append(el('dt', '', t(key)), el('dd', '', value || t('notes_unknown')));
  body.append(facts);
  const links = el('div', 'source-info-links');
  for (const [value, label] of [[source.metadata.homepage, 'notes_source_original'], [source.metadata.license_url, 'notes_source_license_link']]) {
    const link = value ? safeLink(value, t(label) + ' ↗') : null;
    if (link) links.append(link);
  }
  if (source.information_ids.length) {
    const id = source.information_ids[0];
    links.append(button(t('notes_license_full'), 'link', async () => {
      $('source-info-dialog').close();
      await pickNotes({ home: false, collection: source.name, area: '', topic: '', chapter: '',
        kind: 'info', tag: '', verification: '', learning: 'all', marked: false, asked: false });
      await openQuestion(id, true);
    }));
  }
  body.append(links);
  if (source.organization_stale) body.append(el('p', 'notice', t('notes_source_changed')));
  body.append(el('h3', '', t('notes_source_history')));
  if (!source.history.length) body.append(el('p', 'hint', t('notes_no_history')));
  for (const item of [...source.history].reverse().slice(0, 8)) {
    const changes = item.changed;
    body.append(el('p', 'source-history-item', date(item.at) + ' · ' + t('notes_history_item', {
      c: changes.chapters || 0, n: changes.notes || 0, a: changes.areas ? t('notes_history_directory') : t('notes_history_metadata'),
    })));
  }
  body.append(el('p', 'hint', t('notes_manage_hint')));
  $('source-info-dialog').showModal();
}

function installNotesUI() {
  if (installNotesUI.installed) return;
  installNotesUI.installed = true;
  sourceShelf.install();
  $('notes-home').addEventListener('click', () => selectNotesSection(state.notes.section === 'experiences' ? 'experiences' : 'knowledge'));
  for (const section of ['knowledge', 'experiences']) {
    $('notes-section-' + section).addEventListener('click', () => selectNotesSection(section));
  }
  $('notes-browse-experiences').addEventListener('click', () => selectNotesSection('experiences', false));
  $('notes-source-info').addEventListener('click', () => {
    const source = state.notesData?.collections.find(c => c.name === state.notes.collection);
    if (source) showSourceInfo(source);
  });
  $('close-source-info').addEventListener('click', () => $('source-info-dialog').close());
  for (const view of ['knowledge', 'original']) {
    $('notes-view-' + view).addEventListener('click', () => pickNotes({ view, chapter: '', area: '', topic: '', kind: 'study' }));
  }
  $('notes-area').addEventListener('change', () => pickNotes({ area: $('notes-area').value, topic: '', chapter: '' }));
  $('notes-topic').addEventListener('change', () => {
    if (state.notes.view === 'original') return pickNotes({ chapter: $('notes-topic').value });
    const topic = $('notes-topic').value;
    const source = state.notesData.collections.find(c => c.name === state.notes.collection);
    const area = source?.areas.find(a => a.topics.some(t => t.id === topic));
    pickNotes({ area: area?.id || state.notes.area, topic, chapter: '' });
  });
  for (const [id, key] of [['notes-tag', 'tag'], ['notes-kind', 'kind'], ['notes-verification', 'verification'],
    ['notes-question-type', 'question_type'], ['notes-connection', 'connection'],
    ['notes-learning', 'learning'], ['notes-search-scope', 'scope'], ['notes-experience-company', 'company'],
    ['notes-experience-year', 'year'], ['notes-experience-sort', 'sort'], ['notes-experience-domain', 'experience_domain']]) {
    $(id).addEventListener('change', () => pickNotes({ [key]: $(id).value }));
  }
  $('notes-reset').addEventListener('click', () => {
    $('search').value = '';
    pickNotes({ chapter: '', area: '', topic: '', tag: '', kind: 'study', company: '', year: '', experience_domain: '', question_type: '', connection: '', verification: '', learning: 'all',
      marked: false, asked: false, sort: state.notes.section === 'experiences' ? 'recent' : 'order', scope: state.notes.collection ? 'source' : 'all' });
  });
  for (const control of document.querySelectorAll('[data-public-group]')) {
    control.addEventListener('click', () => pickNotes({ experience_group: control.dataset.publicGroup, sort: 'recent' }));
  }
  let timer;
  $('source-search').addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const words = $('source-search').value.trim();
      if (!words) return;
      $('search').value = words;
      Object.assign(state.notes, { home: false, collection: '', chapter: '', area: '', topic: '', scope: 'all',
        tag: '', kind: 'study', company: '', year: '', question_type: '', connection: '', verification: '', learning: 'all', marked: false, asked: false, sort: 'order' });
      store('ibank-notes', state.notes);
      loadNotes(true).then(() => $('search').focus());
    }, 350);
  });
}

function renderPublicDirectory(data) {
  const f = state.notes;
  $('public-total').textContent = t('notes_public_total', { n: data.total }) +
    (f.sort === 'recent' ? ' · ' + t('notes_public_latest') : '');
  for (const control of document.querySelectorAll('[data-public-group]')) {
    control.setAttribute('aria-pressed', String(control.dataset.publicGroup === f.experience_group));
  }
  const active = $('public-active-filters');
  active.replaceChildren();
  for (const [key, value] of [['experience_domain', f.experience_domain ? t('notes_domain_' + f.experience_domain) : ''],
    ['year', f.year === 'unknown' ? t('notes_experience_year_unknown') : f.year],
    ['company', f.company === 'unknown' ? t('notes_experience_company_unknown') : f.company]]) {
    if (!value) continue;
    const clear = button(value + ' ×', 'chip-button', () => pickNotes({ [key]: '' }));
    clear.setAttribute('aria-label', t('notes_public_clear', { value }));
    active.append(clear);
  }
  active.hidden = !active.childElementCount;
}
