"""Anonymous reads must never project an account's interviews or personal layer."""
import hashlib
import http.client
import json
import threading
from urllib.parse import quote
from unittest.mock import patch

from test_foundation import BankFixture
from ibank_core import my_answers, notes, note_organization
from ibank_core.errors import ValidationError
from ibank_core.storage import initialize
from ibank_core.web import LocalServer, WebApp, serve
from ibank_core.weblogin import make_user


class PublicReaderTests(BankFixture):
    def setUp(self):
        super().setUp()
        self.seed()
        source = self.base / 'public-source'
        source.mkdir()
        (source / '01.md').write_text('# 公开资料\n\n## 缓存穿透是什么？\n\n公开正文：布隆过滤器。\n\n'
                                      '## 环境安装教程\n\n公开安装步骤。\n\n## 2026 某公司一面\n\n公开面经正文。\n', encoding='utf-8')
        notes.import_collection(self.bank, source, 'published', title='公开测试来源', origin=str(source))
        catalog = note_organization.catalog(self.bank, 'published')
        entries = catalog['notes']
        note_organization.organize(self.bank, 'published', {
            'schema_version': 1, 'collection': 'published', 'source_digest': catalog['source_digest'],
            'organization_digest': catalog['organization_digest'],
            'notes': {entries[1]['id']: {'kind': 'tutorial'}},
            'experiences': {'first': {'title': '2026 某公司一面', 'kind': 'interview',
                                      'note_ids': [entries[2]['id']], 'company': '某公司',
                                      'interview_time': '2026', 'facts': [
                                          {'field': field, 'quote': '2026 某公司一面', 'note_id': entries[2]['id']}
                                          for field in ('company', 'interview_time')]}},
        })
        self.nid = entries[0]['id']
        self.app = WebApp(self.bank, True, True, True)
        self.qid = self.app.library({})['ids'][0]
        (self.bank / 'collections/links.jsonl').write_text(json.dumps({
            'question_id': self.qid, 'note_id': self.nid, 'relation': 'answers', 'reason': 'PRIVATE-LINK-REASON',
        }) + '\n', encoding='utf-8')
        my_answers.save(self.bank, self.nid, 'PRIVATE-NOTE-SENTINEL', '')
        self.other = self.base / 'bob'
        initialize(self.other)
        login = {'schema_version': 2, 'users': {'alice': make_user('alice', 'synthetic alice pass', bank='bank'),
                                                'bob': make_user('bob', 'synthetic bob pass', bank='bob')}}
        self.server = LocalServer(None, token='synthetic-proxy-' + 'x' * 40, public_origins=['https://bank.example'],
                                  login=login, banks_dir=self.base, read_only=True, allow_my_answers=True,
                                  allow_practice=True, public_bank=self.bank)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path, body=None, cookie=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        sent = {'X-Interview-Token': self.server.token, 'Content-Type': 'application/json',
                'Origin': 'https://bank.example', **({'Cookie': cookie} if cookie else {}), **(headers or {})}
        conn.request('POST' if body is not None else 'GET', quote(path, safe='/?=&'), json.dumps(body) if body is not None else None, sent)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def get(self, path, cookie=None):
        status, _, body = self.request(path, cookie=cookie)
        self.assertEqual(status, 200, body)
        return json.loads(body)

    def session(self, name):
        status, headers, _ = self.request('/api/login', {'username': name, 'password': f'synthetic {name} pass'})
        self.assertEqual(status, 200)
        return headers['Set-Cookie'].split(';', 1)[0]

    def test_guest_bootstrap_and_explicit_login_page(self):
        status, headers, page = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'assets/index-', page)
        self.assertNotIn(b'assets/login-', page)
        self.assertIn(b'name="public-reading"', page)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertIn(b'assets/login-', self.request('/?login=1')[2])
        public = self.get('/api/library?limit=5')
        self.assertTrue(public['guest'])
        self.assertEqual(public['ids'], [])
        self.assertEqual(public['questions'], [])
        self.assertEqual(set(public['summary'].values()), {0})
        self.assertNotIn('account', public)
        self.assertNotIn('updated_at', public)
        self.assertEqual(public['name'], 'Public library')
        for flag in ('can_write_personal', 'can_write_answer', 'can_record', 'can_review', 'can_logout'):
            self.assertFalse(public[flag])

    def test_guest_body_search_and_metadata_have_no_personal_projection(self):
        private = self.app.note(self.nid)
        self.assertTrue(private['questions'])
        self.assertEqual(private['my_answer']['text'], 'PRIVATE-NOTE-SENTINEL')
        for path in ('/api/notes?section=knowledge', '/api/notes?section=learning',
                     '/api/notes?section=experiences', '/api/notes?query=布隆', '/api/note?id=' + self.nid):
            result = self.get(path)
            raw = json.dumps(result, ensure_ascii=False)
            for secret in (self.qid, 'PRIVATE-NOTE-SENTINEL', 'PRIVATE-LINK-REASON', str(self.base)):
                self.assertNotIn(secret, raw)
            for row in result.get('notes', []):
                self.assertEqual((row['linked'], row['asked'], row['has_my_answer']), (0, 0, False))
            for collection in result.get('collections', []):
                self.assertEqual((collection['linked'], collection['history'], collection['origin']), (0, [], ''))
        public = self.get('/api/note?id=' + self.nid)
        self.assertIn('布隆', public['body'])
        self.assertEqual((public['my_answer'], public['questions'], public['asked']), (None, [], 0))
        self.assertEqual(self.get('/api/notes?query=布隆')['total'], 1)
        for section in ('knowledge', 'learning', 'experiences'):
            self.assertEqual(self.get('/api/notes?section=' + section)['total'], 1)
        # Public requests cannot mutate the cached collection seen by the signed-in account.
        self.assertEqual(self.app.note(self.nid)['my_answer'], private['my_answer'])

    def test_guessed_private_ids_and_all_writes_require_login(self):
        for path in ('/api/question?id=' + self.qid, '/api/practice', '/api/my-notes', '/api/favorites',
                     '/api/learning', '/api/dedupe-reviews', '/api/future-account-feature'):
            self.assertEqual(self.request(path)[0], 401, path)
        for path in ('/api/my-answer', '/api/favorites', '/api/learning', '/api/practice', '/api/review',
                     '/api/dedupe-decision', '/api/notes', '/api/note', '/api/library'):
            self.assertEqual(self.request(path, {})[0], 401, path)
        self.assertNotEqual(self.request('/api/note?id=' + self.qid)[0], 200)

    def test_personal_association_filters_do_not_reveal_counts(self):
        for suffix in ('asked=1', 'connection=personal'):
            page = self.get('/api/notes?' + suffix)
            self.assertEqual((page['total'], page['ids'], page['summary']['asked']), (0, [], 0))
        self.assertTrue(all(n['asked'] == 0 for n in self.get('/api/notes?sort=asked')['notes']))

    def test_signed_in_accounts_remain_isolated_and_logout_returns_to_public(self):
        alice = self.session('alice')
        library = self.get('/api/library', alice)
        self.assertEqual(library['account'], 'alice')
        self.assertFalse(library['guest'])
        self.assertGreater(library['summary']['questions'], 0)
        own = self.get('/api/note?id=' + self.nid, alice)
        self.assertEqual(own['my_answer']['text'], 'PRIVATE-NOTE-SENTINEL')
        self.assertTrue(own['questions'])
        bob = self.session('bob')
        self.assertEqual(self.get('/api/library', bob)['total'], 0)
        self.assertEqual(self.get('/api/notes', bob)['total'], 0)
        self.assertEqual(self.request('/api/note?id=' + self.nid, cookie=bob)[0], 400)
        self.assertEqual(self.request('/api/logout', {}, alice)[0], 200)
        self.assertTrue(self.get('/api/library')['guest'])
        self.assertIs(self.server.apps['bank'], self.server.public_app)

    def test_invalid_session_falls_back_to_public_but_cannot_access_private(self):
        self.assertTrue(self.get('/api/library', 'ibank_session=forged')['guest'])
        self.assertEqual(self.request('/api/my-notes', cookie='ibank_session=forged')[0], 401)

    def test_guest_still_requires_proxy_token_host_and_origin(self):
        for headers in ({'X-Interview-Token': ''}, {'Host': 'evil.example'}, {'Origin': 'https://evil.example'}):
            self.assertIn(self.request('/api/notes', headers=headers)[0], (401, 403))
        self.assertEqual(self.request('/api/notes?limit=1&limit=2')[0], 400)

    def test_guest_does_not_read_personal_files_or_change_bank(self):
        def files():
            return {p.relative_to(self.bank).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for folder in ('data', 'personal', 'collections') for p in (self.bank / folder).rglob('*') if p.is_file()}
        before = files()
        with patch('ibank_core.web.my_answers.load', side_effect=AssertionError('Personal notes must not be opened')):
            self.get('/api/library')
            self.get('/api/notes')
            self.get('/api/note?id=' + self.nid)
        self.assertEqual(files(), before)

    def test_public_reading_is_opt_in_and_requires_hosted_login(self):
        with self.assertRaises(ValidationError):
            LocalServer(self.app, public_bank=self.bank)
        with self.assertRaises(ValidationError):
            serve(self.bank, public_bank=self.bank)
        from ibank_core.public_reader import origin
        for value in (str(self.base), 'file:///private', 'https://user:pass@example.org/source'):
            self.assertEqual(origin(value), '')
        self.assertEqual(origin('https://github.com/example/public'), 'https://github.com/example/public')

    def test_public_read_budget_and_concurrency_fail_without_private_data(self):
        from ibank_core.public_reader import ReadBudget
        budget = ReadBudget(per_client=2, overall=3)
        self.assertTrue(budget.allow('a', now=0))
        self.assertTrue(budget.allow('a', now=1))
        self.assertFalse(budget.allow('a', now=2))
        self.assertTrue(budget.allow('b', now=3))
        self.assertFalse(budget.allow('c', now=4))
        self.assertTrue(budget.allow('c', now=64))
        self.assertEqual(set(budget.clients), {'c'})
        with patch.object(self.server.public_budget, 'allow', return_value=False):
            status, headers, body = self.request('/api/notes')
            self.assertEqual(status, 429)
            self.assertIn('Retry-After', headers)
            self.assertNotIn(self.qid.encode(), body)
        for _ in range(4):
            self.server.public_active.acquire()
        try:
            self.assertEqual(self.request('/api/notes')[0], 503)
            self.assertEqual(self.get('/api/library', self.session('alice'))['account'], 'alice')
        finally:
            for _ in range(4):
                self.server.public_active.release()
        self.assertEqual(self.request('/api/notes?query=' + 'a' * 501)[0], 400)
        self.assertEqual(self.request('/api/notes')[0], 200)
