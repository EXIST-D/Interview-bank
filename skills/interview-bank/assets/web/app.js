'use strict';
// Interview Bank local reader. Talks only to the loopback server that served this page.
// Sections: text and helpers · API · library list · reader · human review · merge decisions · practice · events.

// ---------------------------------------------------------------- text

const TEXT = {
  'zh-CN': {
    skip: '跳到题库', sidebar: '题库导航', tagline: '每一次积累，都算数。', space: '个人空间',
    view_all: '全部题目', view_due: '待复习', view_weak: '待巩固', view_unseen: '尚未练习',
    note: '把收集的题目，<br>变成自己的知识。', note_small: '先想一想，再看答案。', local_bank: '本地题库',
    subtitle: '将零散的问题，整理成清晰的思路。', merges: '合并裁决', refresh: '刷新题库', refresh_title: '重新读取题库',
    start_practice: '开始练习', resume: '继续练习', discard: '放弃', summary: '题库概览',
    stat_total: '积累题目', stat_answered: '已收录参考答案', stat_domains: '知识领域', stat_due: '待复习 · 含未练习',
    controls: '搜索和筛选', search: '搜索题目或原始问法…', sort: '排序',
    sort_frequency: '出现频次', sort_recent: '最近更新', sort_title: '题目名称',
    f_domain: '领域', f_role: '岗位', f_technology: '技术栈', f_company: '公司', f_industry: '行业', f_answer: '答案',
    answer_any: '全部答案状态', reset: '重置', workspace: '题库阅读区', list: '题目清单', previous: '上一页', next: '下一页',
    footer_left: '思考在先，参考在后。', footer_right: '出现次数按收集记录统计',
    practice_title: '专注练习', close_practice: '结束并关闭练习', practice_intro: '从当前筛选结果中选题。先独立作答，再对照参考答案。',
    round_size: '本轮题数', round_5: '5 题 · 轻量热身', round_10: '10 题 · 专注一轮', round_20: '20 题 · 深入练习', begin_round: '开始这一轮',
    merge_title: '合并裁决', close: '关闭',
    merge_intro: 'Agent 不确定这些题是否相同。请逐条判断；裁决会先保存，由 Agent 应用后才写入题库。',
    status_source_backed: '有来源', status_reviewed: '人工审阅', status_missing: '待补写', status_ai_draft: 'AI 草稿', status_stale: '待重新核验',
    rating_again: '还不会', rating_hard: '有点难', rating_good: '基本掌握', rating_easy: '很熟悉',
    all_domain: '全部领域', all_role: '全部岗位', all_technology: '全部技术栈', all_company: '全部公司', all_industry: '全部行业',
    no_questions_here: '（暂无题目）', titles_all: '我的题库', titles_due: '待复习', titles_weak: '待巩固', titles_unseen: '尚未练习',
    connecting: '正在连接…', reading: '正在读取', count: '{n} 道', page: '{p} / {t}',
    answered_tip: '当前有效的有来源答案 {a} 题 · 待重新核验 {s} 题',
    notice_v1: '当前题库可浏览与临时练习。若要保存自评和复习进度，请让 Agent 先备份并升级题库到 V2。',
    notice_read_only: '当前以只读模式打开；练习不会保存到题库。',
    empty_filtered: '没有符合条件的题目。\n试试调整筛选条件。', empty_bank: '题库还是空的。\n请先让 Agent 导入一些面试题。',
    start_title: '从一个问题开始。', start_text: '选择题目查看参考答案与出处，也可以开始一组练习。',
    seen: '{n} 次出现', no_company: '公司未注明', back: '← 返回题目清单', seen_long: '出现 {n} 次',
    answer: '答案（参考）', collapse: '收起答案', expand: '展开答案',
    no_answer: '这道题还没有参考答案。可以请 Agent 为它搜索资料、核验后补写，再刷新题库。',
    draft_warning: 'AI 草稿 · 尚未完成来源核验。', stale_warning: '这份答案需要重新核验，请留意版本、题干变化与适用条件。',
    spoken: '口述版', follow_ups: '常见追问', mistakes: '易错点', deep_dive: '深入理解',
    origins: '原始问法与出处 · {n} 条记录', history: '最近练习 · {n} 条', no_note: '未填写作答笔记', next_review: '下次复习：{d}',
    no_practice: '还没有练习记录', practise_one: '练习这一题 ↗', problem: '原题链接 ↗',
    review: '人工审阅', review_hint: '只有你本人核对过这份答案后，才点击“人工审阅通过”。Agent 不能代替你完成这一步。',
    review_placeholder: '写下你核对了什么，例如：对照官方文档确认了要点 1–3。', review_label: '审阅说明',
    review_ok: '人工审阅通过', review_stale: '标记为待重新核验', review_need_note: '请先写一句你核对了什么。',
    review_saved: '已记录人工审阅', stale_saved: '已标记为待重新核验',
    mode_record: '自评和你填写的作答会保存到本地题库，用于后续复习。评分代表自我评价，不是 AI 自动判分。',
    mode_temporary: '本轮为临时练习，自评和作答不保存。若需持久记录，请使用 V2 题库并开启可写模式。',
    round_done: '这一轮，完成了。', round_summary: '练习 {n} 题 · 自评掌握 {k} 题 · 跳过 {s} 题',
    round_saved: '已提交的自评和作答已保存，下次复习日期已安排。', round_temporary: '本轮为临时练习，没有写入题库。',
    back_to_bank: '返回题库', preparing: '正在准备题目…', progress: '第 {i} / {n} 题 · {g}', progress_label: '本轮练习进度',
    my_answer: '我的思路（可选）', my_answer_placeholder: '先用自己的话回答，再查看参考答案。',
    reveal: '查看参考答案', rate: '对照答案后，你觉得自己掌握得如何？', skip_question: '跳过本题',
    retry_first: '请先重试保存；提交结果未确认时不能跳过。', load_failed: '题目暂时无法读取；请刷新或稍后重试。', retry_load: '重试读取',
    save_failed: '{e} 作答仍保留在页面；点击同一评价可重试保存。',
    close_unsaved: '提交结果尚未确认，关闭后请检查该题的练习记录。确定关闭吗？',
    close_unsubmitted: '已保存的练习会保留，当前未提交的作答将丢失。结束这一轮？',
    no_round: '当前筛选下没有可练习的题目。', reloaded: '已重新读取题库',
    resume_text: '上次的练习还没做完：第 {i} / {n} 题。',
    merge_none: '没有待裁决的合并。', merge_new: '新题', merge_existing: '已有题目', merge_reason: 'Agent 的理由：{r}',
    merge_same: '是同一题，合并', merge_related: '相关但不同', merge_distinct: '不同的题',
    merge_note: '你的判断依据（必填）', merge_need_note: '请写一句判断依据。',
    merge_saved: '已保存。全部裁决完成后，请让 Agent 运行：dedupe --resolve {run}，然后提交。',
    merge_decided: '已裁决：{a}', merge_count: '{n}',
    unreachable: '无法连接本地题库，请确认服务仍在运行。', failed: '操作未完成，请重试。', connection: '连接失败，请确认本地服务仍在运行。',
  },
  en: {
    skip: 'Skip to the bank', sidebar: 'Bank navigation', tagline: 'Every question counts.', space: 'Your space',
    view_all: 'All questions', view_due: 'Due for review', view_weak: 'Needs work', view_unseen: 'Not practised',
    note: 'Turn collected questions<br>into your own knowledge.', note_small: 'Think first, then read the answer.', local_bank: 'Local bank',
    subtitle: 'Scattered questions, organised into clear thinking.', merges: 'Merge decisions', refresh: 'Refresh', refresh_title: 'Reload the bank',
    start_practice: 'Practise', resume: 'Resume', discard: 'Discard', summary: 'Bank overview',
    stat_total: 'Questions', stat_answered: 'With reference answers', stat_domains: 'Topics', stat_due: 'Due · incl. unpractised',
    controls: 'Search and filters', search: 'Search questions or original wording…', sort: 'Sort',
    sort_frequency: 'Frequency', sort_recent: 'Recently updated', sort_title: 'Title',
    f_domain: 'Topic', f_role: 'Role', f_technology: 'Tech', f_company: 'Company', f_industry: 'Industry', f_answer: 'Answer',
    answer_any: 'Any answer status', reset: 'Reset', workspace: 'Reading area', list: 'Questions', previous: 'Previous', next: 'Next',
    footer_left: 'Think first, then compare.', footer_right: 'Frequency counts collected occurrences',
    practice_title: 'Focused practice', close_practice: 'End and close practice', practice_intro: 'Questions come from the current filter. Answer on your own first, then compare.',
    round_size: 'Questions', round_5: '5 · warm-up', round_10: '10 · one focused round', round_20: '20 · deep practice', begin_round: 'Start the round',
    merge_title: 'Merge decisions', close: 'Close',
    merge_intro: 'The agent was not sure these are the same question. Decide each one; decisions are saved first and only reach the bank after the agent applies them.',
    status_source_backed: 'Sourced', status_reviewed: 'Human-reviewed', status_missing: 'No answer', status_ai_draft: 'AI draft', status_stale: 'Needs recheck',
    rating_again: 'Don’t know', rating_hard: 'Hard', rating_good: 'Mostly', rating_easy: 'Easy',
    all_domain: 'All topics', all_role: 'All roles', all_technology: 'All tech', all_company: 'All companies', all_industry: 'All industries',
    no_questions_here: ' (no questions)', titles_all: 'My bank', titles_due: 'Due for review', titles_weak: 'Needs work', titles_unseen: 'Not practised',
    connecting: 'Connecting…', reading: 'Loading', count: '{n}', page: '{p} / {t}',
    answered_tip: '{a} currently valid sourced answers · {s} need a recheck',
    notice_v1: 'You can browse and practise without saving. To keep ratings and review dates, ask the agent to back up and upgrade this bank to V2.',
    notice_read_only: 'Opened read-only; practice is not saved.',
    empty_filtered: 'No questions match.\nTry other filters.', empty_bank: 'The bank is empty.\nAsk the agent to import some questions.',
    start_title: 'Start with a question.', start_text: 'Pick a question to read its reference answer and sources, or start a practice round.',
    seen: 'seen {n}×', no_company: 'company unknown', back: '← Back to the list', seen_long: 'Seen {n}×',
    answer: 'Answer (reference)', collapse: 'Hide answer', expand: 'Show answer',
    no_answer: 'No reference answer yet. Ask the agent to research and verify one, then refresh.',
    draft_warning: 'AI draft · not verified against sources.', stale_warning: 'This answer needs a recheck: mind versions, wording changes and scope.',
    spoken: 'Spoken version', follow_ups: 'Follow-up questions', mistakes: 'Common mistakes', deep_dive: 'Deeper dive',
    origins: 'Original wording and sources · {n}', history: 'Recent practice · {n}', no_note: 'No notes written', next_review: 'Next review: {d}',
    no_practice: 'Not practised yet', practise_one: 'Practise this one ↗', problem: 'Original problem ↗',
    review: 'Human review', review_hint: 'Press “Reviewed” only after you checked this answer yourself. The agent cannot do this for you.',
    review_placeholder: 'What did you check? e.g. points 1–3 against the official docs.', review_label: 'Review note',
    review_ok: 'Reviewed', review_stale: 'Mark as needing a recheck', review_need_note: 'Write one line about what you checked.',
    review_saved: 'Review recorded', stale_saved: 'Marked as needing a recheck',
    mode_record: 'Your self-ratings and notes are saved to the local bank for later review. Ratings are your own judgement, not AI grading.',
    mode_temporary: 'This round is not saved. Use a writable V2 bank to keep ratings.',
    round_done: 'Round complete.', round_summary: '{n} practised · {k} rated as known · {s} skipped',
    round_saved: 'Submitted ratings and notes are saved; review dates are scheduled.', round_temporary: 'Practice-only round; nothing was saved.',
    back_to_bank: 'Back to the bank', preparing: 'Preparing the question…', progress: 'Question {i} / {n} · {g}', progress_label: 'Round progress',
    my_answer: 'My answer (optional)', my_answer_placeholder: 'Answer in your own words before revealing the reference.',
    reveal: 'Show reference answer', rate: 'Compared with the answer, how well do you know it?', skip_question: 'Skip',
    retry_first: 'Retry saving first; the last submission is unconfirmed.', load_failed: 'The question could not be loaded; refresh or try again.', retry_load: 'Retry',
    save_failed: '{e} Your answer is still on the page; press the same rating to retry.',
    close_unsaved: 'The last submission is unconfirmed; check this question’s history after closing. Close anyway?',
    close_unsubmitted: 'Saved ratings stay; the unsubmitted answer will be lost. End the round?',
    no_round: 'No questions to practise under this filter.', reloaded: 'Bank reloaded',
    resume_text: 'Your last round is unfinished: question {i} of {n}.',
    merge_none: 'No merges are waiting for a decision.', merge_new: 'New question', merge_existing: 'Existing question', merge_reason: 'Agent’s reason: {r}',
    merge_same: 'Same question, merge', merge_related: 'Related, keep both', merge_distinct: 'Different questions',
    merge_note: 'Why (required)', merge_need_note: 'Write one line explaining your decision.',
    merge_saved: 'Saved. When all are decided, ask the agent to run: dedupe --resolve {run}, then commit.',
    merge_decided: 'Decided: {a}', merge_count: '{n}',
    unreachable: 'Cannot reach the local bank; is the server still running?', failed: 'That did not work; please retry.', connection: 'Connection failed; is the local server still running?',
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
  for (const node of document.querySelectorAll('[data-i18n-html]')) node.innerHTML = t(node.dataset.i18nHtml);  // trusted, from TEXT only
  for (const node of document.querySelectorAll('[data-i18n-placeholder]')) node.placeholder = t(node.dataset.i18nPlaceholder);
  for (const node of document.querySelectorAll('[data-i18n-title]')) node.title = t(node.dataset.i18nTitle);
  for (const node of document.querySelectorAll('[data-i18n-aria]')) node.setAttribute('aria-label', t(node.dataset.i18nAria));
  document.title = 'Interview Bank · ' + t('titles_all');
  setTitle();
  offerResume();
}

// ---------------------------------------------------------------- helpers

const $ = id => document.getElementById(id);
const filters = ['domain', 'role', 'technology', 'company', 'industry', 'answer_status'];
const state = { view: 'all', offset: 0, limit: 20, selected: null, data: null, load: 0, detail: 0, round: null };
const launch = new URLSearchParams(location.hash.slice(1));
let token = launch.get('token');
const openOnLoad = launch.get('question');  // #token=…&question=q_… opens one question directly
try { if (token) sessionStorage.setItem('ibank-token', token); else token = sessionStorage.getItem('ibank-token'); } catch (_) {}
if (location.hash) history.replaceState(null, '', location.pathname);

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
  toastTimer = setTimeout(() => message('toast', ''), 3500);
}

