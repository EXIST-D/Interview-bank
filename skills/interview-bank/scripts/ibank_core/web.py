"""Optional loopback-only reader. No server framework or external assets; the page ships prebuilt.

The only model calls are the opt-in screenshot import (--ai-config), in web_intake."""
import copy
import hmac
import json
import re
import secrets
import socketserver
import threading
import webbrowser
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .catalog import display
from .errors import BankError, LockConflict
from .export import report_group
from .runs import commit_run, stage_snapshot, abandon_run
from .schema import require
from .state import revision, resolve
from .storage import open_bank, guard_bank_path
from .study import event
from .studysets import select
from .selection import apply_expression
from .messages import group_title, label, language
from .ai import BEIJING
from . import notes as notebook
from . import note_organization
from . import note_experiences
from . import fulltext
from . import my_answers
from . import personal
from .timestamps import parse_timestamp

ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'web'
ASSET_TYPES = {'.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8'}
ASSET_NAME = re.compile(r'/assets/[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.(?:js|css)')


def bundled_asset(path):
    """A built script or stylesheet of the reader (web/ builds them into assets/web/assets); nothing else is served."""
    if not ASSET_NAME.fullmatch(path):
        return None
    candidate = ASSETS / 'assets' / path.removeprefix('/assets/')
    folder = (ASSETS / 'assets').resolve()
    return candidate if candidate.is_file() and candidate.resolve().parent == folder else None
FILTERS = {'query', 'domain', 'role', 'technology', 'company', 'industry', 'answer_status', 'group'}
ANSWERED = ('source_backed', 'reviewed')
VIEWS = {'all', 'due', 'weak', 'unseen'}
NOTE_FILTERS = {'collection', 'chapter', 'query', 'marked', 'asked', 'sort', 'offset', 'limit',
                'area', 'topic', 'tag', 'kind', 'verification', 'view', 'section', 'company', 'year',
                'question_type', 'connection', 'experience_domain', 'meta'}


def progress(data, rows):
    latest = {}
    for item in data.get('_state', {}).get('events', {}).values():
        qid = resolve(data, item['question_id'])
        if qid not in latest or (item['occurred_at'], item['id']) > (latest[qid]['occurred_at'], latest[qid]['id']):
            latest[qid] = item
    now = datetime.now(timezone.utc)
    result = {}
    for q in rows:
        last = latest.get(q['id'])
        changed = bool(last and (last['question_revision'] != revision(q) or last['question_id'] != q['id']))
        result[q['id']] = {
            'state': 'unseen' if not last else 'changed' if changed else 'weak' if last['rating'] in ('again', 'hard') else 'familiar',
            'due': not last or changed or parse_timestamp(last['next_review_at']) <= now,
            'next_review_at': last['next_review_at'] if last else None,
            'rating': last['rating'] if last else None,
        }
    return result


def card(q, state, lang='zh-CN'):
    group = report_group(q)
    return {k: q[k] for k in ('id', 'canonical', 'frequency', 'answer_status', 'difficulty', 'updated_at')} | {
        'group': group_title(lang, group, q['domains'][0].split('.')[0] if q['domains'] else None),
        'revision': revision(q), 'progress': state, 'problem_url': q.get('problem_url'),
        'domains': [{'id': d, 'label': label(lang, 'domains', d, display('domains', d))} for d in q['domains']],
        'technologies': [display('technologies', t) for t in q['technologies']],
        'companies': [c['name'] for c in q['companies'] if c['id']],
        'years': sorted({o['event_date'][:4] for o in q['occurrences'] if o['event_date']}, reverse=True),
    }


def filtered(rows, companies, states, params):
    # 'group' is the report topic; answer_status 'answered' means any current sourced or reviewed answer.
    predicates = [{'field': k, 'values': list(ANSWERED) if (k, v) == ('answer_status', 'answered') else [v]}
                  for k, v in params.items() if k in FILTERS - {'group'} and v]
    if predicates:
        rows = apply_expression(rows, companies, {'all': predicates})
    if params.get('group'):
        rows = [q for q in rows if report_group(q) == params['group']]
    view = params.get('view', 'all')
    require(view in VIEWS, 'Unknown library view')
    if view != 'all':
        rows = [q for q in rows if states[q['id']]['due']] if view == 'due' else [
            q for q in rows if states[q['id']]['state'] in ({'weak', 'changed'} if view == 'weak' else {'unseen'})]
    order = params.get('sort', 'frequency')
    require(order in ('frequency', 'recent', 'title'), 'Unknown sort order')
    if order == 'recent':
        rows = sorted(rows, key=lambda q: (q['updated_at'], q['id']), reverse=True)
    elif order == 'title':
        rows = sorted(rows, key=lambda q: (q['canonical'], q['id']))
    return rows


