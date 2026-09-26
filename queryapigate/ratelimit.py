"""A small in-memory token-bucket rate limiter, off unless QUERYAPIGATE_RATE_LIMIT is set (e.g. ``60/minute``).

Each client (by IP address) has a bucket holding up to the full quota, refilled continuously, so short bursts are
allowed but the sustained rate is capped. State lives in this process: with several worker processes each has its
own buckets, so the effective limit is multiplied by the number of workers.

``RateLimiter`` handles the server-wide, IP-keyed limit above. ``KeyRateLimiters`` (below) is the same
mechanism applied per API key instead, for a key's own optional ``rate_limit`` grant (see ``apikeys.py``) -
both are checked, not one instead of the other, so a per-key limit can never be used to escape the
server-wide IP-based one.
"""
import math
import threading
import time
from collections import OrderedDict


class RateLimiter:
    MAX_CLIENTS = 100_000  # bounds memory; the least recently seen clients are forgotten first

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets = OrderedDict()  # client -> [tokens, last_seen]; least recently seen first
        self._spec = None
        self._last_sweep = clock()

    def hit(self, client, count, period):
        """Record a request. Returns (allowed, remaining, retry_after_seconds)."""
        now = self._clock()
        with self._lock:
            if self._spec != (count, period):  # limit changed: start again rather than mix old and new rules
                self._buckets.clear()
                self._spec = (count, period)
            self._sweep(now, period)
            tokens, seen = self._buckets.pop(client, (float(count), now))
            tokens = min(float(count), tokens + (now - seen) * count / period)
            allowed = tokens >= 1
            if allowed:
                tokens -= 1
            self._buckets[client] = (tokens, now)  # re-inserted last: most recently seen
            if len(self._buckets) > self.MAX_CLIENTS:
                self._buckets.popitem(last=False)
            # round first: 20.000000000000004 seconds must not become a 21 second wait
            retry_after = 0 if allowed else max(1, math.ceil(round((1 - tokens) * period / count, 6)))
            return allowed, int(tokens), retry_after

    def _sweep(self, now, period):
        """Forget clients idle for a full period: their bucket has refilled, so they look brand new anyway."""
        if now - self._last_sweep < period:
            return
        self._last_sweep = now
        while self._buckets:
            client, (_, seen) = next(iter(self._buckets.items()))
            if now - seen < period:
                break
            del self._buckets[client]

    def size(self):
        with self._lock:
            return len(self._buckets)


class KeyRateLimiters:
    """Per-API-key rate limiting needs a genuinely separate RateLimiter per distinct (count, period) spec,
    not just a different `client` identifier fed into one shared instance: a single RateLimiter enforces
    exactly one spec at a time and wipes every client's bucket the moment a *different* spec arrives (see
    its own `hit()` - by design, so an admin changing QUERYAPIGATE_RATE_LIMIT doesn't mix old and new rules for
    the IP-based limiter). Two keys configured with different `rate_limit` values are exactly that "two
    different specs" case, so they need their own RateLimiter instances; two keys that happen to share the
    same configured limit correctly share one instance instead (and so still get independent per-key
    buckets within it, keyed by name) - there is no reason to multiply instances beyond one per distinct
    spec actually in use.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._limiters = {}  # (count, period) -> RateLimiter

    def hit(self, key_name, count, period):
        spec = (count, period)
        with self._lock:
            limiter = self._limiters.get(spec)
            if limiter is None:
                limiter = RateLimiter(self._clock)
                self._limiters[spec] = limiter
        return limiter.hit(key_name, count, period)
