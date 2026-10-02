'use strict';
const $ = id => document.getElementById(id);
const filters = ['domain', 'role', 'technology', 'company', 'industry', 'answer_status'];
const answerLabels = {source_backed:'有来源', reviewed:'人工审阅', missing:'待补写', ai_draft:'AI 草稿', stale:'待重新核验'};
const ratingLabels = {again:'还不会', hard:'有点难', good:'基本掌握', easy:'很熟悉'};
const state = {view:'all', offset:0, limit:20, selected:null, data:null, load:0, detail:0, round:null};
let token = new URLSearchParams(location.hash.slice(1)).get('token');
try { if (token) sessionStorage.setItem('ibank-token',token); else token=sessionStorage.getItem('ibank-token'); } catch (_) {}
if (location.hash) history.replaceState(null,'',location.pathname);

function el(tag, cls, text) { const n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; }
function button(text, cls, action) { const b=el('button',cls,text); b.type='button';b.addEventListener('click',action);return b; }
function message(id,text) { $(id).textContent=text||'';$(id).hidden=!text; }
let toastTimer;
function toast(text) { message('toast',text);clearTimeout(toastTimer);toastTimer=setTimeout(()=>message('toast',''),3500); }
async function api(path,body) {
  const response=await fetch(path,{method:body?'POST':'GET',headers:{'X-Interview-Token':token||'',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,cache:'no-store'});
  let result;try{result=await response.json();}catch(_){throw new Error('无法连接本地题库，请确认服务仍在运行。');}
  if(!response.ok)throw new Error(result.error||'操作未完成，请重试。');return result;
}
function params() { const p=new URLSearchParams({view:state.view,sort:$('sort').value});if($('search').value.trim())p.set('query',$('search').value.trim());for(const f of filters)if($(f).value)p.set(f,$(f).value);return p; }
function badge(status) { return el('span','badge '+(['source_backed','reviewed'].includes(status)?'good':status==='ai_draft'?'draft':status==='stale'?'stale':''),answerLabels[status]||status); }
function date(value) { return value?new Date(value).toLocaleDateString('zh-CN'):''; }
function safeLink(url,title) {
  try{const u=new URL(url);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)return null;const a=el('a','',title||u.hostname);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch(_){return null;}
}
function richText(text) {
  // A deliberately small Markdown subset; source HTML is always literal text.
  const root=el('div','answer-content'); let code=null,list=null;
  for(const line of String(text||'').split('\n')){
    if(/^\s*```/.test(line)){if(code){root.append(code);code=null;}else{code=el('pre');}list=null;continue;}
    if(code){code.textContent+=line+'\n';continue;}
    let target;if(/^\s*(?:[-*]|\d+[.)、])\s+/.test(line)){if(!list){list=el('ul');root.append(list);}target=el('li');list.append(target);}else{list=null;if(!line.trim())continue;target=el('p');root.append(target);}
    const clean=line.replace(/^\s*(?:[-*]|\d+[.)、])\s+/,'').replace(/^#{1,6}\s+/,'');
    for(const part of clean.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)){if(part.startsWith('**')&&part.endsWith('**'))target.append(el('strong','',part.slice(2,-2)));else if(part.startsWith('`')&&part.endsWith('`'))target.append(el('code','',part.slice(1,-1)));else target.append(document.createTextNode(part));}
  }
  if(code)root.append(code);return root;
}
function answer(q) {
  const wrap=el('div');
  if(!q.answer){wrap.append(el('p','empty-answer','这道题还没有参考答案。可以请 Agent 为它搜索资料、核验后补写，再刷新题库。'));return wrap;}
  if(q.answer_status==='ai_draft')wrap.append(el('p','answer-warning','AI 草稿 · 尚未完成来源核验。'));
  if(q.answer_status==='stale')wrap.append(el('p','answer-warning','这份答案需要重新核验，请留意版本、题干变化与适用条件。'));
  wrap.append(richText(q.answer.short_answer));
  if(q.answer.code_example)wrap.append(richText('```\n'+q.answer.code_example+'\n```'));
  const links=el('div','source-links');for(const src of q.answer.sources||[]){const a=safeLink(src.url,'↗ '+(src.title||src.url));if(a)links.append(a);}wrap.append(links);
  // Optional practice depth written with the answer; collapsed so the concise answer stays first.
  for(const [field,title] of [['spoken_answer','口述版'],['follow_up_questions','常见追问'],['common_mistakes','易错点'],['deep_dive','深入理解']]){
    const value=q.answer[field];const text=Array.isArray(value)?value.map(v=>'- '+v).join('\n'):String(value||'').trim();if(!text)continue;
    const box=el('details','answer-extra');box.append(el('summary','',title),richText(text));wrap.append(box);
  }
  return wrap;
}
function reviewControls(q) {
  // Human review is the reader's own decision; the agent has no way to submit it.
  const box=el('details','review-box');box.append(el('summary','','人工审阅'));
  const note=el('textarea','practice-response review-note');note.maxLength=2000;note.placeholder='写下你核对了什么，例如：对照官方文档确认了要点 1–3。';note.setAttribute('aria-label','审阅说明');
  const actions=el('div','practice-actions');
  const send=async decision=>{
    if(!note.value.trim()){toast('请先写一句你核对了什么。');note.focus();return;}
    actions.querySelectorAll('button').forEach(b=>b.disabled=true);
    try{await api('/api/review',{question_id:q.id,answer_id:q.answer.id,decision,note:note.value});toast(decision==='reviewed'?'已记录人工审阅':'已标记为待重新核验');await loadLibrary();}
    catch(e){message('error',e.message);}finally{actions.querySelectorAll('button').forEach(b=>b.disabled=false);}
  };
  actions.append(button('人工审阅通过','button small primary',()=>send('reviewed')),button('标记为待重新核验','text-button',()=>send('stale')));
  box.append(el('p','hint','只有你本人核对过这份答案后，才点击“人工审阅通过”。Agent 不能代替你完成这一步。'),note,actions);return box;
}
function updateFacets(facets) {
  const labels={domain:'全部领域',role:'全部岗位',technology:'全部技术栈',company:'全部公司',industry:'全部行业'};
  for(const [key,values] of Object.entries(facets)){
    const value=$(key).value;$(key).replaceChildren(new Option(labels[key],''));
    for(const item of values)$(key).add(new Option(item.label+(item.count?` · ${item.count}`:''),item.value));
    if(value&&!values.some(v=>v.value===value))$(key).add(new Option(value+'（暂无题目）',value));$(key).value=value;
  }
}
async function loadLibrary(reset=false) {
  const generation=++state.load; ++state.detail; if(reset)state.offset=0;
  $('question-list').setAttribute('aria-busy','true');message('error','');
  try{
    const p=params();p.set('offset',state.offset);p.set('limit',state.limit);const data=await api('/api/library?'+p);
    if(generation!==state.load)return;
    if(data.total>0&&state.offset>=data.total){state.offset=Math.floor((data.total-1)/state.limit)*state.limit;return loadLibrary();}
    state.data=data;updateFacets(data.facets);$('bank-name').textContent=data.name;$('bank-name').title=data.name;$('version').textContent='v'+data.version;
    $('stat-total').textContent=data.summary.questions;$('stat-answered').textContent=data.summary.answer_count;$('stat-answered').parentElement.title=`当前有效的有来源答案 ${data.summary.answered} 题 · 待重新核验 ${data.summary.stale} 题`;$('stat-domains').textContent=data.summary.domains;$('stat-due').textContent=data.summary.due;
    for(const key of ['all','due','weak','unseen'])$('nav-'+key).textContent=data.summary[key==='all'?'questions':key];
    message('notice',data.schema_version===1?'当前题库可浏览与临时练习。若要保存自评和复习进度，请让 Agent 先备份并升级题库到 V2。':data.read_only?'当前以只读模式打开；练习不会保存到题库。':'');
    $('result-count').textContent=`${data.total} 道`;$('page-number').textContent=data.total?`${Math.floor(state.offset/state.limit)+1} / ${Math.ceil(data.total/state.limit)}`:'0 / 0';
    $('previous').disabled=state.offset===0;$('next').disabled=state.offset+state.limit>=data.total;$('start-practice').disabled=data.total===0;
    $('question-list').replaceChildren();
    for(const q of data.questions){
      const row=button('','question-row',()=>openQuestion(q.id));row.dataset.id=q.id;row.setAttribute('aria-pressed',String(state.selected===q.id));
      if(state.selected===q.id)row.classList.add('selected');
      const top=el('div','row-top');top.append(el('span','',q.group),el('span','frequency',`${q.frequency} 次出现`));
      const bottom=el('div','row-bottom');bottom.append(badge(q.answer_status),el('span','row-company',q.companies.join('、')||'公司未注明'));
      row.append(top,el('div','row-title',q.canonical),bottom);$('question-list').append(row);
    }
    if(!data.questions.length)$('question-list').append(el('div','empty-state',data.summary.questions?'没有符合条件的题目。\n试试调整筛选条件。':'题库还是空的。\n请先让 Agent 导入一些面试题。'));
    if(state.selected&&data.questions.some(q=>q.id===state.selected)){await openQuestion(state.selected,false);}else{state.selected=null;document.querySelector('.workspace').classList.remove('has-selection');$('reader').replaceChildren();const empty=el('div','reader-placeholder');empty.append(el('span','placeholder-icon','↗'),el('h2','','从一个问题开始。'),el('p','','选择题目查看参考答案与出处，也可以开始一组练习。'));$('reader').append(empty);}
  }catch(e){if(generation===state.load)message('error',e.message||'连接失败，请确认本地服务仍在运行。');}
  finally{if(generation===state.load)$('question-list').setAttribute('aria-busy','false');}
}
async function openQuestion(id,focus=true) {
  const generation=++state.detail;
  try{
    const q=await api('/api/question?id='+encodeURIComponent(id));if(generation!==state.detail)return;
    state.selected=q.id;const reader=$('reader');reader.replaceChildren();
    for(const row of document.querySelectorAll('.question-row')){row.classList.toggle('selected',row.dataset.id===q.id);row.setAttribute('aria-pressed',String(row.dataset.id===q.id));}
    document.querySelector('.workspace').classList.add('has-selection');
    reader.append(button('← 返回题目清单','text-button back-button',()=>{document.querySelector('.workspace').classList.remove('has-selection');document.querySelector('.question-row.selected')?.focus();}));
    const top=el('div','reader-top');top.append(el('span','',q.group),badge(q.answer_status));reader.append(top);
    const heading=el('h2','',q.canonical);heading.tabIndex=-1;reader.append(heading);
    reader.append(el('p','metadata',[`出现 ${q.frequency} 次`,q.companies.join('、'),q.years.join(' / ')].filter(Boolean).join(' · ')));
    const tags=el('div','tags');for(const t of q.technologies)tags.append(el('span','tag',t));reader.append(tags);
    const block=el('section','answer-block');const ah=el('div','answer-heading');ah.append(el('h3','','答案（参考）'));const content=answer(q);
    const toggle=button('收起答案','text-button',()=>{content.hidden=!content.hidden;toggle.textContent=content.hidden?'展开答案':'收起答案';toggle.setAttribute('aria-expanded',String(!content.hidden));});toggle.setAttribute('aria-expanded','true');ah.append(toggle);block.append(ah,content);reader.append(block);
    if(state.data?.can_review&&q.answer)reader.append(reviewControls(q));
    const sources=el('details');sources.append(el('summary','',`原始问法与出处 · ${q.occurrences.length} 条记录`));
    for(const o of q.occurrences){const n=el('div','occurrence',o.text);let time='';if(o.locator){const start=o.locator.start_seconds??o.locator.start;const end=o.locator.end_seconds??o.locator.end;if(start!==undefined)time=`${start}s – ${end??'?'}s`;}
      n.append(el('small','',[o.platform,o.type,o.year,time].filter(Boolean).join(' · ')));sources.append(n);}reader.append(sources);
    if(q.history.length){const history=el('details');history.append(el('summary','',`最近练习 · ${q.history.length} 条`));for(const h of q.history){const n=el('div','occurrence',`${ratingLabels[h.rating]} · ${date(h.occurred_at)}\n${h.note||'未填写作答笔记'}`);n.append(el('small','',`下次复习：${date(h.next_review_at)}`));history.append(n);}reader.append(history);}
    const footer=el('div','reader-footer');footer.append(el('span','',q.progress.next_review_at?'下次复习：'+date(q.progress.next_review_at):'还没有练习记录'),button('练习这一题 ↗','button small',()=>singlePractice(q)));reader.append(footer);
    reader.scrollTop=0;if(focus&&matchMedia('(max-width:800px)').matches)heading.focus({preventScroll:true});
  }catch(e){message('error',e.message);}
}
function preparePractice() {
  state.round=null;$('practice-setup').hidden=false;$('practice-body').hidden=true;message('practice-error','');
  $('practice-mode').textContent=state.data?.can_record?'自评和你填写的作答会保存到本地题库，用于后续复习。评分代表自我评价，不是 AI 自动判分。':'本轮为临时练习，自评和作答不保存。若需持久记录，请使用 V2 题库并开启可写模式。';
  $('practice-dialog').showModal();
}
function singlePractice(q) { preparePractice();startRound([q]); }
function startRound(questions) {
  state.round={questions,index:0,results:[],saving:false,current:null,revealed:false,pending:null};
  $('practice-setup').hidden=true;$('practice-body').hidden=false;renderRound();
}
async function renderRound() {
  const round=state.round;if(!round)return;message('practice-error','');
  const body=$('practice-body');body.replaceChildren();
  if(round.index>=round.questions.length){
    const done=el('div','round-complete');done.append(el('div','complete-symbol','✓'),el('h3','','这一轮，完成了。'));
    const count=round.results.filter(r=>r==='good'||r==='easy').length;
    done.append(el('p','',`练习 ${round.results.length} 题 · 自评掌握 ${count} 题 · 跳过 ${round.questions.length-round.results.length} 题\n${state.data.can_record?'已提交的自评和作答已保存，下次复习日期已安排。':'本轮为临时练习，没有写入题库。'}`));
    done.append(button('返回题库','button primary',closePractice));body.append(done);return;
  }
  body.append(el('p','hint','正在准备题目…'));
  try{
    const q=await api('/api/question?id='+encodeURIComponent(round.questions[round.index].id));if(state.round!==round)return;
    round.current=q;round.revealed=false;round.pending=null;body.replaceChildren();
    const bar=el('div','round-progress');bar.append(el('span','',`第 ${round.index+1} / ${round.questions.length} 题 · ${q.group}`));const meter=el('progress');meter.max=round.questions.length;meter.value=round.index;meter.setAttribute('aria-label','本轮练习进度');bar.append(meter);body.append(bar);
    const title=el('h3','practice-question',q.canonical);title.tabIndex=-1;body.append(title);
    const label=el('label','response-label','我的思路（可选）');label.htmlFor='practice-response';const response=el('textarea','practice-response');response.id='practice-response';response.maxLength=10000;response.placeholder='先用自己的话回答，再查看参考答案。';body.append(label,response);
    const actions=el('div','practice-actions');const reveal=button('查看参考答案','button primary',()=>{
      if(round.revealed)return;round.revealed=true;const reference=el('section','practice-reference');reference.append(el('h3','','答案（参考）'),answer(q));body.append(reference,el('p','rating-label','对照答案后，你觉得自己掌握得如何？'));
      const ratings=el('div','rating-buttons');for(const [rating,text] of Object.entries(ratingLabels))ratings.append(button(text,'',()=>saveRating(rating)));body.append(ratings);reveal.disabled=true;ratings.querySelector('button').focus({preventScroll:true});
    });actions.append(reveal,button('跳过本题','text-button',()=>{if(round.saving)return;if(round.pending){message('practice-error','请先重试保存；提交结果未确认时不能跳过。');return;}round.index++;renderRound();}));body.append(actions);title.focus({preventScroll:true});
  }catch(e){if(state.round===round){body.replaceChildren(el('p','hint','题目暂时无法读取；请刷新或稍后重试。'),button('重试读取','button',renderRound));message('practice-error',e.message);}}
}
async function saveRating(rating) {
  const round=state.round;if(!round||round.saving||!round.current)return;
  round.saving=true;message('practice-error','');
  const buttons=$('practice-body').querySelectorAll('button');buttons.forEach(b=>b.disabled=true);$('close-practice').disabled=true;$('practice-response').disabled=true;
  try{
    if(state.data.can_record){
      if(!round.pending)round.pending={question_id:round.current.id,revision:round.current.revision,rating,request_id:crypto.randomUUID(),note:$('practice-response').value,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC'};
      await api('/api/practice',round.pending);
    }
    round.results.push(round.pending?.rating||rating);round.index++;round.pending=null;await renderRound();
  }catch(e){message('practice-error',e.message+' 作答仍保留在页面；点击同一评价可重试保存。');}
  finally{round.saving=false;$('close-practice').disabled=false;buttons.forEach(b=>b.disabled=false);if($('practice-response'))$('practice-response').disabled=!!round.pending;}
}
function closePractice() {
  if(state.round?.saving)return;
  if(state.round?.pending&&!confirm('提交结果尚未确认，关闭后请检查该题的练习记录。确定关闭吗？'))return;
  if(!state.round?.pending&&state.round&&state.round.index<state.round.questions.length&&$('practice-response')?.value&&!confirm('已保存的练习会保留，当前未提交的作答将丢失。结束这一轮？'))return;
  state.round=null;$('practice-dialog').close();loadLibrary();
}
$('views').addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(!b)return;state.view=b.dataset.view;document.querySelectorAll('[data-view]').forEach(n=>{n.classList.toggle('active',n===b);n.setAttribute('aria-current',n===b?'page':'false');});const titles={all:'我的题库',due:'待复习',weak:'待巩固',unseen:'尚未练习'};$('page-title').replaceChildren(document.createTextNode(titles[state.view]),el('span','title-dot','.'));loadLibrary(true);});
let debounce;$('search').addEventListener('input',()=>{clearTimeout(debounce);debounce=setTimeout(()=>loadLibrary(true),250);});
for(const key of [...filters,'sort'])$(key).addEventListener('change',()=>loadLibrary(true));
$('clear-filters').addEventListener('click',()=>{for(const f of filters)$(f).value='';$('search').value='';$('sort').value='frequency';loadLibrary(true);});
$('refresh').addEventListener('click',async()=>{await loadLibrary();if($('error').hidden)toast('已重新读取题库');});
$('previous').addEventListener('click',()=>{state.offset=Math.max(0,state.offset-state.limit);loadLibrary();});
$('next').addEventListener('click',()=>{state.offset+=state.limit;loadLibrary();});
$('start-practice').addEventListener('click',preparePractice);
$('begin-round').addEventListener('click',async()=>{const b=$('begin-round');b.disabled=true;try{const p=params();p.set('limit',$('practice-limit').value);const r=await api('/api/practice?'+p);if(!r.questions.length)throw new Error('当前筛选下没有可练习的题目。');if($('practice-dialog').open)startRound(r.questions);}catch(e){message('practice-error',e.message);}finally{b.disabled=false;}});
$('close-practice').addEventListener('click',closePractice);
$('practice-dialog').addEventListener('cancel',e=>{e.preventDefault();closePractice();});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!$('practice-dialog').open&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('search').focus();}});
window.addEventListener('beforeunload',e=>{if(state.round&&$('practice-response')?.value){e.preventDefault();e.returnValue='';}});
loadLibrary();
