"""Explicit format upgrade with a verified portable backup and journaled activation."""
import hashlib
import zipfile
import shutil
from pathlib import Path

from .schema import require, validate_data
from .storage import open_bank, bank_file, dumps, read_json, transaction, fingerprint, atomic_write
from .state import empty_state
from .ids import new_id, utc_now


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
        key = new_id('migration')
        backup = bank_file(bank, f'backups/{key}.zip')
        backup.parent.mkdir(exist_ok=True)
        hashes = {}
        for p in paths:
            require(not p.is_symlink() and p.resolve().is_relative_to(bank.resolve()), 'Backup rejects escaped paths')
            hashes[p.relative_to(bank).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        with zipfile.ZipFile(backup, 'x', zipfile.ZIP_DEFLATED) as z:
            for p in paths:
                z.write(p, p.relative_to(bank).as_posix())
            z.writestr('_BACKUP_MANIFEST.json', dumps({'version': 1, 'files': hashes}))
        with zipfile.ZipFile(backup) as z:
            require(z.testzip() is None, 'Backup CRC failed')
            for name, sha in hashes.items():
                require(hashlib.sha256(z.read(name)).hexdigest() == sha, 'Backup hash failed')
        sha = hashlib.sha256(backup.read_bytes()).hexdigest()
        atomic_write(backup.with_suffix('.zip.sha256'), sha + '\n')
        config = {**config, 'bank_version': 2}
        manifest = {**manifest, 'schema_version': 2, 'bank_version': 2, 'last_updated_at': utc_now()}
        data['_state'] = empty_state()
        # Legacy answers remain intact, but their coverage must be rechecked in V2.
        for a in data['answers']:
            a['question_revision'] = None
        validate_data(data, config)
        from .storage import jsonl_text
        transaction(bank, {'manifest.json': dumps(manifest)+'\n', 'config.json': dumps(config)+'\n',
                           'data/state.json': dumps(data['_state'])+'\n',
                           'data/answers.jsonl': jsonl_text(data['answers'])})
        return {**result, 'upgraded': True, 'backup': str(backup), 'sha256': sha, 'after_digest': fingerprint(data)}


def restore_backup(bank, archive, destination):
    """Restore only into a new bank-local directory, never overwrite later writes."""
    import json
    from .storage import atomic_bytes, load_bank
    with open_bank(bank):
        archive = bank_file(bank, str(Path('backups') / archive))
        require(archive.parent.resolve() == bank_file(bank, 'backups').resolve(), 'Backup must be in bank/backups')
        target = bank_file(bank, 'restored/' + destination)
        require(target.resolve().is_relative_to(bank_file(bank, 'restored').resolve()), 'Invalid restore destination')
        require(not target.exists(), 'Restore destination must not exist')
        with zipfile.ZipFile(archive) as z:
            manifest = json.loads(z.read('_BACKUP_MANIFEST.json'))
            require(set(z.namelist()) == {'_BACKUP_MANIFEST.json', *manifest['files']}, 'Backup entry mismatch')
            content = {}
            for name, sha in manifest['files'].items():
                path = target / name
                require(path.resolve().is_relative_to(target.resolve()), 'Unsafe backup path')
                raw = z.read(name)
                require(hashlib.sha256(raw).hexdigest() == sha, 'Backup hash mismatch')
                content[name] = raw
            for name, raw in content.items():
                (target / name).parent.mkdir(parents=True, exist_ok=True)
                atomic_bytes(target / name, raw)
        load_bank(target)
        return {'restored_bank': str(target), 'files': len(content), 'original_bank_unchanged': True}