function badge(status) {
  const kind = ['source_backed', 'reviewed'].includes(status) ? 'good' : status === 'ai_draft' ? 'draft' : status === 'stale' ? 'stale' : '';
  return el('span', 'badge ' + kind, t('status_' + status));
}

function date(value) {
  return value ? new Date(value).toLocaleDateString(lang) : '';
}

function safeLink(url, title) {
  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) return null;
    const link = el('a', '', title || parsed.hostname);
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
  const root = el('div', 'answer-content');
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
    if (/^\s*(?:[-*]|\d+[.)、])\s+/.test(line)) {
      if (!list) { list = el('ul'); root.append(list); }
      target = el('li');
      list.append(target);
    } else {
      list = null;
      if (!line.trim()) continue;
      target = el('p');
      root.append(target);
    }
    const clean = line.replace(/^\s*(?:[-*]|\d+[.)、])\s+/, '').replace(/^#{1,6}\s+/, '');
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
  if (!response.ok) throw new Error(result.error || t('failed'));
  return result;
}

function params() {
  const query = new URLSearchParams({ view: state.view, sort: $('sort').value });
  if ($('search').value.trim()) query.set('query', $('search').value.trim());
  for (const name of filters) if ($(name).value) query.set(name, $(name).value);
  return query;
}

