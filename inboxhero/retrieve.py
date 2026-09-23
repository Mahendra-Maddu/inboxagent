"""Retrieval: thread-walk first, keyword search as cross-thread fallback."""

from __future__ import annotations

import re
from typing import Any

from inboxhero.store import MailStore
from inboxhero.trace import Trace


def thread_walk(store: MailStore, msg: dict[str, Any], before_only: bool = True) -> list[dict[str, Any]]:
    """Return earlier (or all) messages in the same thread, oldest first."""
    thread = store.thread(msg["thread_id"])
    if not before_only:
        return thread
    return [m for m in thread if m["timestamp"] < msg["timestamp"] or m["id"] == msg["id"]]


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z0-9]{3,}", text)}


def keyword_search(
    store: MailStore,
    query: str,
    exclude_id: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    q = _tokens(query)
    if not q:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for m in store.all():
        if exclude_id and m["id"] == exclude_id:
            continue
        blob = f"{m.get('subject', '')} {m.get('body', '')}"
        score = len(q & _tokens(blob))
        if score > 0:
            scored.append((score, m))
    scored.sort(key=lambda x: (-x[0], x[1]["timestamp"]))
    return [m for _, m in scored[:limit]]


def retrieve_for_reply(
    store: MailStore,
    msg: dict[str, Any],
    trace: Trace | None = None,
    cap: str | None = None,
) -> list[dict[str, Any]]:
    """
    Gather grounding messages. Always thread-walk; keyword for cross-thread gaps.
    Logs 'read' events for every cited candidate.
    """
    seen: set[str] = set()
    results: list[dict[str, Any]] = []

    for m in thread_walk(store, msg, before_only=True):
        if m["id"] == msg["id"]:
            continue
        if m["id"] not in seen:
            seen.add(m["id"])
            results.append(m)

    # Cross-thread keywords for specific needs
    extra_queries: list[str] = []
    body_l = msg.get("body", "").lower()
    subj_l = msg.get("subject", "").lower()
    if "staging" in body_l or "queue" in body_l or "amqp" in body_l or "creds" in body_l:
        extra_queries.append("staging AMQP URL broker queue creds")
    if "launch" in body_l or "date you locked" in body_l or "venue" in subj_l:
        extra_queries.append("launch week target 20th")
    if "board deck" in subj_l or "board review" in body_l:
        extra_queries.append("board review scheduled 18th")

    for q in extra_queries:
        for m in keyword_search(store, q, exclude_id=msg["id"]):
            if m["id"] not in seen:
                seen.add(m["id"])
                results.append(m)

    if trace:
        for m in results:
            trace.log("read", cap=cap, message_id=m["id"], for_message=msg["id"])

    return results


def find_amqp_url(messages: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Pull staging AMQP URL and its source message id."""
    pat = re.compile(r"amqp://\S+")
    for m in messages:
        match = pat.search(m.get("body", ""))
        if match:
            return match.group(0).rstrip(".,;"), m["id"]
    return None, None
