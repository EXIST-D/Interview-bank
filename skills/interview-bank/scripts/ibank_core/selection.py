"""Small validated filter AST. Context predicates always share one occurrence."""
from .schema import require, string
from .catalog import matches, company_matches
from .normalize import normalize_company_alias, normalize_technology
from .dates import interval

FIELDS = {'company', 'industry', 'role', 'domain', 'technology', 'query', 'round', 'interview_type',
          'difficulty', 'question_type', 'answer_status', 'year', 'company_type', 'ownership', 'business_model'}


def describe(expr):
    """Readable conditions; exact AST is retained in the structured report."""
    from .catalog import display
    if not expr: return '当前题库全部可复用知识题'
    for op, word in (('all', '且'), ('any', '或')):
        if op in expr: return '（' + f' {word} '.join(describe(x) for x in expr[op]) + '）'
    if 'not' in expr: return '排除满足：' + describe(expr['not'])
    labels = dict(company='公司', industry='行业', role='来源岗位', domain='领域', technology='技术栈',
                  query='包含文字', round='面试轮次', interview_type='面试类型', difficulty='难度',
                  question_type='题目类型', answer_status='答案状态', year='面试年份', company_type='公司类型',
                  ownership='所有制', business_model='商业模式')
    field = expr['field']
    dimension = {'role':'role_tracks','domain':'domains','industry':'industries','technology':'technologies'}.get(field)
    values = [display(dimension, v) if dimension else v for v in expr['values']]
    label = '适用岗位' if field == 'role' and expr.get('scope') == 'suitability' else labels[field]
    return label + '：' + ' / '.join(values)


def validate_expression(expr, depth=0):
    require(depth < 12 and isinstance(expr, dict), 'Invalid/too deep filter expression')
    if not expr:
        return
    for op in ('all', 'any'):
        if op in expr:
            require(set(expr) == {op} and isinstance(expr[op], list) and 0 < len(expr[op]) <= 50, f'Invalid {op} expression')
            for child in expr[op]:
                validate_expression(child, depth+1)
            return
    if 'not' in expr:
        require(set(expr) == {'not'}, 'Invalid not expression')
        validate_expression(expr['not'], depth+1)
        return
    require(set(expr) <= {'field', 'values', 'scope'} and expr.get('field') in FIELDS, 'Unknown filter field')
    require(isinstance(expr.get('values'), list) and 0 < len(expr['values']) <= 100, 'Filter values must be nonempty list')
    for value in expr['values']:
        string(value, 'filter value')
        if expr['field'] == 'year':
            require(len(value) == 4 and value.isdigit(), 'Year filter must be YYYY')
    require(expr.get('scope', 'source') in ('source', 'suitability'), 'Unknown role scope')
    require('scope' not in expr or expr['field'] == 'role', 'Scope only applies to role')


def evaluate(expr, q, occ, company):
    if not expr:
        return True
    if 'all' in expr:
        return all(evaluate(x, q, occ, company) for x in expr['all'])
    if 'any' in expr:
        return any(evaluate(x, q, occ, company) for x in expr['any'])
    if 'not' in expr:
        return not evaluate(expr['not'], q, occ, company)
    field, values = expr['field'], expr['values']
    if field == 'company':
        return any(normalize_company_alias(v) in {normalize_company_alias(x) for x in [company.get('id', ''), company.get('name', ''), *company.get('aliases', [])]} for v in values)
    if field in ('industry', 'company_type', 'ownership', 'business_model'):
        return any(company_matches(company, **{field: v}) for v in values)
    if field in ('role', 'domain'):
        dimension = 'role_tracks' if field == 'role' else 'domains'
        target = occ if field == 'role' and expr.get('scope', 'source') == 'source' else q
        return any(matches(dimension, label, v) for label in target[dimension] for v in values)
    if field == 'technology':
        return any(normalize_technology(v) in {normalize_technology(t) for t in q['technologies']} for v in values)
    if field == 'query':
        return any(v.casefold() in (q['canonical']+'\n'+occ['original_text']).casefold() for v in values)
    if field == 'year':
        return bool(occ['event_date'] and occ['event_date'][:4] in values)
    target = occ if field in ('round', 'interview_type') else q
    return target[field] in values


def apply_expression(questions, companies, expr):
    from collections import Counter
    validate_expression(expr)
    by_id = {c['id']: c for c in companies}
    result = []
    for q in questions:
        matched = [o for o in q['occurrences'] if evaluate(expr, q, o, by_id.get(o['company_id'], {}))]
        if matched:
            counts = Counter(o['company_id'] for o in matched)
            result.append({**q, 'occurrences': matched, 'frequency': len(matched),
                           'companies': [{'id': key, 'name': by_id.get(key, {}).get('name', 'unknown'), 'frequency': n} for key, n in counts.items()]})
    return sorted(result, key=lambda q: (-q['frequency'], q['canonical'], q['id']))
