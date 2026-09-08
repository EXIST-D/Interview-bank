"""Version-two personal-bank state, preserved by the canonical transaction engine."""
import copy
import re

from .schema import require, string, timestamp
from .ids import utc_now, new_id

COLLECTIONS = ('policies', 'workflows', 'studysets', 'events', 'sessions', 'evidence')


def empty_state():
    return {'version': 2, **{name: {} for name in COLLECTIONS}}


def require_v2(data):
    require('_state' in data, 'This feature requires explicit migrate apply to format V2; migrate plan first')
    return data['_state']


def resolve(data, qid):
    q = next((q for q in data['questions'] if q['id'] == qid), None)
    require(q is not None, f'Unknown question: {qid}')
    return q['merged_into'] or qid


def question(data, qid):
    target = resolve(data, qid)
    return next(q for q in data['questions'] if q['id'] == target)


def revision(q):
    from .storage import fingerprint
    return fingerprint({k: q[k] for k in ('canonical', 'question_type', 'language')})


def record(collection, data, key):
    state = require_v2(data)
    require(isinstance(key, str) and key in state[collection], f'Unknown {collection} ID: {key}')
    return state[collection][key]


def validate_state(state, data):
    require(isinstance(state, dict) and set(state) == {'version', *COLLECTIONS} and state['version'] == 2, 'Invalid V2 state')
    qids = {q['id'] for q in data['questions']}
    oids = {o['id'] for o in data['occurrences']}
    for name in COLLECTIONS:
        require(isinstance(state[name], dict), f'{name}: expected object')
        for key, item in state[name].items():
            require(isinstance(key, str) and re.fullmatch(r'[a-z]+_[a-zA-Z0-9_-]+', key), 'Invalid state ID')
            require(isinstance(item, dict) and item.get('id') == key, 'State ID mismatch')
            timestamp(item.get('created_at'), f'{name}.created_at')
            if 'question_ids' in item:
                require(isinstance(item['question_ids'], list) and all(isinstance(x,str) for x in item['question_ids']) and len(set(item['question_ids'])) == len(item['question_ids']), 'Invalid question IDs')
                require(set(item['question_ids']) <= qids, 'State references missing questions')
            if 'question_id' in item:
                require(item['question_id'] in qids, 'State references missing question')
            if 'occurrence_ids' in item:
                require(isinstance(item['occurrence_ids'], list) and all(isinstance(x,str) for x in item['occurrence_ids']), 'Invalid occurrence scope')
                require(set(item['occurrence_ids']) <= oids, 'State references missing occurrences')
            if name == 'policies':
                require(item.get('kind') in ('protect', 'never_merge'), 'Invalid policy kind')
                require(type(item.get('active')) is bool, 'Invalid policy active')
                string(item.get('reason'), 'policy.reason')
                if item['kind'] == 'protect':
                    require(item.get('field') in ('canonical','domains','role_tracks','technologies','difficulty','report_exclusion') and 'value' in item and item.get('question_id') in qids, 'Invalid field protection')
                else:
                    require(len(item.get('question_ids', [])) == 2, 'Invalid forbidden pair')
            elif name == 'workflows':
                require(item.get('status') in ('running', 'paused', 'blocked', 'completed', 'cancelled'), 'Invalid workflow state')
                require(isinstance(item.get('items'), dict), 'Invalid workflow items')
                for field in ('question_revisions','initial_counts','initial_frequencies','scope_spec','limits'):
                    require(isinstance(item.get(field),dict), 'Invalid workflow '+field)
                require(isinstance(item.get('initial_answer_ids'),list), 'Invalid initial answers')
                require(type(item.get('batch_size')) is int and 1 <= item['batch_size'] <= 50, 'Invalid batch size')
                for qid, blocked in item['items'].items():
                    require(qid in qids and isinstance(blocked,dict), 'Invalid workflow blocker')
                    string(blocked.get('reason'), 'blocker.reason')
                    require(type(blocked.get('attempts')) is int and blocked['attempts'] > 0, 'Invalid attempt count')
            elif name == 'studysets':
                require(item.get('mode') in ('snapshot', 'dynamic'), 'Invalid studyset mode')
                string(item.get('name'), 'studyset.name')
                from .selection import validate_expression
                validate_expression(item.get('expression'))
                require(isinstance(item.get('requirements'),list) and isinstance(item.get('history'),list) and isinstance(item.get('question_revisions'),dict), 'Invalid studyset contents')
                require(type(item.get('selection_revision')) is int and item['selection_revision']>0,'Invalid selection revision')
            elif name == 'events':
                require(item.get('rating') in ('again', 'hard', 'good', 'easy'), 'Invalid study rating')
                timestamp(item.get('occurred_at'), 'event.occurred_at')
                timestamp(item.get('next_review_at'), 'event.next_review_at')
                string(item.get('request_id'),'event.request_id')
                string(item.get('question_revision'),'event.question_revision')
                require(type(item.get('interval_days')) is int and item['interval_days']>0,'Invalid review interval')
                require(item.get('session_id') is None or item['session_id'] in state['sessions'],'Invalid practice session')
            elif name == 'sessions':
                require(item.get('status') in ('running', 'completed', 'cancelled'), 'Invalid interview state')
                require(isinstance(item.get('responses'), list), 'Invalid interview responses')
                require(type(item.get('position')) is int and 0 <= item['position'] <= len(item['question_ids']), 'Invalid interview position')
                require(isinstance(item.get('prompts'),dict) and isinstance(item.get('question_revisions'),dict), 'Invalid frozen interview')
                require(set(item['prompts']) == set(item['question_ids']) == set(item['question_revisions']), 'Frozen prompt scope mismatch')
                requests = set()
                for response in item['responses']:
                    require(isinstance(response,dict) and response.get('question_id') in item['question_ids'], 'Invalid response scope')
                    for field in ('id','request_id','prompt','text'): string(response.get(field),'response.'+field)
                    require(response['request_id'] not in requests,'Duplicate interview request')
                    requests.add(response['request_id'])
                    require(type(response.get('follow_up')) is bool and 'feedback' in response,'Invalid response state')
            elif name == 'evidence':
                for field in ('url','title','publisher','type','accessed_at'): string(item.get(field),'evidence.'+field)
    requests = [e['request_id'] for e in state['events'].values()]
    require(len(set(requests)) == len(requests),'Duplicate practice request ID')


