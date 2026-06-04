"""Render scholarships.csv -> deadlines.ics (RFC 5545) with reminder alarms.

Active rows that carry a real date become all-day VEVENTs with -P7D / -P1D
DISPLAY alarms. Stdlib only; import the file into any calendar app.
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tracker import Scholarship, load_rows


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """RFC 5545: physical lines must be <=75 octets; fold with CRLF + space."""
    out = []
    while len(line.encode("utf-8")) > 75:
        cut = 75
        while len(line[:cut].encode("utf-8")) > 75:
            cut -= 1
        out.append(line[:cut])
        line = " " + line[cut:]
    out.append(line)
    return "\r\n".join(out)


def _uid(s: Scholarship) -> str:
    key = f"{s.name}|{s.sponsor}|{s.url}".encode("utf-8")
    return hashlib.md5(key).hexdigest() + "@scholarship-search"


def _event(s: Scholarship, stamp: str) -> list[str]:
    start = s.deadline                  # caller guarantees s.deadline is set
    end = start + timedelta(days=1)     # RFC 5545: all-day DTEND is exclusive
    summary = f"Deadline: {s.name}" + (f" ({s.award})" if s.award else "")
    desc = _escape(
        f"Sponsor: {s.sponsor}\nAward: {s.award}\nStatus: {s.status}\n"
        f"Requirements: {s.requirements}\n{s.url}"
    )
    lines = [
        "BEGIN:VEVENT",
        f"UID:{_uid(s)}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{desc}",
    ]
    if s.url:
        lines.append(f"URL:{s.url}")
    for days, label in ((7, "1 week"), (1, "1 day")):
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_escape(s.name)} due in {label}",
            f"TRIGGER:-P{days}D",
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines


def build_ics(rows: list[Scholarship], now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//scholarship-search//deadlines//EN",
        "CALSCALE:GREGORIAN",
    ]
    for s in rows:
        if s.is_active and s.deadline is not None:
            body += _event(s, stamp)
    body.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in body) + "\r\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Build deadlines.ics from scholarships.csv")
    ap.add_argument("--csv", default="scholarships.csv")
    ap.add_argument("--out", default="deadlines.ics")
    args = ap.parse_args()
    rows = load_rows(args.csv)
    Path(args.out).write_text(build_ics(rows), encoding="utf-8")
    n = sum(1 for s in rows if s.is_active and s.deadline is not None)
    print(f"Wrote {n} deadline event(s) to {args.out}")


if __name__ == "__main__":
    main()
