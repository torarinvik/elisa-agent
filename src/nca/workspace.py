"""Append-only workspace with provenance and rollback."""

from __future__ import annotations

from nca.abi import Message


class Workspace:
    def __init__(self) -> None:
        self._log: list[Message] = []
        self._index: dict[str, Message] = {}
        self.spent = 0.0
        """Total declared cost of the module invocations executed against this workspace."""

    def post(self, message: Message) -> None:
        """Admit a fresh message or reuse the exact previously admitted object.

        Identifiers never change their message binding. Parents must already
        exist; payloads must be immutable or treated as immutable by callers.
        """
        previous = self._index.get(message.message_id)
        if previous is not None:
            if previous is message:
                return
            raise ValueError("message identifier already names a different message")
        missing = [p for p in message.parents if p not in self._index]
        if missing:
            raise ValueError(f"unknown parent messages: {missing}")
        self._log.append(message)
        self._index[message.message_id] = message

    def get(self, message_id: str) -> Message:
        return self._index[message_id]

    def provenance(self, message_id: str) -> list[Message]:
        """All ancestors of ``message_id``, including itself, parents first."""
        seen: dict[str, Message] = {}

        def visit(mid: str) -> None:
            if mid in seen:
                return
            message = self._index[mid]
            for parent in message.parents:
                visit(parent)
            seen[mid] = message

        visit(message_id)
        return list(seen.values())

    def messages(self) -> list[Message]:
        """All messages in posting order."""
        return list(self._log)

    def snapshot(self) -> int:
        return len(self._log)

    def rollback(self, snapshot: int) -> None:
        if (isinstance(snapshot, bool) or not isinstance(snapshot, int)
                or not 0 <= snapshot <= len(self._log)):
            raise ValueError("snapshot must be a valid workspace position")
        for message in reversed(self._log[snapshot:]):
            del self._index[message.message_id]
        del self._log[snapshot:]

    def __contains__(self, message_id: object) -> bool:
        return message_id in self._index

    def __len__(self) -> int:
        return len(self._log)
