'use strict';
// Interview Bank reader. Talks only to the server that served this page (loopback, or the user's own proxy).
// Sections: text · helpers · API · library list · reader · answer · human review · merge decisions · practice · events.

// ---------------------------------------------------------------- text

const TEXT = {
  'zh-CN': {
    library: '题目列表', reader: '阅读', more: '更多', filters: '筛选', topics: '主题', navigation: '切换题目',
    sidebar: '导航', stat_total: '题目', stat_answered: '有答案', stat_topics: '主题', study: '学习', view_all_long: '全部题目',
    tools: '工具', import: '导入题目', research: '补充答案', export: '导出报告', via_agent: 'Agent', think_first_short: '先想再看',
    info_soon: '网页内直接操作会在后续版本提供。',
    info_import_title: '导入题目', info_import_text: '题目由电脑上的 Agent 从截图、文字或音视频中抽取、去重后写入题库，再同步到这里。在电脑上对 Agent 说：',
    info_import_example: '用 interview-bank 把 <截图目录> 里的面试题整理进我的题库，然后同步到服务器',
    info_research_title: '补充答案', info_research_text: '参考答案由 Agent 阅读官方文档等原始资料后撰写，每个要点都附出处，再同步到这里。在电脑上对 Agent 说：',
    info_research_example: '给题库里还没有答案的 AI Agent 方向题目补充有来源的参考答案，然后同步到服务器',
    info_export_title: '导出报告', info_export_text: '带答案版和题目版两份 Markdown 报告由 Agent 在电脑上导出。在电脑上对 Agent 说：',
    info_export_example: '用 interview-bank 导出我的题库报告（带答案版和题目版）',
    practice: '练习一组', merges: '合并裁决', think_first: '先想再看（默认隐藏答案）', refresh: '刷新', logout: '退出登录',
    search: '搜索题目…', search_label: '搜索题目', answered_only: '只看有答案', more_questions: '加载更多',
    resume: '继续练习', discard: '放弃', back: '返回列表', hide_answer: '隐藏答案', show_answer: '显示答案',
    previous: '上一题', next: '下一题', pick: '选一道题开始阅读',
    f_view: '练习状态', view_all: '全部', view_due: '待复习', view_weak: '待巩固', view_unseen: '尚未练习',
    f_domain: '领域', f_technology: '技术栈', f_company: '公司', f_role: '岗位', f_industry: '行业', f_answer: '答案',
    answer_any: '全部', sort: '排序', sort_frequency: '出现次数', sort_recent: '最近更新', sort_title: '题目名称',
    reset: '重置筛选', apply: '完成', close: '关闭',
    practice_title: '练习', close_practice: '结束练习', round_size: '本轮题数', begin_round: '开始',
    merge_intro: '这些题 Agent 不确定是否相同，请逐条判断；由 Agent 应用后才写入题库。',
    status_answered: '有答案', status_source_backed: '有来源', status_reviewed: '已审阅', status_missing: '待补写',
    status_ai_draft: 'AI 草稿', status_stale: '待核验',
    rating_again: '还不会', rating_hard: '有点难', rating_good: '基本掌握', rating_easy: '很熟悉',
    all_group: '全部', all_domain: '全部', all_role: '全部', all_technology: '全部', all_company: '全部', all_industry: '全部',
    no_questions_here: '（暂无）', titles_all: '我的题库',
    count: '{n} 道题', count_answered: '{n} 道题 · {a} 道有答案', position: '{i} / {n}',
    notice_read_only: '只读模式：练习不会保存。', notice_v1: '练习不会保存（题库为 V1，升级到 V2 后可保存进度）。',
    empty_filtered: '没有符合条件的题目。', empty_bank: '题库还是空的。',
    continue: '继续阅读：{q}', seen: '{n} 次', no_answer: '这道题还没有参考答案。',
    draft_warning: 'AI 草稿，尚未核验来源。', stale_warning: '这份答案需要重新核验。',
    answer: '参考答案', points: '要点与出处', code: '代码', sources: '出处',
    spoken: '口述版', follow_ups: '常见追问', mistakes: '易错点', deep_dive: '深入理解',
    origins: '原始问法 · {n}', history: '练习记录 · {n}', no_note: '未填写笔记', next_review: '下次复习：{d}',
    practise_one: '练习这一题', problem: '原题链接',
    review: '人工审阅', review_hint: '只有你本人核对过这份答案后，才点“审阅通过”。',
    review_placeholder: '写下你核对了什么。', review_label: '审阅说明',
    review_ok: '审阅通过', review_stale: '标记待核验', review_need_note: '请先写一句你核对了什么。',
    review_saved: '已记录人工审阅', stale_saved: '已标记为待核验',
    mode_record: '自评和作答会保存，用于安排复习。', mode_temporary: '本轮为临时练习，不保存。',
    round_done: '这一轮完成了', round_summary: '练习 {n} 题 · 掌握 {k} 题 · 跳过 {s} 题',
    round_saved: '自评已保存，复习日期已安排。', round_temporary: '本轮没有写入题库。',
    back_to_bank: '返回题库', preparing: '正在准备…', progress: '第 {i} / {n} 题 · {g}', progress_label: '本轮进度',
    my_answer: '我的思路（可选）', my_answer_placeholder: '先用自己的话回答，再看参考答案。',
    reveal: '查看参考答案', rate: '对照之后，掌握得如何？', skip_question: '跳过',
    retry_first: '请先重试保存。', load_failed: '题目暂时无法读取。', retry_load: '重试',
    save_failed: '{e} 点同一评价可重试保存。',
    close_unsaved: '提交结果尚未确认，确定关闭吗？', close_unsubmitted: '未提交的作答将丢失，结束这一轮？',
    no_round: '当前筛选下没有可练习的题目。', reloaded: '已刷新', resume_text: '上次的练习还没做完：第 {i} / {n} 题。',
    merge_none: '没有待裁决的合并。', merge_new: '新题', merge_existing: '已有题目', merge_reason: 'Agent 的理由：{r}',
    merge_same: '同一题，合并', merge_related: '相关但不同', merge_distinct: '不同的题',
    merge_note: '判断依据（必填）', merge_need_note: '请写一句判断依据。',
    merge_saved: '已保存。全部裁决后请让 Agent 运行 dedupe --resolve {run}。', merge_decided: '已裁决：{a}',
    unreachable: '连不上题库服务，请稍后重试。', failed: '操作未完成，请重试。', connection: '连接失败，请稍后重试。',
  },
  en: {
    library: 'Questions', reader: 'Reader', more: 'More', filters: 'Filters', topics: 'Topics', navigation: 'Question navigation',
    sidebar: 'Navigation', stat_total: 'Questions', stat_answered: 'Answered', stat_topics: 'Topics', study: 'Study', view_all_long: 'All questions',
    tools: 'Tools', import: 'Import questions', research: 'Add answers', export: 'Export reports', via_agent: 'Agent', think_first_short: 'Think first',
    info_soon: 'Doing this directly in the page is planned for a later version.',
    info_import_title: 'Import questions', info_import_text: 'The agent on your computer extracts and deduplicates questions from screenshots, text or recordings, then syncs the bank here. Ask the agent, for example',
    info_import_example: 'Use interview-bank to add the interview questions in <screenshot folder> to my bank, then sync it to the server',
    info_research_title: 'Add answers', info_research_text: 'The agent writes reference answers from official docs and other primary sources, with a source for every key point, then syncs. Ask the agent, for example',
    info_research_example: 'Add sourced reference answers to the unanswered AI Agent questions in my bank, then sync it to the server',
    info_export_title: 'Export reports', info_export_text: 'The agent exports the two Markdown reports (with answers and questions only) on your computer. Ask the agent, for example',
    info_export_example: 'Use interview-bank to export my bank reports (with answers and questions only)',
    practice: 'Practise a round', merges: 'Merge decisions', think_first: 'Think first (hide answers by default)', refresh: 'Refresh', logout: 'Sign out',
    search: 'Search questions…', search_label: 'Search questions', answered_only: 'Answered only', more_questions: 'Load more',
    resume: 'Resume', discard: 'Discard', back: 'Back to the list', hide_answer: 'Hide answer', show_answer: 'Show answer',
    previous: 'Previous', next: 'Next', pick: 'Pick a question to start reading',
    f_view: 'Practice state', view_all: 'All', view_due: 'Due', view_weak: 'Needs work', view_unseen: 'Not practised',
    f_domain: 'Topic', f_technology: 'Tech', f_company: 'Company', f_role: 'Role', f_industry: 'Industry', f_answer: 'Answer',
    answer_any: 'Any', sort: 'Sort', sort_frequency: 'Frequency', sort_recent: 'Recently updated', sort_title: 'Title',
    reset: 'Reset filters', apply: 'Done', close: 'Close',
    practice_title: 'Practice', close_practice: 'End practice', round_size: 'Questions', begin_round: 'Start',
    merge_intro: 'The agent was unsure whether these are the same question. Decide each; the agent applies your decisions.',
    status_answered: 'Answered', status_source_backed: 'Sourced', status_reviewed: 'Reviewed', status_missing: 'No answer',
    status_ai_draft: 'AI draft', status_stale: 'Recheck',
    rating_again: 'Don’t know', rating_hard: 'Hard', rating_good: 'Mostly', rating_easy: 'Easy',
    all_group: 'All', all_domain: 'All', all_role: 'All', all_technology: 'All', all_company: 'All', all_industry: 'All',
    no_questions_here: ' (none)', titles_all: 'My bank',
    count: '{n} questions', count_answered: '{n} questions · {a} answered', position: '{i} / {n}',
    notice_read_only: 'Read-only: practice is not saved.', notice_v1: 'Practice is not saved (V1 bank; upgrade to V2 to keep progress).',
    empty_filtered: 'No questions match.', empty_bank: 'The bank is empty.',
    continue: 'Continue: {q}', seen: '{n}×', no_answer: 'No reference answer yet.',
    draft_warning: 'AI draft, not verified.', stale_warning: 'This answer needs a recheck.',
    answer: 'Reference answer', points: 'Key points and sources', code: 'Code', sources: 'Sources',
    spoken: 'Spoken version', follow_ups: 'Follow-ups', mistakes: 'Common mistakes', deep_dive: 'Deeper dive',
    origins: 'Original wording · {n}', history: 'Practice history · {n}', no_note: 'No notes', next_review: 'Next review: {d}',
    practise_one: 'Practise this one', problem: 'Original problem',
    review: 'Human review', review_hint: 'Press “Reviewed” only after you checked this answer yourself.',
    review_placeholder: 'What did you check?', review_label: 'Review note',
    review_ok: 'Reviewed', review_stale: 'Needs recheck', review_need_note: 'Write one line about what you checked.',
    review_saved: 'Review recorded', stale_saved: 'Marked as needing a recheck',
    mode_record: 'Ratings and notes are saved to schedule reviews.', mode_temporary: 'Practice only; nothing is saved.',
    round_done: 'Round complete', round_summary: '{n} practised · {k} known · {s} skipped',
    round_saved: 'Ratings saved; reviews scheduled.', round_temporary: 'Nothing was saved.',
    back_to_bank: 'Back to the bank', preparing: 'Preparing…', progress: 'Question {i} / {n} · {g}', progress_label: 'Round progress',
    my_answer: 'My answer (optional)', my_answer_placeholder: 'Answer in your own words first.',
    reveal: 'Show reference answer', rate: 'Compared with the answer, how well do you know it?', skip_question: 'Skip',
    retry_first: 'Retry saving first.', load_failed: 'The question could not be loaded.', retry_load: 'Retry',
    save_failed: '{e} Press the same rating to retry.',
    close_unsaved: 'The last submission is unconfirmed. Close anyway?', close_unsubmitted: 'The unsubmitted answer will be lost. End the round?',
    no_round: 'No questions to practise under this filter.', reloaded: 'Refreshed', resume_text: 'Your last round is unfinished: question {i} of {n}.',
    merge_none: 'No merges are waiting.', merge_new: 'New question', merge_existing: 'Existing question', merge_reason: 'Agent’s reason: {r}',
    merge_same: 'Same, merge', merge_related: 'Related, keep both', merge_distinct: 'Different',
    merge_note: 'Why (required)', merge_need_note: 'Write one line explaining your decision.',
    merge_saved: 'Saved. When all are decided, ask the agent to run dedupe --resolve {run}.', merge_decided: 'Decided: {a}',
    unreachable: 'Cannot reach the bank server; try again shortly.', failed: 'That did not work; please retry.', connection: 'Connection failed; try again shortly.',
  },
};
const RATINGS = ['again', 'hard', 'good', 'easy'];
let lang = 'zh-CN';

