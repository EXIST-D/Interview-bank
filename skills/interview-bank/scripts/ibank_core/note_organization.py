"""Source-local navigation metadata. Never rewrites a published note or its ID."""
import copy
from collections import Counter
from urllib.parse import urlsplit

from .ids import utc_now
from .schema import require
from .storage import atomic_write, bank_file, dumps, fingerprint, open_bank, read_json

KINDS = ('material', 'qa', 'knowledge', 'case', 'reading', 'info')
VERIFICATIONS = ('reference', 'verified', 'needs_review', 'outdated')
META_FIELDS = {'description', 'author', 'homepage', 'license', 'license_url', 'version', 'updated_at', 'language'}
ITEM_FIELDS = {'area', 'topic', 'tags', 'kind', 'verification', 'language', 'evidence', 'locked', 'user_quote'}
PATH = 'collections/_organization.json'


def load(bank):
    path = bank_file(bank, PATH)
    value = read_json(path) if path.is_file() else {'schema_version': 1, 'collections': {}}
    require(isinstance(value, dict) and value.get('schema_version') == 1 and
            isinstance(value.get('collections'), dict), 'Invalid notes organization file')
    return value


def source_digest(collection):
    return fingerprint({'chapters': collection['chapters'], 'notes': [
        {k: v for k, v in note.items() if k != 'organization'} for note in collection['notes']]})


def profile_digest(profile):
    return fingerprint(profile or {})


def _string(value, name, limit=160, empty=True):
    require(isinstance(value, str) and len(value) <= limit and (empty or value.strip()), f'Invalid {name}')
    return value.strip()


def _url(value, name):
    _string(value, name, 2000)
    try:
        parsed = urlsplit(value)
        valid = not value or (parsed.scheme in ('http', 'https') and parsed.hostname and
                              not parsed.username and not parsed.password)
    except ValueError:
        valid = False
    require(bool(valid), f'{name} must be a public HTTP(S) URL without credentials')


def _areas(value):
    require(isinstance(value, list) and len(value) <= 40, 'areas must be a list, at most 40')
    areas, topics = set(), set()
    for area in value:
        require(isinstance(area, dict) and set(area) == {'id', 'title', 'topics'}, 'Area needs id, title, topics')
        _string(area['id'], 'area id', 80, False)
        _string(area['title'], 'area title', 100, False)
        require(area['id'] not in areas, 'Duplicate area id')
        areas.add(area['id'])
        require(isinstance(area['topics'], list) and len(area['topics']) <= 80, 'Invalid topics')
        for topic in area['topics']:
            require(isinstance(topic, dict) and set(topic) == {'id', 'title'}, 'Topic needs id and title')
            _string(topic['id'], 'topic id', 80, False)
            _string(topic['title'], 'topic title', 100, False)
            require(topic['id'] not in topics, 'Duplicate topic id within source')
            topics.add(topic['id'])
    return areas, {t['id']: a['id'] for a in value for t in a['topics']}


def _item(value, area_ids, topic_areas):
    require(isinstance(value, dict) and set(value) <= ITEM_FIELDS, 'Unknown organization item field')
    for key in ('area', 'topic', 'language', 'user_quote'):
        if key in value:
            _string(value[key], key, 2000 if key == 'user_quote' else 80)
    if value.get('area'):
        require(value['area'] in area_ids, 'Unknown area')
    if value.get('topic'):
        require(topic_areas.get(value['topic']) == value.get('area'), 'Topic must belong to this area')
    if 'tags' in value:
        require(isinstance(value['tags'], list) and len(value['tags']) <= 20, 'Invalid tags')
        require(len(set(value['tags'])) == len(value['tags']) if all(isinstance(t, str) for t in value['tags']) else False,
                'Tags must be unique strings')
        for tag in value['tags']:
            _string(tag, 'tag', 80, False)
    if 'kind' in value:
        require(value['kind'] in KINDS, 'Unknown content kind')
    if 'verification' in value:
        require(value['verification'] in VERIFICATIONS, 'Unknown verification state')
    if 'evidence' in value:
        require(isinstance(value['evidence'], list) and len(value['evidence']) <= 20, 'Invalid evidence')
        for url in value['evidence']:
            _url(url, 'evidence URL')
            require(bool(url), 'Evidence URL must not be empty')
    if value.get('verification') == 'verified':
        require(bool(value.get('evidence')), 'Verified notes require evidence URLs; reading is not verification')
    if 'locked' in value:
        require(isinstance(value['locked'], bool), 'locked must be a boolean')
    if value.get('locked'):
        require(bool(value.get('user_quote', '').strip()), 'Protected classification needs the user\'s words')


