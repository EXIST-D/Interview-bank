'use strict';
// Interview Bank reader. Talks only to the server that served this page (loopback, or the user's own proxy).
// Sections: text · helpers · API · library list · reader · answer · notes · human review · merge decisions · practice · events.

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
    modes: '板块', mode_bank: '面经', mode_notes: '八股', search_notes: '搜索八股…', marked_only: '重点', asked_only: '面经考过',
    asked_sort: '按考频', notes_count: '{n} 条', notes_all: '全部八股', all_chapters: '全部章节', stat_notes: '八股',
    stat_marked: '重点', stat_asked: '面经考过', empty_notes: '没有符合条件的条目。', marked: '重点', asked_times: '面经考过 {n} 次',
    note_answer: '原文答案', no_note_answer: '原文没有给出答案。', note_source: '出处', source_line: '{file} 第 {line} 行',
    imported: '导入于 {d}', asked_in: '面经里这样问 · {n}', related_notes: '相关八股 · {n}',
    relation_answers: '同一题', relation_covers: '相关知识点',
    random: '随机一题', random_hint: '优先未读', random_none: '当前列表是空的。', fold_all: '全部折叠', unfold_all: '全部展开',
    to_top: '回到顶部', text_size: '字号', size_0: '字号：标准', size_1: '字号：大', size_2: '字号：特大',
    theme_auto: '外观：跟随系统', theme_light: '外观：浅色', theme_dark: '外观：深色',
    peek: '速览答案', read_all: '阅读全文 ›', read_mark: '已读', group_count: '{n} 条 · 已读 {r}',
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
    modes: 'Sections', mode_bank: 'Interviews', mode_notes: 'Notes', search_notes: 'Search notes…', marked_only: 'Key', asked_only: 'Asked',
    asked_sort: 'Most asked', notes_count: '{n} notes', notes_all: 'All notes', all_chapters: 'All chapters', stat_notes: 'Notes',
    stat_marked: 'Key', stat_asked: 'Asked', empty_notes: 'No notes match.', marked: 'Key', asked_times: 'Asked {n}×',
    note_answer: 'Answer in the collection', no_note_answer: 'The collection gives no answer.', note_source: 'Source', source_line: '{file}, line {line}',
    imported: 'imported {d}', asked_in: 'Asked in interviews · {n}', related_notes: 'Related notes · {n}',
    relation_answers: 'Same question', relation_covers: 'Related topic',
    random: 'Random pick', random_hint: 'unread first', random_none: 'The list is empty.', fold_all: 'Collapse all', unfold_all: 'Expand all',
    to_top: 'Back to top', text_size: 'Text size', size_0: 'Text: normal', size_1: 'Text: large', size_2: 'Text: larger',
    theme_auto: 'Theme: system', theme_light: 'Theme: light', theme_dark: 'Theme: dark',
    peek: 'Peek at the answer', read_all: 'Read all ›', read_mark: 'Read', group_count: '{n} · {r} read',
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
  $('search').placeholder = t(state.mode === 'notes' ? 'search_notes' : 'search');
  applyTheme(stored('ibank-theme', 'auto'));
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
  // 'bank': your interview questions; 'notes': 八股 collections. Both share the list and the reader.
  mode: 'bank', notes: { collection: '', chapter: '', marked: false, asked: false, sort: 'order' }, notesData: null,
};
const launch = new URLSearchParams(location.hash.slice(1));
let token = launch.get('token');
const openOnLoad = launch.get('question') || launch.get('note');  // #question=q_… or #note=note_… opens one item directly
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

const isNote = id => String(id).startsWith('note_');

async function question(id) {
  // One cache for both kinds: note IDs and question IDs never collide.
  const path = (isNote(id) ? '/api/note?id=' : '/api/question?id=') + encodeURIComponent(id);
  if (!state.cache.has(id)) state.cache.set(id, api(path).catch(error => { state.cache.delete(id); throw error; }));
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
  groups.hidden = false;
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
  for (const key of ['total', 'answered', 'topics']) $(`stat-${key}-label`).textContent = t('stat_' + key);
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
    $('modes').hidden = $('side-modes').hidden = !data.notes?.total;
    $('account').textContent = data.account || data.name;
    $('side-logout').hidden = !data.can_logout;
    $('logout').hidden = !data.can_logout;
    if (state.mode !== 'bank') {
      if (data.notes?.total) return;
      setMode('bank');  // the notes were removed since last time
      return;
    }
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
  $('group-tools').hidden = true;
  for (const q of state.questions) {
    const meta = el('span', 'question-meta');
    meta.append(el('span', '', q.group), el('span', '', t('seen', { n: q.frequency })));
    if (answered(q.answer_status)) meta.append(el('span', 'has-answer', '✓ ' + t('status_answered')));
    list.append(listRow(q.id, q.canonical, meta));
  }
  if (!state.questions.length) list.append(el('li', 'empty', state.data?.summary.questions ? t('empty_filtered') : t('empty_bank')));
  $('more').hidden = state.questions.length >= (state.data?.total || 0);
}

