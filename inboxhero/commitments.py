"""Extract commitments and surface calendar conflicts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Commitment:
    title: str
    when: str  # ISO-ish display datetime or date
    when_key: str  # sortable key for conflict detection YYYY-MM-DDTHH:MM
    cited: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_commitments(messages: list[dict[str, Any]]) -> tuple[list[Commitment], list[dict[str, Any]]]:
    by_id = {m["id"]: m for m in messages}
    commitments: list[Commitment] = []

    # Multi-message: board review (m038) + deck due two days before (m040)
    if "m038" in by_id and "m040" in by_id:
        commitments.append(
            Commitment(
                title="Board deck due (two days before board review)",
                when="2026-09-16",
                when_key="2026-09-16",
                cited=["m038", "m040"],
                notes="Board review is Sep 18 10:00 (m038); deck due two days prior (m040)",
            )
        )
        commitments.append(
            Commitment(
                title="Quarterly board review",
                when="2026-09-18T10:00",
                when_key="2026-09-18T10:00",
                cited=["m038"],
                notes="In-person at the office",
            )
        )

    # Investor intro Tue 15th 15:00
    if "m010" in by_id:
        commitments.append(
            Commitment(
                title="Intro call with Aria (Northwind VC)",
                when="2026-09-15T15:00",
                when_key="2026-09-15T15:00",
                cited=["m010"],
            )
        )

    # Dentist same slot
    if "m061" in by_id:
        commitments.append(
            Commitment(
                title="Dental cleaning with Dr. Osei",
                when="2026-09-15T15:00",
                when_key="2026-09-15T15:00",
                cited=["m061"],
            )
        )

    # Raghav 1:1 Wed 14:00
    if "m013" in by_id:
        commitments.append(
            Commitment(
                title="Move weekly 1:1 with Raghav",
                when="2026-09-10T14:00",  # "this week" Wednesday after Sep 8 => Sep 10
                when_key="2026-09-10T14:00",
                cited=["m013"],
                notes="Proposed Wednesday 2:00pm this week",
            )
        )

    # Acme demo Wednesday 14:00 — conflicts with Raghav
    if "m016" in by_id:
        commitments.append(
            Commitment(
                title="PaperJet demo with Acme evaluation team",
                when="2026-09-10T14:00",
                when_key="2026-09-10T14:00",
                cited=["m016"],
            )
        )

    # Launch target 20th (from t-launch / m026)
    if "m026" in by_id:
        commitments.append(
            Commitment(
                title="Product launch target date",
                when="2026-09-20",
                when_key="2026-09-20",
                cited=["m026", "m036"] if "m036" in by_id else ["m026"],
            )
        )

    # Pricing copy by 12th
    if "m030" in by_id:
        commitments.append(
            Commitment(
                title="Approve final pricing page annual-discount copy",
                when="2026-09-12",
                when_key="2026-09-12",
                cited=["m030"],
            )
        )

    # Candidate offer response by 19th
    if "m042" in by_id:
        commitments.append(
            Commitment(
                title="Respond to Jordan on backend role timeline",
                when="2026-09-19",
                when_key="2026-09-19",
                cited=["m042"],
            )
        )

    # Early investor slot that violates preference
    if "m043" in by_id:
        commitments.append(
            Commitment(
                title="Northwind partner slot (conflicts with no-meetings-before-11 preference)",
                when="2026-09-14T09:00",  # Monday after Sep 9
                when_key="2026-09-14T09:00",
                cited=["m043", "m041"] if "m041" in by_id else ["m043"],
                notes="Proposed Monday 9:00am — before earliest_hour preference",
            )
        )

    # SAFE signature Friday
    if "m018" in by_id:
        commitments.append(
            Commitment(
                title="Sign SAFE amendment via portal",
                when="2026-09-12",  # Friday after Sep 9
                when_key="2026-09-12",
                cited=["m018"],
            )
        )

    conflicts = _find_conflicts(commitments)
    return commitments, conflicts


def _find_conflicts(commitments: list[Commitment]) -> list[dict[str, Any]]:
    by_slot: dict[str, list[Commitment]] = {}
    for c in commitments:
        # Date-only deadlines (no clock time) are not same-slot conflicts.
        if "T" not in c.when_key or c.when_key.endswith("T00:00"):
            continue
        by_slot.setdefault(c.when_key, []).append(c)

    conflicts = []
    for slot, items in sorted(by_slot.items()):
        if len(items) < 2:
            continue
        conflicts.append(
            {
                "when": slot,
                "message": f"CONFLICT: {len(items)} items at {slot}",
                "items": [{"title": i.title, "cited": i.cited} for i in items],
            }
        )
    return conflicts
