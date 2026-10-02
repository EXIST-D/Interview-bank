"""Public CLI routing for durable maintenance, study sets and practice."""
from .schema import require
from .storage import read_json, open_bank

COMMANDS = {
    'migrate': ('plan','apply','restore'),
    'policy': ('list','add','disable'),
    'workflow': ('list','create','show','next','pause','resume','cancel','block','reconcile','revise','summary','export'),
    'studyset': ('list','create','show','refresh','export'),
    'study': ('record','queue','history'),
    'interview': ('list','start','next','answer','feedback','follow-up','end','show','summary','turn','review'),
    'evidence': ('list',),
}


# Composite commits only for routine lifecycle writes; policy and migrate stay explicit.
COMMIT_ALLOWED = ('workflow', 'studyset', 'study', 'interview')


def add_parsers(sub, common):
    from pathlib import Path
    for name, actions in COMMANDS.items():
        p = sub.add_parser(name, parents=[common])
        p.add_argument('action', choices=actions)
        p.add_argument('--id')
        p.add_argument('--input', type=Path)
        p.add_argument('--output')
        p.add_argument('--answers', choices=('both','with','without'), default='both')
        if name in COMMIT_ALLOWED:
            p.add_argument('--commit', action='store_true', help='Commit at once when the stage has no review items')
        if name == 'migrate':
            p.add_argument('--archive')
            p.add_argument('--destination')


def dispatch(bank, args):
    result = _dispatch(bank, args)
    if getattr(args, 'commit', False) and isinstance(result, dict) and 'run_id' in result:
        from .flows import commit_unless_review
        return commit_unless_review(bank, result)
    return result


def _dispatch(bank, args):
    payload = read_json(args.input) if args.input else {}
    require(isinstance(payload, dict), 'Input must be a JSON object')
    if payload:
        from .ingestion import privacy_check
        from .storage import dumps
        with open_bank(bank) as (_, config, _):
            privacy_check(dumps(payload), config)
    if args.command == 'migrate':
        from .migrations import migrate, restore_backup
        if args.action == 'restore':
            require(bool(args.archive and args.destination), 'restore needs --archive filename and --destination new-name')
            return restore_backup(bank, args.archive, args.destination)
        return migrate(bank, args.action)
    if args.command == 'policy':
        from .state import policy
        return policy(bank,args.action,payload,args.id)
    if args.command == 'workflow':
        from .workflows import workflow, next_batch, workflow_summary
        if args.action == 'next': return next_batch(bank,args.id)
        if args.action == 'summary': return workflow_summary(bank,args.id,args.output or 'update.md')
        if args.action == 'export':
            from .export import export_bank
            view = workflow(bank,'show',key=args.id)
            require(bool(args.output), 'export requires --output')
            return export_bank(bank,args.output,answer_mode=args.answers,question_ids=list(view['items']), occurrence_ids=view['occurrence_ids'])
        return workflow(bank,args.action,payload,args.id)
    if args.command == 'studyset':
        from .studysets import studyset, export_set
        if args.action == 'export':
            require(bool(args.output), 'export requires --output')
            return export_set(bank,args.id,args.output,args.answers)
        return studyset(bank,args.action,payload,args.id)
    if args.command == 'study':
        from .study import study
        return study(bank,args.action,payload)
    if args.command == 'interview':
        from .interview import interview
        if args.action in ('turn', 'review'):
            # turn = answer + commit + next (the feedback packet); review = feedback + commit + next question.
            from .flows import commit_unless_review
            staged = commit_unless_review(bank, interview(bank, 'answer' if args.action == 'turn' else 'feedback', payload, args.id))
            if staged.get('already_recorded'):
                return {**staged, 'next': interview(bank, 'next', {}, args.id)}
            if not staged.get('committed'):
                return staged
            return {'committed': staged['run_id'], 'next': interview(bank, 'next', {}, args.id)}
        return interview(bank,args.action,payload,args.id)
    from .state import require_v2
    with open_bank(bank) as (_,_,data):
        entries = list(require_v2(data)['evidence'].values())
        from .schema import string
        string(payload.get('query',''), 'query', empty=True)
        query = payload.get('query','').casefold()
        require(type(payload.get('limit',20)) is int and 0 < payload.get('limit',20) <= 100, 'Evidence limit must be 1..100')
        return {'evidence':[e for e in entries if query in (e.get('title','')+' '+e.get('evidence_note','')).casefold()][:payload.get('limit',20)],
                'instruction':'Reuse only after checking claim and version applicability; recorded access dates are not refreshed by this lookup.'}
