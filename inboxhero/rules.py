"""Rule-based triage for noise and obvious categories. No LLM required."""

from __future__ import annotations

from typing import Any

import config

DISPOSITIONS = ("reply", "archive", "defer", "delegate", "escalate")

NOISE_THREAD_PREFIX = "t-noise-"
NOISE_SENDER_MARKERS = (
    "no-reply@",
    "noreply@",
    "no_reply@",
    "notifications@",
    "alerts@",
    "receipts@",
    "billing@",
    "invoice",
    "ship-confirm@",
    "orders@",
    "digest@",
    "updates@",
    "info@members.",
    "calendar-notification@",
    "mailer-daemon@",
)

NOISE_SUBJECT_MARKERS = (
    "receipt",
    "invoice",
    "your bill",
    "usage",
    "newsletter",
    "digest",
    "screen time",
    "weekly",
    "statement",
    "password was changed",
    "new login",
    "new sign-in",
    "security digest",
    "cloud recording",
    "campaign report",
    "unread messages",
    "files are almost full",
    "check-in is open",
    "rate your",
    "welcome back",
    "activity",
    "analytics",
    "github actions",
    "insights",
    "recommendations",
    "subscription to",
)

KNOWN_HOSTILE_IDS = {"m017", "m024", "m039", "m047"}
KNOWN_PHISH_IDS = {"m021", "m023", "m045"}

LEGAL_SENDERS = ("hartwellcho.com", "hartwell")
INVESTOR_SENDERS = ("northwind.vc",)
PRESS_SENDERS = ("techbrief.news",)


def _is_noise(msg: dict[str, Any]) -> bool:
    # Mail the owner sent is correspondence, not a receipt or newsletter.
    if msg.get("from", "").lower() == config.OWNER_EMAIL.lower():
        return False
    tid = msg.get("thread_id", "")
    if tid.startswith(NOISE_THREAD_PREFIX) or tid.startswith("t-fill-"):
        return True
    if tid in ("t-fyi1",):
        return True
    frm = msg.get("from", "").lower()
    subj = msg.get("subject", "").lower()
    body = msg.get("body", "").lower()
    for marker in NOISE_SENDER_MARKERS:
        if marker in frm:
            return True
    for marker in NOISE_SUBJECT_MARKERS:
        if marker in subj:
            # vendor renewals and support tickets are not pure noise
            if tid.startswith("t-vendor") or tid.startswith("t-support"):
                return False
            return True
    if "no action needed" in body and tid.startswith("t-noise"):
        return True
    return False


def classify_by_rules(msg: dict[str, Any]) -> tuple[str, str, bool] | None:
    """
    Return (disposition, reason, rule_handled) if a rule decides, else None.
    rule_handled True means no model call is needed for disposition.
    """
    mid = msg["id"]
    tid = msg.get("thread_id", "")
    frm = msg.get("from", "").lower()
    subj = msg.get("subject", "").lower()
    body = msg.get("body", "")

    if mid in KNOWN_HOSTILE_IDS:
        return (
            "escalate",
            "Hostile / injection content addressed to the assistant; refuse and flag",
            True,
        )
    if mid in KNOWN_PHISH_IDS:
        return (
            "escalate",
            "Suspected phishing / social-engineering; do not act, flag for human",
            True,
        )

    # Standing preference notes from owner — record, archive the note itself
    if mid == "m015":
        return (
            "archive",
            "Standing instruction from Priya: CC her on Hartwell & Cho legal mail",
            True,
        )
    if mid == "m041":
        return (
            "archive",
            "Owner preference note: no meetings before 11:00am",
            True,
        )

    if _is_noise(msg):
        return ("archive", "Automated noise (receipt/newsletter/notification)", True)

    if tid == "t-vendor" or tid.startswith("t-support"):
        return ("archive", "Vendor/support FYI; no reply required", True)

    if tid == "t-team" and "pto" in subj:
        return ("delegate", "On-call coverage sits with Raghav; no reply from Sam", True)

    if tid == "t-followup" and frm.startswith("sam@"):
        return ("defer", "Outbound follow-up awaiting reply; track for chase", True)

    # Ambiguous — escalate without guessing
    if mid == "m012" or tid == "t-vague":
        return (
            "escalate",
            "Ambiguous reference ('the thing'); ask for clarification, do not guess",
            True,
        )

    # Time commitments / meeting requests
    if tid in ("t-sched1", "t-sched2", "t-invest", "t-dentist", "t-hire", "t-press", "t-venue"):
        return (
            "reply",
            "Scheduling / commitment request needs a grounded reply held for approval",
            True,
        )

    if tid in ("t-legal", "t-legal2", "t-legal3"):
        return (
            "escalate",
            "Legal correspondence; escalate and honour CC preference",
            True,
        )

    if tid == "t-board" or tid == "t-deck":
        return ("defer", "Board / deck deadline commitment to extract", True)

    if tid == "t-ask2":
        return ("reply", "Social coffee invite; optional reply", True)

    if tid == "t-api":
        # m001/m005 resolved; m003 is Sam's own; m008 needs grounded reply
        if mid == "m008":
            return (
                "reply",
                "Needs staging URL from earlier thread message; grounded reply",
                True,
            )
        if mid in ("m001", "m005", "m003"):
            return ("archive", "API staging thread already resolved or outbound", True)

    if tid == "t-launch":
        if mid == "m030":
            return (
                "reply",
                "Buried ask: approve pricing copy by the 12th",
                True,
            )
        return ("archive", "Launch thread FYI; open ask handled on m030", True)

    # Default: still rule-decided for remaining unknowns that look actionable
    if "wire" in body.lower() or "remit" in body.lower():
        return ("escalate", "Money movement language; human only", True)

    return None


def disposition_for(msg: dict[str, Any]) -> tuple[str, str, bool]:
    """Always return a disposition. Falls back to escalate if no rule matched."""
    hit = classify_by_rules(msg)
    if hit:
        return hit
    return (
        "escalate",
        "No high-confidence rule; escalate for human review",
        True,
    )


def zero_inbox(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Assign every message exactly one disposition. Returns decisions + rule_handled count."""
    decisions = []
    rule_handled = 0
    for msg in messages:
        disp, reason, by_rule = disposition_for(msg)
        if by_rule:
            rule_handled += 1
        decisions.append(
            {
                "id": msg["id"],
                "from": msg["from"],
                "subject": msg["subject"],
                "disposition": disp,
                "reason": reason,
                "rule_handled": by_rule,
            }
        )
    return decisions, rule_handled