class WebApp:
    def __init__(self, bank, read_only=False, allow_my_answers=False, allow_practice=False, ai_config=None, allow_intake=False):
        self.bank = guard_bank_path(bank)
        self.read_only = read_only
        # A hosted reader stays read-only for the bank but may let the person keep their own layer (notes, favourites,
        # learning state) and, separately, save practice ratings.
        self.allow_my_answers, self.allow_practice = allow_my_answers, allow_practice
        self.mutation_lock = threading.Lock()
        self.notes_cache = (None, None)
        self.notes_cache_lock = threading.Lock()
        with open_bank(self.bank, shared=True):
            pass
        # Screenshot import writes interview questions and draft answers, so a read-only reader needs --allow-intake.
        self.intake = None
        if ai_config and (not read_only or allow_intake):
            from .web_intake import IntakeJobs
            self.intake = IntakeJobs(self.bank, ai_config, self.mutation_lock)
        # Mock interviews use the same model, usage ledger and daily budget, and save as practice records.
        self.coach = None
        if self.intake and self.can_practise:
            from .web_interview import Coach
            self.coach = Coach(self.bank, ai_config, self.mutation_lock, self.intake.ledger)

    def intake_jobs(self):
        require(self.intake is not None, 'Screenshot import is not enabled on this server')
        return self.intake

    def interviews(self):
        require(self.coach is not None, 'AI mock interviews are not enabled on this server')
        return self.coach

    def interview_overview(self):
        coach = self.interviews()
        with open_bank(self.bank, shared=True) as (manifest, _config, _data):
            require(manifest['schema_version'] == 2, 'Mock interviews need a V2 bank')
        return coach.overview()

    def interview_start(self, payload):
        """Questions chosen by the person (IDs) or by direction (the library's filters); the session keeps only IDs."""
        coach = self.interviews()
        require(isinstance(payload, dict) and set(payload) <= {'mode', 'question_ids', 'filters', 'limit', 'order', 'direction', 'reasons', 'jd', 'name'},
                'Invalid interview payload')
        meta = {k: payload[k] for k in ('direction', 'reasons', 'jd') if payload.get(k) is not None}
        require(isinstance(meta.get('direction', ''), str) and len(meta.get('direction', '')) <= 200, 'Invalid direction')
        ids = payload.get('question_ids')
        if payload.get('filters') is not None:
            require(ids is None, 'Choose either question_ids or filters')
            filters = payload['filters']
            require(isinstance(filters, dict) and set(filters) <= FILTERS | {'view'} and all(isinstance(v, str) for v in filters.values()), 'Unknown filter')
            limit, order = payload.get('limit', 10), payload.get('order', 'frequency')
            require(type(limit) is int and 1 <= limit <= 20 and order in ('frequency', 'random'), 'limit is 1..20; order is frequency or random')
            with open_bank(self.bank, shared=True) as (manifest, config, data):
                require(manifest['schema_version'] == 2, 'Mock interviews need a V2 bank')
                rows = select(data, config, self.bank)
                found = filtered(rows, data['companies'], progress(data, rows), filters)
            # Questions with a sourced or reviewed answer first: only they can be judged confidently.
            from .web_interview import has_reference
            groups = [[q for q in found if has_reference(q)], [q for q in found if not has_reference(q)]]
            if order == 'random':
                import random
                for group in groups:
                    random.shuffle(group)
            ids = [q['id'] for q in (groups[0] + groups[1])[:limit]]
            require(bool(ids), '没有符合条件的题')
        return coach.start({'name': payload.get('name'), 'question_ids': ids, 'mode': payload.get('mode', 'mock'), 'meta': meta})

    # ---- preparation: most-asked ranking, companies, saved job-description lists ---------------------------------
    def prepare_top(self, params):
        """Questions by how often (and how recently) they were asked, within the library's filters."""
        from . import web_prepare as prep
        extra = {'window', 'half_life', 'order', 'offset', 'limit'}
        require(set(params) <= FILTERS | {'view'} | extra, 'Unknown filter')
        window, order = params.get('window', 'all'), params.get('order', 'weighted')
        half_life, limit, offset = int(params.get('half_life', 365)), int(params.get('limit', 30)), int(params.get('offset', 0))
        require(1 <= limit <= 100 and offset >= 0, 'Invalid pagination (limit 1..100)')
        with open_bank(self.bank, shared=True) as (manifest, config, data):
            rows = select(data, config, self.bank)
            states = progress(data, rows)
            found = filtered(rows, data['companies'], states, {k: v for k, v in params.items() if k in FILTERS | {'view'}})
            ranked = prep.rank(found, datetime.now(BEIJING).date(), half_life, window, order)
            lang = language(config)
            # Without any interview date, recency cannot be weighed and a time window would be empty: the page says so.
            dated = sum(1 for q in found for o in q['occurrences'] if prep.occurrence_day(o.get('event_date')))
            return {'dated': dated, 'occurrences': sum(len(q['occurrences']) for q in found), 'total': len(ranked), 'offset': offset, 'limit': limit, 'window': window, 'order': order, 'half_life': half_life,
                    'unknown_weight': prep.UNKNOWN_WEIGHT, 'undated': sum(r['undated'] for r in ranked),
                    'questions': [{**card(r['q'], states[r['q']['id']], lang), 'rank': offset + n + 1, 'count': r['count'], 'score': r['score'],
                                   'companies_n': r['companies'], 'last_year': r['last_year']}
                                  for n, r in enumerate(ranked[offset:offset + limit])]}

    def prepare_companies(self):
        from . import web_prepare as prep
        with open_bank(self.bank, shared=True) as (_, config, data):
            rows = select(data, config, self.bank)
            lang = language(config)
            index = prep.company_index(rows, data['companies'])
            for entry in index:
                entry['domains'] = [{'id': d['id'], 'count': d['count'], 'label': label(lang, 'domains', d['id'], display('domains', d['id']))} for d in entry['domains']]
            return {'companies': index, 'total': len(index)}

    def prepare_company(self, params):
        from . import web_prepare as prep
        require(set(params) == {'id'}, 'Expected company ID')
        with open_bank(self.bank, shared=True) as (_, config, data):
            company = next((c for c in data['companies'] if c['id'] == params['id']), None)
            require(company is not None, '这家公司已经不在题库里')
            rows = select(data, config, self.bank)
            states = progress(data, rows)
            lang = language(config)
            entries = prep.company_questions(rows, company['id'], datetime.now(BEIJING).date())
            summary = next((c for c in prep.company_index(rows, data['companies']) if c['id'] == company['id']), None)
            for entry in summary['domains']:
                entry['label'] = label(lang, 'domains', entry['id'], display('domains', entry['id']))
            return {'id': company['id'], 'name': company['name'], 'summary': summary, 'total': len(entries),
                    'questions': [{**card(e['q'], states[e['q']['id']], lang), 'count': e['count'], 'score': e['score'],
                                   'rounds': e['rounds'], 'years_here': e['years']} for e in entries]}

    def prepare_lists(self):
        from .studysets import view
        with open_bank(self.bank, shared=True) as (manifest, config, data):
            require(manifest['schema_version'] == 2, '备考清单需要 V2 题库')
            items = sorted(data['_state']['studysets'].values(), key=lambda i: i['created_at'], reverse=True)
            lists = []
            for item in items:
                shown = view(data, item)
                lists.append({'id': item['id'], 'name': item['name'], 'created_at': item['created_at'], 'intent': item.get('source_intent', ''),
                              'questions': len(shown['resolved_question_ids']), 'changed': len(shown['changed_questions']),
                              'requirements': shown['jd_coverage']['requirements'], 'covered': shown['jd_coverage']['directly_covered'],
                              'has_jd': bool(item.get('jd_text'))})
            return {'lists': lists, 'can_save': self.coach is not None and self.can_practise}

    def prepare_list(self, params):
        from .studysets import view
        require(set(params) == {'id'}, 'Expected list ID')
        with open_bank(self.bank, shared=True) as (manifest, config, data):
            require(manifest['schema_version'] == 2, '备考清单需要 V2 题库')
            item = data['_state']['studysets'].get(params['id'])
            require(item is not None, '这份备考清单不存在')
            shown = view(data, item)
            rows = {q['id']: q for q in select(data, config, self.bank, ids=shown['resolved_question_ids'])}
            states = progress(data, list(rows.values()))
            lang = language(config)
            ordered = [rows[qid] for qid in shown['resolved_question_ids'] if qid in rows]
            titles = {qid: q['canonical'] for qid, q in rows.items()}
            requirements = []
            for r in shown['requirements']:
                matches = [{'question_id': m['resolved_question_id'], 'title': titles.get(m['resolved_question_id']), 'coverage': m['coverage'],
                            'reason': m['reason'], 'needs_recheck': bool(m.get('needs_recheck'))} for m in r['matches']]
                requirements.append({'id': r['id'], 'quote': r['quote'], 'priority': r['priority'], 'matches': matches})
            counts = Counter(states[q['id']]['state'] for q in ordered)
            return {'id': item['id'], 'name': item['name'], 'created_at': item['created_at'], 'intent': item.get('source_intent', ''),
                    'requirements': requirements, 'coverage': shown['jd_coverage'], 'changed': shown['changed_questions'],
                    'summary': {'questions': len(ordered), 'unseen': counts['unseen'], 'weak': counts['weak'] + counts['changed'], 'familiar': counts['familiar'],
                                'due': sum(states[q['id']]['due'] for q in ordered)},
                    'questions': [card(q, states[q['id']], lang) for q in ordered]}

    def prepare_save(self, payload):
        """Keep the picks of a finished job-description selection as a saved list (a snapshot `studyset`)."""
        from . import web_prepare as prep
        coach = self.interviews()
        require(isinstance(payload, dict) and set(payload) == {'plan_id', 'question_ids', 'name'}, 'Invalid list payload')
        require(isinstance(payload['plan_id'], str) and isinstance(payload['name'], str) and isinstance(payload['question_ids'], list)
                and all(isinstance(i, str) for i in payload['question_ids']), 'Invalid list payload')
        name = payload['name'].strip() or f"JD 备考 {datetime.now(BEIJING):%m-%d %H:%M}"
        require(len(name) <= 120 and 1 <= len(payload['question_ids']) <= 30, '名称最长 120 字，题数 1 到 30')
        jd, picks, uncovered = coach.plan_basis(payload['plan_id'], payload['question_ids'])
        return {'id': prep.save_list(self.bank, self.mutation_lock, name, jd, picks, uncovered)}

    def interview_plan(self, payload):
        coach = self.interviews()
        from .web_interview import has_reference
        with open_bank(self.bank, shared=True) as (manifest, config, data):
            require(manifest['schema_version'] == 2, 'Mock interviews need a V2 bank')
            candidates = [{'id': q['id'], 'canonical': q['canonical'], 'frequency': q['frequency'], 'answered': has_reference(q)}
                          for q in select(data, config, self.bank)]
        return coach.plan(payload, candidates)

    @property
    def can_write_answer(self):
        return not self.read_only or self.allow_my_answers

    @property
    def can_practise(self):
        return not self.read_only or self.allow_practice

    def _notes(self, data):
        """Collections and links, parsed once per change. The caller holds the bank lock."""
        key = notebook.signature(self.bank)
        with self.notes_cache_lock:
            if self.notes_cache[0] != key:
                self.notes_cache = (key, notebook.load_notes(self.bank))
        return notebook.resolve_links(self.notes_cache[1], data)

    def warm(self):
        """Parse the notes and build the search index in the background, so the first visitor does not wait."""
        def run():
            try:
                with open_bank(self.bank, shared=True) as (_, _config, data):
                    fulltext.prepare(self.bank, self._notes(data))
            except Exception:  # A failed warm-up only means the first search builds the index itself.
                pass
        threading.Thread(target=run, name='ibank-warm', daemon=True).start()

    def library(self, params, practice=False):
        require(set(params) <= FILTERS | {'view', 'sort', 'offset', 'limit'}, 'Unknown filter')
        limit = int(params.get('limit', 20 if not practice else 10))
        offset = int(params.get('offset', 0))
        require(1 <= limit <= 100 and offset >= 0, 'Invalid pagination (limit 1..100)')
        with open_bank(self.bank, shared=True) as (manifest, config, data):
            rows = select(data, config, self.bank)
            states = progress(data, rows)
            found = filtered(rows, data['companies'], states, params)
            if practice:
                return {'total': len(found), 'questions': [card(q, states[q['id']], language(config)) for q in found[offset:offset + limit]]}
            facets = {}
            for name, dimension, values in (
                ('domain', 'domains', [d for q in rows for d in set(q['domains'])]),
                ('technology', 'technologies', [t for q in rows for t in set(q['technologies'])]),
                ('role', 'role_tracks', [r for q in rows for r in {r for o in q['occurrences'] for r in o['role_tracks']}]),
            ):
                counts = Counter(values)
                facets[name] = [{'value': v, 'label': label(language(config), dimension, v, display(dimension, v)), 'count': n} for v, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
            groups = Counter(report_group(q) for q in rows)
            facets['group'] = [{'value': g, 'label': group_title(language(config), g, next((q['domains'][0].split('.')[0] for q in rows
                                if report_group(q) == g and q['domains']), None)), 'count': n}
                               for g, n in sorted(groups.items(), key=lambda x: (-x[1], x[0]))]
            company_counts = Counter(c['id'] for q in rows for c in q['companies'] if c['id'])
            facets['company'] = [{'value': c['id'], 'label': c['name'], 'count': company_counts[c['id']]} for c in data['companies'] if company_counts[c['id']]]
            used = [c for c in data['companies'] if company_counts[c['id']]]
            bundle = self._notes(data)
            mine = set(my_answers.texts(my_answers.load(self.bank), data))
            facets['industry'] = [{'value': v, 'label': display('industries', v)} for v in sorted({v for c in used for v in c['industries']})]
            return {
                'name': self.bank.name, 'version': __version__, 'schema_version': manifest['schema_version'],
                'can_record': manifest['schema_version'] == 2 and self.can_practise, 'can_review': not self.read_only,
                'can_write_answer': self.can_write_answer, 'can_write_personal': self.can_write_answer,
                'can_intake': self.intake is not None, 'can_prepare': True, 'can_interview': self.coach is not None and manifest['schema_version'] == 2,
                'can_research': bool(self.intake and self.intake.config.get('search')), 'language': language(config),
                'read_only': self.read_only, 'updated_at': manifest.get('last_updated_at'),
                'summary': {'questions': len(rows), 'answered': sum(q['answer_status'] in ('source_backed', 'reviewed') for q in rows),
                            'answer_count': sum(q['answer'] is not None for q in rows), 'stale': sum(q['answer_status'] == 'stale' for q in rows),
                            'due': sum(s['due'] for s in states.values()), 'weak': sum(s['state'] in ('weak', 'changed') for s in states.values()),
                            'unseen': sum(s['state'] == 'unseen' for s in states.values()), 'domains': len(facets['domain'])},
                'notes': {'total': len(bundle['notes']), 'collections': len(bundle['collections'])},
                'total': len(found), 'total_answered': sum(q['answer_status'] in ANSWERED for q in found),
                'offset': offset, 'limit': limit, 'facets': facets,
                # The whole filtered order, so the reader can step to the previous or next question across pages.
                'ids': [q['id'] for q in found],
                'questions': [{**card(q, states[q['id']], language(config)), 'has_my_answer': q['id'] in mine}
                              for q in found[offset:offset + limit]],
            }

    def public_library(self, params):
        """Bootstrap the public reader without disclosing the personal bank's name, counts or state."""
        require(set(params) <= FILTERS | {'view', 'sort', 'offset', 'limit'}, 'Unknown filter')
        limit, offset = int(params.get('limit', 20)), int(params.get('offset', 0))
        require(1 <= limit <= 100 and offset >= 0, 'Invalid pagination (limit 1..100)')
        with open_bank(self.bank, shared=True) as (manifest, config, data):
            bundle = self._notes(data)
        return {
            'name': 'Public library', 'version': __version__, 'schema_version': manifest['schema_version'],
            'language': language(config), 'guest': True, 'can_login': True, 'can_logout': False,
            'read_only': True, 'can_record': False, 'can_review': False,
            'can_write_answer': False, 'can_write_personal': False, 'can_intake': False, 'can_prepare': False, 'can_interview': False, 'can_research': False,
            'summary': dict.fromkeys(('questions', 'answered', 'answer_count', 'stale', 'due', 'weak', 'unseen', 'domains'), 0),
            'notes': {'total': len(bundle['notes']), 'collections': len(bundle['collections'])},
            'total': 0, 'total_answered': 0, 'offset': offset, 'limit': limit,
            'facets': {key: [] for key in ('group', 'domain', 'technology', 'company', 'role', 'industry')},
            'ids': [], 'questions': [],
        }

    def question(self, qid):
        with open_bank(self.bank, shared=True) as (_, config, data):
            rows = select(data, config, self.bank, ids=[qid])
            require(bool(rows), 'Question is no longer available; refresh the library')
            q = rows[0]
            sources = {s['id']: s for s in data['sources']}
            result = card(q, progress(data, rows)[q['id']], language(config))
            result['answer'] = q['answer']
            result['my_answer'] = my_answers.for_question(my_answers.load(self.bank), data, q['id'])
            bundle = self._notes(data)
            collections = {c['name']: c for c in bundle['collections']}
            notes = {n['id']: n for n in bundle['notes']}
            result['notes'] = [{'id': link['note_id'], 'relation': link['relation'], 'title': notes[link['note_id']]['title'],
                                'marked': bool(notes[link['note_id']]['marks']),
                                'where': f"{collections[notes[link['note_id']]['collection']]['title']} › "
                                         f"{notebook.chapter_title(collections[notes[link['note_id']]['collection']], notes[link['note_id']])}"}
                               for link in sorted(bundle['links'], key=lambda l: (l['relation'] != 'answers', notes[l['note_id']]['order']))
                               if link['question_id'] == q['id']]
            visible_notes = {}
            for edge in result['notes']:
                note = note_experiences.find(bundle, edge['id'])
                if note['id'] not in visible_notes:
                    visible_notes[note['id']] = {**edge, 'id': note['id'], 'title': note['title']}
            result['notes'] = list(visible_notes.values())
            result['occurrences'] = [{
                'text': o['original_text'], 'year': o['event_date'][:4] if o['event_date'] else None,
                'type': sources[o['source_id']]['type'], 'platform': sources[o['source_id']].get('platform'),
                'locator': o.get('locator'),
            } for o in q['occurrences']]
            history = [e for e in data.get('_state', {}).get('events', {}).values() if resolve(data, e['question_id']) == q['id']]
            result['history'] = [{k: e[k] for k in ('rating', 'occurred_at', 'next_review_at', 'note')} for e in sorted(history, key=lambda e: (e['occurred_at'], e['id']), reverse=True)[:20]]
            return result

    def notes(self, params, *, public=False):
        """八股 collections: chapters, filters and one page of note cards in reading order."""
        require(set(params) <= NOTE_FILTERS, 'Unknown filter')
        # Note cards are short: the reader loads a whole collection so chapters can fold.
        limit, offset = int(params.get('limit', 30)), int(params.get('offset', 0))
        require(1 <= limit <= 1000 and offset >= 0, 'Invalid pagination (limit 1..1000)')
        # meta=0: the caller already holds the source cards (hundreds of KB for large banks) and wants only the list.
        require(params.get('meta', '1') in ('0', '1'), 'meta must be 0 or 1')
        with open_bank(self.bank, shared=True) as (_, config, data):
            bundle = self._notes(data)
            rows = [] if public else select(data, config, self.bank)
        linked = notebook.linked_questions(bundle, rows)
        collections = {c['name']: c for c in bundle['collections']}
        section = params.get('section', 'all')
        found = note_experiences.select(bundle, section)
        # A collection remembered by the browser may have been removed since: show everything instead.
        if params.get('collection') in collections:
            found = [n for n in found if n['collection'] == params['collection']]
            if params.get('chapter', '') != '':
                found = [n for n in found if str(n['chapter']) == params['chapter']]
        scoped = found
        article_links = lambda n: note_experiences.linked(n, linked)
        for field in ('area', 'topic', 'verification', 'question_type'):
            if params.get(field):
                if field == 'verification':
                    require(params[field] in note_organization.VERIFICATIONS, 'Unknown verification state')
                if field == 'question_type':
                    require(params[field] in note_organization.QUESTION_TYPES, 'Unknown question type')
                found = [n for n in found if n['organization'][field] == params[field]]
        if params.get('tag'):
            found = [n for n in found if params['tag'] in n['organization']['tags']]
        if params.get('kind'):
            require(params['kind'] in (*note_organization.KINDS, *note_experiences.KINDS, 'study'), 'Unknown content kind')
            found = [n for n in found if n['organization']['kind'] != 'info'] if params['kind'] == 'study' else [
                n for n in found if n['organization']['kind'] == params['kind']]
        if params.get('company'):
            require(section == 'experiences' and len(params['company']) <= 160, 'Company filter needs public experiences')
            found = [n for n in found if (n['experience']['company'] or 'unknown') == params['company']]
        if params.get('year'):
            require(section == 'experiences' and (params['year'] == 'unknown' or
                    len(params['year']) == 4 and params['year'].isdigit()), 'Invalid interview year')
            found = [n for n in found if (n['experience']['year'] or 'unknown') == params['year']]
        if params.get('experience_domain'):
            require(section == 'experiences' and params['experience_domain'] in note_experiences.DOMAINS,
                    'Unknown public experience domain')
            found = [n for n in found if n['experience']['domain'] == params['experience_domain']]
        require(params.get('view', 'original') in ('original', 'knowledge'), 'Unknown notes view')
        if params.get('query', '').strip():
            found = fulltext.search(self.bank, bundle, found, params['query'])
        if params.get('marked') == '1':
            found = [n for n in found if n['marks']]
        if params.get('asked') == '1':
            found = [n for n in found if article_links(n)]
        if params.get('connection'):
            connection = params['connection']
            require(connection in ('any', 'personal', 'public', 'none'), 'Unknown connection scope')
            def matches(n):
                personal = bool(article_links(n))
                public = bool(n.get('study_notes') or n.get('public_experiences'))
                return {'any': personal or public, 'personal': personal, 'public': public,
                        'none': not personal and not public}[connection]
            found = [n for n in found if matches(n)]
        require(params.get('sort', 'order') in ('order', 'asked') or
                section == 'experiences' and params.get('sort') in ('recent', 'domain'), 'Unknown sort order')
        if params.get('sort') == 'asked':
            found = sorted(found, key=lambda n: -sum(q['frequency'] for q, _ in article_links(n)))
        elif params.get('sort') in ('recent', 'domain'):
            # Unknown interview years stay last. Publication/import dates are not interview dates.
            found = sorted(found, key=note_experiences.date_key, reverse=True)
            if params['sort'] == 'domain':
                order = list(note_experiences.DOMAINS)
                found = sorted(found, key=lambda n: order.index(n['experience']['domain']))
        elif params.get('view') == 'knowledge' and not params.get('query', '').strip():
            area_order = {(c['name'], a['id']): i for c in bundle['collections']
                          for i, a in enumerate(c.get('organization', {}).get('areas', []))}
            topic_order = {(c['name'], t['id']): i for c in bundle['collections']
                           for a in c.get('organization', {}).get('areas', []) for i, t in enumerate(a['topics'])}
            found = sorted(found, key=lambda n: (list(collections).index(n['collection']),
                           area_order.get((n['collection'], n['organization']['area']), 999),
                           topic_order.get((n['collection'], n['organization']['topic']), 999), n['order']))
        mine = set() if public else {key for key, entry in my_answers.load(self.bank).items()
                                    if key.startswith('note_') and entry.get('text')}
        card = lambda n: {**notebook.note_card(n, collections[n['collection']], [q for q, _ in article_links(n)]),
                          'has_my_answer': n['id'] in mine}
        learning = note_experiences.select(bundle, 'learning')
        result = {
            'section': section,
            **({'collections': [note_organization.collection_card(c, linked, section) for c in bundle['collections']]}
               if params.get('meta', '1') == '1' else {}),
            'summary': {'notes': len(bundle['notes']), 'marked': sum(bool(n['marks']) for n in bundle['notes']),
                        'asked': sum(n['id'] in linked for n in bundle['notes'])},
            'section_counts': {'knowledge': sum(n['organization']['kind'] != 'info' for n in note_experiences.select(bundle, 'knowledge')),
                               'learning': len(learning),
                               'experiences': len(note_experiences.select(bundle, 'experiences'))},
            'reading_groups_incomplete': sum(c.get('reading_groups_incomplete', 0) for c in bundle['collections']),
            'learning_categories': [{'kind': kind,
                                     'count': sum(n['organization']['kind'] == kind for n in learning),
                                     'sources': len({n['collection'] for n in learning if n['organization']['kind'] == kind})}
                                    for kind in note_organization.LEARNING_KINDS],
            'facets': {'tags': sorted({t for n in scoped for t in n['organization']['tags']}),
                       'kinds': dict(Counter(n['organization']['kind'] for n in scoped)),
                       'question_types': dict(Counter(n['organization'].get('question_type') for n in scoped
                                                      if n['organization'].get('question_type'))),
                       'verification': dict(Counter(n['organization']['verification'] for n in scoped)),
                       'companies': sorted({n['experience']['company'] for n in scoped if n.get('experience', {}).get('company')}),
                       'years': sorted({n['experience']['year'] for n in scoped if n.get('experience', {}).get('year')}, reverse=True),
                       'experience_domains': {key: count for key in note_experiences.DOMAINS
                                              if (count := sum(n.get('experience', {}).get('domain') == key for n in scoped))},
                       'experience_years': dict(Counter(n['experience']['year'] or 'unknown' for n in scoped if 'experience' in n)),
                       'unknown_company': any('experience' in n and not n['experience']['company'] for n in scoped),
                       'unknown_year': any('experience' in n and not n['experience']['year'] for n in scoped)},
            'total': len(found), 'offset': offset, 'limit': limit, 'ids': [n['id'] for n in found],
            'notes': [card(n) for n in found[offset:offset + limit]],
        }
        if public:
            from .public_reader import collection as public_collection
            if 'collections' in result:
                result['collections'] = [public_collection(c) for c in result['collections']]
        return result

    def note(self, note_id, *, public=False):
        with open_bank(self.bank, shared=True) as (_, config, data):
            bundle = self._notes(data)
            rows = [] if public else select(data, config, self.bank)
        note = note_experiences.find(bundle, note_id)
        require(note is not None, 'This note is no longer available; refresh the list')
        collection = next(c for c in bundle['collections'] if c['name'] == note['collection'])
        linked = note_experiences.linked(note, notebook.linked_questions(bundle, rows))
        linked.sort(key=lambda pair: (pair[1]['relation'] != 'answers', -pair[0]['frequency']))
        from .note_relations import detail
        section = 'experiences' if 'experience' in note else (
            'learning' if note['organization']['kind'] in note_organization.LEARNING_KINDS else 'knowledge')
        result = {**notebook.note_card(note, collection, [q for q, _ in linked]), **detail(note), 'body': note['body'],
                'section': section, 'my_answer': None if public else my_answers.for_note(my_answers.load(self.bank), note['id']),
                'source': notebook.source_of(note, collection),
                'questions': [{'id': q['id'], 'canonical': q['canonical'], 'frequency': q['frequency'], 'relation': link['relation'],
                               'answered': q['answer_status'] in ANSWERED} for q, link in linked]}
        if public:
            from .public_reader import origin
            result['source']['origin'] = origin(result['source']['origin'])
        return result

    def record(self, payload):
        require(self.can_practise, 'This server is in read-only mode')
        require(isinstance(payload, dict) and set(payload) == {'question_id', 'revision', 'rating', 'request_id', 'note', 'timezone'}, 'Invalid practice payload')
        require(all(isinstance(v, str) for v in payload.values()), 'Practice values must be strings')
        require(len(payload['note']) <= 10000 and 1 <= len(payload['request_id']) <= 100, 'Practice input too long')
        # Do not accept a fabricated date, score or client-controlled interval.
        submitted = {k: v for k, v in payload.items() if k != 'revision'}
        with self.mutation_lock:
            with open_bank(self.bank) as (manifest, config, data):
                require('_state' in data, 'Saving practice requires an explicit V2 migration')
                prior = next((e for e in data['_state']['events'].values() if e['request_id'] == submitted['request_id']), None)
                if prior:
                    value, _ = event(copy.deepcopy(data), submitted, source='user_self_rating', review=config.get('review'))
                    require(prior['question_revision'] == payload['revision'], 'Practice retry has a different revision')
                    return {'saved': True, 'already_recorded': True, 'event': value}
                q = next((q for q in data['questions'] if q['id'] == submitted['question_id'] and q['status'] == 'active'), None)
                require(q is not None and revision(q) == payload['revision'], 'Question changed; refresh it before rating')
                from .editorial import exclusion_reason
                require(not exclusion_reason(q), 'This question is excluded from practice')
                final = copy.deepcopy(data)
                value, _ = event(final, submitted, source='user_self_rating', review=config.get('review'))
                staged = stage_snapshot(self.bank, data, final, config, operation='study', audit=[{'event': value, 'interface': 'local_web'}], summary={'event_id': value['id']})
                # Commit under the same lock: no reader or CLI commit can slip between stage and commit.
                try:
                    commit_run(self.bank, staged['run_id'], loaded=(manifest, config, data))
                except BankError:
                    abandon_run(self.bank, staged['run_id'], locked=True)
                    raise
            return {'saved': True, 'already_recorded': False, 'event': value}


    def review(self, payload):
        """The person at the page marks the answer they just read as reviewed or stale."""
        require(not self.read_only, 'This server is in read-only mode')
        require(isinstance(payload, dict) and set(payload) == {'question_id', 'answer_id', 'decision', 'note'}, 'Invalid review payload')
        require(all(isinstance(v, str) for v in payload.values()), 'Review values must be strings')
        require(payload['decision'] in ('reviewed', 'stale'), 'decision must be reviewed or stale')
        require(1 <= len(payload['note'].strip()) <= 2000, 'Write a short note on what you checked')
        from .answers import review_change
        with self.mutation_lock:
            with open_bank(self.bank) as (manifest, config, data):
                final, audit, summary = review_change(data, payload['question_id'], payload['decision'], payload['note'].strip(),
                                                      'local_web', answer_id=payload['answer_id'])
                staged = stage_snapshot(self.bank, data, final, config, operation='answer-review', audit=audit, summary=summary)
                try:
                    commit_run(self.bank, staged['run_id'], loaded=(manifest, config, data))
                except BankError:
                    abandon_run(self.bank, staged['run_id'], locked=True)
                    raise
            return {'saved': True, **summary}


    def my_answer(self, payload):
        """The person's own note on a question or a collection entry; independent of reference answers, may be empty."""
        require(self.can_write_answer, 'This server does not save your own answers')
        require(isinstance(payload, dict) and len({'question_id', 'item_id'} & set(payload)) == 1 and
                set(payload) - {'question_id', 'item_id'} == {'text', 'expected_updated_at'}, 'Invalid answer payload')
        require(all(isinstance(v, str) for v in payload.values()), 'Answer values must be strings')
        with self.mutation_lock:
            return my_answers.save(self.bank, payload.get('item_id') or payload['question_id'], payload['text'], payload['expected_updated_at'])

    def my_notes(self, params):
        require(set(params) <= {'query', 'section'}, 'Unknown filter')
        require(params.get('section', '') in ('', 'bank', 'knowledge', 'experiences', 'learning'), 'Unknown section')
        with open_bank(self.bank, shared=True) as (_, _config, data):
            bundle = self._notes(data)
            rows = my_answers.listing(self.bank, data, bundle, params.get('query', ''), params.get('section', ''))
        return {'notes': rows, 'can_write': self.can_write_answer}

    def _describe(self, ids):
        """Title and section of favourite items now; removed ones stay listed and are flagged."""
        with open_bank(self.bank, shared=True) as (_, _config, data):
            bundle = self._notes(data)
            targets = {q['id']: q['merged_into'] or q['id'] for q in data['questions']}
            questions = {q['id']: q for q in data['questions']}
        sources = {c['name']: c['title'] for c in bundle['collections']}
        described = {}
        for key in ids:
            if key.startswith('q_'):
                q = questions.get(targets.get(key, key))
                described[key] = {'section': 'bank', 'target': q['id'] if q else key, 'title': q['canonical'] if q else '',
                                  'where': report_group(q) if q else None, 'missing': q is None or q['status'] != 'active'}
            else:
                note = note_experiences.find(bundle, key)
                described[key] = {'section': my_answers.section_of(note) if note else 'knowledge', 'target': note['id'] if note else key,
                                  'title': note['title'] if note else '', 'where': sources.get(note['collection']) if note else None,
                                  'missing': note is None}
        return described

    def favorites(self, folders=None):
        folders = personal.favorites(self.bank) if folders is None else folders
        described = self._describe({entry['id'] for f in folders for entry in f['items']})
        return {'can_write': self.can_write_answer,
                'folders': [{**f, 'items': [{**entry, **described[entry['id']]} for entry in f['items']]} for f in folders]}

    def change_favorites(self, payload):
        require(self.can_write_answer, 'This server does not save favourites')
        with self.mutation_lock:
            return self.favorites(personal.change_favorites(self.bank, payload))

    def learning(self):
        return {**personal.learning(self.bank), 'can_write': self.can_write_answer}

    def change_learning(self, payload):
        require(self.can_write_answer, 'This server does not save learning state')
        return {**personal.change_learning(self.bank, payload), 'can_write': True}

    def dedupe_decision(self, payload):
        """The person decides one uncertain merge; the agent applies it later with dedupe --resolve."""
        require(not self.read_only, 'This server is in read-only mode')
        require(isinstance(payload, dict) and set(payload) == {'run_id', 'question_id', 'action', 'note'}, 'Invalid decision payload')
        require(all(isinstance(v, str) for v in payload.values()), 'Decision values must be strings')
        require(1 <= len(payload['note'].strip()) <= 2000, 'Write a short reason for your decision')
        from .dedupe import record_human_decision
        from .runs import run_path
        run_path(self.bank, payload['run_id'])
        with self.mutation_lock:
            return {'saved': True, **record_human_decision(self.bank, payload['run_id'], payload['question_id'], payload['action'], payload['note'])}


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, app, port=0, token=None, public_origins=(), login=None, banks_dir=None, read_only=True, allow_my_answers=False,
                 allow_practice=False, public_bank=None, ai_config=None, allow_intake=False):
        # One bank for everyone (app), or one bank per account under banks_dir (hosting several people).
        self.app = app
        self.banks_dir, self.read_only, self.apps, self.apps_lock = banks_dir, read_only, {}, threading.Lock()
        self.allow_my_answers, self.allow_practice = allow_my_answers, allow_practice
        self.ai_config, self.allow_intake = ai_config, allow_intake
        require(not public_bank or login and public_origins, 'Public reading needs a hosted login and public origin')
        self.public_app = None
        if public_bank:
            from .public_reader import ReadBudget
            path = guard_bank_path(public_bank)
            self.public_app = app if app and app.bank == path else WebApp(path, read_only, allow_my_answers, allow_practice,
                                                                          ai_config, allow_intake)
            self.public_budget, self.public_active = ReadBudget(), threading.BoundedSemaphore(4)
        self.token = token or secrets.token_urlsafe(32)
        # Optional login page (hosting only): one account, signed session cookie, limited failed attempts.
        self.login = login
        if login:
            from .weblogin import Attempts, Sessions
            self.sessions, self.attempts = Sessions(self.token, login), Attempts()
        # Hosting behind a reverse proxy: the proxy authenticates the person and adds the token header; the
        # browser's Origin is the public site. The server itself still binds to loopback only.
        self.public_origins = tuple(public_origins)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'

    def server_bind(self):
        # HTTPServer.server_bind() resolves socket.getfqdn('127.0.0.1'); slow reverse DNS can stall
        # startup for tens of seconds and a loopback-only server never uses the name.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = '127.0.0.1', self.server_address[1]

    @property
    def url(self):
        return f'{self.origin}/#token={self.token}'


