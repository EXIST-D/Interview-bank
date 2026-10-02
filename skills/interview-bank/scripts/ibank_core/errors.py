"""Error classes, exit codes and the stable error_type/hint an agent can act on without parsing prose."""
import re


class BankError(Exception):
    code = 1


class ValidationError(BankError):
    code = 2


class BankUnavailable(BankError):
    code = 3


class LockConflict(BankError):
    code = 4


class ReviewRequired(BankError):
    code = 5


# Specific ValidationError situations, matched on the messages raised by require(); first match wins.
_SPECIFIC = (
    ("Compacted", r"compacted by gc",
     "This run's stored data was removed by gc; scope the operation by question_ids or expression instead."),
    ("StaleInput", r"changed since staging|[Ss]tale|regenerate|[Bb]ank changed|configuration changed|Task input changed|moved on",
     "The bank changed after this task or stage was created. Create a fresh task/stage from current data; do not edit run files."),
    ("PrivacyRejected", r"contact information",
     "Remove the personal contact detail (or use an example.com-style placeholder) and retry."),
    ("NeedsMigration", r"migrate apply|format V2",
     "This feature needs a V2 bank. Ask the user, then run migrate plan and migrate apply on this bank only."),
    ("AlreadyExists", r"must not exist|already exists",
     "Choose a new destination or ID; existing data is never overwritten."),
)
_DEFAULT = {
    "LockConflict": "Another command is still using the bank. Retry shortly, or raise INTERVIEW_BANK_LOCK_TIMEOUT; never delete .bank.lock.",
    "ReviewRequired": "The stage has review items. Read them with run-show --run <id>, fix the input with evidence, then stage again.",
    "BankUnavailable": "Run init for a new bank, or pass the right --bank / INTERVIEW_BANK_HOME.",
    "InvalidInput": "Fix the field named in the error and retry; the protocol reference for this command gives the expected shape.",
    "OSError": "A filesystem operation failed; check the path, free space and permissions.",
    "Error": "Unexpected failure; report the error text to the user.",
}


def describe_error(exc):
    """(error_type, hint) for an exception raised by a command."""
    if isinstance(exc, ValidationError):
        message = str(exc)
        for name, pattern, hint in _SPECIFIC:
            if re.search(pattern, message):
                return name, hint
        return "InvalidInput", _DEFAULT["InvalidInput"]
    for cls in (LockConflict, ReviewRequired, BankUnavailable):
        if isinstance(exc, cls):
            return cls.__name__, _DEFAULT[cls.__name__]
    if isinstance(exc, OSError):
        return "OSError", _DEFAULT["OSError"]
    return "Error", _DEFAULT["Error"]
