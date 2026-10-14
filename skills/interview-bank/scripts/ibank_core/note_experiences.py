"""Source-owned public interview articles, projected from existing note IDs."""
import hashlib
import re

from .schema import require

KINDS = ('interview', 'company_questions', 'career')
LABELS = {'interview': '面试记录', 'company_questions': '公司题单', 'career': '求职经验'}
FACT_FIELDS = ('company', 'role', 'round', 'interview_time', 'published_time')
FIELDS = {'title', 'kind', 'note_ids', 'summary', 'facts', *FACT_FIELDS}

# Browsing topics, not claims about the author's job. Never infer from the repository name.
DOMAINS = {
    'agent': 'Agent 与 AI 应用', 'llm': '大模型与机器学习', 'multimodal': '多模态与视觉',
    'backend': '后端与数据库', 'frontend': '前端与客户端', 'fullstack': '全栈开发',
    'infra': '基础设施与系统', 'coding': '算法与编程', 'career': '求职与面试经验',
    'other': '综合 / 待分类',
}
DOMAIN_PATTERNS = {
    'multimodal': (r'多模态', r'\bvlm\b', r'视觉', r'\bclip\b', r'图像'),
    'fullstack': (r'全栈', r'full[ -]?stack'),
    'agent': (r'(?<![a-z])agent(?![a-z])|智能体', r'(?<![a-z])rag(?![a-z])', r'\bmcp\b', r'langgraph', r'langchain',
              r'\bfde\b', r'AI\s*应用', r'工具调用', r'function\s*call'),
    'infra': (r'\binfra\b', r'分布式', r'操作系统', r'计算机网络', r'\bkubernetes\b', r'云原生'),
    'backend': (r'后端', r'\bjava\b|\bjvm\b', r'\bspring\b', r'\bredis\b', r'\bmysql\b', r'数据库', r'缓存'),
    'frontend': (r'前端', r'\breact\b', r'\bvue\b', r'\bjavascript\b', r'\btypescript\b', r'\bcss\b', r'客户端'),
    'llm': (r'大模型', r'(?<![a-z])llm(?![a-z])', r'机器学习', r'深度学习', r'\btransformer\b', r'\blora\b',
            r'\bsft\b', r'\brl\b|\bdpo\b|\bgrpo\b', r'模型训练', r'微调'),
    'coding': (r'笔试', r'算法题', r'编程题', r'\bleetcode\b', r'动态规划', r'二叉树'),
}


def domain(title, role, body, kind='interview'):
    """Prefer explicit heading/role topics; fall back to several distinct body signals."""
    if kind == 'career':
        return 'career', 'kind'
    heading = title + '\n' + role
    for key, patterns in DOMAIN_PATTERNS.items():
        if any(re.search(p, heading, re.I) for p in patterns):
            return key, 'title_role'
    scores = {key: sum(bool(re.search(p, body, re.I)) for p in patterns)
              for key, patterns in DOMAIN_PATTERNS.items()}
    best = max(scores, key=scores.get)
    # A lone mention does not justify classifying an otherwise unspecified account.
    return (best, 'body') if scores[best] >= 2 else ('other', 'unspecified')


def date_key(note):
    """Known interview dates first; partial dates keep their original precision."""
    value = note['experience']
    if not value['year']:
        return ('', 0, 0)
    text = re.sub(r'^\s*(?:20\d{2}|\d{2}\s*年)\s*(?:年|[-/.])?\s*', '', value['interview_time'])
    parts = re.findall(r'\d+', text)
    return (value['year'], *(int(p) for p in (parts + ['0', '0'])[:2]))


def identifier(collection, key):
    return 'note_experience_' + hashlib.sha256(f'{collection}\n{key}'.encode('utf-8')).hexdigest()[:20]


def year(value):
    """Only derive a year explicitly written in the interview date, never a file or import date."""
    found = re.search(r'(?<!\d)(20\d{2})(?:\s*年|[-/.]|$)', value or '')
    if found:
        return found[1]
    found = re.search(r'(?<!\d)(\d{2})\s*年', value or '')
    return '20' + found[1] if found else ''


