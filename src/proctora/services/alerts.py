from __future__ import annotations

from collections import Counter
from threading import Lock


class AlertStore:
    def __init__(self) -> None:
        self._alerts: Counter[str] = Counter()
        self._lock = Lock()

    def add(self, message: str) -> None:
        with self._lock:
            self._alerts[message] += 1

    def remove(self, message: str) -> None:
        with self._lock:
            self._alerts.pop(message, None)

    def as_list(self) -> list[dict[str, int | str]]:
        with self._lock:
            return [
                {"message": message, "count": count}
                for message, count in self._alerts.items()
            ]
