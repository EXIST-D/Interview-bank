"""Reviewed reading units. Raw notes, original IDs and evidence links remain immutable."""
import re

from .schema import require
from .storage import fingerprint

FIELDS = {'title', 'note_ids', 'source_url', 'content_digest', 'reason'}
FOOTER = re.compile(r'\n*原文[：:]\s*\[查看来源\]\((https?://[^)]+)\)[^\n]*\s*\Z')


def digest(notes):
    return fingerprint([{k: n[k] for k in ('id', 'title', 'body')} for n in notes])


def source_url(note):
    match = FOOTER.search(note['body'])
    return match[1].split('#')[0] if match else ''


def _members(value, notes, profile):
    if not isinstance(value, dict) or set(value) != FIELDS:
        return None
    ids = value['note_ids']
    if not isinstance(ids, list) or not 2 <= len(ids) <= 500 or not all(isinstance(i, str) for i in ids):
        return None
    if len(set(ids)) != len(ids) or any(i not in notes for i in ids):
        return None
    members = [notes[i] for i in ids]
    public = {i for v in profile.get('experiences', {}).values() for i in v['note_ids']}
    classifications = [{**profile.get('chapters', {}).get(n['file'], {}),
                        **profile.get('notes', {}).get(n['id'], {})} for n in members]
    signatures = {(c.get('kind', 'material'), c.get('area', ''), c.get('topic', '')) for c in classifications}
    if len(signatures) != 1 or classifications[0].get('kind') == 'info' or public.intersection(ids):
        return None
    if any(c.get('locked') for c in classifications):
        return None
    if not value['source_url'] or any(source_url(n) != value['source_url'] for n in members):
        return None
    if value['content_digest'] != digest(members):
        return None
    return members


def validate(entries, collection, profile):
    from .note_organization import _string, _url
    require(isinstance(entries, dict) and len(entries) <= 5000, 'Invalid reading groups')
    notes = {n['id']: n for n in collection['notes']}
    assigned = set()
    for key, value in entries.items():
        require(isinstance(key, str) and re.fullmatch(r'[a-z0-9_-]{1,80}', key), 'Invalid reading group key')
        require(isinstance(value, dict) and set(value) == FIELDS, 'Invalid reading group fields')
        _string(value['title'], 'reading title', 300, False)
        _string(value['reason'], 'reading reason', 500, False)
        _url(value['source_url'], 'reading source URL')
        require(_members(value, notes, profile) is not None,
                'Reading groups need unchanged, unprotected source-local members from one original article and classification')
        require(not assigned.intersection(value['note_ids']), 'A note belongs to one reading group only')
        assigned.update(value['note_ids'])


def _cards(cards):
    """One destination card; the original quote-bearing edges stay in the organization file."""
    result = {}
    for card in cards:
        prior = result.get(card['id'])
        if prior is None or card['relation'] == 'answers' and prior['relation'] != 'answers':
            result[card['id']] = card
    return list(result.values())


def _body(members, title, url):
    parts = []
    for i, note in enumerate(members):
        text = FOOTER.sub('', note['body']).strip()
        # Only the generated citation footer is removed. Code, tables and source headings stay verbatim.
        intro = re.sub(r'\s*·\s*导读$', '', note['title']).strip()
        parts.append(text if i == 0 and intro == title else '### ' + note['title'] + '\n\n' + text)
    return '\n\n'.join(parts) + '\n\n原文：[查看来源](' + url + ')'


def project(collection):
    profile = collection.get('organization', {})
    notes = {n['id']: n for n in collection['notes']}
    grouped, aliases, incomplete = {}, {}, 0
    for key, value in profile.get('reading_groups', {}).items():
        members = _members(value, notes, profile)
        if members is None or any(i in aliases for i in value['note_ids']):
            incomplete += 1
            continue  # A stale group must never hide a new/changed source segment.
        first = members[0]
        status = max((n['organization']['verification'] for n in members), key=(
            'verified', 'reference', 'needs_review', 'outdated').index)
        reading = {'note_ids': value['note_ids'], 'content_digest': value['content_digest'],
                   'source_url': value['source_url'], 'key': key, 'reason': value['reason']}
        grouped[first['id']] = {**first, 'title': value['title'], 'heading': value['title'], 'group': None,
                               'body': _body(members, value['title'], value['source_url']), 'reading': reading,
                               'order': min(n['order'] for n in members),
                               'marks': list(dict.fromkeys(m for n in members for m in n['marks'])),
                               'organization': {**first['organization'], 'verification': status,
                                   'evidence': list(dict.fromkeys(u for n in members for u in n['organization']['evidence'])),
                                   'tags': list(dict.fromkeys(t for n in members for t in n['organization']['tags']))},
                               'study_notes': _cards([c for n in members for c in n.get('study_notes', [])]),
                               'public_experiences': _cards([c for n in members for c in n.get('public_experiences', [])]),
                               'study_links_incomplete': sum(n.get('study_links_incomplete', 0) for n in members)}
        aliases.update({i: first['id'] for i in value['note_ids']})
    for note in collection['notes']:
        if note['id'] not in aliases and note['organization'].get('display_title'):
            grouped[note['id']] = {**note, 'title': note['organization']['display_title']}
            aliases[note['id']] = note['id']
    readings = sorted([grouped.get(n['id'], n) for n in collection['notes']
                       if n['id'] not in aliases or aliases[n['id']] == n['id']], key=lambda n: n['order'])
    by_id = {n['id']: n for n in readings}
    articles = []
    for article in collection.get('experiences', []):
        cards = []
        for edge in article.get('study_notes', []):
            target = by_id[aliases.get(edge['id'], edge['id'])]
            cards.append({**edge, 'id': target['id'], 'title': target['title'],
                          'area_title': target['organization']['area_title'],
                          'topic_title': target['organization']['topic_title']})
        articles.append({**article, 'study_notes': _cards(cards)})
    return {**collection, 'readings': readings, 'reading_aliases': aliases,
            'reading_groups_incomplete': incomplete, 'experiences': articles}


def members(note):
    group = note.get('reading', note.get('experience', {}))
    return group['note_ids'] if 'note_ids' in group else [note['id']]
