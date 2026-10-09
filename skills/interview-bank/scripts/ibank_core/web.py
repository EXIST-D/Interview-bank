"""Optional loopback-only reader. No framework, external assets or model calls."""
import copy
import hmac
import json
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
from . import notes as notebook
from .timestamps import parse_timestamp

ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'web'
FILTERS = {'query', 'domain', 'role', 'technology', 'company', 'industry', 'answer_status', 'group'}
ANSWERED = ('source_backed', 'reviewed')
VIEWS = {'all', 'due', 'weak', 'unseen'}
NOTE_FILTERS = {'collection', 'chapter', 'query', 'marked', 'asked', 'sort', 'offset', 'limit'}


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
    def __init__(self, bank, read_only=False):
        self.bank = guard_bank_path(bank)
        self.read_only = read_only
        self.mutation_lock = threading.Lock()
        self.notes_cache = (None, None)
        with open_bank(self.bank, shared=True):
            pass

    def _notes(self, data):
        """Collections and links, parsed once per change. The caller holds the bank lock."""
        key = notebook.signature(self.bank)
        if self.notes_cache[0] != key:
            self.notes_cache = (key, notebook.load_notes(self.bank))
        return notebook.resolve_links(self.notes_cache[1], data)

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
            facets['industry'] = [{'value': v, 'label': display('industries', v)} for v in sorted({v for c in used for v in c['industries']})]
            return {
                'name': self.bank.name, 'version': __version__, 'schema_version': manifest['schema_version'],
                'can_record': manifest['schema_version'] == 2 and not self.read_only, 'can_review': not self.read_only,
                'language': language(config),
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
                'questions': [card(q, states[q['id']], language(config)) for q in found[offset:offset + limit]],
            }

    def question(self, qid):
        with open_bank(self.bank, shared=True) as (_, config, data):
            rows = select(data, config, self.bank, ids=[qid])
            require(bool(rows), 'Question is no longer available; refresh the library')
            q = rows[0]
            sources = {s['id']: s for s in data['sources']}
            result = card(q, progress(data, rows)[q['id']], language(config))
            result['answer'] = q['answer']
            bundle = self._notes(data)
            collections = {c['name']: c for c in bundle['collections']}
            notes = {n['id']: n for n in bundle['notes']}
            result['notes'] = [{'id': link['note_id'], 'relation': link['relation'], 'title': notes[link['note_id']]['title'],
                                'marked': bool(notes[link['note_id']]['marks']),
                                'where': f"{collections[notes[link['note_id']]['collection']]['title']} › "
                                         f"{notebook.chapter_title(collections[notes[link['note_id']]['collection']], notes[link['note_id']])}"}
                               for link in sorted(bundle['links'], key=lambda l: (l['relation'] != 'answers', notes[l['note_id']]['order']))
                               if link['question_id'] == q['id']]
            result['occurrences'] = [{
                'text': o['original_text'], 'year': o['event_date'][:4] if o['event_date'] else None,
                'type': sources[o['source_id']]['type'], 'platform': sources[o['source_id']].get('platform'),
                'locator': o.get('locator'),
            } for o in q['occurrences']]
            history = [e for e in data.get('_state', {}).get('events', {}).values() if resolve(data, e['question_id']) == q['id']]
            result['history'] = [{k: e[k] for k in ('rating', 'occurred_at', 'next_review_at', 'note')} for e in sorted(history, key=lambda e: (e['occurred_at'], e['id']), reverse=True)[:20]]
            return result

    def notes(self, params):
        """八股 collections: chapters, filters and one page of note cards in reading order."""
        require(set(params) <= NOTE_FILTERS, 'Unknown filter')
        limit, offset = int(params.get('limit', 30)), int(params.get('offset', 0))
        require(1 <= limit <= 100 and offset >= 0, 'Invalid pagination (limit 1..100)')
        with open_bank(self.bank, shared=True) as (_, config, data):
            bundle = self._notes(data)
            rows = select(data, config, self.bank)
        linked = notebook.linked_questions(bundle, rows)
        collections = {c['name']: c for c in bundle['collections']}
        found = bundle['notes']
        # A collection remembered by the browser may have been removed since: show everything instead.
        if params.get('collection') in collections:
            found = [n for n in found if n['collection'] == params['collection']]
            if params.get('chapter', '') != '':
                found = [n for n in found if str(n['chapter']) == params['chapter']]
        if params.get('query', '').strip():
            needle = params['query'].strip().casefold()
            found = [n for n in found if needle in n['title'].casefold()] + \
                    [n for n in found if needle not in n['title'].casefold() and needle in n['body'].casefold()]
        if params.get('marked') == '1':
            found = [n for n in found if n['marks']]
        if params.get('asked') == '1':
            found = [n for n in found if n['id'] in linked]
        require(params.get('sort', 'order') in ('order', 'asked'), 'Unknown sort order')
        if params.get('sort') == 'asked':
            found = sorted(found, key=lambda n: -sum(q['frequency'] for q, _ in linked.get(n['id'], [])))
        card = lambda n: notebook.note_card(n, collections[n['collection']], [q for q, _ in linked.get(n['id'], [])])
        return {
            'collections': [{'name': c['name'], 'title': c['title'], 'origin': c.get('origin', ''), 'total': len(c['notes']),
                             'chapters': [{'index': ch['index'], 'title': ch['title'], 'count': ch['notes'], 'intro': ch['intro']}
                                          for ch in c['chapters']]} for c in bundle['collections']],
            'summary': {'notes': len(bundle['notes']), 'marked': sum(bool(n['marks']) for n in bundle['notes']),
                        'asked': sum(n['id'] in linked for n in bundle['notes'])},
            'total': len(found), 'offset': offset, 'limit': limit, 'ids': [n['id'] for n in found],
            'notes': [card(n) for n in found[offset:offset + limit]],
        }

    def note(self, note_id):
        with open_bank(self.bank, shared=True) as (_, config, data):
            bundle = self._notes(data)
            rows = select(data, config, self.bank)
        note = next((n for n in bundle['notes'] if n['id'] == note_id), None)
        require(note is not None, 'This note is no longer available; refresh the list')
        collection = next(c for c in bundle['collections'] if c['name'] == note['collection'])
        linked = notebook.linked_questions(bundle, rows).get(note_id, [])
        linked.sort(key=lambda pair: (pair[1]['relation'] != 'answers', -pair[0]['frequency']))
        return {**notebook.note_card(note, collection, [q for q, _ in linked]), 'body': note['body'],
                'source': notebook.source_of(note, collection),
                'questions': [{'id': q['id'], 'canonical': q['canonical'], 'frequency': q['frequency'], 'relation': link['relation'],
                               'answered': q['answer_status'] in ANSWERED} for q, link in linked]}

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

    def __init__(self, app, port=0, token=None, public_origins=(), login=None, banks_dir=None, read_only=True):
        # One bank for everyone (app), or one bank per account under banks_dir (hosting several people).
        self.app = app
        self.banks_dir, self.read_only, self.apps, self.apps_lock = banks_dir, read_only, {}, threading.Lock()
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

    def send(self, status, body, content_type='application/json; charset=utf-8', headers=()):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
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
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/app.css': ('app.css', 'text/css; charset=utf-8'), '/login.js': ('login.js', 'text/javascript; charset=utf-8')}
        if path in assets and not post:
            name, mime = assets[path]
            if path == '/' and self.server.login and not self.user():
                name = 'login.html'
            return self.send(200, (ASSETS / name).read_bytes(), mime)
        supplied = self.headers.get('X-Interview-Token', '')
        if not hmac.compare_digest(supplied, self.server.token):
            return self.send(401, {'error': '访问凭据已失效，请使用 Agent 提供的完整启动链接重新打开。'})
        if self.server.login:
            if post and path in ('/api/login', '/api/logout'):
                return self.login(path)
            if not self.user():
                return self.send(401, {'error': '请先登录。', 'login': True})
        app = self.app()
        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        require(all(len(v) == 1 for v in query.values()), 'Duplicate query parameters')
        params = {k: v[0] for k, v in query.items()}
        if post:
            if path not in ('/api/practice', '/api/review', '/api/dedupe-decision'):
                return self.send(404, {'error': 'Unknown endpoint'})
            body = self.json_body()
            handler = {'/api/practice': app.record, '/api/review': app.review, '/api/dedupe-decision': app.dedupe_decision}[path]
            result = handler(body)
        elif path == '/api/library':
            result = app.library(params)
            if self.server.login:
                result = {**result, 'can_logout': True, 'account': self.user()}
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
        else:
            return self.send(404, {'error': 'Unknown endpoint'})
        self.send(200, result)

    def json_body(self):
        require(self.headers.get('Content-Type', '').split(';')[0] == 'application/json', 'Expected JSON')
        require(not self.headers.get('Transfer-Encoding'), 'Transfer encoding not supported')
        sizes = self.headers.get_all('Content-Length', [])
        require(len(sizes) == 1 and sizes[0].isdigit() and 0 < int(sizes[0]) <= 65536, 'Invalid content length')
        body = self.rfile.read(int(sizes[0]))
        require(len(body) == int(sizes[0]), 'Incomplete request')
        return json.loads(body)

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
                self.server.apps[name] = WebApp(bank, self.server.read_only)
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


