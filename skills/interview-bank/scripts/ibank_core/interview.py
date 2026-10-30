"""One-question-at-a-time interviews with durable user responses and sourced feedback."""
import copy
import json
from .schema import require, string
from .state import require_v2, record, resolve, revision, question
from .ids import new_id, utc_now
from .storage import open_bank, fingerprint
from .runs import stage_snapshot
from .studysets import select


def next_item(data, config, bank, session):
    if session['status'] != 'running':
        return {'status':session['status'], 'remaining':0, 'responses':len(session['responses'])}
    if session['responses'] and session['responses'][-1].get('feedback') is None:
        response = session['responses'][-1]
        rows = select(data,config,bank,ids=[response['question_id']])
        q = rows[0] if rows else None
        valid = bool(q and q['answer_status'] in ('source_backed','reviewed') and q['answer']['sources'])
        from .my_answers import for_question, load
        return {'status':'awaiting_feedback','response':response,'reference_answer':q['answer'] if valid else None,
                'reference_status':q['answer_status'] if q else 'excluded',
                # The person's own prepared answer: compare with it, but it is not a source of correctness.
                'my_answer':for_question(load(bank),data,q['id']) if q else None,
                'instruction':'Agent-only feedback packet. Cite actual answer omissions and boundaries; unavailable sources limit correctness judgments.'}
    pos = session['position']
    if session.get('follow_up'):
        return {'status':'question','question_id':session['question_ids'][pos-1], 'prompt':session['follow_up']['prompt'], 'follow_up':True}
    if pos >= len(session['question_ids']):
        return {'status':'completed','remaining':0}
    qid = session['question_ids'][pos]
    # Ask the frozen wording; changes are disclosed without rewriting a live session.
    q = question(data,qid)
    return {'status':'question','question_id':qid,'prompt':session['prompts'][qid],
            'changed_since_start':session['question_revisions'][qid] != revision(q),
            'remaining':len(session['question_ids'])-pos,'follow_up':False}


