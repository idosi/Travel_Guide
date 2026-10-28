"""Conversation history per user. In-memory for now; swap for Redis/SQLite later."""

from typing import Protocol


class SessionStore(Protocol):
    def get(self, user_id: str) -> list[dict]: ...
    def save(self, user_id: str, messages: list[dict]) -> None: ...
    def reset(self, user_id: str) -> None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._data: dict[str, list[dict]] = {}

    def get(self, user_id: str) -> list[dict]:
        return list(self._data.get(user_id, []))

    def save(self, user_id: str, messages: list[dict]) -> None:
        self._data[user_id] = list(messages)

    def reset(self, user_id: str) -> None:
        self._data.pop(user_id, None)
