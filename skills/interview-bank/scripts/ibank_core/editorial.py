"""Small deterministic guard; broader relevance decisions belong to the host."""
import re
import unicodedata


def is_self_introduction(text):
    text = unicodedata.normalize('NFKC', text).strip()
    text = re.sub(r'^\d+[.、)\s]+', '', text)
    return bool(re.match(
        r'^(?:(?:请|先|你|做|一个|一下|下|简短|简单|针对性|针对性的|的|来|进行|分钟|\d+|\s))*自我介绍(?=$|[\s，,。.!！?？、:：；;]|一下|下)'
        r'|^(?:请|先|简单|简短|你|\s)*介绍(?:一下|下)?(?:你|您)?自己'
        r'|^(?:please\s+)?(?:briefly\s+)?introduce\s+yourself\b'
        r'|^tell\s+me\s+about\s+yourself\b', text, re.I))


def exclusion_reason(question):
    if question.get('report_exclusion'):
        return question['report_exclusion']
    if is_self_introduction(question['canonical']):
        return '个人自我介绍，不属于可复用的面试知识题'
    return None