def _patch_items(existing, patch, known):
    require(isinstance(patch, dict) and len(patch) <= 20000, 'Invalid classification patch')
    result = copy.deepcopy(existing)
    for key, change in patch.items():
        require(key in known, f'Unknown chapter/note: {key}')
        require(change is None or isinstance(change, dict), 'Invalid item change')
        previous = result.get(key, {})
        if previous.get('locked') and change != previous:
            require(isinstance(change, dict) and bool(change.get('user_quote', '').strip()),
                    'Classification is protected; explicit user words are required')
        if change is None:
            result.pop(key, None)
        else:
            result[key] = {**previous, **change}
    return result


def organize(bank, name, payload, preview=False):
    """Patch one collection atomically with optimistic concurrency and no original-content writes."""
    require(isinstance(payload, dict) and set(payload) <= {
        'schema_version', 'collection', 'source_digest', 'organization_digest', 'metadata', 'areas', 'chapters', 'notes'
    }, 'Invalid organization payload')
    require(payload.get('schema_version') == 1 and payload.get('collection') == name, 'Wrong organization collection/version')
    from .notes import load_notes
    with open_bank(bank):
        bundle = load_notes(bank)
        collection = next((c for c in bundle['collections'] if c['name'] == name), None)
        require(collection is not None, f'Unknown collection: {name}')
        all_profiles = load(bank)
        previous = all_profiles['collections'].get(name, {})
        require(payload.get('source_digest') == source_digest(collection), 'Source changed; regenerate the organization catalog')
        require(payload.get('organization_digest') == profile_digest(previous), 'Organization changed; regenerate the catalog')
        candidate = copy.deepcopy(previous)
        metadata = payload.get('metadata', {})
        require(isinstance(metadata, dict) and set(metadata) <= META_FIELDS, 'Unknown source metadata field')
        for key, value in metadata.items():
            _string(value, key, 2000 if key in ('description', 'homepage', 'license_url') else 200)
            if key in ('homepage', 'license_url'):
                _url(value, key)
        candidate['metadata'] = {**candidate.get('metadata', {}), **metadata}
        candidate['areas'] = copy.deepcopy(payload.get('areas', candidate.get('areas', [])))
        area_ids, topic_areas = _areas(candidate['areas'])
        candidate['chapters'] = _patch_items(candidate.get('chapters', {}), payload.get('chapters', {}),
                                             {c['file'] for c in collection['chapters']})
        candidate['notes'] = _patch_items(candidate.get('notes', {}), payload.get('notes', {}),
                                          {n['id'] for n in collection['notes']})
        for value in candidate['chapters'].values():
            _item(value, area_ids, topic_areas)
        for note in collection['notes']:
            explicit = candidate['notes'].get(note['id'], {})
            _item(explicit, area_ids, topic_areas)
            inherited = {**candidate['chapters'].get(note['file'], {}), **explicit}
            protected = {**previous.get('chapters', {}).get(note['file'], {}),
                         **previous.get('notes', {}).get(note['id'], {})}
            if protected.get('locked') and inherited != protected:
                note_change = payload.get('notes', {}).get(note['id']) or {}
                chapter_change = payload.get('chapters', {}).get(note['file']) or {}
                require(bool(note_change.get('user_quote', '').strip() or
                             chapter_change.get('user_quote', '').strip()),
                        'Classification is protected; explicit user words are required')
            _item(inherited, area_ids, topic_areas)
        changed = {key: sum(old.get(k) != value for k, value in new.items()) + len(set(old) - set(new))
                   for key, old, new in (
                       ('metadata', previous.get('metadata', {}), candidate['metadata']),
                       ('chapters', previous.get('chapters', {}), candidate['chapters']),
                       ('notes', previous.get('notes', {}), candidate['notes']))}
        changed['areas'] = int(previous.get('areas', []) != candidate['areas'])
        changed['source'] = int(bool(previous.get('source_digest') and
                                     previous['source_digest'] != source_digest(collection)))
        changes = any(changed.values())
        if changes and not preview:
            candidate['updated_at'] = utc_now()
            candidate['source_digest'] = source_digest(collection)
            history = previous.get('history', [])
            candidate['history'] = (history + [{'at': candidate['updated_at'], 'changed': changed,
                                                 'source_digest': candidate['source_digest']}])[-30:]
            all_profiles['collections'][name] = candidate
            atomic_write(bank_file(bank, PATH), dumps(all_profiles) + '\n')
        return {'collection': name, 'preview': preview, 'changed': changes, 'changes': changed,
                'areas': len(candidate['areas']), 'topics': sum(len(a['topics']) for a in candidate['areas']),
                'source_unchanged': True, 'links_unchanged': True,
                'organization_digest': profile_digest(candidate if changes and not preview else previous)}


