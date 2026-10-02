"""Optional loopback-only reader. No framework, external assets or model calls."""
import copy
import hmac
import json
import secrets
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
from .timestamps import parse_timestamp

ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'web'
FILTERS = {'query', 'domain', 'role', 'technology', 'company', 'industry', 'answer_status'}
VIEWS = {'all', 'due', 'weak', 'unseen'}


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


def card(q, state):
    return {k: q[k] for k in ('id', 'canonical', 'frequency', 'answer_status', 'difficulty', 'updated_at')} | {
        'group': report_group(q), 'revision': revision(q), 'progress': state,
        'domains': [{'id': d, 'label': display('domains', d)} for d in q['domains']],
        'technologies': [display('technologies', t) for t in q['technologies']],
        'companies': [c['name'] for c in q['companies'] if c['id']],
        'years': sorted({o['event_date'][:4] for o in q['occurrences'] if o['event_date']}, reverse=True),
    }


def filtered(rows, companies, states, params):
    predicates = [{'field': k, 'values': [v]} for k, v in params.items() if k in FILTERS and v]
    if predicates:
        rows = apply_expression(rows, companies, {'all': predicates})
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
    def __init__(self, bank, read_only=False):
        self.bank = guard_bank_path(bank)
        self.read_only = read_only
        self.mutation_lock = threading.Lock()
        with open_bank(self.bank):
            pass

    def library(self, params, practice=False):
        require(set(params) <= FILTERS | {'view', 'sort', 'offset', 'limit'}, 'Unknown filter')
        limit = int(params.get('limit', 20 if not practice else 10))
        offset = int(params.get('offset', 0))
        require(1 <= limit <= 100 and offset >= 0, 'Invalid pagination (limit 1..100)')
        with open_bank(self.bank) as (manifest, config, data):
            rows = select(data, config, self.bank)
            states = progress(data, rows)
            found = filtered(rows, data['companies'], states, params)
            if practice:
                return {'total': len(found), 'questions': [card(q, states[q['id']]) for q in found[offset:offset + limit]]}
            facets = {}
            for name, dimension, values in (
                ('domain', 'domains', [d for q in rows for d in set(q['domains'])]),
                ('technology', 'technologies', [t for q in rows for t in set(q['technologies'])]),
                ('role', 'role_tracks', [r for q in rows for r in {r for o in q['occurrences'] for r in o['role_tracks']}]),
            ):
                counts = Counter(values)
                facets[name] = [{'value': v, 'label': display(dimension, v), 'count': n} for v, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
            company_counts = Counter(c['id'] for q in rows for c in q['companies'] if c['id'])
            facets['company'] = [{'value': c['id'], 'label': c['name'], 'count': company_counts[c['id']]} for c in data['companies'] if company_counts[c['id']]]
            used = [c for c in data['companies'] if company_counts[c['id']]]
            facets['industry'] = [{'value': v, 'label': display('industries', v)} for v in sorted({v for c in used for v in c['industries']})]
            return {
                'name': self.bank.name, 'version': __version__, 'schema_version': manifest['schema_version'],
                'can_record': manifest['schema_version'] == 2 and not self.read_only,
                'read_only': self.read_only, 'updated_at': manifest.get('last_updated_at'),
                'summary': {'questions': len(rows), 'answered': sum(q['answer_status'] in ('source_backed', 'reviewed') for q in rows),
                            'answer_count': sum(q['answer'] is not None for q in rows), 'stale': sum(q['answer_status'] == 'stale' for q in rows),
                            'due': sum(s['due'] for s in states.values()), 'weak': sum(s['state'] in ('weak', 'changed') for s in states.values()),
                            'unseen': sum(s['state'] == 'unseen' for s in states.values()), 'domains': len(facets['domain'])},
                'total': len(found), 'offset': offset, 'limit': limit, 'facets': facets,
                'questions': [card(q, states[q['id']]) for q in found[offset:offset + limit]],
            }

    def question(self, qid):
        with open_bank(self.bank) as (_, config, data):
            rows = select(data, config, self.bank, ids=[qid])
            require(bool(rows), 'Question is no longer available; refresh the library')
            q = rows[0]
            sources = {s['id']: s for s in data['sources']}
            result = card(q, progress(data, rows)[q['id']])
            result['answer'] = q['answer']
            result['occurrences'] = [{
                'text': o['original_text'], 'year': o['event_date'][:4] if o['event_date'] else None,
                'type': sources[o['source_id']]['type'], 'platform': sources[o['source_id']].get('platform'),
                'locator': o.get('locator'),
            } for o in q['occurrences']]
            history = [e for e in data.get('_state', {}).get('events', {}).values() if resolve(data, e['question_id']) == q['id']]
            result['history'] = [{k: e[k] for k in ('rating', 'occurred_at', 'next_review_at', 'note')} for e in sorted(history, key=lambda e: (e['occurred_at'], e['id']), reverse=True)[:20]]
            return result

    def record(self, payload):
        require(not self.read_only, 'This server is in read-only mode')
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
                    value, _ = event(copy.deepcopy(data), submitted)
                    require(prior['question_revision'] == payload['revision'], 'Practice retry has a different revision')
                    return {'saved': True, 'already_recorded': True, 'event': value}
                q = next((q for q in data['questions'] if q['id'] == submitted['question_id'] and q['status'] == 'active'), None)
                require(q is not None and revision(q) == payload['revision'], 'Question changed; refresh it before rating')
                from .editorial import exclusion_reason
                require(not exclusion_reason(q), 'This question is excluded from practice')
                final = copy.deepcopy(data)
                value, _ = event(final, submitted)
                staged = stage_snapshot(self.bank, data, final, config, operation='study', audit=[{'event': value, 'interface': 'local_web'}], summary={'event_id': value['id']})
                # Commit under the same lock: no reader or CLI commit can slip between stage and commit.
                try:
                    commit_run(self.bank, staged['run_id'], loaded=(manifest, config, data))
                except BankError:
                    abandon_run(self.bank, staged['run_id'], locked=True)
                    raise
            return {'saved': True, 'already_recorded': False, 'event': value}


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, app, port=0):
        self.app = app
        self.token = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'

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

    def send(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def route(self, post=False):
        host = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get_all('Host') != [host] or self.headers.get('Origin') not in (None, self.server.origin):
            return self.send(403, {'error': '仅支持当前本机页面访问。'})
        path = urlsplit(self.path).path
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/app.css': ('app.css', 'text/css; charset=utf-8')}
        if path in assets and not post:
            name, mime = assets[path]
            return self.send(200, (ASSETS / name).read_bytes(), mime)
        supplied = self.headers.get('X-Interview-Token', '')
        if not hmac.compare_digest(supplied, self.server.token):
            return self.send(401, {'error': '访问凭据已失效，请使用 Agent 提供的完整启动链接重新打开。'})
        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        require(all(len(v) == 1 for v in query.values()), 'Duplicate query parameters')
        params = {k: v[0] for k, v in query.items()}
        if post:
            if path != '/api/practice':
                return self.send(404, {'error': 'Unknown endpoint'})
            require(self.headers.get('Content-Type', '').split(';')[0] == 'application/json', 'Expected JSON')
            require(not self.headers.get('Transfer-Encoding'), 'Transfer encoding not supported')
            sizes = self.headers.get_all('Content-Length', [])
            require(len(sizes) == 1 and sizes[0].isdigit() and 0 < int(sizes[0]) <= 65536, 'Invalid content length')
            body = self.rfile.read(int(sizes[0]))
            require(len(body) == int(sizes[0]), 'Incomplete request')
            result = self.server.app.record(json.loads(body))
        elif path == '/api/library':
            result = self.server.app.library(params)
        elif path == '/api/practice':
            result = self.server.app.library(params, practice=True)
        elif path == '/api/question':
            require(set(params) == {'id'}, 'Expected question ID')
            result = self.server.app.question(params['id'])
        else:
            return self.send(404, {'error': 'Unknown endpoint'})
        self.send(200, result)

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


def serve(bank, port=0, read_only=False, open_browser=False):
    require(0 <= port <= 65535, 'Port must be 0..65535')
    server = LocalServer(WebApp(bank, read_only), port)
    print(json.dumps({'ok': True, 'command': 'web', 'result': {'url': server.url, 'pid': __import__('os').getpid(), 'read_only': read_only, 'version': __version__}}, ensure_ascii=False), flush=True)
    if open_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return {'stopped': True}
