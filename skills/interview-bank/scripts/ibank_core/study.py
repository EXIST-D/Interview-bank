"""Append-only personal practice events and timezone-aware review queues."""
import copy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .schema import require, string, timestamp
from .state import require_v2, question, revision, resolve
from .ids import new_id, utc_now
from .storage import open_bank
from .runs import stage_snapshot


def user_zone(name):
    string(name, 'timezone')
    if name in ('UTC', 'Asia/Shanghai'):
        return timezone.utc if name == 'UTC' else timezone(timedelta(hours=8), name)
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        from .errors import ValidationError
        raise ValidationError('Timezone data unavailable; use UTC/Asia/Shanghai or install system timezone data') from exc


def event(data, payload):
    from .storage import fingerprint
    state = require_v2(data)
    q = question(data, payload.get('question_id'))
    string(payload.get('request_id'), 'request_id: stable ID for retries')
    prior = next((e for e in state['events'].values() if e['request_id'] == payload['request_id']), None)
    if prior:
        require(prior['request_digest'] == fingerprint(payload), 'Request ID reused for different practice')
        return prior, True
    rating = payload.get('rating')
    require(rating in ('again','hard','good','easy'), 'rating must be again/hard/good/easy')
    zone = payload.get('timezone', 'Asia/Shanghai')
    tz = user_zone(zone)
    at = payload.get('occurred_at', utc_now())
    timestamp(at, 'occurred_at')
    now = datetime.fromisoformat(at)
    require(now <= datetime.now(timezone.utc)+timedelta(minutes=5), 'Practice time cannot be in the future')
    history = sorted([e for e in state['events'].values() if resolve(data,e['question_id']) == q['id']], key=lambda e:(e['occurred_at'],e['id']))
    if history:
        require(now >= datetime.fromisoformat(history[-1]['occurred_at']), 'Backdated events would rewrite scheduling; submit in chronological order')
    revision_matches = history and history[-1]['question_revision'] == revision(q) and history[-1]['question_id'] == q['id']
    previous = history[-1]['interval_days'] if revision_matches else 0
    days = {'again':1, 'hard':max(1,previous), 'good':3 if previous < 3 else min(90,previous*2), 'easy':7 if previous < 7 else min(180,previous*2)}[rating]
    custom = payload.get('interval_days')
    if custom is not None:
        require(type(custom) is int and 1 <= custom <= 3650, 'interval_days must be 1..3650')
        days = custom
    due = now.astimezone(tz)+timedelta(days=days)
    if payload.get('next_review_at'):
        timestamp(payload['next_review_at'], 'next_review_at')
        due = datetime.fromisoformat(payload['next_review_at'])
        require(due > now, 'Next review must follow this practice')
    value = {'id':new_id('event'), 'created_at':utc_now(), 'request_id':payload['request_id'], 'request_digest':fingerprint(payload), 'question_id':q['id'],
             'question_revision':revision(q), 'rating':rating, 'timezone':zone, 'occurred_at':now.astimezone(timezone.utc).isoformat(),
             'next_review_at':due.astimezone(timezone.utc).isoformat(), 'interval_days':days,
             'session_id':payload.get('session_id'), 'note':payload.get('note',''), 'rating_source':'user_self_rating'}
    string(value['note'], 'note', empty=True)
    state['events'][value['id']] = value
    return value, False


def study(bank, action, payload=None):
    payload = payload or {}
    with open_bank(bank) as (_, config, current):
        state = require_v2(current)
        if action in ('queue','history'):
            if action == 'history':
                events = list(state['events'].values())
                if payload.get('question_id'):
                    qid = resolve(current,payload['question_id'])
                    events = [e for e in events if resolve(current,e['question_id']) == qid]
                return {'events':sorted(events,key=lambda e:(e['occurred_at'],e['id']))}
            from .studysets import select
            ids = payload.get('question_ids')
            if payload.get('studyset_id'):
                from .state import record
                ids = record('studysets',current,payload['studyset_id'])['question_ids']
            rows = select(current,config,bank,ids=ids)
            as_of = payload.get('as_of',utc_now())
            timestamp(as_of,'as_of')
            at = datetime.fromisoformat(as_of)
            tz = user_zone(payload.get('timezone','Asia/Shanghai'))
            queue = []
            targets = {q['id']:q['merged_into'] or q['id'] for q in current['questions']}
            histories = {}
            for e in state['events'].values():
                histories.setdefault(targets[e['question_id']], []).append(e)
            for q in rows:
                history = sorted(histories.get(q['id'], []),key=lambda e:(e['occurred_at'],e['id']))
                latest = history[-1] if history else None
                changed = bool(latest and (latest['question_revision'] != revision(q) or latest['question_id'] != q['id']))
                due = not latest or changed or datetime.fromisoformat(latest['next_review_at']) <= at
                if due or payload.get('include_future') is True:
                    queue.append({'question_id':q['id'],'canonical':q['canonical'],'due':due,
                                  'state':'unseen' if not latest else 'needs_repractice' if changed else 'mastered' if latest['rating'] in ('good','easy') else 'needs_practice',
                                  'next_review_at':datetime.fromisoformat(latest['next_review_at']).astimezone(tz).isoformat() if latest else None,
                                  'changed_since_practice':changed})
            return {'questions':sorted(queue,key=lambda q:(not q['due'],q['next_review_at'] or '',q['canonical'])),'timezone':str(tz)}
        require(action == 'record','Unknown study action')
        final = copy.deepcopy(current)
        value, repeated = event(final,payload)
        if repeated:
            return {'already_recorded':True,'event':value}
        return stage_snapshot(bank,current,final,config,operation='study',audit=[{'event':value}],summary={'event_id':value['id']})