function t(key, values = {}) {
  const template = (TEXT[lang] && TEXT[lang][key]) ?? TEXT['zh-CN'][key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ''));
}

function applyLanguage(code) {
  lang = String(code || '').toLowerCase().startsWith('en') ? 'en' : 'zh-CN';
  document.documentElement.lang = lang;
  for (const node of document.querySelectorAll('[data-i18n]')) node.textContent = t(node.dataset.i18n);
  for (const node of document.querySelectorAll('[data-i18n-placeholder]')) node.placeholder = t(node.dataset.i18nPlaceholder);
  for (const node of document.querySelectorAll('[data-i18n-aria]')) node.setAttribute('aria-label', t(node.dataset.i18nAria));
  document.title = 'Interview Bank · ' + t('titles_all');
  offerResume();
}

// ---------------------------------------------------------------- helpers

const $ = id => document.getElementById(id);
const filters = ['domain', 'role', 'technology', 'company', 'industry', 'answer_status'];
const wide = matchMedia('(min-width: 900px)');
const roomy = matchMedia('(min-width: 1100px)');  // three columns: sidebar, list, reader
const state = {
  group: '', offset: 0, limit: 30, questions: [], ids: [], data: null, load: 0, detail: 0,
  current: null, revealed: true, cache: new Map(), round: null, merges: [],
};
const launch = new URLSearchParams(location.hash.slice(1));
let token = launch.get('token');
const openOnLoad = launch.get('question');  // #question=q_… opens one question directly
try { if (token) sessionStorage.setItem('ibank-token', token); else token = sessionStorage.getItem('ibank-token'); } catch (_) {}
if (location.hash) history.replaceState(null, '', location.pathname);