def serve(bank, port=0, read_only=False, open_browser=False, token_file=None, public_origins=(), login_file=None, banks_dir=None):
    require(0 <= port <= 65535, 'Port must be 0..65535')
    for origin in public_origins:
        parsed = urlsplit(origin)
        require(parsed.scheme == 'https' and parsed.netloc and not parsed.path.strip('/') and not parsed.query,
                'A public origin is https://host[:port] without a path')
    require(not public_origins or token_file, 'A public origin needs --token-file: the reverse proxy must add the token')
    require(not login_file or public_origins, 'A login page is only for hosting: also pass --public-origin')
    login = None
    if login_file:
        from .weblogin import load_login
        login = load_login(login_file)
    require(not banks_dir or login, 'One bank per account (--banks-dir) needs --login-file')
    if banks_dir:
        banks_dir = Path(banks_dir).expanduser().resolve()
        require(banks_dir.is_dir(), f'Not a directory: {banks_dir}')
    server = LocalServer(None if banks_dir else WebApp(bank, read_only), port, _read_token(token_file) if token_file else None,
                         [o.rstrip('/') for o in public_origins], login, banks_dir, read_only)
    # A fixed token lives in a file the proxy also reads; never print it into service logs.
    url = server.origin + '/' if token_file else server.url
    print(json.dumps({'ok': True, 'command': 'web', 'result': {'url': url, 'pid': __import__('os').getpid(), 'read_only': read_only,
                      'public_origins': list(server.public_origins), 'version': __version__}}, ensure_ascii=False), flush=True)
    if open_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return {'stopped': True}