// ---------------------------------------------------------------- library list

function setTitle() {
  $('page-title').replaceChildren(document.createTextNode(t('titles_' + state.view)), el('span', 'title-dot', '.'));
}

function updateFacets(facets) {
  for (const [key, values] of Object.entries(facets)) {
    const value = $(key).value;
    $(key).replaceChildren(new Option(t('all_' + key), ''));
    for (const item of values) $(key).add(new Option(item.label + (item.count ? ` · ${item.count}` : ''), item.value));
    if (value && !values.some(v => v.value === value)) $(key).add(new Option(value + t('no_questions_here'), value));
    $(key).value = value;
  }
}

function placeholder() {
  const empty = el('div', 'reader-placeholder');
  empty.append(el('span', 'placeholder-icon', '↗'), el('h2', '', t('start_title')), el('p', '', t('start_text')));
  $('reader').replaceChildren(empty);
}

async function loadLibrary(reset = false) {
  const generation = ++state.load;
  ++state.detail;
  if (reset) state.offset = 0;
  $('question-list').setAttribute('aria-busy', 'true');
  message('error', '');
  try {
    const query = params();
    query.set('offset', state.offset);
    query.set('limit', state.limit);
    const data = await api('/api/library?' + query);
    if (generation !== state.load) return;
    if (data.total > 0 && state.offset >= data.total) {
      state.offset = Math.floor((data.total - 1) / state.limit) * state.limit;
      return loadLibrary();
    }
    if (!state.data || state.data.language !== data.language) applyLanguage(data.language);
    state.data = data;
    updateFacets(data.facets);
    $('bank-name').textContent = data.name;
    $('bank-name').title = data.name;
    $('version').textContent = 'v' + data.version;
    $('stat-total').textContent = data.summary.questions;
    $('stat-answered').textContent = data.summary.answer_count;
    $('stat-answered').parentElement.title = t('answered_tip', { a: data.summary.answered, s: data.summary.stale });
    $('stat-domains').textContent = data.summary.domains;
    $('stat-due').textContent = data.summary.due;
    for (const key of ['all', 'due', 'weak', 'unseen']) $('nav-' + key).textContent = data.summary[key === 'all' ? 'questions' : key];
    message('notice', data.schema_version === 1 ? t('notice_v1') : data.read_only ? t('notice_read_only') : '');
    $('result-count').textContent = t('count', { n: data.total });
    $('page-number').textContent = data.total ? t('page', { p: Math.floor(state.offset / state.limit) + 1, t: Math.ceil(data.total / state.limit) }) : '0 / 0';
    $('previous').disabled = state.offset === 0;
    $('next').disabled = state.offset + state.limit >= data.total;
    $('start-practice').disabled = data.total === 0;
    renderList(data);
    if (state.selected && data.questions.some(q => q.id === state.selected)) {
      await openQuestion(state.selected, false);
    } else {
      state.selected = null;
      document.querySelector('.workspace').classList.remove('has-selection');
      placeholder();
    }
    loadMerges();
  } catch (error) {
    if (generation === state.load) message('error', error.message || t('connection'));
  } finally {
    if (generation === state.load) $('question-list').setAttribute('aria-busy', 'false');
  }
}

