"""Sliding-window rate limit per client, kept in memory (the service runs as a single instance)."""

import threading
import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(self, *, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._limit = limit
        self._window_s = window_s
        self._clock = clock
        self._requests: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        """Record an attempt by the client; False when it is over the limit for the current window."""
        with self._lock:
            now = self._clock()
            self._forget_before(now - self._window_s)
            requests = self._requests.setdefault(client, deque())
            if len(requests) >= self._limit:
                return False
            requests.append(now)
            return True

    def tracked_clients(self) -> int:
        with self._lock:
            return len(self._requests)

    def _forget_before(self, cutoff: float) -> None:
        for client, requests in list(self._requests.items()):
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if not requests:
                del self._requests[client]