class Handler(BaseHTTPRequestHandler):
    server_version = 'InterviewBank'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_):
        pass  # No credentials, question text or private paths in access logs.

    def send(self, status, body, content_type='application/json; charset=utf-8', headers=(), cache='no-store', nonce=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        # A page's nonce admits only the <style> elements its own scripts create (dialog scroll lock); no inline script.
        styles = f"'self' 'nonce-{nonce}'" if nonce else "'self'"
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', f"default-src 'none'; script-src 'self'; style-src {styles}; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def route(self, post=False):
        # Both loopback names are accepted; any other Host (DNS rebinding) or foreign Origin is refused.
        port = self.server.server_port
        hosts = [f'127.0.0.1:{port}', f'localhost:{port}']
        if len(self.headers.get_all('Host') or []) != 1 or self.headers.get('Host') not in hosts \
                or self.headers.get('Origin') not in (None, *(f'http://{h}' for h in hosts), *self.server.public_origins):
            return self.send(403, {'error': f'仅支持本机访问：请打开 Agent 提供的 http://127.0.0.1:{port}/ 链接。'})
        path = urlsplit(self.path).path
        if path == '/' and not post:
            needs_login = not self.server.public_app or parse_qs(urlsplit(self.path).query).get('login') == ['1']
            name = 'login.html' if self.server.login and not self.user() and needs_login else 'index.html'
            nonce = secrets.token_urlsafe(18)
            page = (ASSETS / name).read_bytes().replace(b'__CSP_NONCE__', nonce.encode('ascii'))
            if self.server.public_app:
                page = page.replace(b'</head>', b'<meta name="public-reading" content="1"></head>')
            return self.send(200, page, 'text/html; charset=utf-8', nonce=nonce)
        if not post and (asset := bundled_asset(path)):
            # Built file names carry a content hash, so a phone may keep them until the next release.
            return self.send(200, asset.read_bytes(), ASSET_TYPES[asset.suffix], cache='public, max-age=31536000, immutable')
        supplied = self.headers.get('X-Interview-Token', '')
        if not hmac.compare_digest(supplied, self.server.token):
            return self.send(401, {'error': '访问凭据已失效，请使用 Agent 提供的完整启动链接重新打开。'})
        if self.server.login:
            if post and path in ('/api/login', '/api/logout'):
                return self.login(path)
            if not self.user():
                if self.server.public_app and not post and path in ('/api/library', '/api/notes', '/api/note'):
                    return self.public_read(path)
                return self.send(401, {'error': '请先登录。', 'login': True,
                                       'public_access': bool(self.server.public_app)})
        app = self.app()
        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        require(all(len(v) == 1 for v in query.values()), 'Duplicate query parameters')
        params = {k: v[0] for k, v in query.items()}
        if post and path == '/api/intake/upload':
            require(set(params) <= {'job', 'image', 'view'} and {'job', 'image'} <= set(params), 'Expected job and image')
            require(all(params.get(k, '0').isdigit() for k in ('image', 'view')), 'image and view are numbers')
            from .web_intake import MAX_IMAGE
            result = app.intake_jobs().upload(params['job'], int(params['image']),
                                              int(params['view']) if 'view' in params else None, self.raw_body(MAX_IMAGE))
        elif post and path.startswith('/api/intake/'):
            jobs = app.intake_jobs()
            handlers = {'/api/intake/jobs': jobs.create, '/api/intake/start': jobs.start, '/api/intake/confirm': jobs.confirm,
                        '/api/intake/merge': jobs.merge, '/api/intake/answers': jobs.retry_answers,
                        '/api/intake/retry': jobs.retry_extract, '/api/intake/cancel': jobs.cancel,
                        '/api/intake/research': jobs.research}
            if path not in handlers:
                return self.send(404, {'error': 'Unknown endpoint'})
            result = handlers[path](self.json_body(512 * 1024))
        elif post and path == '/api/prepare/save':
            require(app.can_practise, 'This server is in read-only mode')
            result = app.prepare_save(self.json_body())
        elif post and path.startswith('/api/interview/'):
            coach = app.interviews()
            handlers = {'/api/interview/start': app.interview_start, '/api/interview/plan': app.interview_plan,
                        '/api/interview/answer': coach.answer, '/api/interview/regrade': coach.regrade,
                        '/api/interview/follow-up': coach.follow_up, '/api/interview/end': coach.end}
            if path not in handlers:
                return self.send(404, {'error': 'Unknown endpoint'})
            result = handlers[path](self.json_body())
        elif post:
            handlers = {'/api/practice': app.record, '/api/review': app.review, '/api/dedupe-decision': app.dedupe_decision,
                        '/api/my-answer': app.my_answer, '/api/favorites': app.change_favorites, '/api/learning': app.change_learning}
            if path not in handlers:
                return self.send(404, {'error': 'Unknown endpoint'})
            body = self.json_body()
            handler = handlers[path]
            result = handler(body)
        elif path == '/api/intake':
            require(not params, 'No parameters expected')
            result = app.intake_jobs().overview() if app.intake else {'enabled': False}
        elif path == '/api/intake/job':
            require(set(params) == {'id'}, 'Expected job ID')
            result = app.intake_jobs().job(params['id'])
        elif path == '/api/prepare/top':
            result = app.prepare_top(params)
        elif path == '/api/prepare/companies':
            require(not params, 'No parameters expected')
            result = app.prepare_companies()
        elif path == '/api/prepare/company':
            result = app.prepare_company(params)
        elif path == '/api/prepare/lists':
            require(not params, 'No parameters expected')
            result = app.prepare_lists()
        elif path == '/api/prepare/list':
            result = app.prepare_list(params)
        elif path == '/api/interview':
            require(not params, 'No parameters expected')
            result = app.interview_overview() if app.coach else {'enabled': False}
        elif path in ('/api/interview/session', '/api/interview/plan'):
            require(set(params) == {'id'}, 'Expected ID')
            coach = app.interviews()
            result = coach.session(params['id']) if path.endswith('session') else coach.plan_result(params['id'])
        elif path == '/api/library':
            result = app.library(params)
            if self.server.login:
                result = {**result, 'can_logout': True, 'account': self.user(),
                          'guest': False, 'can_login': bool(self.server.public_app)}
        elif path == '/api/practice':
            result = app.library(params, practice=True)
        elif path == '/api/dedupe-reviews':
            from .dedupe import review_queue
            result = {'items': review_queue(app.bank)}
        elif path == '/api/notes':
            result = app.notes(params)
        elif path == '/api/note':
            require(set(params) == {'id'}, 'Expected note ID')
            result = app.note(params['id'])
        elif path == '/api/question':
            require(set(params) == {'id'}, 'Expected question ID')
            result = app.question(params['id'])
        elif path == '/api/my-notes':
            result = app.my_notes(params)
        elif path == '/api/favorites':
            require(not params, 'No parameters expected')
            result = app.favorites()
        elif path == '/api/learning':
            require(not params, 'No parameters expected')
            result = app.learning()
        else:
            return self.send(404, {'error': 'Unknown endpoint'})
        self.send(200, result)

    def public_read(self, path):
        """A GET-only allowlist. Future account endpoints remain private without needing to remember a denylist."""
        if not self.server.public_budget.allow(self.client()):
            return self.send(429, {'error': '公开资料访问较频繁，请稍后重试。'}, headers=[('Retry-After', '60')])
        if not self.server.public_active.acquire(blocking=False):
            return self.send(503, {'error': '公开资料正在读取，请稍后重试。'}, headers=[('Retry-After', '2')])
        try:
            return self.public_result(path)
        finally:
            self.server.public_active.release()

    def public_result(self, path):
        require(len(self.path) <= 8192, 'Request URL too long')
        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        require(all(len(v) == 1 for v in query.values()), 'Duplicate query parameters')
        params = {k: v[0] for k, v in query.items()}
        require(len(params.get('query', '')) <= 500, 'Search query too long')
        app = self.server.public_app
        if path == '/api/library':
            result = app.public_library(params)
        elif path == '/api/notes':
            result = app.notes(params, public=True)
        else:
            require(set(params) == {'id'}, 'Expected note ID')
            result = app.note(params['id'], public=True)
        self.send(200, result)

    def json_body(self, limit=65536):
        require(self.headers.get('Content-Type', '').split(';')[0] == 'application/json', 'Expected JSON')
        return json.loads(self.body(limit))

    def body(self, limit):
        require(not self.headers.get('Transfer-Encoding'), 'Transfer encoding not supported')
        sizes = self.headers.get_all('Content-Length', [])
        require(len(sizes) == 1 and sizes[0].isdigit() and 0 < int(sizes[0]) <= limit, 'Invalid content length')
        body = self.rfile.read(int(sizes[0]))
        require(len(body) == int(sizes[0]), 'Incomplete request')
        return body

    def raw_body(self, limit):
        """One screenshot as the request body; its bytes, not this header, decide the type."""
        from .web_intake import MIMES
        require(self.headers.get('Content-Type', '').split(';')[0] in MIMES, 'Expected a PNG, JPEG, WebP or GIF image')
        return self.body(limit)

    def cookie(self):
        from http.cookies import CookieError, SimpleCookie
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get('Cookie', ''))
        except CookieError:
            return None
        from .weblogin import COOKIE
        return jar[COOKIE].value if COOKIE in jar else None

    def user(self):
        return self.server.sessions.user(self.cookie())

    def app(self):
        """The signed-in account's bank when each account has its own; otherwise the one bank."""
        if not self.server.banks_dir:
            return self.server.app
        name = self.server.login['users'][self.user()]['bank']
        with self.server.apps_lock:
            if name not in self.server.apps:
                bank = Path(self.server.banks_dir) / name
                require((bank / 'manifest.json').is_file(), '这个账号的题库还没有同步到服务器。')
                shared = self.server.public_app
                self.server.apps[name] = shared if shared and shared.bank == bank.resolve() else WebApp(
                    bank, self.server.read_only, self.server.allow_my_answers, self.server.allow_practice,
                    self.server.ai_config, self.server.allow_intake)
                self.server.apps[name].warm()
            return self.server.apps[name]

    def client(self):
        # Behind the proxy every connection comes from loopback; the proxy names the real client.
        return self.headers.get('X-Real-IP') or self.client_address[0]

    def session_cookie(self, value, max_age):
        import re
        from .weblogin import COOKIE
        prefix = self.headers.get('X-Forwarded-Prefix', '/')
        path = prefix if re.fullmatch(r'/[A-Za-z0-9._~/-]*', prefix) else '/'
        return ('Set-Cookie', f'{COOKIE}={value}; Path={path.rstrip("/") or "/"}; Max-Age={max_age}; HttpOnly; Secure; SameSite=Strict')

    def login(self, path):
        from .weblogin import SESSION_SECONDS, verify
        if path == '/api/logout':
            return self.send(200, {'signed_out': True}, headers=[self.session_cookie('', 0)])
        client = self.client()
        if self.server.attempts.blocked(client):
            return self.send(429, {'error': '尝试次数过多，请 15 分钟后再试。'})
        body = self.json_body()
        require(isinstance(body, dict) and set(body) == {'username', 'password'}, 'Expected username and password')
        account = verify(self.server.login, body['username'], body['password'])
        if not account:
            self.server.attempts.failed(client)
            return self.send(401, {'error': '用户名或密码不正确。'})
        self.server.attempts.succeeded(client)
        return self.send(200, {'signed_in': True}, headers=[self.session_cookie(self.server.sessions.issue(account), SESSION_SECONDS)])

    def handle_route(self, post=False):
        try:
            self.route(post)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except LockConflict:
            self.send(409, {'error': '题库正在被其他任务使用，请稍后重试。'})
        except (BankError, ValueError, TypeError) as exc:
            self.send(400, {'error': str(exc)})
        except Exception:
            self.send(500, {'error': '题库暂时无法读取或保存。请保留作答并让 Agent 运行 doctor 检查后重试。'})

    def do_GET(self):
        self.handle_route()

    def do_POST(self):
        self.handle_route(True)