function renderList(data) {
  $('question-list').replaceChildren();
  for (const q of data.questions) {
    const row = button('', 'question-row', () => openQuestion(q.id));
    row.dataset.id = q.id;
    row.setAttribute('aria-pressed', String(state.selected === q.id));
    if (state.selected === q.id) row.classList.add('selected');
    const top = el('div', 'row-top');
    top.append(el('span', '', q.group), el('span', 'frequency', t('seen', { n: q.frequency })));
    const bottom = el('div', 'row-bottom');
    bottom.append(badge(q.answer_status), el('span', 'row-company', q.companies.join(lang === 'en' ? ', ' : '、') || t('no_company')));
    row.append(top, el('div', 'row-title', q.canonical), bottom);
    $('question-list').append(row);
  }
  if (!data.questions.length) {
    $('question-list').append(el('div', 'empty-state', data.summary.questions ? t('empty_filtered') : t('empty_bank')));
  }
}

// ---------------------------------------------------------------- reader

function answer(q) {
  const wrap = el('div');
  if (!q.answer) {
    wrap.append(el('p', 'empty-answer', t('no_answer')));
    return wrap;
  }
  if (q.answer_status === 'ai_draft') wrap.append(el('p', 'answer-warning', t('draft_warning')));
  if (q.answer_status === 'stale') wrap.append(el('p', 'answer-warning', t('stale_warning')));
  wrap.append(richText(q.answer.short_answer));
  if (q.answer.code_example) wrap.append(richText('```\n' + q.answer.code_example + '\n```'));
  const links = el('div', 'source-links');
  for (const source of q.answer.sources || []) {
    const link = safeLink(source.url, '↗ ' + (source.title || source.url));
    if (link) links.append(link);
  }
  wrap.append(links);
  // Optional practice depth written with the answer; collapsed so the concise answer stays first.
  for (const [field, key] of [['spoken_answer', 'spoken'], ['follow_up_questions', 'follow_ups'], ['common_mistakes', 'mistakes'], ['deep_dive', 'deep_dive']]) {
    const value = q.answer[field];
    const text = Array.isArray(value) ? value.map(v => '- ' + v).join('\n') : String(value || '').trim();
    if (!text) continue;
    const box = el('details', 'answer-extra');
    box.append(el('summary', '', t(key)), richText(text));
    wrap.append(box);
  }
  return wrap;
}

