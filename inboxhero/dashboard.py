"""Three-pane dashboard: pending, flagged, commitments."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import config
from inboxhero.commitments import extract_commitments


def build_dashboard(
    messages: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    flags: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    html_path: Path | None = None,
    json_path: Path | None = None,
) -> dict[str, Any]:
    commitments, conflicts = extract_commitments(messages)

    data = {
        "pending_actions": pending,
        "flagged": flags,
        "commitments": [c.to_dict() for c in commitments],
        "conflicts": conflicts,
        "summary": {
            "messages": len(messages),
            "pending": len(pending),
            "flagged": len(flags),
            "commitments": len(commitments),
            "conflicts": len(conflicts),
        },
    }

    json_path = json_path or config.DASHBOARD_JSON
    html_path = html_path or config.DASHBOARD_HTML
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    html_path.write_text(_render_html(data), encoding="utf-8")
    return data


def _render_html(data: dict[str, Any]) -> str:
    def esc(x: Any) -> str:
        return html.escape(str(x))

    pending_rows = ""
    for p in data["pending_actions"]:
        pending_rows += (
            f"<tr><td>{esc(p.get('message_id'))}</td>"
            f"<td>{esc(p.get('proposed_action'))}</td>"
            f"<td>{esc(p.get('why_human'))}</td></tr>\n"
        )

    flagged_rows = ""
    for fl in data["flagged"]:
        flagged_rows += (
            f"<tr><td>{esc(fl.get('message_id'))}</td>"
            f"<td>{esc(fl.get('kind'))}</td>"
            f"<td>{esc(fl.get('attempted'))}</td>"
            f"<td>{esc(fl.get('action'))}</td></tr>\n"
        )

    commit_rows = ""
    for c in data["commitments"]:
        commit_rows += (
            f"<tr><td>{esc(c.get('when'))}</td>"
            f"<td>{esc(c.get('title'))}</td>"
            f"<td>{esc(c.get('cited'))}</td>"
            f"<td>{esc(c.get('notes'))}</td></tr>\n"
        )

    conflict_html = ""
    for conf in data["conflicts"]:
        conflict_html += f"<li class='conflict'><strong>{esc(conf['message'])}</strong> — {esc(conf['items'])}</li>\n"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>inboxHero Dashboard</title>
<style>
  body {{ font-family: Georgia, 'Times New Roman', serif; margin: 2rem; background: #f7f4ef; color: #1a1a1a; }}
  h1 {{ font-size: 1.8rem; }}
  h2 {{ margin-top: 2rem; border-bottom: 2px solid #333; padding-bottom: 0.3rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; vertical-align: top; }}
  th {{ background: #e8e2d8; }}
  .conflict {{ color: #8b0000; margin: 0.4rem 0; }}
  .pane {{ margin-bottom: 1.5rem; }}
</style>
</head>
<body>
<h1>inboxHero — run dashboard</h1>
<p>Messages: {data['summary']['messages']} · Pending: {data['summary']['pending']} ·
Flagged: {data['summary']['flagged']} · Commitments: {data['summary']['commitments']} ·
Conflicts: {data['summary']['conflicts']}</p>

<section class="pane" id="pending">
<h2>1. Pending actions</h2>
<p>Everything the system wants to do but may not do alone.</p>
<table>
<thead><tr><th>Message</th><th>Proposed action</th><th>Why human</th></tr></thead>
<tbody>
{pending_rows or '<tr><td colspan="3">(none)</td></tr>'}
</tbody>
</table>
</section>

<section class="pane" id="flagged">
<h2>2. Flagged</h2>
<p>Refused / hostile / phishing / ungroundable.</p>
<table>
<thead><tr><th>Message</th><th>Kind</th><th>Attempted</th><th>Instead</th></tr></thead>
<tbody>
{flagged_rows or '<tr><td colspan="4">(none)</td></tr>'}
</tbody>
</table>
</section>

<section class="pane" id="commitments">
<h2>3. Commitments</h2>
<p>Dates, deadlines and obligations extracted from the inbox (with citations).</p>
<table>
<thead><tr><th>When</th><th>Title</th><th>Cited</th><th>Notes</th></tr></thead>
<tbody>
{commit_rows or '<tr><td colspan="4">(none)</td></tr>'}
</tbody>
</table>
<ul>
{conflict_html or '<li>No timed conflicts detected.</li>'}
</ul>
</section>
</body>
</html>
"""