const lastKey = () => state.mode === 'notes' ? 'ibank-last-note' : 'ibank-last';

function offerContinue() {
  const last = stored(lastKey(), null);
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
    if (isNote(q.id)) renderNote(q); else renderReading(q);
    document.body.classList.add('reading-open');
    $('reader').hidden = false;
    $('empty-reader').hidden = true;
    // On a phone the reader covers the list; the system back gesture closes it.
    const hash = (isNote(q.id) ? '#note=' : '#question=') + q.id;
    if (!wide.matches && opening && fromList) history.pushState({ reader: true }, '', location.pathname + hash);
    else history.replaceState(history.state, '', location.pathname + hash);
    const title = q.canonical || q.title;
    store(isNote(q.id) ? 'ibank-last-note' : 'ibank-last', { id: q.id, title: title.slice(0, 40) + (title.length > 40 ? '…' : '') });
    updateNav();
    $('reading').scrollTop = 0;
    updateProgress();
    markRead(q.id);
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
  if (q.notes?.length) reading.append(linkedNotes(q.notes));
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

// ---------------------------------------------------------------- notes (八股 collections)

const LIST_ITEM = /^(\s*)([-*+•]|\d+[.)、])\s+(.*)$/;
const indentOf = line => line.match(/^\s*/)[0].length;

function inline(target, text) {
  // Bold, code, links and <br>; everything else, including any HTML in the source, stays literal text.
  for (const part of String(text).split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\)|<br\s*\/?>)/gi)) {
    if (!part) continue;
    const link = part.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
    if (/^<br\s*\/?>$/i.test(part)) target.append(el('br'));
    else if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) target.append(el('strong', '', part.slice(2, -2)));
    else if (part.length > 2 && part.startsWith('`') && part.endsWith('`')) target.append(el('code', '', part.slice(1, -1)));
    else if (link) target.append(safeLink(link[2], link[1]) || document.createTextNode(link[1]));
    else target.append(document.createTextNode(part));
  }
}

function table(rows) {
  const cells = row => row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim());
  const parsed = rows.map(cells);
  const headed = parsed.length > 1 && parsed[1].every(cell => /^:?-+:?$/.test(cell));
  const node = el('table');
  const add = (parent, row, tag) => {
    const tr = el('tr');
    for (const cell of row) { const td = el(tag); inline(td, cell); tr.append(td); }
    parent.append(tr);
  };
  if (headed) { const head = el('thead'); add(head, parsed[0], 'th'); node.append(head); }
  const body = el('tbody');
  for (const row of parsed.slice(headed ? 2 : 0)) add(body, row, 'td');
  node.append(body);
  const wrap = el('div', 'table-wrap');
  wrap.append(node);
  return wrap;
}

function list(lines, start) {
  // A list and everything indented under its items: nested lists, paragraphs, quotes and code.
  const first = lines[start].match(LIST_ITEM);
  const indent = first[1].length;
  const node = el(/\d/.test(first[2]) ? 'ol' : 'ul');
  if (/\d/.test(first[2]) && parseInt(first[2], 10) > 1) node.start = parseInt(first[2], 10);
  let i = start;
  let item = null;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      const next = lines[i + 1];
      if (item && next !== undefined && next.trim() && indentOf(next) > indent) { i++; continue; }
      if (next !== undefined && LIST_ITEM.test(next) && indentOf(next) === indent) { i++; continue; }
      break;
    }
    const match = line.match(LIST_ITEM);
    if (match && match[1].length === indent) {
      item = el('li');
      inline(item, match[3]);
      node.append(item);
      i++;
    } else if (match && match[1].length > indent && item) {
      const [child, next] = list(lines, i);
      item.append(child);
      i = next;
    } else if (item && indentOf(line) > indent) {
      const block = [];
      const cut = indentOf(line);
      while (i < lines.length && lines[i].trim() && indentOf(lines[i]) > indent && !LIST_ITEM.test(lines[i])) {
        block.push(lines[i].slice(Math.min(cut, indentOf(lines[i]))));
        i++;
      }
      item.append(...Array.from(markdown(block.join('\n'), true).childNodes));
    } else {
      break;
    }
  }
  return [node, i];
}

