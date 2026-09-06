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
