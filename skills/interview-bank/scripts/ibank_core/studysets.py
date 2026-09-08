"""Saved selections and evidence-linked JD requirement mappings."""
import copy
from .schema import require, string
from .state import require_v2, record, resolve, revision
from .ids import new_id, utc_now
from .storage import open_bank, fingerprint
from .runs import stage_snapshot
from .selection import validate_expression, apply_expression
from .editorial import exclusion_reason


def select(data, config, bank, expr=None, ids=None, limit=None, occurrence_ids=None):
    from .search import select_questions
    from .index import connect_index
    conn = connect_index(bank, data)
    try:
        rows = select_questions(conn, stale_days=config.get('answer_stale_days', 180), occurrence_ids=occurrence_ids)
    finally:
        conn.close()
    rows = [q for q in rows if not exclusion_reason(q)]
    if expr is not None:
        rows = apply_expression(rows, data['companies'], expr)
    if ids is not None:
        require(isinstance(ids, list) and all(isinstance(qid, str) for qid in ids), 'question_ids must be a string list')
        targets = {q['id']: q['merged_into'] or q['id'] for q in data['questions']}
        require(set(ids) <= targets.keys(), 'Unknown question ID in selection')
        selected = {targets[qid] for qid in ids}
        rows = [q for q in rows if q['id'] in selected]
    if limit is not None:
        require(type(limit) is int and limit > 0, 'limit must be positive')
        rows = rows[:limit]
    return rows


def requirements(payload, rows):
    source = payload.get('jd_text')
    specs = payload.get('requirements', [])
    require(isinstance(specs, list), 'requirements must be a list')
    if not specs:
        return []
    string(source, 'jd_text')
    by_id = {q['id']: q for q in rows}
    seen, result = set(), []
    for item in specs:
        require(isinstance(item, dict), 'Invalid JD requirement')
        string(item.get('id'), 'requirement.id')
        require(item['id'] not in seen, 'Duplicate requirement ID')
        seen.add(item['id'])
        string(item.get('quote'), 'requirement.quote')
        require(item['quote'] in source, 'JD quote must be an actual verbatim excerpt')
        require(item.get('priority') in ('must', 'nice', 'unspecified'), 'Invalid requirement priority')
        string(item.get('reason'), 'requirement.reason')
        mapped = item.get('matches', [])
        require(isinstance(mapped, list), 'matches must be a list')
        ids = set()
        for match in mapped:
            require(isinstance(match, dict) and match.get('question_id') in by_id, 'JD match must belong to selected questions')
            require(match['question_id'] not in ids, 'Duplicate JD mapping')
            ids.add(match['question_id'])
            require(match.get('coverage') in ('direct', 'partial', 'uncertain'), 'Invalid JD coverage')
            string(match.get('reason'), 'match.reason')
        result.append(copy.deepcopy(item))
    return result


def view(data, item):
    item = copy.deepcopy(item)
    questions = {q['id']: q for q in data['questions']}
    item['resolved_question_ids'] = list(dict.fromkeys(questions[qid]['merged_into'] or qid for qid in item['question_ids']))
    item['changed_questions'] = [qid for qid in item['resolved_question_ids'] if item['question_revisions'].get(qid) != revision(questions[qid])]
    # Keep historical evidence, but do not claim a changed/excluded question still covers a JD.
    for requirement in item['requirements']:
        for match in requirement['matches']:
            target = resolve(data, match['question_id'])
            match['resolved_question_id'] = target
            match['original_coverage'] = match['coverage']
            if target in item['changed_questions'] or exclusion_reason(questions[target]):
                match['coverage'] = 'uncertain'
                match['needs_recheck'] = True
    item['jd_coverage'] = {'requirements': len(item['requirements']),
                           'directly_covered': sum(any(m['coverage'] == 'direct' for m in r['matches']) for r in item['requirements']),
                           'uncovered': [r['id'] for r in item['requirements'] if not r['matches']]}
    return item