def enrich(bundle, profiles):
    """Add display fields to an in-memory bundle; original dictionaries stay unchanged."""
    collections = []
    for source in bundle['collections']:
        profile = profiles['collections'].get(source['name'], {})
        labels = {a['id']: a['title'] for a in profile.get('areas', [])}
        topic_labels = {t['id']: t['title'] for a in profile.get('areas', []) for t in a['topics']}
        notes = []
        for raw in source['notes']:
            value = {**profile.get('chapters', {}).get(raw['file'], {}), **profile.get('notes', {}).get(raw['id'], {})}
            notes.append({**raw, 'organization': {
                'area': value.get('area', ''), 'area_title': labels.get(value.get('area'), ''),
                'topic': value.get('topic', ''), 'topic_title': topic_labels.get(value.get('topic'), ''),
                'tags': value.get('tags', []), 'kind': value.get('kind', 'material'),
                'verification': value.get('verification', 'reference'),
                'language': value.get('language', profile.get('metadata', {}).get('language', '')),
                'evidence': value.get('evidence', []), 'locked': bool(value.get('locked')),
            }})
        collections.append({**source, 'notes': notes, 'organization': profile})
    return {**bundle, 'collections': collections, 'notes': [n for c in collections for n in c['notes']]}


def collection_card(collection, linked=()):
    notes = collection['notes']
    active = [n for n in notes if n['organization']['kind'] != 'info']
    profile = collection.get('organization', {})
    areas = []
    for area in profile.get('areas', []):
        mine = [n for n in active if n['organization']['area'] == area['id']]
        areas.append({**area, 'count': len(mine), 'topics': [
            {**t, 'count': sum(n['organization']['topic'] == t['id'] for n in mine)} for t in area['topics']]})
    return {'name': collection['name'], 'title': collection['title'], 'origin': collection.get('origin', ''),
            'imported_at': collection['imported_at'], 'total': len(notes), 'content_total': len(active),
            'information_total': len(notes) - len(active), 'content_ids': [n['id'] for n in active],
            'information_ids': [n['id'] for n in notes if n['organization']['kind'] == 'info'],
            'marked': sum(bool(n['marks']) for n in active), 'linked': sum(n['id'] in linked for n in active),
            'chapters': [{**ch, 'count': sum(n['chapter'] == ch['index'] for n in active)} for ch in collection['chapters']],
            'areas': areas, 'uncategorized': sum(not n['organization']['area'] for n in active),
            'tags': sorted({t for n in active for t in n['organization']['tags']}),
            'kinds': dict(Counter(n['organization']['kind'] for n in active)),
            'verification': dict(Counter(n['organization']['verification'] for n in active)),
            'metadata': profile.get('metadata', {}), 'history': profile.get('history', []),
            'organization_updated_at': profile.get('updated_at'),
            'organization_stale': bool(profile.get('source_digest') and profile['source_digest'] != source_digest(collection))}


def catalog(bank, name):
    from .notes import load_notes
    with open_bank(bank, shared=True):
        bundle = load_notes(bank)
        profiles = load(bank)
        collection = next((c for c in bundle['collections'] if c['name'] == name), None)
        require(collection is not None, f'Unknown collection: {name}')
        profile = profiles['collections'].get(name, {})
        return {'collection': name, 'source_digest': source_digest(collection), 'organization_digest': profile_digest(profile),
                'metadata': profile.get('metadata', {}), 'areas': profile.get('areas', []),
                'chapters': collection['chapters'], 'chapter_rules': profile.get('chapters', {}),
                'note_rules': profile.get('notes', {}), 'notes': [
                    {'id': n['id'], 'title': n['title'], 'file': n['file'], 'group': n['group'],
                     'classification': n['organization']} for n in collection['notes']]}
