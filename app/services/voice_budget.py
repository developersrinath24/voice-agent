"""A daily ceiling on realtime calls.

An open call spends ElevenLabs credits for as long as it lasts, and the demo is
public. The cap lives on the server because a client-side one is a suggestion:
anyone can call the API directly.

Deliberately in process memory: one uvicorn worker, and a restart resets the
count. That is the safe direction — the failure mode is "the allowance came
back", never "the account was drained while nobody was looking".
"""

import threading
from datetime import UTC, date, datetime


class CallBudget:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._lock = threading.Lock()
        self._day = datetime.now(UTC).date()
        self._used = 0

    def _roll(self) -> None:
        today: date = datetime.now(UTC).date()
        if today != self._day:
            self._day = today
            self._used = 0

    def remaining(self) -> int:
        with self._lock:
            self._roll()
            return max(self.limit - self._used, 0)

    def take(self) -> bool:
        """Reserve one call. False when today's allowance is spent."""
        with self._lock:
            self._roll()
            if self._used >= self.limit:
                return False
            self._used += 1
            return True
