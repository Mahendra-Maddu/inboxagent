"""Mail store over inbox.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config


class MailStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config.INBOX_PATH
        with self.path.open(encoding="utf-8") as f:
            self.messages: list[dict[str, Any]] = json.load(f)
        self.by_id: dict[str, dict[str, Any]] = {m["id"]: m for m in self.messages}

    def all(self) -> list[dict[str, Any]]:
        return list(self.messages)

    def get(self, msg_id: str) -> dict[str, Any] | None:
        return self.by_id.get(msg_id)

    def thread(self, thread_id: str) -> list[dict[str, Any]]:
        msgs = [m for m in self.messages if m["thread_id"] == thread_id]
        return sorted(msgs, key=lambda m: m["timestamp"])

    def from_sender(self, sender: str, unread_only: bool = False) -> list[dict[str, Any]]:
        sender_l = sender.lower()
        out = []
        for m in self.messages:
            if m["from"].lower() != sender_l:
                continue
            if unread_only and not m.get("unread"):
                continue
            out.append(m)
        return out

    def outbound(self, owner: str | None = None) -> list[dict[str, Any]]:
        owner = (owner or config.OWNER_EMAIL).lower()
        return [m for m in self.messages if m["from"].lower() == owner]

    def count(self) -> int:
        return len(self.messages)