def _read_token(path):
    from pathlib import Path
    token = Path(path).read_text(encoding='utf-8').strip()
    require(len(token) >= 32 and token.isascii() and token.isprintable() and ' ' not in token,
            'The token file must hold one printable token of at least 32 characters')
    return token


def serve(bank, port=0, read_only=False, open_browser=False, token_file=None, public_origins=(), login_file=None, banks_dir=None,
          allow_my_answers=False, allow_practice=False, public_bank=None, ai_config_file=None, allow_intake=False):
    require(0 <= port <= 65535, 'Port must be 0..65535')
    require(not allow_intake or ai_config_file, '--allow-intake needs --ai-config (the model that reads screenshots)')
    require(not ai_config_file or not read_only or allow_intake,
            'A read-only reader imports screenshots only with --allow-intake; drop --ai-config or add it')
    ai_config = None
    if ai_config_file:
        from .ai import load_config
        ai_config = load_config(ai_config_file)
    for origin in public_origins:
        parsed = urlsplit(origin)
        require(parsed.scheme == 'https' and parsed.netloc and not parsed.path.strip('/') and not parsed.query,
                'A public origin is https://host[:port] without a path')
    require(not public_origins or token_file, 'A public origin needs --token-file: the reverse proxy must add the token')
    require(not login_file or public_origins, 'A login page is only for hosting: also pass --public-origin')
    require(not public_bank or login_file and public_origins, '--public-bank needs --login-file and --public-origin')
    login = None
    if login_file:
        from .weblogin import load_login
        login = load_login(login_file)
    require(not banks_dir or login, 'One bank per account (--banks-dir) needs --login-file')
    if banks_dir:
        banks_dir = Path(banks_dir).expanduser().resolve()
        require(banks_dir.is_dir(), f'Not a directory: {banks_dir}')
    server = LocalServer(None if banks_dir else WebApp(bank, read_only, allow_my_answers, allow_practice, ai_config, allow_intake), port,
                         _read_token(token_file) if token_file else None, [o.rstrip('/') for o in public_origins], login, banks_dir,
                         read_only, allow_my_answers, allow_practice, public_bank, ai_config, allow_intake)
    # A fixed token lives in a file the proxy also reads; never print it into service logs.
    url = server.origin + '/' if token_file else server.url
    from .ai import describe
    print(json.dumps({'ok': True, 'command': 'web', 'result': {'url': url, 'pid': __import__('os').getpid(), 'read_only': read_only,
                      'my_answers': not read_only or allow_my_answers, 'practice': not read_only or allow_practice,
                      'intake': describe(ai_config) if ai_config else None,
                      'public_origins': list(server.public_origins), 'public_reading': bool(server.public_app),
                      'version': __version__}}, ensure_ascii=False), flush=True)
    if server.app:
        server.app.warm()
    if server.public_app and server.public_app is not server.app:
        server.public_app.warm()
    if open_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return {'stopped': True}
