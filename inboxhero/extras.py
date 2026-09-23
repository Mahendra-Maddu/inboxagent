"""Extra capability helpers: follow-ups, digest, sender lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import config
from inboxhero.store import MailStore


def unread_from_sender(store: MailStore, sender: str) -> list[dict[str, Any]]:
    return [
        {
            "id": m["id"],
            "subject": m["subject"],
            "timestamp": m["timestamp"],
            "unread": m.get("unread"),
        }
        for m in store.from_sender(sender, unread_only=True)
    ]


def unanswered_outbound(
    store: MailStore,
    min_days: int = 3,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Messages Sam sent that nobody answered in-thread for min_days+.
    A reply exists if a later message in the same thread is from someone else.
    """
    now = now or datetime.fromisoformat(config.REFERENCE_NOW)
    owner = config.OWNER_EMAIL.lower()
    results = []

    for msg in store.outbound(owner):
        # Notes to self are not unanswered correspondence.
        if msg.get("to", "").lower() == owner:
            continue
        sent_at = datetime.fromisoformat(msg["timestamp"])
        age = (now - sent_at).days
        if age < min_days:
            continue

        thread = store.thread(msg["thread_id"])
        answered = False
        for other in thread:
            if other["id"] == msg["id"]:
                continue
            if other["timestamp"] <= msg["timestamp"]:
                continue
            if other["from"].lower() != owner:
                answered = True
                break
        if answered:
            continue

        draft = (
            f"Hi -\n\n"
            f"Just bumping this in case it got buried "
            f"(re: {msg['subject']}). Let me know if you need anything from me.\n\n"
            f"- Sam"
        )
        results.append(
            {
                "message_id": msg["id"],
                "to": msg["to"],
                "subject": msg["subject"],
                "days_waiting": age,
                "draft": draft,
            }
        )
    return results


def morning_digest(
    decisions: list[dict[str, Any]],
    flags: list[dict[str, Any]],
) -> dict[str, Any]:
    needs_you = []
    can_wait = []
    auto_archived = []

    for d in decisions:
        disp = d["disposition"]
        entry = {"id": d["id"], "subject": d["subject"], "reason": d["reason"]}
        if disp in ("escalate", "reply") or d["id"] in {f["message_id"] for f in flags}:
            # noisy archive of flags still needs you for awareness — handled separately
            if disp in ("escalate", "reply"):
                needs_you.append(entry)
            elif disp == "defer":
                can_wait.append(entry)
            elif disp == "archive" and d.get("rule_handled"):
                auto_archived.append(entry)
        elif disp == "defer":
            can_wait.append(entry)
        elif disp == "archive" and d.get("rule_handled"):
            auto_archived.append(entry)
        elif disp == "delegate":
            can_wait.append(entry)

    return {
        "needs_you": needs_you,
        "can_wait": can_wait,
        "auto_archived_count": len(auto_archived),
        "auto_archived_sample": auto_archived[:5],
        "flagged_count": len(flags),
    }
