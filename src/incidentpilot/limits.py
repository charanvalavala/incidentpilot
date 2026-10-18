from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request

WINDOW_SECONDS = 60
_requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = Lock()


def enforce_limit(request: Request, route: str, maximum: int):
    address = request.client.host if request.client else "unknown"
    key = (route, address)
    current = monotonic()
    with _lock:
        bucket = _requests[key]
        while bucket and current - bucket[0] >= WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= maximum:
            raise HTTPException(status_code=429, detail="Request limit reached. Try again shortly.")
        bucket.append(current)
