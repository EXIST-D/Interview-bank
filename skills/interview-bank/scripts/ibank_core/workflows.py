"""Persistent research scopes with receipt-derived progress and resumable batches."""
import copy
from datetime import datetime, timezone

from .schema import require, string, timestamp
from .state import require_v2, record, resolve, revision
from .storage import open_bank, read_json, bank_file, fingerprint, atomic_write, dumps
from .ids import new_id, utc_now
from .runs import stage_snapshot
from .studysets import select


def progress(bank, data, config, flow):
    rows = select(data, config, bank, ids=flow['question_ids'], occurrence_ids=flow['occurrence_ids'])
    items, ready = {}, []
    for q in rows:
        prior = flow['items'].get(q['id'], {})
        valid = q['answer_status'] in ('source_backed', 'reviewed') and bool(q['answer'] and q['answer']['sources'])
        state = 'committed' if valid and q['answer']['id'] not in flow['initial_answer_ids'] else 'reused' if valid else 'blocked' if prior.get('reason') else 'pending'
        items[q['id']] = {'state': state, 'canonical': q['canonical'], 'revision': revision(q),
                          'answer_id': q['answer']['id'] if q['answer'] else None, 'reason': None if valid else prior.get('reason'),
                          'attempts': prior.get('attempts', 0)}
        if valid:
            ready.append(q['id'])
    targets = {q['id']: q['merged_into'] or q['id'] for q in data['questions']}
    removed = [qid for qid in flow['question_ids'] if targets[qid] not in items]
    requested_status = flow['status']
    status = requested_status if requested_status in ('paused', 'cancelled') else 'completed' if len(ready) == len(items) and not removed else 'blocked' if any(v['state'] == 'blocked' for v in items.values()) or removed else 'running'
    return {**copy.deepcopy(flow), 'status': status, 'items': items, 'total': len(items), 'answered': len(ready),
            'remaining': len(items)-len(ready), 'excluded_since_creation': removed,
            'coverage': len(ready)/len(items) if items else None,
            'new_answers': sum(i['state'] == 'committed' for i in items.values())}


def progress_card(view):
    """Keep routine tool output bounded; full scope is available via show/export."""
    return {**{k:view[k] for k in ('id','name','status','scope_revision','total','answered','remaining','coverage','new_answers')},
            'blocked':sum(i['state']=='blocked' for i in view['items'].values()),
            'excluded_since_creation':len(view['excluded_since_creation'])}