def studyset(bank, action, payload=None, key=None):
    payload = payload or {}
    with open_bank(bank) as (_, config, current):
        state = require_v2(current)
        if action == 'list':
            return {'studysets': [view(current, s) for s in state['studysets'].values()]}
        if action == 'show':
            return view(current, record('studysets', current, key))
        final = copy.deepcopy(current)
        if action == 'refresh':
            old = record('studysets', current, key)
            require(old['mode'] == 'dynamic', 'Snapshot sets do not refresh; create a new set')
            payload = {**old, **payload}
        else:
            require(action == 'create', 'Unknown studyset action')
            old = None
        string(payload.get('name'), 'name')
        string(payload.get('source_intent', ''), 'source_intent', empty=True)
        expr = payload.get('expression', {})
        validate_expression(expr)
        mode = payload.get('mode', 'snapshot')
        require(mode in ('snapshot', 'dynamic'), 'Invalid studyset mode')
        rows = select(current, config, bank, expr, payload.get('selected_ids'))
        mapped = requirements(payload, rows)
        if mapped:
            def relevance(q):
                direct_must = sum(r['priority']=='must' and any(m['question_id']==q['id'] and m['coverage']=='direct' for m in r['matches']) for r in mapped)
                direct = sum(any(m['question_id']==q['id'] and m['coverage']=='direct' for m in r['matches']) for r in mapped)
                return (-direct_must, -direct, -q['frequency'], q['canonical'], q['id'])
            rows.sort(key=relevance)
        limit = payload.get('limit')
        if limit is not None:
            require(type(limit) is int and limit > 0, 'limit must be positive')
            rows = rows[:limit]
        selected = {q['id'] for q in rows}
        for requirement in mapped:
            requirement['matches'] = [m for m in requirement['matches'] if m['question_id'] in selected]
        key = key if old else new_id('set')
        item = {'id': key, 'created_at': old['created_at'] if old else utc_now(), 'name': payload['name'], 'mode': mode,
                'source_intent': payload.get('source_intent', ''),
                'expression': expr, 'selected_ids': payload.get('selected_ids'), 'limit': payload.get('limit'),
                'question_ids': [q['id'] for q in rows], 'occurrence_ids': [o['id'] for q in rows for o in q['occurrences']], 'question_revisions': {q['id']: revision(q) for q in rows},
                'selection_revision': old['selection_revision']+1 if old else 1, 'bank_digest': fingerprint(current),
                'jd_text': payload.get('jd_text'), 'requirements': mapped,
                'history': [*old.get('history', []), {k: copy.deepcopy(v) for k, v in old.items() if k != 'history'}] if old else []}
        final['_state']['studysets'][key] = item
        return stage_snapshot(bank, current, final, config, operation='studyset', audit=[{'action': action, 'studyset_id': key}],
                              summary={'studyset_id': key, 'questions': len(rows), 'selection_revision': item['selection_revision']})


def export_set(bank, key, output, answers='both'):
    from .export import export_bank
    item = studyset(bank, 'show', key=key)
    # The snapshot keeps both IDs and matching source context. New questions are never added here.
    return export_bank(bank, output, answer_mode=answers, question_ids=item['resolved_question_ids'],
                       occurrence_ids=item['occurrence_ids'], report_context={'name': item['name'], 'selection_revision': item['selection_revision'],
                       'source_intent': item.get('source_intent', ''), 'changed_questions': item['changed_questions'],
                       'requirement_mappings': item['requirements'],
                       'jd_coverage': item['jd_coverage'], 'expression': item['expression'],
                       'requirements':[{'quote':r['quote'], 'priority':r['priority'],
                                        'coverage':'直接覆盖' if any(m['coverage']=='direct' for m in r['matches']) else '部分相关/待判断' if r['matches'] else '当前题库未覆盖'} for r in item['requirements']]})
