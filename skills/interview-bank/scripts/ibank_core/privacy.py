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
# Payloads carry generated IDs (src_<uuid hex>) and SHA-256 digests; their digit runs are not phone numbers.
HEX_RUN = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32,}(?![0-9A-Fa-f])")


def classified_findings(text):
    """Contact-like matches by kind (email, mobile, account), masked so errors do not repeat them."""
    text = HEX_RUN.sub(" ", text)
    found = [("email", m.group(0)) for m in EMAIL.finditer(text) if not EXAMPLE_DOMAIN.search(m.group(1))]
    found += [("mobile", m) for m in MOBILE.findall(text)]
    found += [("account", m.group(0)) for m in ACCOUNT.finditer(text)]
    return [{"kind": kind, "masked": _mask(value)} for kind, value in found]


def contact_findings(text):
    return [item["masked"] for item in classified_findings(text)]


def _mask(value):
    keep = max(1, len(value) // 4)
    return value[:keep] + "*" * (len(value) - 2 * keep) + value[-keep:] if len(value) > 2 * keep else "*" * len(value)


HINTS = {"email": "an email address (use user@example.com in technical examples)",
         "mobile": "a mobile number (use 138xxxxxxxx-style placeholders)",
         "account": "an account ID after a 微信/QQ/手机号 label"}


def describe(findings):
    kinds = list(dict.fromkeys(item["kind"] for item in findings))
    return "; ".join(HINTS[kind] for kind in kinds) + " — found " + ", ".join(item["masked"] for item in findings[:3])


def privacy_check(text, config):
    if config["privacy"]["persist_pii"]:
        return
    findings = classified_findings(text)
    require(not findings, "Possible personal contact information: " + describe(findings)
            + ". Remove it before staging; it is not needed to keep the question.")