def interview(bank,action,payload=None,key=None):
    payload = payload or {}
    with open_bank(bank) as (_,config,current):
        state = require_v2(current)
        if action == 'list':
            return {'sessions':[{'id':s['id'],'name':s['name'],'status':s['status'],'position':s['position'],'total':len(s['question_ids'])} for s in state['sessions'].values()]}
        if action in ('show','next','summary'):
            s = record('sessions',current,key)
            if action == 'next':return next_item(current,config,bank,s)
            if action == 'show':return copy.deepcopy(s)
            return {'name':s['name'],'status':s['status'],'answered':s['position'],'total':len(s['question_ids']),
                    'feedback':[r['feedback'] for r in s['responses'] if r.get('feedback')],
                    'ungraded':sum(r.get('feedback') is None for r in s['responses']),
                    'weak_topics':list(dict.fromkeys(topic for r in s['responses'] for topic in (r.get('feedback') or {}).get('review_topics',[])))}
        final = copy.deepcopy(current)
        if action == 'start':
            string(payload.get('name'),'name')
            ids = payload.get('question_ids')
            if payload.get('studyset_id'):ids=record('studysets',current,payload['studyset_id'])['question_ids']
            require(ids is not None,'Choose a question set for the interview')
            rows = select(current,config,bank,ids=ids,limit=payload.get('limit',10))
            require(bool(rows),'No questions selected')
            if payload.get('keep_order') is True and not payload.get('studyset_id'):
                # The caller chose the order (for example by relevance to a job description).
                position = {}
                for index, qid in enumerate(ids):
                    position.setdefault(resolve(current, qid), index)
                rows.sort(key=lambda q: position.get(q['id'], len(ids)))
            key = new_id('session')
            s = {'id':key,'created_at':utc_now(),'name':payload['name'],'status':'running','position':0,
                 'question_ids':[q['id'] for q in rows], 'question_revisions':{q['id']:revision(q) for q in rows},
                 'prompts':{q['id']:q['canonical'] for q in rows},'responses':[], 'follow_up':None}
            # How the session came about (the Web reader: direction, JD reasons); display only, never evidence.
            meta = payload.get('meta')
            if meta is not None:
                require(isinstance(meta, dict) and len(json.dumps(meta, ensure_ascii=False)) <= 20000, 'Invalid session meta')
                s['meta'] = copy.deepcopy(meta)
            final['_state']['sessions'][key]=s
        else:
            s=record('sessions',final,key)
            # A lost receipt can be retried even after the session has ended.
            if action == 'answer':
                string(payload.get('request_id'),'request_id')
                prior = next((r for r in s['responses'] if r['request_id']==payload['request_id']), None)
                if prior:
                    require(prior['text']==payload.get('text') and prior['question_id']==payload.get('question_id'), 'Request ID reused for a different response')
                    return {'already_recorded':True,'response_id':prior['id']}
            if action == 'feedback':
                prior = next((r for r in s['responses'] if r['id']==payload.get('response_id')), None)
                if prior and prior.get('feedback'):
                    require(prior['feedback'].get('request_digest')==fingerprint(payload), 'Feedback already recorded with different content')
                    return {'already_recorded':True,'response_id':prior['id']}
            if action == 'end' and s['status'] != 'running':
                return {'already_ended':True,'status':s['status']}
            require(s['status']=='running','Session already ended')
            item=next_item(current,config,bank,s)
            if action=='answer':
                string(payload.get('request_id'),'request_id')
                string(payload.get('text'),'actual user response')
                require(item['status']=='question','Finish feedback before another answer')
                require(payload.get('question_id')==item['question_id'],'Question ID does not match the current prompt')
                captured = payload.get('captured_via', 'chat')
                require(captured in ('chat', 'voice_transcript'), 'captured_via must be chat or voice_transcript')
                # The text is the user's own answer, saved verbatim; the agent must not paraphrase or write it.
                r={'id':new_id('response'),'request_id':payload['request_id'],'question_id':item['question_id'],
                   'prompt':item['prompt'],'text':payload['text'],'created_at':utc_now(),'feedback':None,'follow_up':item['follow_up'],
                   'captured_via':captured}
                s['responses'].append(r)
                if not item['follow_up']:s['position']+=1
                s['follow_up']=None
            elif action=='feedback':
                require(item['status']=='awaiting_feedback','No response awaiting feedback')
                require(payload.get('response_id')==item['response']['id'],'Feedback response mismatch')
                observations=payload.get('observations')
                require(isinstance(observations,list) and bool(observations),'Feedback needs concrete observations')
                for o in observations:
                    require(isinstance(o,dict) and o.get('dimension') in ('accuracy','coverage','constraints','clarity'),'Invalid feedback dimension')
                    string(o.get('note'),'observation.note')
                    if o.get('quote'):
                        string(o['quote'], 'observation.quote')
                        require(o['quote'] in item['response']['text'],'Feedback quote is not in the actual response')
                ref=item['reference_answer']
                require(ref is not None or payload.get('limited_basis') is True,'No verified reference: explicitly limit feedback')
                # A changed frozen question needs an explicit applicability check by the host.
                qid=item['response']['question_id']
                changed=s['question_revisions'][qid]!=revision(question(current,qid))
                require(not changed or payload.get('limited_basis') is True,'Question changed: feedback must disclose limited applicability')
                topics=payload.get('review_topics',[])
                require(isinstance(topics,list) and all(isinstance(t,str) and t.strip() for t in topics),'Invalid review topics')
                s['responses'][-1]['feedback']={'observations':copy.deepcopy(observations),'review_topics':topics,
                    'limited_basis':payload.get('limited_basis',False),'reference_answer_id':ref['id'] if ref else None,
                    'reference_sources':copy.deepcopy(ref['sources']) if ref else [],'created_at':utc_now(),
                    'request_digest':fingerprint(payload)}
                # Feedback written by the Web reader's model says so, and may carry a per-key-point check of the reference.
                if payload.get('generated_by') is not None:
                    author = payload['generated_by']
                    require(isinstance(author, dict) and author.get('kind') == 'model' and isinstance(author.get('model'), str) and author['model'].strip()
                            and isinstance(author.get('checks', []), list) and all(isinstance(c, str) for c in author.get('checks', [])), 'Invalid generated_by')
                    s['responses'][-1]['feedback']['generated_by'] = copy.deepcopy(author)
                if payload.get('follow_up_suggestion') is not None:
                    suggestion = payload['follow_up_suggestion']
                    require(isinstance(suggestion, dict) and set(suggestion) == {'prompt', 'reason'}, 'Invalid follow-up suggestion')
                    string(suggestion['prompt'], 'follow-up prompt');string(suggestion['reason'], 'follow-up reason')
                    s['responses'][-1]['feedback']['suggested_follow_up'] = copy.deepcopy(suggestion)
                if payload.get('key_point_checks') is not None:
                    checks = payload['key_point_checks']
                    require(isinstance(checks, list) and all(isinstance(c, dict) and type(c.get('index')) is int and c.get('status') in ('covered', 'partial', 'missed')
                                                             for c in checks), 'Invalid key point checks')
                    s['responses'][-1]['feedback']['key_point_checks'] = copy.deepcopy(checks)
            elif action=='follow-up':
                require(s['responses'] and s['responses'][-1]['feedback'] is not None,'Feedback must precede a follow-up')
                require(not s.get('follow_up'),'Answer the existing follow-up first')
                string(payload.get('prompt'),'follow-up prompt');string(payload.get('reason'),'follow-up reason')
                s['follow_up']={'prompt':payload['prompt'],'reason':payload['reason']}
            else:
                require(action=='end','Unknown interview action')
                s['status']='completed' if s['position']==len(s['question_ids']) and all(r['feedback'] is not None for r in s['responses']) and not s.get('follow_up') else 'cancelled'
        return stage_snapshot(bank,current,final,config,operation='interview',audit=[{'action':action,'session_id':key}],summary={'session_id':key})
