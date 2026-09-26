"""Opt-in, in-process TTL response cache for saved queries.

Never applies to ad-hoc ``/execute_sql`` (there is no stable name to hang a TTL off), and the caller
(``run_saved`` in ``app.py``) only ever consults this cache for a saved query whose SQL is read-only -
serving a cached response in place of a write would silently skip that write. Cache keys already include
the resolved parameter values, connection, format and page, so entries are shared across API keys that can
both use the same connection - that reveals nothing a scoped key could not already see by running the
query itself.

Like ``ratelimit.RateLimiter``, one instance lives per Flask app (``app.extensions['queryapigate_cache']``) so
tests get a clean cache instead of leaking entries between them; a multi-process deployment would need a
shared backing store instead of this one process's memory.
"""
import hashlib
import json
import threading
import time
from collections import OrderedDict

MAX_ENTRIES = 10_000  # bounds memory; the least recently used entry is evicted first


class ResponseCache:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._entries = OrderedDict()  # key -> (body, content_type, headers, etag, expires_at)

    @staticmethod
    def key(**parts):
        """A stable cache key from whatever makes the response unique (name, version, connection, resolved
        parameter values, format, page, page_size - never raw, unresolved input)."""
        blob = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode('utf-8')).hexdigest()

    def get(self, key):
        """(body, content_type, headers, etag) for a live entry, or None if missing or expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            body, content_type, headers, etag, expires_at = entry
            if self._clock() >= expires_at:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)  # most recently used
            return body, content_type, headers, etag

    def set(self, key, body, content_type, headers, ttl):
        """Store a response and return its ETag (a hash of the body, so it changes only when content does)."""
        etag = hashlib.sha256(body).hexdigest()
        with self._lock:
            self._entries[key] = (body, content_type, headers, etag, self._clock() + ttl)
            self._entries.move_to_end(key)
            while len(self._entries) > MAX_ENTRIES:
                self._entries.popitem(last=False)
        return etag

    def size(self):
        with self._lock:
            return len(self._entries)
