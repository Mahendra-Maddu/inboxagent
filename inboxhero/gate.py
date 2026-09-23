"""Irreversible-action gate: dry-run and/or per-action human approval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config
from inboxhero.safety import is_blocked_recipient
from inboxhero.trace import Trace


class Gate:
    """
    Only this module may write to outbox/ or perform deletes.
    dry_run=True (default for demos) never mutates.
    """

    def __init__(
        self,
        dry_run: bool = True,
        interactive: bool = False,
        outbox: Path | None = None,
        trace: Trace | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.interactive = interactive
        self.outbox = outbox or config.OUTBOX_DIR
        self.trace = trace or Trace()
        self.writes = 0
        self.proposed: list[dict[str, Any]] = []

    def require_approval(self, action: str, detail: dict[str, Any], cap: str | None = None) -> bool:
        proposal = {"action": action, **detail}
        self.proposed.append(proposal)

        if self.dry_run:
            self.trace.log(
                "gate",
                cap=cap,
                action=action,
                decision="dry-run-suppressed",
                proposed=detail,
            )
            return False

        if not self.interactive:
            # Explicit non-interactive approve mode still requires --approve flag path
            self.trace.log(
                "gate",
                cap=cap,
                action=action,
                decision="denied-no-approval",
                proposed=detail,
            )
            return False

        print(f"\n=== APPROVAL REQUIRED: {action} ===")
        print(json.dumps(detail, indent=2, ensure_ascii=False))
        ans = input("Approve? [y/N] ").strip().lower()
        ok = ans in ("y", "yes")
        self.trace.log(
            "gate",
            cap=cap,
            action=action,
            decision="approved" if ok else "rejected",
            human=ans,
            proposed=detail,
        )
        return ok

    def send(self, draft: dict[str, Any], cap: str | None = None) -> bool:
        to_addr = (draft.get("to") or "").lower()
        if is_blocked_recipient(to_addr):
            self.trace.log(
                "refusal",
                cap=cap,
                action="send",
                to=to_addr,
                reason="blocked hostile destination",
            )
            return False
        for cc in draft.get("cc") or []:
            if is_blocked_recipient(cc):
                self.trace.log(
                    "refusal",
                    cap=cap,
                    action="send",
                    to=cc,
                    reason="blocked hostile CC",
                )
                return False

        detail = {
            "to": draft.get("to"),
            "cc": draft.get("cc"),
            "subject": draft.get("subject"),
            "in_reply_to": draft.get("in_reply_to"),
            "body_preview": (draft.get("body") or "")[:200],
            "cited": draft.get("cited"),
        }
        if not self.require_approval("send", detail, cap=cap):
            return False

        self.outbox.mkdir(parents=True, exist_ok=True)
        mid = draft.get("in_reply_to", "unknown")
        path = self.outbox / f"reply_to_{mid}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(draft, f, indent=2, ensure_ascii=False)
        self.writes += 1
        self.trace.log("send", cap=cap, path=str(path), to=draft.get("to"))
        return True

    def delete(self, message_id: str, cap: str | None = None) -> bool:
        # Deletes are irreversible in this mock store (no trash). Always gated; never auto.
        detail = {"message_id": message_id, "note": "no trash — irreversible"}
        if not self.require_approval("delete", detail, cap=cap):
            return False
        # We still refuse to actually remove from inbox.json — flag only.
        self.trace.log(
            "delete_refused_policy",
            cap=cap,
            message_id=message_id,
            reason="inbox messages are never deleted by inboxHero; flag instead",
        )
        return False