function markdown(text, nested = false) {
  // Markdown as written in the collections: headings, lists, quotes, tables and code, built as DOM nodes.
  const root = el('div', nested ? '' : 'rich md');
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n');
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*(```|~~~)/.test(line)) {
      const fence = line.trim().slice(0, 3);
      const code = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence)) code.push(lines[i++]);
      i++;
      root.append(el('pre', '', code.join('\n')));
      continue;
    }
    if (!line.trim()) { i++; continue; }
    const heading = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (heading) {
      const node = el(heading[1].length <= 3 ? 'h3' : 'h4');
      inline(node, heading[2]);
      root.append(node);
      i++;
      continue;
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { root.append(el('hr')); i++; continue; }
    if (/^\s*>/.test(line)) {
      const quote = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) quote.push(lines[i++].replace(/^\s*>\s?/, ''));
      const box = el('blockquote');
      box.append(...Array.from(markdown(quote.join('\n'), true).childNodes));
      root.append(box);
      continue;
    }
    if (/^\s*\|/.test(line)) {
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
      root.append(table(rows));
      continue;
    }
    if (LIST_ITEM.test(line)) {
      const [node, next] = list(lines, i);
      root.append(node);
      i = next;
      continue;
    }
    const paragraph = el('p');
    let first = true;
    while (i < lines.length && lines[i].trim() && !/^\s*(```|~~~|>|\||#{1,6}\s)/.test(lines[i]) && !LIST_ITEM.test(lines[i])) {
      if (!first) paragraph.append(el('br'));
      inline(paragraph, lines[i++].trim());
      first = false;
    }
    root.append(paragraph);
  }
  return root;
}

function renderNote(n) {
  const reading = $('reading');
  reading.replaceChildren();
  const top = el('p', 'reading-meta');
  top.append(el('span', 'topic', n.chapter_title), el('span', '', [n.collection_title, n.group].filter(Boolean).join(' · ')));
  reading.append(top, el('h1', 'reading-title', n.title));
  const tags = el('div', 'tags');
  if (n.marked) tags.append(el('span', 'tag mark', t('marked')));
  if (n.asked) tags.append(el('span', 'tag asked', t('asked_times', { n: n.asked })));
  if (tags.childNodes.length) reading.append(tags);
  $('toggle-answer').hidden = !n.body;
  if (!n.body) {
    reading.append(el('p', 'no-answer', t('no_note_answer')), sourceBox(n.source));
  } else {
    const body = el('section', 'answer-body');
    body.append(el('h2', 'answer-head', t('note_answer')), markdown(n.body), sourceBox(n.source));
    reading.append(button(t('show_answer'), 'reveal button primary', () => setReveal(true)), body);
    setReveal(state.revealed);
  }
  if (n.questions.length) {
    const box = el('section', 'linked');
    box.append(el('h3', '', t('asked_in', { n: n.questions.length })));
    const items = el('ul', 'linked-list');
    for (const q of n.questions) {
      const entry = button('', 'linked-item', () => jump('bank', q.id));
      const meta = el('span', 'question-meta');
      meta.append(el('span', '', t('seen', { n: q.frequency })), el('span', '', t('relation_' + q.relation)));
      if (q.answered) meta.append(el('span', 'has-answer', '✓ ' + t('status_answered')));
      entry.append(el('span', 'linked-title', q.canonical), meta);
      const li = el('li');
      li.append(entry);
      items.append(li);
    }
    box.append(items);
    reading.append(box);
  }
}

function sourceBox(source) {
  // The collection's own answer is quoted as published; say where it came from.
  const box = el('p', 'note-source');
  box.append(el('strong', '', t('note_source') + '：'),
             document.createTextNode([source.collection, source.chapter, t('source_line', { file: source.file, line: source.line })].join(' › ')));
  const extra = [source.origin, t('imported', { d: date(source.imported_at) })].filter(Boolean).join(' · ');
  if (extra) box.append(el('small', '', extra));
  return box;
}