def workflow(bank, action, payload=None, key=None):
    payload = payload or {}
    with open_bank(bank) as (_, config, current):
        state = require_v2(current)
        if action == 'list':
            return {'workflows': [progress_card(progress(bank, current, config, f)) for f in state['workflows'].values()]}
        if action == 'show':
            return progress(bank, current, config, record('workflows', current, key))
        final = copy.deepcopy(current)
        if action == 'create':
            string(payload.get('name'), 'name')
            require(sum(k in payload for k in ('question_ids', 'studyset_id', 'from_run', 'expression')) == 1, 'Choose exactly one explicit scope')
            ids = payload.get('question_ids')
            set_revision = None
            occurrence_ids = None
            intake_receipt = None
            if 'studyset_id' in payload:
                s = record('studysets', current, payload['studyset_id'])
                ids, set_revision = s['question_ids'], s['selection_revision']
                occurrence_ids = s['occurrence_ids']
            if 'from_run' in payload:
                from .runs import run_path
                meta = read_json(run_path(bank, payload['from_run'])/'run.json')
                require(meta['status'] == 'committed', 'Intake scope requires a committed run')
                from .storage import read_jsonl
                occurrences = read_jsonl(run_path(bank, payload['from_run'])/'occurrences.jsonl')
                if meta.get('mode') == 'snapshot':
                    before = read_json(run_path(bank, payload['from_run'])/'before.json')
                    old_ids = {o['id'] for o in before['occurrences']}
                    occurrences = [o for o in occurrences if o['id'] not in old_ids]
                ids = list({o['question_id'] for o in occurrences})
                occurrence_ids = [o['id'] for o in occurrences]
                intake_receipt = read_json(run_path(bank, payload['from_run'])/'commit.json')
            rows = select(current, config, bank, payload.get('expression'), ids, occurrence_ids=occurrence_ids)
            limits = payload.get('limits', {})
            require(isinstance(limits, dict) and set(limits) <= {'max_questions', 'max_batches', 'deadline'}, 'Supported limits: max_questions, max_batches, deadline; host token usage is unavailable')
            for field in ('max_questions', 'max_batches'):
                if field in limits:
                    require(type(limits[field]) is int and limits[field] > 0, f'{field} must be positive')
            if 'deadline' in limits:
                timestamp(limits['deadline'], 'deadline')
            batch = payload.get('batch_size', 5)
            require(type(batch) is int and 1 <= batch <= 50, 'batch_size must be 1..50')
            key = new_id('wf')
            flow = {'id': key, 'created_at': utc_now(), 'name': payload['name'], 'status': 'running',
                    'question_ids': [q['id'] for q in rows], 'occurrence_ids': [o['id'] for q in rows for o in q['occurrences']], 'intake_receipt': intake_receipt, 'question_revisions': {q['id']: revision(q) for q in rows},
                    'initial_answer_ids': [a['id'] for a in current['answers']], 'initial_counts': {t: len(current[t]) for t in ('sources','questions','occurrences')},
                    'initial_frequencies': {q['id']: q['total_frequency'] for q in rows},
                    'scope_spec': copy.deepcopy(payload), 'scope_revision': 1, 'studyset_revision': set_revision,
                    'batch_size': batch, 'limits': limits, 'items': {}}
            final['_state']['workflows'][key] = flow
        else:
            flow = record('workflows', final, key)
            if action == 'revise':
                require('question_ids' in payload or 'expression' in payload, 'Revised scope must be explicit')
                string(payload.get('reason'), 'scope revision reason')
                rows = select(current,config,bank,payload.get('expression'),payload.get('question_ids'))
                flow.setdefault('scope_history', []).append({k:copy.deepcopy(flow[k]) for k in ('scope_revision','question_ids','occurrence_ids','scope_spec')})
                flow.update(question_ids=[q['id'] for q in rows], occurrence_ids=[o['id'] for q in rows for o in q['occurrences']],
                            question_revisions={q['id']:revision(q) for q in rows}, scope_revision=flow['scope_revision']+1,
                            scope_spec=copy.deepcopy(payload), status='running')
                flow['items']={qid:item for qid,item in flow['items'].items() if qid in flow['question_ids']}
            elif action in ('pause', 'resume', 'cancel'):
                require(flow['status'] != 'cancelled', 'Cancelled workflow cannot resume; create a new scope')
                flow['status'] = {'pause':'paused','resume':'running','cancel':'cancelled'}[action]
                if action == 'resume':
                    if payload.get('retry_blocked') is True:
                        flow['items'] = {}
                    if 'limits' in payload:
                        limits = payload['limits']
                        require(isinstance(limits, dict) and set(limits) <= {'max_questions','max_batches','deadline'}, 'Invalid limits')
                        for name, value in limits.items():
                            if name == 'deadline': timestamp(value, name)
                            else: require(type(value) is int and value > 0, 'Limit must be positive')
                        flow['limits'] = limits
            elif action == 'block':
                qid = resolve(current, payload.get('question_id'))
                require(qid in {resolve(current, x) for x in flow['question_ids']}, 'Question outside workflow')
                string(payload.get('reason'), 'reason')
                old = flow['items'].get(qid, {})
                flow['items'][qid] = {'reason': payload['reason'], 'attempts': old.get('attempts', 0)+1}
            else:
                require(action == 'reconcile', 'Unknown workflow action')
                view = progress(bank, current, config, flow)
                flow['status'] = view['status']
                flow['last_progress'] = {k: view[k] for k in ('total','answered','remaining','excluded_since_creation')}
        return stage_snapshot(bank, current, final, config, operation='workflow', audit=[{'action': action, 'workflow_id': key}], summary={'workflow_id': key})