def validate(entries, collection):
    from .note_organization import _string, _url
    require(isinstance(entries, dict) and len(entries) <= 2000, 'Invalid public experiences')
    notes = {n['id']: n for n in collection['notes']}
    chapters = {c['file']: c for c in collection['chapters']}
    assigned = set()
    for key, value in entries.items():
        require(isinstance(key, str) and re.fullmatch(r'[a-z0-9_-]{1,80}', key), 'Invalid experience key')
        require(isinstance(value, dict) and set(value) <= FIELDS, 'Unknown public experience field')
        _string(value.get('title'), 'experience title', 200, False)
        require(value.get('kind') in KINDS, 'Unknown public experience kind')
        members = value.get('note_ids')
        require(isinstance(members, list) and 1 <= len(members) <= 500 and
                all(isinstance(n, str) and n in notes for n in members), 'Experience needs source-local note IDs')
        require(len(set(members)) == len(members) and not assigned.intersection(members),
                'A note belongs to one public experience only')
        assigned.update(members)
        _string(value.get('summary', ''), 'experience summary', 1000)
        for field in FACT_FIELDS:
            _string(value.get(field, ''), field, 160)
        require(value['kind'] == 'interview' or not value.get('interview_time'),
                'A company question list or career guide has no interview date')
        facts = value.get('facts', [])
        require(isinstance(facts, list) and len(facts) <= 20, 'Invalid experience facts')
        supported = set()
        for fact in facts:
            require(isinstance(fact, dict) and set(fact) <= {'field', 'quote', 'note_id', 'url'},
                    'Invalid experience fact')
            field = fact.get('field')
            require(field in FACT_FIELDS and bool(value.get(field)), 'Fact needs a populated field')
            quote = _string(fact.get('quote'), 'fact quote', 2000, False)
            require(value[field] in quote, 'Experience value must be supported by its source quote')
            note_id, url = fact.get('note_id'), fact.get('url', '')
            _url(url, 'experience fact URL')
            require(note_id in members if note_id else bool(url), 'Fact needs a member note or a public URL')
            if note_id and not url:
                note = notes[note_id]
                chapter = chapters[note['file']]
                text = '\n'.join(str(x or '') for x in (note['title'], note['heading'], note['body'],
                                                       chapter['title'], chapter['intro']))
                require(quote in text, 'Fact quote is absent from the source note')
            supported.add(field)
        require(all(not value.get(field) or field in supported for field in FACT_FIELDS),
                'Company, role, round and dates need separate source facts')


def project(collection):
    """Build article views without rewriting any original note, link or personal occurrence."""
    profile = collection.get('organization', {})
    by_id = {n['id']: n for n in collection['notes']}
    result = []
    for key, value in profile.get('experiences', {}).items():
        members = [by_id[n] for n in value['note_ids'] if n in by_id]
        if not members:
            continue
        first = members[0]
        kind = value['kind']
        details = {f: value.get(f, '') for f in FACT_FIELDS}
        details.update(summary=value.get('summary', ''), year=year(details['interview_time']),
                       note_ids=value['note_ids'], facts=value.get('facts', []),
                       incomplete=len(members) != len(value['note_ids']))
        body = first['body'] if len(members) == 1 and first['title'] == value['title'] else '\n\n'.join(
            '### ' + n['title'] + '\n\n' + n['body'] for n in members)
        topic, basis = domain(value['title'], details['role'], body, kind)
        details.update(domain=topic, domain_title=DOMAINS[topic], domain_basis=basis)
        verification = 'needs_review' if details['incomplete'] or any(
            n['organization']['verification'] in ('needs_review', 'outdated') for n in members) else 'reference'
        result.append({**first, 'id': identifier(collection['name'], key), 'title': value['title'],
                       'heading': value['title'], 'body': body, 'group': None, 'order': len(result),
                       'marks': list(dict.fromkeys(m for n in members for m in n['marks'])),
                       'experience': details, 'organization': {
                           'area': 'public-experiences', 'area_title': '公开面经',
                           'topic': kind, 'topic_title': LABELS[kind], 'kind': kind,
                           'tags': [], 'question_type': '', 'verification': verification, 'language': first['organization']['language'],
                           'evidence': [], 'locked': False,
                       }})
    return result


def members(collection):
    return {n for v in collection.get('organization', {}).get('experiences', {}).values() for n in v['note_ids']}


def select(bundle, section='all'):
    require(section in ('all', 'knowledge', 'experiences'), 'Unknown notes section')
    if section == 'experiences':
        return [n for c in bundle['collections'] for n in c.get('experiences', [])]
    if section == 'knowledge':
        excluded = {n for c in bundle['collections'] for n in members(c)}
        return [n for n in bundle['notes'] if n['id'] not in excluded]
    return bundle['notes']


def find(bundle, note_id):
    return next((n for n in [*bundle['notes'], *select(bundle, 'experiences')] if n['id'] == note_id), None)


def linked(note, links):
    """Count a personal question once even if it links to several sections of the same article."""
    ids = note['experience']['note_ids'] if 'experience' in note else [note['id']]
    result = {}
    for member in ids:
        for question, link in links.get(member, []):
            previous = result.get(question['id'])
            if previous is None or link['relation'] == 'answers':
                result[question['id']] = (question, link)
    return list(result.values())