function linkedNotes(notes) {
  const box = el('section', 'linked');
  box.append(el('h3', '', t('related_notes', { n: notes.length })));
  const items = el('ul', 'linked-list');
  for (const n of notes) {
    const entry = button('', 'linked-item', () => jump('notes', n.id));
    const meta = el('span', 'question-meta');
    meta.append(el('span', '', n.where), el('span', '', t('relation_' + n.relation)));
    if (n.marked) meta.append(el('span', 'mark', t('marked')));
    entry.append(el('span', 'linked-title', n.title), meta);
    const li = el('li');
    li.append(entry);
    items.append(li);
  }
  box.append(items);
  return box;
}

function reload(reset = false) {
  return state.mode === 'notes' ? loadNotes(reset) : loadLibrary(reset);
}

function setMode(mode, keepReader = false) {
  state.mode = mode;
  store('ibank-mode', mode);
  document.body.classList.toggle('notes-mode', mode === 'notes');
  for (const tab of document.querySelectorAll('[data-mode]')) tab.setAttribute('aria-selected', String(tab.dataset.mode === mode));
  $('search').value = '';
  $('search').placeholder = t(mode === 'notes' ? 'search_notes' : 'search');
  $('chapter-intro').hidden = true;
  if (!keepReader) closeReader();
  return reload(true);
}

async function jump(mode, id) {
  // From a question to its notes and back; the list behind switches too, the reader stays open.
  if (state.mode !== mode) await setMode(mode, true);
  openQuestion(id);
}

async function loadNotes(reset = false) {
  const generation = ++state.load;
  if (reset) { state.offset = 0; state.questions = []; }
  $('question-list').setAttribute('aria-busy', 'true');
  message('error', '');
  try {
    const f = state.notes;
    // Notes load whole (a few hundred short cards), so chapters can fold and count what was read.
    const query = new URLSearchParams({ offset: state.offset, limit: NOTES_PAGE, sort: f.sort });
    // A search looks through every collection; the chosen chapter comes back when the search is cleared.
    const words = $('search').value.trim();
    if (words) query.set('query', words);
    if (f.collection && !words) query.set('collection', f.collection);
    if (f.collection && f.chapter !== '' && !words) query.set('chapter', f.chapter);
    if (f.marked) query.set('marked', '1');
    if (f.asked) query.set('asked', '1');
    const data = await api('/api/notes?' + query);
    if (generation !== state.load) return;
    state.notesData = data;
    state.ids = data.ids;
    state.questions = state.offset ? [...state.questions, ...data.notes] : data.notes;
    renderNoteFilters(data);
    $('result-count').textContent = t('notes_count', { n: data.total });
    renderNoteList();
    offerContinue();
    if (state.current && !state.ids.includes(state.current) && wide.matches) closeReader();
    else updateNav();
  } catch (error) {
    if (generation === state.load) message('error', error.message || t('connection'));
  } finally {
    if (generation === state.load) $('question-list').setAttribute('aria-busy', 'false');
  }
}

function pickNotes(changes) {
  if ('collection' in changes || 'chapter' in changes) $('search').value = '';
  Object.assign(state.notes, changes);
  store('ibank-notes', state.notes);
  loadNotes(true);
}

