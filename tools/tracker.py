"""Shared tracker model: load scholarships.csv into typed rows and judge deadline urgency."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

# Statuses meaning the award is no longer an open opportunity.
CLOSED_STATUSES = {"CLOSED", "INELIGIBLE", "SUBMITTED", "RESULT"}

# Deadline tokens that are not real calendar dates.
NON_DATE_DEADLINES = {"", "ROLLING", "UNKNOWN", "VARIES", "TBD"}


@dataclass(frozen=True)
class Scholarship:
    name: str
    sponsor: str
    award: str
    deadline_raw: str
    eligibility: str
    requirements: str
    url: str
    odds: str
    status: str

    @property
    def deadline(self) -> date | None:
        """ISO-parsed deadline, or None for rolling/unknown/blank/malformed."""
        token = self.deadline_raw.strip()
        if token.upper() in NON_DATE_DEADLINES:
            return None
        try:
            return datetime.strptime(token, "%Y-%m-%d").date()
        except ValueError:
            return None

    @property
    def is_active(self) -> bool:
        return self.status.strip().upper() not in CLOSED_STATUSES

    def days_until(self, today: date) -> int | None:
        d = self.deadline
        return None if d is None else (d - today).days


def load_rows(path) -> list[Scholarship]:
    """Read scholarships.csv into Scholarship rows. Missing file -> []."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        text = p.read_text(encoding="utf-8-sig")  # tolerate Excel's UTF-8 BOM
    except UnicodeDecodeError as exc:
        raise SystemExit(
            f"{p} is not UTF-8 (Excel may have saved it as Windows-1252). "
            f"Re-save it as 'CSV UTF-8'. ({exc})"
        )
    reader = csv.DictReader(io.StringIO(text))  # StringIO preserves quoted newlines
    rows = [
        Scholarship(
            name=(r.get("Name") or "").strip(),
            sponsor=(r.get("Sponsor") or "").strip(),
            award=(r.get("Award $") or "").strip(),
            deadline_raw=(r.get("Deadline") or "").strip(),
            eligibility=(r.get("Eligibility match notes") or "").strip(),
            requirements=(r.get("Requirements") or "").strip(),
            url=(r.get("Source URL") or "").strip(),
            odds=(r.get("Est. odds") or "").strip(),
            status=(r.get("Status") or "").strip(),
        )
        for r in reader
    ]
    return [s for s in rows if s.name]  # drop blank trailing rows