async function openQuestion(id, focus = true) {
  const generation = ++state.detail;
  try {
    const q = await api('/api/question?id=' + encodeURIComponent(id));
    if (generation !== state.detail) return;
    state.selected = q.id;
    const reader = $('reader');
    reader.replaceChildren();
    for (const row of document.querySelectorAll('.question-row')) {
      row.classList.toggle('selected', row.dataset.id === q.id);
      row.setAttribute('aria-pressed', String(row.dataset.id === q.id));
    }
    document.querySelector('.workspace').classList.add('has-selection');
    reader.append(button(t('back'), 'text-button back-button', () => {
      document.querySelector('.workspace').classList.remove('has-selection');
      document.querySelector('.question-row.selected')?.focus();
    }));
    const top = el('div', 'reader-top');
    top.append(el('span', '', q.group), badge(q.answer_status));
    reader.append(top);
    const heading = el('h2', '', q.canonical);
    heading.tabIndex = -1;
    reader.append(heading);
    reader.append(el('p', 'metadata', [t('seen_long', { n: q.frequency }), q.companies.join(lang === 'en' ? ', ' : '、'), q.years.join(' / ')].filter(Boolean).join(' · ')));
    const tags = el('div', 'tags');
    for (const tech of q.technologies) tags.append(el('span', 'tag', tech));
    if (q.problem_url) {
      const link = safeLink(q.problem_url.url, t('problem'));
      if (link) { link.className = 'tag'; tags.append(link); }
    }
    reader.append(tags);

    const block = el('section', 'answer-block');
    const head = el('div', 'answer-heading');
    head.append(el('h3', '', t('answer')));
    const content = answer(q);
    const toggle = button(t('collapse'), 'text-button', () => {
      content.hidden = !content.hidden;
      toggle.textContent = content.hidden ? t('expand') : t('collapse');
      toggle.setAttribute('aria-expanded', String(!content.hidden));
    });
    toggle.setAttribute('aria-expanded', 'true');
    head.append(toggle);
    block.append(head, content);
    reader.append(block);
    if (state.data?.can_review && q.answer) reader.append(reviewControls(q));

    const origins = el('details');
    origins.append(el('summary', '', t('origins', { n: q.occurrences.length })));
    for (const occurrence of q.occurrences) {
      const node = el('div', 'occurrence', occurrence.text);
      let time = '';
      if (occurrence.locator) {
        const start = occurrence.locator.start_seconds ?? occurrence.locator.start;
        const end = occurrence.locator.end_seconds ?? occurrence.locator.end;
        if (start !== undefined && start !== null) time = `${start}s – ${end ?? '?'}s`;
      }
      node.append(el('small', '', [occurrence.platform, occurrence.type, occurrence.year, time].filter(Boolean).join(' · ')));
      origins.append(node);
    }
    reader.append(origins);

    if (q.history.length) {
      const history = el('details');
      history.append(el('summary', '', t('history', { n: q.history.length })));
      for (const item of q.history) {
        const node = el('div', 'occurrence', `${t('rating_' + item.rating)} · ${date(item.occurred_at)}\n${item.note || t('no_note')}`);
        node.append(el('small', '', t('next_review', { d: date(item.next_review_at) })));
        history.append(node);
      }
      reader.append(history);
    }
    const footer = el('div', 'reader-footer');
    footer.append(el('span', '', q.progress.next_review_at ? t('next_review', { d: date(q.progress.next_review_at) }) : t('no_practice')),
                  button(t('practise_one'), 'button small', () => singlePractice(q)));
    reader.append(footer);
    reader.scrollTop = 0;
    if (focus && matchMedia('(max-width:800px)').matches) heading.focus({ preventScroll: true });
  } catch (error) {
    message('error', error.message);
  }
}