function renderNoteFilters(data) {
  const searching = Boolean($('search').value.trim());
  const f = searching ? { ...state.notes, collection: '', chapter: '' } : state.notes;
  const current = data.collections.find(c => c.name === f.collection);
  // Phones: a row of collections and, inside one, a row of its chapters.
  const collections = $('collections');
  collections.replaceChildren();
  for (const item of [{ name: '', title: t('notes_all'), total: data.summary.notes }, ...data.collections]) {
    const chip = button('', 'chip' + (f.collection === item.name ? ' active' : ''), () => pickNotes({ collection: item.name, chapter: '' }));
    chip.append(el('span', '', item.title), el('small', '', String(item.total)));
    chip.setAttribute('aria-pressed', String(f.collection === item.name));
    collections.append(chip);
  }
  const groups = $('groups');
  groups.replaceChildren();
  groups.hidden = !current;
  if (current) {
    for (const chapter of [{ index: '', title: t('all_chapters'), count: current.total }, ...current.chapters]) {
      const active = String(f.chapter) === String(chapter.index);
      const chip = button('', 'chip' + (active ? ' active' : ''), () => pickNotes({ chapter: String(chapter.index) }));
      chip.append(el('span', '', chapter.title), el('small', '', String(chapter.count)));
      chip.setAttribute('aria-pressed', String(active));
      groups.append(chip);
    }
    groups.querySelector('.active')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }
  const chapter = current && f.chapter !== '' ? current.chapters[Number(f.chapter)] : null;
  $('chapter-intro').textContent = chapter?.intro ? chapter.intro.replace(/^\s*>\s?/gm, '').replace(/\*\*/g, '') : '';
  $('chapter-intro').hidden = !chapter?.intro;
  for (const [id, on] of [['marked-only', f.marked], ['asked-only', f.asked], ['asked-sort', f.sort === 'asked']]) $(id).setAttribute('aria-pressed', String(on));
  // Wide screens: the sidebar lists every collection with its chapters.
  for (const [key, label, value] of [['total', 'stat_notes', data.summary.notes], ['answered', 'stat_marked', data.summary.marked], ['topics', 'stat_asked', data.summary.asked]]) {
    $(`stat-${key}`).textContent = value;
    $(`stat-${key}-label`).textContent = t(label);
  }
  const side = $('side-notes');
  side.replaceChildren();
  const entry = (parent, label, count, active, action, cls = '') => {
    const node = button('', 'side-item' + cls + (active ? ' active' : ''), action);
    node.append(el('span', '', label), el('small', '', count === undefined ? '' : String(count)));
    parent.append(node);
  };
  const section = (title, key) => {
    const head = el('p', 'side-title', title);
    const body = el('div', 'side-list');
    side.append(head, body);
    foldable(head, body, key);
    return body;
  };
  const views = section(t('mode_notes'), 'side:notes');
  entry(views, t('notes_all'), data.summary.notes, !f.collection && !f.marked && !f.asked, () => pickNotes({ collection: '', chapter: '', marked: false, asked: false }));
  entry(views, t('marked_only'), data.summary.marked, f.marked, () => pickNotes({ marked: !f.marked }));
  entry(views, t('asked_only'), data.summary.asked, f.asked, () => pickNotes({ asked: !f.asked }));
  for (const c of data.collections) {
    const body = section(c.title, 'side:c:' + c.name);
    entry(body, t('all_chapters'), c.total, f.collection === c.name && f.chapter === '', () => pickNotes({ collection: c.name, chapter: '' }));
    for (const ch of c.chapters) {
      entry(body, ch.title, ch.count, f.collection === c.name && String(f.chapter) === String(ch.index),
            () => pickNotes({ collection: c.name, chapter: String(ch.index) }), ' side-sub');
    }
  }
}

function grouped() {
  // Chapter headers only where the list is in chapter order and spans several chapters.
  const f = state.notes;
  return f.sort === 'order' && !$('search').value.trim() && !(f.collection && f.chapter !== '');
}

function renderNoteList() {
  const list = $('question-list');
  list.replaceChildren();
  const groups = grouped();
  $('group-tools').hidden = !groups || !state.questions.length;
  let head = null;
  for (const n of state.questions) {
    const key = `${n.collection}:${n.chapter}`;
    if (groups && head?.dataset.group !== key) {
      head = el('li', 'group');
      head.dataset.group = key;
      head.dataset.label = state.notes.collection ? n.chapter_title : `${n.collection_title} › ${n.chapter_title}`;
      head.append(button('', 'group-head', () => { setFolded('list:' + key, !folded.has('list:' + key)); syncGroup(key); }));
      list.append(head);
    }
    const meta = el('span', 'question-meta');
    meta.append(el('span', '', n.group || n.chapter_title));
    if (n.marked) meta.append(el('span', 'mark', t('marked')));
    if (n.asked) meta.append(el('span', 'has-answer', t('asked_times', { n: n.asked })));
    const item = listRow(n.id, n.title, meta);
    if (groups) item.dataset.member = key;
    list.append(item);
  }
  for (const node of list.querySelectorAll('li.group')) syncGroup(node.dataset.group);
  if (!state.questions.length) list.append(el('li', 'empty', t('empty_notes')));
  $('more').hidden = state.questions.length >= (state.notesData?.total || 0);
}

// ---------------------------------------------------------------- list rows, folding and reading comfort

const NOTES_PAGE = 1000;
const THEMES = ['auto', 'light', 'dark'];
const read = new Set(stored('ibank-read', []));
const folded = new Set(stored('ibank-folded', []));

