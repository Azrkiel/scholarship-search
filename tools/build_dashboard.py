"""Render scholarships.csv -> scholarships.html: an urgency-sorted, color-coded dashboard.

Stdlib only; open the file in any browser. Active rows first, soonest deadline first;
closing-soon rows are flagged. No connector, no server.
"""
from __future__ import annotations

import argparse
import html
from datetime import date
from pathlib import Path

from tracker import Scholarship, load_rows

URGENT_DAYS = 14

STYLE = """<style>
body{font-family:system-ui,Segoe UI,sans-serif;margin:2rem;color:#1a1a1a}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ddd;padding:6px 10px;text-align:left;font-size:14px;vertical-align:top}
th{background:#f4f4f4}
tr.urgent td{background:#fff3cd}
tr.overdue td{background:#f8d7da}
tr.rolling td{background:#eef6ff}
tr.closed td{color:#999;text-decoration:line-through}
a{color:#0645ad}
.tag{padding:0 4px;border-radius:3px}
.tag.urgent{background:#fff3cd}
</style>"""


def _row_class(s: Scholarship, today: date) -> str:
    if not s.is_active:
        return "closed"
    d = s.days_until(today)
    if d is None:
        return "rolling"
    if d < 0:
        return "overdue"
    if d <= URGENT_DAYS:
        return "urgent"
    return ""


def _deadline_cell(s: Scholarship, today: date) -> str:
    d = s.days_until(today)
    if d is None:
        return html.escape(s.deadline_raw or "—")
    if d < 0:
        return f"{html.escape(s.deadline_raw)} (past)"
    return f"{html.escape(s.deadline_raw)} ({d}d)"


def _sort_key(s: Scholarship, today: date):
    d = s.days_until(today)
    return (not s.is_active, d is None, d if d is not None else 0)


def build_html(rows: list[Scholarship], today: date) -> str:
    ordered = sorted(rows, key=lambda s: _sort_key(s, today))
    trs = []
    for s in ordered:
        name = html.escape(s.name)
        safe = s.url if s.url.startswith(("http://", "https://")) else ""  # block javascript:/data:
        name_cell = f'<a href="{html.escape(safe)}">{name}</a>' if safe else name
        cells = [
            name_cell,
            html.escape(s.sponsor),
            html.escape(s.award),
            _deadline_cell(s, today),
            html.escape(s.status),
            html.escape(s.odds),
            html.escape(s.eligibility),
        ]
        tds = "".join(f"<td>{c}</td>" for c in cells)
        trs.append(f'<tr class="{_row_class(s, today)}">{tds}</tr>')
    active = sum(1 for s in rows if s.is_active)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Scholarship Tracker</title>" + STYLE + "</head><body>"
        "<h1>Scholarship Tracker</h1>"
        f"<p>Generated {today.isoformat()} — {active} active / {len(rows)} total. "
        f"<span class='tag urgent'>Urgent</span> = due within {URGENT_DAYS} days.</p>"
        "<table><thead><tr>"
        "<th>Name</th><th>Sponsor</th><th>Award</th><th>Deadline</th>"
        "<th>Status</th><th>Odds</th><th>Eligibility</th>"
        "</tr></thead><tbody>" + "\n".join(trs) + "</tbody></table></body></html>"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Build scholarships.html from scholarships.csv")
    ap.add_argument("--csv", default="scholarships.csv")
    ap.add_argument("--out", default="scholarships.html")
    args = ap.parse_args()
    rows = load_rows(args.csv)
    Path(args.out).write_text(build_html(rows, date.today()), encoding="utf-8")
    print(f"Wrote dashboard with {len(rows)} row(s) to {args.out}")


if __name__ == "__main__":
    main()
