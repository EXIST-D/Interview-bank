from datetime import datetime, timezone
from uuid import uuid4


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_id(prefix):
    return f"{prefix}_{uuid4().hex}"


def new_question_id():
    return new_id("q")


def new_occurrence_id():
    return new_id("occ")


def new_source_id():
    return new_id("src")


def new_answer_id():
    return new_id("ans")


def new_relation_id():
    return new_id("rel")


def new_run_id():
    return new_id("run")


def new_company_id():
    return new_id("company")