function highlight(target, text) {
  // Marks the search words in a title; the text itself stays plain text.
  const words = $('search').value.trim();
  if (!words) { target.textContent = text; return; }
  const pattern = new RegExp('(' + words.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
  for (const part of String(text).split(pattern)) {
    if (!part) continue;
    target.append(part.toLowerCase() === words.toLowerCase() ? el('mark', '', part) : document.createTextNode(part));
  }
}

function listRow(id, title, meta) {
  const item = el('li', 'row');
  const main = button('', 'question' + (state.current === id ? ' current' : '') + (read.has(id) ? ' read' : ''), () => openQuestion(id, true));
  main.dataset.id = id;
  const heading = el('span', 'question-title');
  highlight(heading, title);
  if (read.has(id)) meta.append(el('span', 'read-mark', t('read_mark')));
  main.append(heading, meta);
  const peek = button('⌄', 'peek', () => togglePeek(item, id, peek));
  peek.setAttribute('aria-label', t('peek'));
  peek.setAttribute('aria-expanded', 'false');
  item.append(main, peek);
  return item;
}

async function togglePeek(item, id, control) {
  // A quick look at the answer without leaving the list; opening the reader still marks it read.
  const open = item.querySelector('.peek-body');
  control.setAttribute('aria-expanded', String(!open));
  item.classList.toggle('peeking', !open);
  if (open) { open.remove(); return; }
  const body = el('div', 'peek-body', t('preparing'));
  item.append(body);
  try {
    const data = await question(id);
    body.replaceChildren();
    const text = isNote(id) ? data.body : data.answer?.short_answer;
    if (text) {
      const clip = el('div', 'peek-clip');
      clip.append(isNote(id) ? markdown(text) : richText(text));
      body.append(clip);
    } else {
      body.append(el('p', 'hint', t(isNote(id) ? 'no_note_answer' : 'no_answer')));
    }
    body.append(button(t('read_all'), 'link', () => openQuestion(id, true)));
  } catch (error) {
    body.textContent = error.message;
  }
}

function markRead(id) {
  if (read.has(id)) return;
  read.add(id);
  store('ibank-read', [...read].slice(-5000));
  const row = document.querySelector(`.question[data-id="${CSS.escape(id)}"]`);
  if (row) { row.classList.add('read'); row.querySelector('.question-meta').append(el('span', 'read-mark', t('read_mark'))); }
  const member = row?.closest('li')?.dataset.member;
  if (member) syncGroup(member);
}

function setFolded(key, on) {
  if (on) folded.add(key); else folded.delete(key);
  store('ibank-folded', [...folded]);
}

function syncGroup(key) {
  const list = $('question-list');
  const head = list.querySelector(`li.group[data-group="${CSS.escape(key)}"]`);
  if (!head) return;
  const on = folded.has('list:' + key);
  const members = [...list.querySelectorAll(`li[data-member="${CSS.escape(key)}"]`)];
  for (const item of members) item.hidden = on;
  const ids = members.map(item => item.querySelector('.question').dataset.id);
  const control = head.querySelector('.group-head');
  control.replaceChildren(el('span', 'chevron', '›'), el('span', 'group-title', head.dataset.label),
                          el('small', '', t('group_count', { n: ids.length, r: ids.filter(id => read.has(id)).length })));
  control.setAttribute('aria-expanded', String(!on));
}

function foldAll(on) {
  for (const head of $('question-list').querySelectorAll('li.group')) {
    setFolded('list:' + head.dataset.group, on);
    syncGroup(head.dataset.group);
  }
}

function foldable(title, body, key) {
  // Sidebar sections fold on a click or Enter; the choice is remembered on this device.
  title.classList.add('foldable');
  title.tabIndex = 0;
  title.setAttribute('role', 'button');
  const sync = () => {
    body.classList.toggle('folded', folded.has(key));
    title.setAttribute('aria-expanded', String(!folded.has(key)));
  };
  const toggle = () => { setFolded(key, !folded.has(key)); sync(); };
  title.addEventListener('click', toggle);
  title.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggle(); } });
  sync();
}

function randomPick() {
  // For a spare minute: any question of the current list, unread ones first.
  $('menu').hidden = true;
  const pool = state.ids.filter(id => id !== state.current);
  if (!pool.length) { toast(t('random_none')); return; }
  const unread = pool.filter(id => !read.has(id));
  const from = unread.length ? unread : pool;
  openQuestion(from[Math.floor(Math.random() * from.length)], true);
}

