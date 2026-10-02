"""Explicit format upgrade with a verified portable backup and journaled activation."""
import shutil
from pathlib import Path

from .backups import restore_into, write_archive
from .schema import require, validate_data
from .storage import open_bank, bank_file, dumps, read_json, transaction, fingerprint
from .state import empty_state, revision
from .ids import new_id, utc_now
from .timestamps import parse_timestamp


def migrate(bank, action='plan'):
    require(action in ('plan', 'apply'), 'Unknown migration action')
    with open_bank(bank) as (manifest, config, data):
        pending = []
        for p in bank_file(bank, 'runs').glob('run_*/run.json'):
            meta = read_json(p)
            if meta['status'] == 'staged':
                pending.append(meta['id'])
        result = {'from_version': manifest['schema_version'], 'to_version': 2,
                  'pending_stages': pending, 'counts': {k: len(v) for k, v in data.items() if k != '_state'},
                  'already_current': manifest['schema_version'] == 2}
        paths = [p for p in bank.rglob('*') if p.is_file() and p.relative_to(bank).parts[0] not in ('backups', 'cache', 'exports') and p.name != '.bank.lock']
        result['backup_files'] = len(paths)
        result['backup_uncompressed_bytes'] = sum(p.stat().st_size for p in paths)
        result['required_free_bytes_estimate'] = result['backup_uncompressed_bytes'] * 2 + 1024 * 1024
        result['available_bytes'] = shutil.disk_usage(bank).free
        if action == 'plan' or result['already_current']:
            return result
        require(not pending, 'Resolve or explicitly abandon pending stages before migration')
        require(result['available_bytes'] >= result['required_free_bytes_estimate'], 'Insufficient free space for verified backup and migration journal')
        for p in paths:
            require(not p.is_symlink() and p.resolve().is_relative_to(bank.resolve()), 'Backup rejects escaped paths')
        backup = bank_file(bank, f"backups/{new_id('migration')}.zip")
        sha = write_archive(bank, paths, backup, kind='migration', created_at=utc_now(),
                            bank_schema_version=manifest['schema_version'])['sha256']
        config = {**config, 'bank_version': 2}
        manifest = {**manifest, 'schema_version': 2, 'bank_version': 2, 'last_updated_at': utc_now()}
        data['_state'] = empty_state()
        # A question untouched since its answer was written still has the wording that answer covered.
        # Anything edited afterwards (curate, merge, reclassification) keeps None and needs a coverage recheck.
        questions = {q['id']: q for q in data['questions']}
        for a in data['answers']:
            q = questions[a['question_id']]
            unchanged = parse_timestamp(q['updated_at']) <= parse_timestamp(a['created_at'])
            a['question_revision'] = revision(q) if unchanged else None
        result['answers_bound'] = sum(a['question_revision'] is not None for a in data['answers'])
        result['answers_need_recheck'] = len(data['answers']) - result['answers_bound']
        validate_data(data, config)
        from .storage import jsonl_text
        transaction(bank, {'manifest.json': dumps(manifest)+'\n', 'config.json': dumps(config)+'\n',
                           'data/state.json': dumps(data['_state'])+'\n',
                           'data/answers.jsonl': jsonl_text(data['answers'])})
        return {**result, 'upgraded': True, 'backup': str(backup), 'sha256': sha, 'after_digest': fingerprint(data)}


def restore_backup(bank, archive, destination):
    """Legacy form: restore a bank-local backup into bank/restored/<name>. Prefer `backup restore`."""
    with open_bank(bank):
        archive = bank_file(bank, str(Path('backups') / archive))
        require(archive.parent.resolve() == bank_file(bank, 'backups').resolve(), 'Backup must be in bank/backups')
        target = bank_file(bank, 'restored/' + destination)
        require(target.resolve().is_relative_to(bank_file(bank, 'restored').resolve()), 'Invalid restore destination')
        return restore_into(archive, target)