// ---------------------------------------------------------------- human review

function reviewControls(q) {
  // Human review is the reader's own decision; the agent has no way to submit it.
  const box = el('details', 'review-box');
  box.append(el('summary', '', t('review')));
  const note = el('textarea', 'practice-response review-note');
  note.maxLength = 2000;
  note.placeholder = t('review_placeholder');
  note.setAttribute('aria-label', t('review_label'));
  const actions = el('div', 'practice-actions');
  const send = async decision => {
    if (!note.value.trim()) { toast(t('review_need_note')); note.focus(); return; }
    actions.querySelectorAll('button').forEach(b => { b.disabled = true; });
    try {
      await api('/api/review', { question_id: q.id, answer_id: q.answer.id, decision, note: note.value });
      toast(decision === 'reviewed' ? t('review_saved') : t('stale_saved'));
      await loadLibrary();
    } catch (error) {
      message('error', error.message);
    } finally {
      actions.querySelectorAll('button').forEach(b => { b.disabled = false; });
    }
  };
  actions.append(button(t('review_ok'), 'button small primary', () => send('reviewed')),
                 button(t('review_stale'), 'text-button', () => send('stale')));
  box.append(el('p', 'hint', t('review_hint')), note, actions);
  return box;
}

// ---------------------------------------------------------------- merge decisions