def next_batch(bank, key):
    from .answers import research_task
    from .tasks import write_task
    # Generate under one lock using a compact packet, with the same digest rule as research.
    with open_bank(bank) as (_, config, data):
        flow = record('workflows', data, key)
        view = progress(bank, data, config, flow)
        if view['status'] in ('paused', 'cancelled', 'completed'):
            return {'workflow': progress_card(view), 'task': None, 'reason': view['status']}
        limits = flow['limits']
        if limits.get('deadline') and datetime.now(timezone.utc) >= datetime.fromisoformat(limits['deadline']):
            return {'workflow': progress_card(view), 'task': None, 'reason': 'deadline reached'}
        tasks = []
        for p in bank_file(bank, 'runs').glob('run_*/task.json'):
            task = read_json(p)
            if task.get('workflow_id') == key:
                tasks.append(task)
        for task in reversed(tasks):
            if task['base_digest'] == fingerprint(data) and task['config_digest'] == fingerprint(config):
                return {'workflow': progress_card(view), 'task': task, 'reused_task': True}
        if limits.get('max_batches') and len(tasks) >= limits['max_batches']:
            return {'workflow': progress_card(view), 'task': None, 'reason': 'max_batches reached'}
        remaining = limits.get('max_questions', len(view['items'])) - view['new_answers']
        if remaining <= 0:
            return {'workflow': progress_card(view), 'task': None, 'reason': 'max_questions reached'}
        ids = [qid for qid, item in view['items'].items() if item['state'] == 'pending'][:min(flow['batch_size'], remaining)]
        if not ids:
            return {'workflow': progress_card(view), 'task': None, 'reason': 'Remaining items need explicit blocker resolution'}
        rows = select(data, config, bank, ids=ids)
        items = [{'question': {k:q[k] for k in ('id','canonical','question_type','language','domains','technologies','answer_status')},
                  'previous_answer': ({k:q['answer'][k] for k in ('id','version','short_answer','sources')} if q['answer'] else None)} for q in rows]
        task = write_task(bank, 'research', data, config, items, workflow_id=key,
                          instruction='Read answer-policy.md. Actually read primary sources and verify every subquestion. Submit one answer or explicit skip for each item via answer and commit. Then workflow next; this batch is not the full assignment.')
        return {'workflow': progress_card(view), 'task': task}


def workflow_summary(bank, key, output='update.md'):
    from pathlib import Path
    from .export import md
    view = workflow(bank, 'show', key=key)
    with open_bank(bank) as (_, config, data):
        target = bank_file(bank, 'exports/'+output)
        require(target.resolve().is_relative_to(bank_file(bank,'exports').resolve()), 'Summary must be inside exports')
        counts = {t:len(data[t])-view['initial_counts'][t] for t in view['initial_counts']}
        result = {'workflow': view, 'intake_receipt': view['intake_receipt'], 'bank_changes_since_workflow_creation': counts,
                  'frequency_changes': {q['id']:q['total_frequency']-view['initial_frequencies'].get(q['id'],0) for q in select(data,config,bank,ids=view['question_ids'])}}
        text = f"# 本次整理进度\n\n{md(view['name'])}\n\n范围 {view['total']} 题；已有有效参考答案 {view['answered']} 题，剩余 {view['remaining']} 题。\n\n状态：{view['status']}。统计为收集记录，不是面试概率。\n"
        if view['intake_receipt']:
            added = view['intake_receipt'].get('counts', {})
            text += '\n本次入库回执：' + '；'.join(f'{label} {added.get(field, 0)} 条' for field, label in (('sources','新增来源'),('questions','新增题目'),('occurrences','新增收集记录'))) + '。\n'
        text += f"\n本范围新增有效答案 {view['new_answers']} 题；复用有效答案 {sum(i['state']=='reused' for i in view['items'].values())} 题。\n"
        blocked = [f"- {md(i['canonical'])}：{md(i['reason'])}" for i in view['items'].values() if i.get('reason')]
        if blocked: text += '\n待处理：\n\n'+'\n'.join(blocked)+'\n'
        atomic_write(target, text)
        atomic_write(target.with_name(target.name+'.json'), dumps(result)+'\n')
        return {'output': str(target), 'answered':view['answered'], 'remaining':view['remaining']}
