"""Evidence-bearing, source-local study links. Separate from personal interview frequency."""
import re

from .schema import require

FIELDS = {'from_note', 'to_note', 'relation', 'question_quote', 'answer_quote', 'reason'}


def _text(note):
    return '\n'.join((note['title'], note['body']))


def _valid(edge, notes, members, profile):
    if not isinstance(edge, dict) or set(edge) != FIELDS:
        return False
    if not all(isinstance(edge[k], str) for k in FIELDS):
        return False
    source, target = notes.get(edge['from_note']), notes.get(edge['to_note'])
    if not source or not target or edge['from_note'] not in members or edge['to_note'] in members:
        return False
    classification = {**profile.get('chapters', {}).get(target['file'], {}),
                      **profile.get('notes', {}).get(target['id'], {})}
    if classification.get('kind') == 'info' or edge['relation'] not in ('answers', 'covers'):
        return False
    return all(8 <= len(edge[key].strip()) <= 2000 and edge[key] in _text(note)
               for key, note in (('question_quote', source), ('answer_quote', target))) and \
        1 <= len(edge['reason'].strip()) <= 500


def validate(profile, collection):
    """Exact quotes establish provenance, not technical truth or a new interview occurrence."""
    entries = profile.get('study_links', {})
    require(isinstance(entries, dict) and len(entries) <= 20000, 'Invalid study links')
    notes = {n['id']: n for n in collection['notes']}
    members = {n for v in profile.get('experiences', {}).values() for n in v['note_ids']}
    seen = set()
    for key, edge in entries.items():
        require(isinstance(key, str) and re.fullmatch(r'[a-z0-9_-]{1,80}', key), 'Invalid study link key')
        require(_valid(edge, notes, members, profile),
                'Study links need source-local experience/knowledge notes, exact quotes and a reason')
        signature = (edge['from_note'], edge['to_note'], edge['question_quote'])
        require(signature not in seen, 'Duplicate study link')
        seen.add(signature)


def project(collection):
    """Attach bidirectional display cards; stale links remain in metadata, excluded from counts."""
    profile = collection.get('organization', {})
    notes = {n['id']: {**n, 'study_notes': [], 'public_experiences': [], 'study_links_incomplete': 0}
             for n in collection['notes']}
    articles = [{**n, 'study_notes': [], 'public_experiences': [], 'study_links_incomplete': 0}
                for n in collection.get('experiences', [])]
    member_articles = {member: article for article in articles for member in article['experience']['note_ids']}
    members = set(member_articles)
    valid, incomplete, seen = [], 0, set()
    for key, edge in profile.get('study_links', {}).items():
        signature = (edge.get('from_note'), edge.get('to_note'), edge.get('question_quote')) if isinstance(edge, dict) else ()
        if not _valid(edge, notes, members, profile) or signature in seen:
            incomplete += 1
            if isinstance(edge, dict):
                affected = [notes.get(edge.get('from_note')), notes.get(edge.get('to_note')),
                            member_articles.get(edge.get('from_note'))]
                for note in affected:
                    if note:
                        note['study_links_incomplete'] += 1
            continue
        seen.add(signature)
        valid.append(key)
        source, target = notes[edge['from_note']], notes[edge['to_note']]
        article = member_articles[source['id']]
        common = {k: edge[k] for k in ('relation', 'question_quote', 'answer_quote', 'reason')}
        knowledge = {**common, 'id': target['id'], 'title': target['title'],
                     'area_title': target['organization']['area_title'],
                     'topic_title': target['organization']['topic_title']}
        source['study_notes'].append(knowledge)
        article['study_notes'].append(knowledge)
        target['public_experiences'].append({**common, 'id': article['id'], 'title': article['title'],
                                             'company': article['experience']['company'],
                                             'interview_time': article['experience']['interview_time']})
    return {**collection, 'notes': list(notes.values()), 'experiences': articles,
            'valid_study_links': valid, 'study_links_incomplete': incomplete}


def detail(note):
    return {k: note.get(k, [] if k != 'study_links_incomplete' else 0)
            for k in ('study_notes', 'public_experiences', 'study_links_incomplete')}