function stored(key, fallback) {
  try { const value = localStorage.getItem(key); return value === null ? fallback : JSON.parse(value); } catch (_) { return fallback; }
}

function store(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {}
}

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(text, cls, action) {
  const node = el('button', cls, text);
  node.type = 'button';
  node.addEventListener('click', action);
  return node;
}

function message(id, text) {
  $(id).textContent = text || '';
  $(id).hidden = !text;
}

let toastTimer;
function toast(text) {
  message('toast', text);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => message('toast', ''), 3000);
}

function answered(status) {
  return status === 'source_backed' || status === 'reviewed';
}

function date(value) {
  return value ? new Date(value).toLocaleDateString(lang) : '';
}

function safeLink(url, title) {
  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) return null;
    const link = el('a', '', title || parsed.hostname.replace(/^www\./, ''));
    link.href = parsed.href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  } catch (_) {
    return null;
  }
}

function richText(text) {
  // A deliberately small Markdown subset; source HTML is always literal text.
  const root = el('div', 'rich');
  let code = null;
  let list = null;
  for (const line of String(text || '').split('\n')) {
    if (/^\s*```/.test(line)) {
      if (code) { root.append(code); code = null; } else { code = el('pre'); }
      list = null;
      continue;
    }
    if (code) { code.textContent += line + '\n'; continue; }
    let target;
    if (/^\s*(?:[-*•]|\d+[.)、])\s+/.test(line)) {
      if (!list) { list = el('ul'); root.append(list); }
      target = el('li');
      list.append(target);
    } else {
      list = null;
      if (!line.trim()) continue;
      target = el('p');
      root.append(target);
    }
    const clean = line.replace(/^\s*(?:[-*•]|\d+[.)、])\s+/, '').replace(/^#{1,6}\s+/, '');
    for (const part of clean.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)) {
      if (part.startsWith('**') && part.endsWith('**')) target.append(el('strong', '', part.slice(2, -2)));
      else if (part.startsWith('`') && part.endsWith('`')) target.append(el('code', '', part.slice(1, -1)));
      else target.append(document.createTextNode(part));
    }
  }
  if (code) root.append(code);
  return root;
}

// ---------------------------------------------------------------- API

async function api(path, body) {
  // Relative to the page, so the reader also works behind a reverse proxy under a path such as /ibank/.
  const response = await fetch(path.replace(/^\//, ''), {
    method: body ? 'POST' : 'GET',
    headers: { 'X-Interview-Token': token || '', ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  });
  let result;
  try { result = await response.json(); } catch (_) { throw new Error(t('unreachable')); }
  // A hosted reader whose session ended shows its login page again.
  if (response.status === 401 && result.login) { location.reload(); return new Promise(() => {}); }
  if (!response.ok) throw new Error(result.error || t('failed'));
  return result;
}

function params() {
  const query = new URLSearchParams({ view: $('view').value, sort: $('sort').value });
  if ($('search').value.trim()) query.set('query', $('search').value.trim());
  if (state.group) query.set('group', state.group);
  for (const name of filters) if ($(name).value) query.set(name, $(name).value);
  if ($('answered-only').getAttribute('aria-pressed') === 'true' && !$('answer_status').value) query.set('answer_status', 'answered');
  return query;
}

async function question(id) {
  if (!state.cache.has(id)) state.cache.set(id, api('/api/question?id=' + encodeURIComponent(id)).catch(error => { state.cache.delete(id); throw error; }));
  return state.cache.get(id);
}

// ---------------------------------------------------------------- library list

function updateFacets(facets) {
  for (const key of ['domain', 'technology', 'company', 'role', 'industry']) {
    const values = facets[key] || [];
    const value = $(key).value;
    $(key).replaceChildren(new Option(t('all_' + key), ''));
    for (const item of values) $(key).add(new Option(item.label + (item.count ? ` · ${item.count}` : ''), item.value));
    if (value && !values.some(v => v.value === value)) $(key).add(new Option(value + t('no_questions_here'), value));
    $(key).value = value;
  }
  const groups = $('groups');
  groups.replaceChildren();
  const total = (facets.group || []).reduce((sum, g) => sum + g.count, 0);
  for (const item of [{ value: '', label: t('all_group'), count: total }, ...(facets.group || [])]) {
    const chip = button('', 'chip' + (state.group === item.value ? ' active' : ''), () => {
      state.group = item.value;
      loadLibrary(true);
    });
    chip.append(el('span', '', item.label), el('small', '', String(item.count)));
    chip.setAttribute('aria-pressed', String(state.group === item.value));
    groups.append(chip);
  }
  groups.querySelector('.active')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  const side = $('side-groups');
  side.replaceChildren();
  for (const item of [{ value: '', label: t('all_group'), count: total }, ...(facets.group || [])]) {
    const entry = button('', 'side-item' + (state.group === item.value ? ' active' : ''), () => { state.group = item.value; loadLibrary(true); });
    entry.append(el('span', '', item.label), el('small', '', String(item.count)));
    side.append(entry);
  }
}

function updateSidebar(data) {
  $('stat-total').textContent = data.summary.questions;
  $('stat-answered').textContent = data.summary.answered;
  $('stat-topics').textContent = (data.facets.group || []).length;
  for (const key of ['all', 'due', 'weak', 'unseen']) $('nav-' + key).textContent = data.summary[key === 'all' ? 'questions' : key];
  for (const node of document.querySelectorAll('[data-view]')) node.classList.toggle('active', node.dataset.view === $('view').value);
  $('account').textContent = data.account || data.name;
  $('side-logout').hidden = !data.can_logout;
  $('side-status').textContent = [data.read_only ? t('notice_read_only') : data.schema_version === 1 ? t('notice_v1') : '', 'v' + data.version].filter(Boolean).join(' · ');
}

function placeFilters() {
  // Wide screens keep the filters inline above the list; phones open them as a bottom sheet.
  if (roomy.matches) $('inline-filters').append($('filter-fields'));
  else $('filter-dialog').querySelector('.sheet-head').after($('filter-fields'));
  if (!roomy.matches) $('inline-filters').hidden = true;
}

function showInfo(kind) {
  $('info-title').textContent = t(`info_${kind}_title`);
  $('info-text').textContent = t(`info_${kind}_text`);
  $('info-example').textContent = t(`info_${kind}_example`);
  $('info-dialog').showModal();
}

function filterCount() {
  const n = filters.filter(name => $(name).value).length + ($('view').value !== 'all') + ($('sort').value !== 'frequency');
  $('filter-count').textContent = String(n);
  $('filter-count').hidden = !n;
}

async function loadLibrary(reset = false) {
  const generation = ++state.load;
  if (reset) { state.offset = 0; state.questions = []; }
  $('question-list').setAttribute('aria-busy', 'true');
  message('error', '');
  try {
    const query = params();
    query.set('offset', state.offset);
    query.set('limit', state.limit);
    const data = await api('/api/library?' + query);
    if (generation !== state.load) return;
    if (!state.data || state.data.language !== data.language) applyLanguage(data.language);
    state.data = data;
    state.ids = data.ids;
    state.questions = state.offset ? [...state.questions, ...data.questions] : data.questions;
    updateFacets(data.facets);
    updateSidebar(data);
    filterCount();
    $('version').textContent = `${data.name} · v${data.version}`;
    $('logout').hidden = !data.can_logout;
    $('result-count').textContent = t('count_answered', { n: data.total, a: data.total_answered });
    message('notice', data.read_only ? t('notice_read_only') : data.schema_version === 1 ? t('notice_v1') : '');
    renderList();
    offerContinue();
    loadMerges();
    if (state.current && !state.ids.includes(state.current) && wide.matches) closeReader();
    else updateNav();
  } catch (error) {
    if (generation === state.load) message('error', error.message || t('connection'));
  } finally {
    if (generation === state.load) $('question-list').setAttribute('aria-busy', 'false');
  }
}

function renderList() {
  const list = $('question-list');
  list.replaceChildren();
  for (const q of state.questions) {
    const item = el('li');
    const row = button('', 'question' + (state.current === q.id ? ' current' : ''), () => openQuestion(q.id, true));
    row.dataset.id = q.id;
    const meta = el('span', 'question-meta');
    meta.append(el('span', '', q.group), el('span', '', t('seen', { n: q.frequency })));
    if (answered(q.answer_status)) meta.append(el('span', 'has-answer', '✓ ' + t('status_answered')));
    row.append(el('span', 'question-title', q.canonical), meta);
    item.append(row);
    list.append(item);
  }
  if (!state.questions.length) list.append(el('li', 'empty', state.data?.summary.questions ? t('empty_filtered') : t('empty_bank')));
  $('more').hidden = state.questions.length >= (state.data?.total || 0);
}

function offerContinue() {
  const last = stored('ibank-last', null);
  const show = last && last.id !== state.current && state.ids.includes(last.id);
  $('continue').hidden = !show;
  if (show) $('continue').textContent = t('continue', { q: last.title });
}

// ---------------------------------------------------------------- reader

function updateNav() {
  const index = state.ids.indexOf(state.current);
  $('position').textContent = index >= 0 ? t('position', { i: index + 1, n: state.ids.length }) : '';
  $('previous').disabled = index <= 0;
  $('next').disabled = index < 0 || index >= state.ids.length - 1;
  for (const row of document.querySelectorAll('.question')) row.classList.toggle('current', row.dataset.id === state.current);
}

function closeReader() {
  state.current = null;
  document.body.classList.remove('reading-open');
  $('reader').hidden = true;
  $('empty-reader').hidden = !wide.matches;
  updateNav();
  offerContinue();
}

async function openQuestion(id, fromList = false) {
  const generation = ++state.detail;
  try {
    const q = await question(id);
    if (generation !== state.detail) return;
    const opening = !document.body.classList.contains('reading-open');
    state.current = q.id;
    state.revealed = !stored('ibank-think-first', false);
    renderReading(q);
    document.body.classList.add('reading-open');
    $('reader').hidden = false;
    $('empty-reader').hidden = true;
    // On a phone the reader covers the list; the system back gesture closes it.
    if (!wide.matches && opening && fromList) history.pushState({ reader: true }, '', location.pathname + '#question=' + q.id);
    else history.replaceState(history.state, '', location.pathname + '#question=' + q.id);
    store('ibank-last', { id: q.id, title: q.canonical.slice(0, 40) + (q.canonical.length > 40 ? '…' : '') });
    updateNav();
    $('reading').scrollTop = 0;
    $('reading').focus({ preventScroll: true });
    const index = state.ids.indexOf(q.id);
    for (const neighbour of [state.ids[index + 1], state.ids[index - 1]]) if (neighbour) question(neighbour).catch(() => {});
    document.querySelector('.question.current')?.scrollIntoView({ block: 'nearest' });
  } catch (error) {
    message('error', error.message);
    toast(error.message);
  }
}

function step(delta) {
  const index = state.ids.indexOf(state.current);
  const target = state.ids[index + delta];
  if (target) openQuestion(target);
}

function setReveal(visible) {
  state.revealed = visible;
  const body = $('reading').querySelector('.answer-body');
  const gate = $('reading').querySelector('.reveal');
  if (body) body.hidden = !visible;
  if (gate) gate.hidden = visible;
  $('toggle-answer').textContent = visible ? t('hide_answer') : t('show_answer');
}

function renderReading(q) {
  const reading = $('reading');
  reading.replaceChildren();
  const top = el('p', 'reading-meta');
  top.append(el('span', 'topic', q.group));
  const facts = [t('seen', { n: q.frequency }), q.companies.slice(0, 3).join(lang === 'en' ? ', ' : '、'), q.years.join('/')].filter(Boolean);
  top.append(el('span', '', facts.join(' · ')));
  reading.append(top, el('h1', 'reading-title', q.canonical));
  if (q.technologies.length || q.problem_url) {
    const tags = el('div', 'tags');
    for (const tech of q.technologies.slice(0, 6)) tags.append(el('span', 'tag', tech));
    if (q.problem_url) {
      const link = safeLink(q.problem_url.url, t('problem') + ' ↗');
      if (link) { link.className = 'tag'; tags.append(link); }
    }
    reading.append(tags);
  }
  if (!q.answer) {
    reading.append(el('p', 'no-answer', t('no_answer')));
    $('toggle-answer').hidden = true;
  } else {
    $('toggle-answer').hidden = false;
    reading.append(button(t('show_answer'), 'reveal button primary', () => setReveal(true)), answerView(q));
    setReveal(state.revealed);
  }
  const more = el('div', 'reading-more');
  const origins = el('details');
  origins.append(el('summary', '', t('origins', { n: q.occurrences.length })));
  for (const occurrence of q.occurrences) {
    const node = el('p', 'origin', occurrence.text);
    let time = '';
    if (occurrence.locator) {
      const start = occurrence.locator.start_seconds ?? occurrence.locator.start;
      if (start !== undefined && start !== null) time = `${start}s`;
    }
    const where = [occurrence.platform, occurrence.year, time].filter(Boolean).join(' · ');
    if (where) node.append(el('small', '', where));
    origins.append(node);
  }
  more.append(origins);
  if (q.history.length) {
    const history = el('details');
    history.append(el('summary', '', t('history', { n: q.history.length })));
    for (const item of q.history) {
      const node = el('p', 'origin', `${t('rating_' + item.rating)} · ${date(item.occurred_at)} — ${item.note || t('no_note')}`);
      node.append(el('small', '', t('next_review', { d: date(item.next_review_at) })));
      history.append(node);
    }
    more.append(history);
  }
  if (state.data?.can_review && q.answer) more.append(reviewControls(q));
  more.append(button(t('practise_one'), 'link', () => singlePractice(q)));
  reading.append(more);
}

// ---------------------------------------------------------------- answer

function answerView(q) {
  const wrap = el('section', 'answer-body');
  const answer = q.answer;
  if (q.answer_status === 'ai_draft') wrap.append(el('p', 'warning', t('draft_warning')));
  if (q.answer_status === 'stale') wrap.append(el('p', 'warning', t('stale_warning')));
  const head = el('h2', 'answer-head', t('answer'));
  if (answered(q.answer_status)) head.append(el('span', 'verified', t('status_' + q.answer_status)));
  wrap.append(head, richText(answer.short_answer));
  if (answer.code_example) {
    const code = el('details', 'extra');
    code.open = true;
    code.append(el('summary', '', t('code')), richText('```\n' + answer.code_example + '\n```'));
    wrap.append(code);
  }
  // Each key point with the sources that support it: the answer is checkable, not only plausible.
  const sources = answer.sources || [];
  const points = answer.key_points || [];
  if (points.length) {
    const box = el('details', 'extra points');
    box.append(el('summary', '', t('points')));
    const list = el('ol');
    points.forEach((point, index) => {
      const item = el('li', '', point);
      const urls = (answer.evidence || []).filter(e => e.key_point === index).flatMap(e => e.source_urls || []);
      const refs = el('span', 'refs');
      for (const url of [...new Set(urls)]) {
        const source = sources.find(s => s.url === url);
        const link = safeLink(url, (sources.indexOf(source) + 1 || '↗').toString());
        if (link) { link.title = source?.title || url; refs.append(link); }
      }
      if (refs.childNodes.length) item.append(refs);
      list.append(item);
    });
    box.append(list);
    wrap.append(box);
  }
  for (const [field, key] of [['spoken_answer', 'spoken'], ['follow_up_questions', 'follow_ups'], ['common_mistakes', 'mistakes'], ['deep_dive', 'deep_dive']]) {
    const value = answer[field];
    const text = Array.isArray(value) ? value.map(v => '- ' + v).join('\n') : String(value || '').trim();
    if (!text) continue;
    const box = el('details', 'extra');
    box.append(el('summary', '', t(key)), richText(text));
    wrap.append(box);
  }
  if (sources.length) {
    const list = el('ol', 'sources');
    for (const source of sources) {
      const link = safeLink(source.url, source.title || undefined);
      if (!link) continue;
      const item = el('li');
      item.append(link, el('small', '', new URL(source.url).hostname.replace(/^www\./, '')));
      list.append(item);
    }
    const box = el('div', 'sources-box');
    box.append(el('h3', '', t('sources')), list);
    wrap.append(box);
  }
  return wrap;
}

// ---------------------------------------------------------------- human review

function reviewControls(q) {
  // Human review is the reader's own decision; the agent has no way to submit it.
  const box = el('details');
  box.append(el('summary', '', t('review')));
  const note = el('textarea', 'note');
  note.maxLength = 2000;
  note.placeholder = t('review_placeholder');
  note.setAttribute('aria-label', t('review_label'));
  const actions = el('div', 'actions');
  const send = async decision => {
    if (!note.value.trim()) { toast(t('review_need_note')); note.focus(); return; }
    actions.querySelectorAll('button').forEach(b => { b.disabled = true; });
    try {
      await api('/api/review', { question_id: q.id, answer_id: q.answer.id, decision, note: note.value });
      toast(decision === 'reviewed' ? t('review_saved') : t('stale_saved'));
      state.cache.delete(q.id);
      await loadLibrary();
      await openQuestion(q.id);
    } catch (error) {
      toast(error.message);
    } finally {
      actions.querySelectorAll('button').forEach(b => { b.disabled = false; });
    }
  };
  actions.append(button(t('review_ok'), 'button primary', () => send('reviewed')), button(t('review_stale'), 'button', () => send('stale')));
  box.append(el('p', 'hint', t('review_hint')), note, actions);
  return box;
}

// ---------------------------------------------------------------- merge decisions

async function loadMerges() {
  if (state.data?.read_only) { $('open-merges').hidden = true; $('side-merges').hidden = true; return; }
  try {
    const { items } = await api('/api/dedupe-reviews');
    state.merges = items;
    const open = items.filter(item => !item.decision).length;
    $('open-merges').hidden = !items.length;
    $('side-merges').hidden = !items.length;
    $('merge-count').textContent = open ? String(open) : '✓';
    $('side-merge-count').textContent = open ? String(open) : '✓';
    if ($('merge-dialog').open) renderMerges();
  } catch (_) {
    $('open-merges').hidden = true;
  }
}

function renderMerges() {
  const list = $('merge-list');
  list.replaceChildren();
  message('merge-error', '');
  if (!state.merges.length) { list.append(el('p', 'hint', t('merge_none'))); return; }
  const labels = { MERGE_VARIANT: t('merge_same'), KEEP_RELATED: t('merge_related'), KEEP_DISTINCT: t('merge_distinct') };
  for (const item of state.merges) {
    const card = el('section', 'merge');
    for (const [label, text] of [[t('merge_new'), item.question], [t('merge_existing'), item.target]]) {
      const side = el('div', 'merge-side');
      side.append(el('small', '', label), el('p', '', text));
      card.append(side);
    }
    card.append(el('p', 'hint', t('merge_reason', { r: item.reason })));
    if (item.decision) {
      card.append(el('p', 'hint', t('merge_decided', { a: labels[item.decision.action] })));
    } else {
      const note = el('textarea', 'note');
      note.maxLength = 2000;
      note.placeholder = t('merge_note');
      note.setAttribute('aria-label', t('merge_note'));
      const actions = el('div', 'actions');
      for (const action of ['MERGE_VARIANT', 'KEEP_RELATED', 'KEEP_DISTINCT']) {
        actions.append(button(labels[action], action === 'MERGE_VARIANT' ? 'button primary' : 'button', async () => {
          if (!note.value.trim()) { message('merge-error', t('merge_need_note')); note.focus(); return; }
          actions.querySelectorAll('button').forEach(b => { b.disabled = true; });
          try {
            await api('/api/dedupe-decision', { run_id: item.run_id, question_id: item.question_id, action, note: note.value });
            toast(t('merge_saved', { run: item.run_id }));
            await loadMerges();
          } catch (error) {
            message('merge-error', error.message);
            actions.querySelectorAll('button').forEach(b => { b.disabled = false; });
          }
        }));
      }
      card.append(note, actions);
    }
    list.append(card);
  }
}

// ---------------------------------------------------------------- practice

const ROUND_KEY = 'ibank-round';

function saveRound() {
  // Lets a refresh resume the round; only IDs and positions are kept, never answers.
  try {
    const round = state.round;
    if (!round || round.index >= round.questions.length) sessionStorage.removeItem(ROUND_KEY);
    else sessionStorage.setItem(ROUND_KEY, JSON.stringify({ questions: round.questions.map(q => ({ id: q.id })), index: round.index, results: round.results }));
  } catch (_) {}
}

function storedRound() {
  try { return JSON.parse(sessionStorage.getItem(ROUND_KEY) || 'null'); } catch (_) { return null; }
}

function offerResume() {
  const saved = storedRound();
  $('resume-bar').hidden = !saved;
  if (saved) $('resume-text').textContent = t('resume_text', { i: saved.index + 1, n: saved.questions.length });
}

function preparePractice() {
  $('menu').hidden = true;
  state.round = null;
  $('practice-setup').hidden = false;
  $('practice-body').hidden = true;
  message('practice-error', '');
  $('practice-mode').textContent = state.data?.can_record ? t('mode_record') : t('mode_temporary');
  $('practice-dialog').showModal();
}

function singlePractice(q) {
  preparePractice();
  startRound([q]);
}

function startRound(questions, index = 0, results = []) {
  state.round = { questions, index, results, saving: false, current: null, revealed: false, pending: null };
  $('practice-setup').hidden = true;
  $('practice-body').hidden = false;
  $('resume-bar').hidden = true;
  renderRound();
}

async function renderRound() {
  const round = state.round;
  if (!round) return;
  saveRound();
  message('practice-error', '');
  const body = $('practice-body');
  body.replaceChildren();
  if (round.index >= round.questions.length) {
    const done = el('div', 'round-done');
    const known = round.results.filter(r => r === 'good' || r === 'easy').length;
    done.append(el('h3', '', '✓ ' + t('round_done')),
                el('p', '', t('round_summary', { n: round.results.length, k: known, s: round.questions.length - round.results.length })),
                el('p', 'hint', state.data.can_record ? t('round_saved') : t('round_temporary')),
                button(t('back_to_bank'), 'button primary', closePractice));
    body.append(done);
    return;
  }
  body.append(el('p', 'hint', t('preparing')));
  try {
    const q = await question(round.questions[round.index].id);
    if (state.round !== round) return;
    round.current = q;
    round.revealed = false;
    round.pending = null;
    body.replaceChildren();
    const bar = el('div', 'round-progress');
    bar.append(el('span', '', t('progress', { i: round.index + 1, n: round.questions.length, g: q.group })));
    const meter = el('progress');
    meter.max = round.questions.length;
    meter.value = round.index;
    meter.setAttribute('aria-label', t('progress_label'));
    bar.append(meter);
    const title = el('h3', 'practice-question', q.canonical);
    title.tabIndex = -1;
    const label = el('label', 'hint', t('my_answer'));
    label.htmlFor = 'practice-response';
    const response = el('textarea', 'note');
    response.id = 'practice-response';
    response.maxLength = 10000;
    response.placeholder = t('my_answer_placeholder');
    body.append(bar, title, label, response);
    const actions = el('div', 'actions');
    const reveal = button(t('reveal'), 'button primary', () => {
      if (round.revealed) return;
      round.revealed = true;
      body.append(q.answer ? answerView(q) : el('p', 'no-answer', t('no_answer')), el('p', 'hint', t('rate')));
      const ratings = el('div', 'ratings');
      for (const rating of RATINGS) ratings.append(button(t('rating_' + rating), 'button', () => saveRating(rating)));
      body.append(ratings);
      reveal.disabled = true;
      ratings.querySelector('button').focus({ preventScroll: true });
    });
    actions.append(reveal, button(t('skip_question'), 'button', () => {
      if (round.saving) return;
      if (round.pending) { message('practice-error', t('retry_first')); return; }
      round.index++;
      renderRound();
    }));
    body.append(actions);
    title.focus({ preventScroll: true });
  } catch (error) {
    if (state.round === round) {
      body.replaceChildren(el('p', 'hint', t('load_failed')), button(t('retry_load'), 'button', renderRound));
      message('practice-error', error.message);
    }
  }
}

async function saveRating(rating) {
  const round = state.round;
  if (!round || round.saving || !round.current) return;
  round.saving = true;
  message('practice-error', '');
  const buttons = $('practice-body').querySelectorAll('button');
  buttons.forEach(b => { b.disabled = true; });
  $('close-practice').disabled = true;
  $('practice-response').disabled = true;
  try {
    if (state.data.can_record) {
      if (!round.pending) {
        round.pending = {
          question_id: round.current.id, revision: round.current.revision, rating, request_id: crypto.randomUUID(),
          note: $('practice-response').value, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
        };
      }
      await api('/api/practice', round.pending);
    }
    round.results.push(round.pending?.rating || rating);
    round.index++;
    round.pending = null;
    await renderRound();
  } catch (error) {
    message('practice-error', t('save_failed', { e: error.message }));
  } finally {
    round.saving = false;
    $('close-practice').disabled = false;
    buttons.forEach(b => { b.disabled = false; });
    if ($('practice-response')) $('practice-response').disabled = !!round.pending;
  }
}

function closePractice() {
  if (state.round?.saving) return;
  if (state.round?.pending && !confirm(t('close_unsaved'))) return;
  const unfinished = state.round && state.round.index < state.round.questions.length;
  if (!state.round?.pending && unfinished && $('practice-response')?.value && !confirm(t('close_unsubmitted'))) return;
  const recorded = state.round?.results.length && state.data?.can_record;
  state.round = null;
  try { sessionStorage.removeItem(ROUND_KEY); } catch (_) {}
  $('practice-dialog').close();
  if (recorded) { state.cache.clear(); loadLibrary(); }
}

// ---------------------------------------------------------------- events

let debounce;
$('search').addEventListener('input', () => { clearTimeout(debounce); debounce = setTimeout(() => loadLibrary(true), 250); });
$('answered-only').addEventListener('click', () => {
  const on = $('answered-only').getAttribute('aria-pressed') !== 'true';
  $('answered-only').setAttribute('aria-pressed', String(on));
  store('ibank-answered-only', on);
  loadLibrary(true);
});
$('more').addEventListener('click', () => { state.offset = state.questions.length; loadLibrary(); });
$('continue').addEventListener('click', () => { const last = stored('ibank-last', null); if (last) openQuestion(last.id, true); });
$('open-filters').addEventListener('click', () => {
  if (roomy.matches) $('inline-filters').hidden = !$('inline-filters').hidden;
  else $('filter-dialog').showModal();
});
for (const name of [...filters, 'view', 'sort']) $(name).addEventListener('change', () => { if (roomy.matches) loadLibrary(true); });
roomy.addEventListener('change', placeFilters);
$('views').addEventListener('click', event => {
  const target = event.target.closest('[data-view]');
  if (!target) return;
  $('view').value = target.dataset.view;
  loadLibrary(true);
});
for (const node of document.querySelectorAll('[data-info]')) node.addEventListener('click', () => { $('menu').hidden = true; showInfo(node.dataset.info); });
$('close-info').addEventListener('click', () => $('info-dialog').close());
$('side-practice').addEventListener('click', preparePractice);
$('side-merges').addEventListener('click', () => { renderMerges(); $('merge-dialog').showModal(); });
$('side-refresh').addEventListener('click', () => $('refresh').click());
$('side-logout').addEventListener('click', () => $('logout').click());
$('side-think-first').addEventListener('change', () => { $('think-first').checked = $('side-think-first').checked; $('think-first').dispatchEvent(new Event('change')); });
$('practise-current').addEventListener('click', () => { if (state.current) question(state.current).then(singlePractice).catch(error => toast(error.message)); });
$('close-filters').addEventListener('click', () => $('filter-dialog').close());
$('apply-filters').addEventListener('click', () => { $('filter-dialog').close(); loadLibrary(true); });
$('clear-filters').addEventListener('click', () => {
  for (const name of filters) $(name).value = '';
  $('view').value = 'all';
  $('sort').value = 'frequency';
  if ($('filter-dialog').open) $('filter-dialog').close();
  loadLibrary(true);
});
$('open-menu').addEventListener('click', event => { event.stopPropagation(); $('menu').hidden = !$('menu').hidden; });
document.addEventListener('click', event => { if (!$('menu').hidden && !$('menu').contains(event.target)) $('menu').hidden = true; });
$('think-first').addEventListener('change', () => {
  store('ibank-think-first', $('think-first').checked);
  $('side-think-first').checked = $('think-first').checked;
  if (state.current) setReveal(!$('think-first').checked);
});
$('refresh').addEventListener('click', async () => {
  $('menu').hidden = true;
  state.cache.clear();
  await loadLibrary(true);
  if ($('error').hidden) toast(t('reloaded'));
});
$('logout').addEventListener('click', async () => { try { await api('/api/logout', {}); } finally { location.reload(); } });
$('back').addEventListener('click', () => { if (history.state?.reader) history.back(); else closeReader(); });
window.addEventListener('popstate', () => { if (document.body.classList.contains('reading-open') && !wide.matches) closeReader(); });
$('previous').addEventListener('click', () => step(-1));
$('next').addEventListener('click', () => step(1));
$('toggle-answer').addEventListener('click', () => setReveal(!state.revealed));
wide.addEventListener('change', () => { if (!state.current) closeReader(); });

// Swipe between questions on touch screens; vertical scrolling is left alone.
let touch = null;
$('reading').addEventListener('touchstart', event => {
  const point = event.touches[0];
  touch = event.touches.length === 1 ? { x: point.clientX, y: point.clientY, at: Date.now() } : null;
}, { passive: true });
$('reading').addEventListener('touchend', event => {
  if (!touch) return;
  const point = event.changedTouches[0];
  const dx = point.clientX - touch.x;
  const dy = point.clientY - touch.y;
  const quick = Date.now() - touch.at < 600;
  touch = null;
  if (quick && Math.abs(dx) > 70 && Math.abs(dy) < Math.abs(dx) / 2) step(dx < 0 ? 1 : -1);
});

document.addEventListener('keydown', event => {
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
  const dialog = $('practice-dialog').open || $('merge-dialog').open || $('filter-dialog').open || $('info-dialog').open;
  if (typing || dialog) return;
  if (event.key === '/') { event.preventDefault(); $('search').focus(); }
  if (!state.current) return;
  if (event.key === 'ArrowRight' || event.key === 'j') step(1);
  if (event.key === 'ArrowLeft' || event.key === 'k') step(-1);
  if (event.key === ' ' && !state.revealed) { event.preventDefault(); setReveal(true); }
  if (event.key === 'Escape' && !wide.matches) $('back').click();
});

$('start-practice').addEventListener('click', preparePractice);
$('begin-round').addEventListener('click', async () => {
  const begin = $('begin-round');
  begin.disabled = true;
  try {
    const query = params();
    query.set('limit', $('practice-limit').value);
    const result = await api('/api/practice?' + query);
    if (!result.questions.length) throw new Error(t('no_round'));
    if ($('practice-dialog').open) startRound(result.questions);
  } catch (error) {
    message('practice-error', error.message);
  } finally {
    begin.disabled = false;
  }
});
$('close-practice').addEventListener('click', closePractice);
$('practice-dialog').addEventListener('cancel', event => { event.preventDefault(); closePractice(); });
$('resume-round').addEventListener('click', () => {
  const saved = storedRound();
  if (!saved) return offerResume();
  preparePractice();
  startRound(saved.questions, saved.index, saved.results || []);
});
$('discard-round').addEventListener('click', () => { try { sessionStorage.removeItem(ROUND_KEY); } catch (_) {} offerResume(); });
$('open-merges').addEventListener('click', () => { $('menu').hidden = true; renderMerges(); $('merge-dialog').showModal(); });
$('close-merges').addEventListener('click', () => $('merge-dialog').close());
window.addEventListener('beforeunload', event => {
  if (state.round && $('practice-response')?.value) { event.preventDefault(); event.returnValue = ''; }
});

$('think-first').checked = stored('ibank-think-first', false);
$('side-think-first').checked = $('think-first').checked;
placeFilters();
$('answered-only').setAttribute('aria-pressed', String(stored('ibank-answered-only', false)));
closeReader();
offerResume();
loadLibrary(true).then(() => { if (openOnLoad) openQuestion(openOnLoad, true); });