async function loadMerges() {
  try {
    const { items } = await api('/api/dedupe-reviews');
    state.merges = items;
    const open = items.filter(item => !item.decision).length;
    $('open-merges').hidden = !items.length || state.data?.read_only;
    $('merge-count').textContent = open ? t('merge_count', { n: open }) : '✓';
    if ($('merge-dialog').open) renderMerges();
  } catch (_) {
    $('open-merges').hidden = true;
  }
}

function renderMerges() {
  const list = $('merge-list');
  list.replaceChildren();
  message('merge-error', '');
  if (!state.merges?.length) { list.append(el('p', 'hint', t('merge_none'))); return; }
  const labels = { MERGE_VARIANT: t('merge_same'), KEEP_RELATED: t('merge_related'), KEEP_DISTINCT: t('merge_distinct') };
  for (const item of state.merges) {
    const card = el('section', 'merge-item');
    const pair = el('div', 'merge-pair');
    for (const [label, text] of [[t('merge_new'), item.question], [t('merge_existing'), item.target]]) {
      const side = el('div', 'merge-side');
      side.append(el('small', '', label), el('p', '', text));
      pair.append(side);
    }
    card.append(pair, el('p', 'hint', t('merge_reason', { r: item.reason })));
    if (item.decision) {
      card.append(el('p', 'merge-decided', t('merge_decided', { a: labels[item.decision.action] })));
    } else {
      const note = el('textarea', 'practice-response review-note');
      note.maxLength = 2000;
      note.placeholder = t('merge_note');
      note.setAttribute('aria-label', t('merge_note'));
      const actions = el('div', 'practice-actions');
      for (const action of ['MERGE_VARIANT', 'KEEP_RELATED', 'KEEP_DISTINCT']) {
        actions.append(button(labels[action], action === 'MERGE_VARIANT' ? 'button small primary' : 'button small', async () => {
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
    const done = el('div', 'round-complete');
    done.append(el('div', 'complete-symbol', '✓'), el('h3', '', t('round_done')));
    const known = round.results.filter(r => r === 'good' || r === 'easy').length;
    done.append(el('p', '', t('round_summary', { n: round.results.length, k: known, s: round.questions.length - round.results.length }) + '\n'
                            + (state.data.can_record ? t('round_saved') : t('round_temporary'))));
    done.append(button(t('back_to_bank'), 'button primary', closePractice));
    body.append(done);
    return;
  }
  body.append(el('p', 'hint', t('preparing')));
  try {
    const q = await api('/api/question?id=' + encodeURIComponent(round.questions[round.index].id));
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
    body.append(bar);
    const title = el('h3', 'practice-question', q.canonical);
    title.tabIndex = -1;
    body.append(title);
    const label = el('label', 'response-label', t('my_answer'));
    label.htmlFor = 'practice-response';
    const response = el('textarea', 'practice-response');
    response.id = 'practice-response';
    response.maxLength = 10000;
    response.placeholder = t('my_answer_placeholder');
    body.append(label, response);
    const actions = el('div', 'practice-actions');
    const reveal = button(t('reveal'), 'button primary', () => {
      if (round.revealed) return;
      round.revealed = true;
      const reference = el('section', 'practice-reference');
      reference.append(el('h3', '', t('answer')), answer(q));
      body.append(reference, el('p', 'rating-label', t('rate')));
      const ratings = el('div', 'rating-buttons');
      for (const rating of RATINGS) ratings.append(button(t('rating_' + rating), '', () => saveRating(rating)));
      body.append(ratings);
      reveal.disabled = true;
      ratings.querySelector('button').focus({ preventScroll: true });
    });
    actions.append(reveal, button(t('skip_question'), 'text-button', () => {
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
  state.round = null;
  try { sessionStorage.removeItem(ROUND_KEY); } catch (_) {}
  $('practice-dialog').close();
  loadLibrary();
}

// ---------------------------------------------------------------- events

$('views').addEventListener('click', event => {
  const target = event.target.closest('[data-view]');
  if (!target) return;
  state.view = target.dataset.view;
  document.querySelectorAll('[data-view]').forEach(node => {
    node.classList.toggle('active', node === target);
    node.setAttribute('aria-current', node === target ? 'page' : 'false');
  });
  setTitle();
  loadLibrary(true);
});
let debounce;
$('search').addEventListener('input', () => { clearTimeout(debounce); debounce = setTimeout(() => loadLibrary(true), 250); });
for (const key of [...filters, 'sort']) $(key).addEventListener('change', () => loadLibrary(true));
$('clear-filters').addEventListener('click', () => {
  for (const name of filters) $(name).value = '';
  $('search').value = '';
  $('sort').value = 'frequency';
  loadLibrary(true);
});
$('refresh').addEventListener('click', async () => { await loadLibrary(); if ($('error').hidden) toast(t('reloaded')); });
$('previous').addEventListener('click', () => { state.offset = Math.max(0, state.offset - state.limit); loadLibrary(); });
$('next').addEventListener('click', () => { state.offset += state.limit; loadLibrary(); });
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
$('open-merges').addEventListener('click', () => { renderMerges(); $('merge-dialog').showModal(); });
$('close-merges').addEventListener('click', () => $('merge-dialog').close());
document.addEventListener('keydown', event => {
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
  if (event.key === '/' && !$('practice-dialog').open && !$('merge-dialog').open && !typing) {
    event.preventDefault();
    $('search').focus();
  }
});
window.addEventListener('beforeunload', event => {
  if (state.round && $('practice-response')?.value) { event.preventDefault(); event.returnValue = ''; }
});
offerResume();
loadLibrary().then(() => { if (openOnLoad) openQuestion(openOnLoad, false); });