def enforce_policies(current, final, operation):
    if '_state' not in current or operation in ('policy', 'undo'):
        return
    for rule in current['_state']['policies'].values():
        if not rule['active']:
            continue
        # Explicit user override replaces the protected value in the same audited snapshot.
        updated = final['_state']['policies'].get(rule['id'])
        if operation == 'curate' and updated != rule:
            continue
        if rule['kind'] == 'never_merge':
            targets = {resolve(final, qid) for qid in rule['question_ids']}
            require(len(targets) == 2, f"Protected pair cannot merge: {rule['id']}; {rule['reason']}")
        else:
            q = question(final, rule['question_id'])
            require(q[rule['field']] == rule['value'], f"Protected field conflict: {rule['question_id']}.{rule['field']}; {rule['reason']}")


def policy(bank, action, payload=None, key=None):
    from .storage import open_bank
    from .runs import stage_snapshot
    payload = payload or {}
    with open_bank(bank) as (_, config, current):
        state = require_v2(current)
        if action == 'list':
            return {'policies': list(state['policies'].values())}
        final = copy.deepcopy(current)
        if action == 'disable':
            string(payload.get('reason'), 'reason')
            rule = record('policies', final, key)
            rule.update(active=False, disabled_reason=payload['reason'])
        else:
            require(action == 'add', 'Unknown policy action')
            require(payload.get('user_requested') is True, 'Policy requires an actual user instruction')
            string(payload.get('reason'), 'reason')
            kind = payload.get('kind')
            rule = {'id': new_id('pol'), 'created_at': utc_now(), 'kind': kind, 'active': True, 'reason': payload['reason']}
            if kind == 'protect':
                q = question(current, payload.get('question_id'))
                field = payload.get('field')
                require(field in ('canonical', 'domains', 'role_tracks', 'technologies', 'difficulty', 'report_exclusion'), 'Unsupported protected field')
                require(field in q, 'Set the field through curate before protecting it')
                rule.update(question_id=q['id'], field=field, value=copy.deepcopy(q[field]))
            else:
                require(kind == 'never_merge', 'Unknown policy kind')
                ids = payload.get('question_ids')
                require(isinstance(ids, list) and len(ids) == 2, 'A forbidden pair needs two IDs')
                ids = sorted({resolve(current, x) for x in ids})
                require(len(ids) == 2, 'Pair must contain distinct active targets')
                rule['question_ids'] = ids
            final['_state']['policies'][rule['id']] = rule
        return stage_snapshot(bank, current, final, config, operation='policy',
                              audit=[{'action': action, 'policy': rule}], summary={'policy_id': rule['id']})
