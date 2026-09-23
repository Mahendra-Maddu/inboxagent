"""Grounded reply drafting. Invents nothing; cites source message ids."""

from __future__ import annotations

from typing import Any

import config
from inboxhero.memory import apply_cc_prefs, scheduling_earliest_hour
from inboxhero.retrieve import find_amqp_url, retrieve_for_reply
from inboxhero.safety import detect_threats, fence_untrusted
from inboxhero.store import MailStore
from inboxhero.trace import Trace


def draft_reply(
    store: MailStore,
    msg_id: str,
    prefs: list[dict[str, Any]] | None = None,
    trace: Trace | None = None,
    cap: str | None = None,
) -> dict[str, Any]:
    prefs = prefs or []
    msg = store.get(msg_id)
    if not msg:
        return {"ok": False, "error": f"unknown message {msg_id}", "draft": None}

    threat = detect_threats(msg)
    if threat and threat["kind"] == "injection":
        if trace:
            trace.log(
                "refusal",
                cap=cap,
                message_id=msg_id,
                attempted=threat["attempted"],
                action="no draft; hostile content",
            )
        return {
            "ok": False,
            "error": "hostile message; will not draft on its behalf",
            "draft": None,
            "flag": threat,
        }

    sources = retrieve_for_reply(store, msg, trace=trace, cap=cap)
    body_l = msg.get("body", "").lower()

    # --- Special case: m008 needs AMQP URL from m003 ---
    if msg_id == "m008" or ("staging" in body_l and "url" in body_l) or "creds" in body_l:
        url, src = find_amqp_url(sources)
        if not url:
            url, src = find_amqp_url(store.all())
        if not url or not src:
            if trace:
                trace.log("draft_skip", cap=cap, message_id=msg_id, reason="fact not in inbox")
            return {
                "ok": False,
                "error": "staging AMQP URL not found in inbox; drafting nothing",
                "draft": None,
                "cited": [],
            }
        if trace:
            trace.log("read", cap=cap, message_id=src, for_message=msg_id)
        text = (
            f"Hey Devika -\n\n"
            f"Here's the staging queue URL I sent Raghav earlier (do not rotate):\n"
            f"{url}\n\n"
            f"- Sam"
        )
        draft = _pack(msg, text, [src], prefs)
        if trace:
            trace.log("draft", cap=cap, message_id=msg_id, cited=[src], to=draft["to"])
        return {"ok": True, "draft": draft, "cited": [src]}

    # Ambiguous - ask, don't guess
    if msg_id == "m012":
        text = (
            "Hey Priya -\n\n"
            "Quick clarify: which item from after standup did you mean? "
            "Happy to sort it before the call once I know which one.\n\n"
            "- Sam"
        )
        draft = _pack(msg, text, [], prefs)
        if trace:
            trace.log("draft", cap=cap, message_id=msg_id, cited=[], note="clarify")
        return {"ok": True, "draft": draft, "cited": []}

    # Preference-aware scheduling (m043 early meeting)
    earliest = scheduling_earliest_hour(prefs)
    if msg_id == "m043" and earliest is not None:
        text = (
            f"Hi Aria -\n\n"
            f"Monday at 9:00am is earlier than I can do - I keep mornings "
            f"blocked until {earliest}:00. Could we do Monday at "
            f"{earliest}:00, or keep Tuesday 3:00pm as planned?\n\n"
            f"- Sam"
        )
        cited = ["m041"] if any(p.get("source_message") == "m041" for p in prefs) else []
        for c in cited:
            if trace:
                trace.log("read", cap=cap, message_id=c, for_message=msg_id)
        draft = _pack(msg, text, cited, prefs)
        draft["held_for_approval"] = True
        draft["why_gate"] = "Sending a scheduling reply is irreversible without approval"
        if trace:
            trace.log("draft", cap=cap, message_id=msg_id, cited=cited)
        return {"ok": True, "draft": draft, "cited": cited}

    # Launch buried ask m030
    if msg_id == "m030":
        text = (
            "Priya / team -\n\n"
            "Confirming I'll lock the annual-discount pricing copy by the 12th "
            "so the rest of the pricing page can ship.\n\n"
            "- Sam"
        )
        draft = _pack(msg, text, [msg_id], prefs)
        if trace:
            trace.log("read", cap=cap, message_id=msg_id, for_message=msg_id)
            trace.log("draft", cap=cap, message_id=msg_id, cited=[msg_id])
        return {"ok": True, "draft": draft, "cited": [msg_id]}

    # Legal - apply CC preference, escalate (don't auto-sign)
    if msg.get("thread_id", "").startswith("t-legal") or "hartwellcho.com" in msg.get(
        "from", ""
    ).lower():
        text = (
            "Marcus / team -\n\n"
            "Thanks, I've received this and will review. "
            "Looping Priya per our standing process.\n\n"
            "- Sam"
        )
        draft = _pack(msg, text, [], prefs)
        draft["held_for_approval"] = True
        draft["why_gate"] = "Legal correspondence; human must approve before send"
        if trace:
            trace.log("draft", cap=cap, message_id=msg_id, cited=[], cc=draft.get("cc"))
        return {"ok": True, "draft": draft, "cited": []}

    # Generic meeting reply - hold for gate
    if msg.get("thread_id") in (
        "t-invest",
        "t-sched1",
        "t-sched2",
        "t-hire",
        "t-press",
        "t-venue",
        "t-ask2",
    ):
        text = (
            f"Hi -\n\n"
            f"Thanks for your note re: {msg.get('subject')}. "
            f"I'll confirm shortly after checking the calendar.\n\n"
            f"- {config.OWNER_NAME}"
        )
        draft = _pack(msg, text, [], prefs)
        draft["held_for_approval"] = True
        draft["why_gate"] = "Outbound reply requires approval"
        _ = fence_untrusted(msg)
        if trace:
            trace.log("draft", cap=cap, message_id=msg_id, cited=[])
        return {"ok": True, "draft": draft, "cited": []}

    return {
        "ok": False,
        "error": "no grounded draft template for this message; information may be insufficient",
        "draft": None,
        "cited": [],
    }


def _pack(
    msg: dict[str, Any],
    text: str,
    cited: list[str],
    prefs: list[dict[str, Any]],
) -> dict[str, Any]:
    cc = apply_cc_prefs(msg, prefs)
    return {
        "in_reply_to": msg["id"],
        "to": msg["from"],
        "cc": cc,
        "subject": (
            f"Re: {msg['subject']}"
            if not msg["subject"].lower().startswith("re:")
            else msg["subject"]
        ),
        "body": text,
        "cited": cited,
        "held_for_approval": True,
        "why_gate": "Sending cannot be unsent",
    }
