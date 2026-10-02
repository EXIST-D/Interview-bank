"""Narrow contact-information guard. It catches common mistakes; it is not anonymization."""
import re

from .schema import require

# No trailing \b: CJK text right after the address ("…@qq.com的") must still match.
EMAIL = re.compile(r"[\w.+-]+@((?:[\w-]+\.)+[A-Za-z]{2,})")
# RFC 2606/6761 names are documentation placeholders, not someone's inbox.
EXAMPLE_DOMAIN = re.compile(r"(?:^|\.)(?:example\.(?:com|net|org)|[\w-]+\.(?:example|test|invalid|localhost))$", re.I)
MOBILE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
# An account label followed by an ID-like token. "微信：朋友圈 Feed 流如何设计" is a question, not an account.
ACCOUNT = re.compile(r"(?:微信号?|手机号|QQ群?|群号|wechat|weixin)[\s　]*[:：][\s　]*[A-Za-z0-9][A-Za-z0-9_-]{4,}", re.I)


def contact_findings(text):
    found = [m.group(0) for m in EMAIL.finditer(text) if not EXAMPLE_DOMAIN.search(m.group(1))]
    found += MOBILE.findall(text)
    found += [m.group(0) for m in ACCOUNT.finditer(text)]
    return found


def privacy_check(text, config):
    if config["privacy"]["persist_pii"]:
        return
    require(not contact_findings(text),
            "Possible personal contact information; remove irrelevant PII before staging "
            "(technical examples can use example.com-style placeholders)")
