"""Metadata suitable for a deliberately published collection; never publish bank or account metadata."""
from urllib.parse import urlsplit
from collections import deque
import threading
import time


class ReadBudget:
    """Bounded rolling window for anonymous reads; rejected requests do not allocate client records."""
    def __init__(self, per_client=120, overall=600, window=60):
        self.per_client, self.overall, self.window = per_client, overall, window
        self.events, self.clients, self.lock = deque(), {}, threading.Lock()

    def allow(self, client, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            while self.events and self.events[0][0] <= now - self.window:
                _, old = self.events.popleft()
                self.clients[old] -= 1
                if not self.clients[old]:
                    del self.clients[old]
            if len(self.events) >= self.overall or self.clients.get(client, 0) >= self.per_client:
                return False
            self.events.append((now, client))
            self.clients[client] = self.clients.get(client, 0) + 1
            return True


def origin(value):
    """Older imports may name a local path instead of a public source URL."""
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in ('http', 'https') and parsed.netloc and not parsed.username and not parsed.password else ''
    except ValueError:
        return ''


def collection(value):
    # The organization audit history may contain private review reasons. It is not public reading content.
    return {**value, 'origin': origin(value.get('origin', '')), 'history': [],
            'metadata': {key: item for key, item in value.get('metadata', {}).items()
                         if key in ('author', 'description', 'language', 'license', 'version', 'updated_at') or
                         key in ('homepage', 'license_url') and origin(item)}}
