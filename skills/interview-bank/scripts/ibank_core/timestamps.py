"""ISO-8601 timestamps as agents and browsers write them, on every supported Python."""
from datetime import datetime


def parse_timestamp(value):
    # Python 3.10 rejects a trailing "Z" (JavaScript toISOString, most agents); 3.11+ accepts it.
    if isinstance(value, str) and value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)