function applyTheme(theme) {
  if (theme === 'auto') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  $('theme').textContent = $('side-theme').textContent = t('theme_' + theme);
}

function cycleTheme() {
  const next = THEMES[(THEMES.indexOf(stored('ibank-theme', 'auto')) + 1) % THEMES.length];
  store('ibank-theme', next);
  applyTheme(next);
}

function updateProgress() {
  const reading = $('reading');
  const room = reading.scrollHeight - reading.clientHeight;
  $('read-progress').style.transform = `scaleX(${room > 0 ? Math.min(1, reading.scrollTop / room) : 0})`;
}

function listScrolled() {
  return wide.matches ? document.querySelector('.library').scrollTop : window.scrollY;
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
$('search').addEventListener('input', () => { clearTimeout(debounce); debounce = setTimeout(() => reload(true), 250); });
$('answered-only').addEventListener('click', () => {
  const on = $('answered-only').getAttribute('aria-pressed') !== 'true';
  $('answered-only').setAttribute('aria-pressed', String(on));
  store('ibank-answered-only', on);
  loadLibrary(true);
});
$('more').addEventListener('click', () => { state.offset = state.questions.length; reload(); });
$('continue').addEventListener('click', () => { const last = stored(lastKey(), null); if (last) openQuestion(last.id, true); });
for (const tabs of [$('modes'), $('side-modes')]) {
  tabs.addEventListener('click', event => {
    const tab = event.target.closest('[data-mode]');
    if (tab && tab.dataset.mode !== state.mode) setMode(tab.dataset.mode);
  });
}
$('marked-only').addEventListener('click', () => pickNotes({ marked: !state.notes.marked }));
$('asked-only').addEventListener('click', () => pickNotes({ asked: !state.notes.asked }));
$('asked-sort').addEventListener('click', () => pickNotes({ sort: state.notes.sort === 'asked' ? 'order' : 'asked' }));
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
  if (state.mode === 'notes') await loadNotes(true);
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
$('random').addEventListener('click', randomPick);
$('side-random').addEventListener('click', randomPick);
$('theme').addEventListener('click', () => { $('menu').hidden = true; cycleTheme(); });
$('side-theme').addEventListener('click', cycleTheme);
$('fold-all').addEventListener('click', () => foldAll(true));
$('unfold-all').addEventListener('click', () => foldAll(false));
$('text-size').addEventListener('click', () => {
  const size = (Number(stored('ibank-text-size', 0)) + 1) % 3;
  store('ibank-text-size', size);
  document.body.dataset.size = String(size);
  toast(t('size_' + size));
  updateProgress();
});
$('reading').addEventListener('scroll', updateProgress, { passive: true });
const showTop = () => { $('to-top').hidden = listScrolled() < 600; };
window.addEventListener('scroll', showTop, { passive: true });
document.querySelector('.library').addEventListener('scroll', showTop, { passive: true });
$('to-top').addEventListener('click', () => {
  if (wide.matches) document.querySelector('.library').scrollTo({ top: 0, behavior: 'smooth' });
  else window.scrollTo({ top: 0, behavior: 'smooth' });
});
for (const title of document.querySelectorAll('[data-fold]')) foldable(title, $(title.dataset.fold), 'side:' + title.dataset.fold);
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

applyTheme(stored('ibank-theme', 'auto'));
document.body.dataset.size = String(stored('ibank-text-size', 0));
$('think-first').checked = stored('ibank-think-first', false);
$('side-think-first').checked = $('think-first').checked;
placeFilters();
$('answered-only').setAttribute('aria-pressed', String(stored('ibank-answered-only', false)));
state.notes = { ...state.notes, ...stored('ibank-notes', {}) };
state.mode = openOnLoad ? (isNote(openOnLoad) ? 'notes' : 'bank') : stored('ibank-mode', 'bank') === 'notes' ? 'notes' : 'bank';
document.body.classList.toggle('notes-mode', state.mode === 'notes');
for (const tab of document.querySelectorAll('[data-mode]')) tab.setAttribute('aria-selected', String(tab.dataset.mode === state.mode));
closeReader();
offerResume();
loadLibrary(true)
  .then(() => {
    if (state.mode !== 'notes') return;
    $('search').placeholder = t('search_notes');
    return loadNotes(true);
  })
  .then(() => { if (openOnLoad) openQuestion(openOnLoad, true); });
