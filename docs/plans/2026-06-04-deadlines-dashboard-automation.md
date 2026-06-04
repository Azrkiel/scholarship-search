# Plan: Deadline reminders, dashboard & scheduled sweeps

## Goal
Turn the agent-maintained `scholarships.csv` into a single source of truth that renders, for free and with zero API keys, into calendar deadline reminders, a browser dashboard, and an unattended weekly sweep.

## Architecture
`scholarships.csv` is the source of truth. Two small deterministic Python renderers (stdlib only) project it into derived artifacts: `tools/build_ics.py` → `deadlines.ics` (RFC 5545 events with reminder alarms you import into any calendar) and `tools/build_dashboard.py` → `scholarships.html` (urgency-sorted, color-coded table). A shared `tools/tracker.py` owns CSV parsing and deadline-urgency logic so both renderers stay DRY. Automation is a thin wrapper (`tools/run-sweep.ps1` / `.sh`) that runs `claude -p "/sweep"` headless then re-runs the two renderers. No third-party deps, no paid services, no connectors — consistent with the WebFetch+Jina free-tools policy.

## Tech stack
- Python 3.11 (confirmed: 3.11.4), **stdlib only** — `csv`, `datetime`, `dataclasses`, `hashlib`, `html`, `argparse`, `pathlib`.
- Tests: stdlib `unittest` (zero pip installs).
- Automation: `claude -p` headless mode (CLI confirmed at `C:\Users\Kevin\.local\bin\claude.exe`) + OS scheduler (Task Scheduler / cron).
- Calendar format: iCalendar / RFC 5545 `.ics` — universally importable, no Google API.

## Data flow & error states (sanity-check this before coding)

```
  WebSearch (snippets) --triage--> shortlist --WebFetch/Jina--> verify
                                                                  |
                                                                  v
                                                      [ scholarships.csv ]  <-- source of truth
                                                      Deadline col = ISO YYYY-MM-DD
                                                        | Rolling | Unknown
                                                                  |
                          +---------------------------------------+----------------------------+
                          |                                                                    |
                          v                                                                    v
                 tools/build_ics.py                                                 tools/build_dashboard.py
                 load_rows() -> Scholarship[]                                       load_rows() -> Scholarship[]
                          |                                                                    |
        per active row with a real date                                     sort: active first, soonest deadline
                          |                                                                    |
                          v                                                                    v
                  deadlines.ics  --import-->  Google/Apple/Outlook            scholarships.html --open--> browser
                  (VEVENT + VALARM -P7D/-P1D)                                  urgent<=14d, overdue, rolling, closed

  ERROR / EDGE PATHS
  -----------------
  scholarships.csv missing -----> load_rows() returns []  --> ics has 0 events; html shows "no rows" (valid empty files, exit 0)
  Deadline = Rolling/Unknown/'' -> deadline None          --> EXCLUDED from .ics; shown as "—/rolling" in dashboard
  Deadline malformed (not ISO) --> deadline None           --> same as above (never crash, never a bogus event)
  Status CLOSED/INELIGIBLE/...  -> is_active False         --> EXCLUDED from .ics; struck-through + gray in dashboard
  field contains comma/semicolon -> CSV-quoted on read; RFC5545-escaped in .ics; html-escaped in dashboard
  long SUMMARY (>75 octets) -----> RFC 5545 line folding (CRLF + space) so .ics stays valid

  AUTOMATION
  ----------
  OS scheduler --weekly--> run-sweep.{ps1,sh}
        |
        v
  claude -p "/sweep" (headless, --allowedTools WebSearch,WebFetch,Read,Write,Edit)
        |                         |                                  |
   profile.md missing       web tool denied                     sweep ok -> CSV updated
        v                         v                                  v
  log warning, no prompt    log error, continue            run build_ics + build_dashboard
        |_________________________|__________________________________|
                                  v
                  renderers ALWAYS run on whatever CSV exists -> fresh .ics + .html
                  (python missing -> logged at render step; sweep log still saved)
```

Scope guard: scheduled sweeps automate **search + log to the tracker only**. They never draft-submit or auto-apply — application submission stays human-in-the-loop per `CLAUDE.md`.

---

## File map

**New**
- `tools/tracker.py` — `Scholarship` dataclass + `load_rows()`; deadline parsing & urgency. Shared by both renderers.
- `tools/build_ics.py` — CSV → `deadlines.ics`.
- `tools/build_dashboard.py` — CSV → `scholarships.html`.
- `tools/run-sweep.ps1` — Windows headless sweep + rebuild views.
- `tools/run-sweep.sh` — macOS/Linux headless sweep + rebuild views.
- `tests/test_tracker.py`, `tests/test_build_ics.py`, `tests/test_build_dashboard.py`
- `tests/fixtures/sample_scholarships.csv` — synthetic test rows (not real awards).
- `.claude/commands/sync.md` — `/sync` rebuilds `.ics` + `.html` from the CSV.

**Modified**
- `CLAUDE.md` — Deadline=ISO rule; "Derived views" section; automation note; Project Layout rows.
- `.claude/commands/sweep.md` — final step: rebuild views.
- `README.md` — Calendar/dashboard + automation sections; file list.
- `.gitignore` — add `deadlines.ics`, `scholarships.html`, `logs/`, `__pycache__/`, `*.pyc`.

---

## Phase 0 — Test fixture

- [ ] Create `tests/fixtures/sample_scholarships.csv` (synthetic rows; row 2 has a comma inside a quoted field; "today" in tests is `2026-06-04`):

```csv
Name,Sponsor,Award $,Deadline,Eligibility match notes,Requirements,Source URL,Est. odds,Status
Example STEM Award,Example Foundation,5000,2026-07-01,Test row; CS major,Essay; transcript,https://example.org/stem,High,VETTED
Example Local Grant,Example Community Fund,1000,2026-06-10,"Test row, local, low competition",Essay,https://example.org/local,High,FOUND
Example Rolling Fund,Example Org,2000,Rolling,Test row no fixed date,None,https://example.org/rolling,Medium,FOUND
Example Past Award,Example Old Sponsor,3000,2026-05-01,Test row already expired,Essay,https://example.org/past,Low,FOUND
Example Closed Award,Example Sponsor,4000,2026-08-01,Test row,Essay,https://example.org/closed,Low,CLOSED
```

Expected derived counts at `today=2026-06-04`: 4 active rows (STEM, Local, Rolling, Past); ICS emits 3 events (STEM, Local, Past — Rolling undated, Closed inactive).

- [ ] Commit: `test: add synthetic scholarship fixture`

---

## Phase 1 — Shared tracker model (TDD)

- [ ] Write `tests/test_tracker.py`:

```python
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from tracker import Scholarship, load_rows  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_scholarships.csv"


def make(deadline="2026-07-01", status="FOUND"):
    return Scholarship(
        name="X", sponsor="S", award="100", deadline_raw=deadline,
        eligibility="", requirements="", url="", odds="", status=status,
    )


class TrackerTest(unittest.TestCase):
    def test_parse_iso_deadline(self):
        self.assertEqual(make("2026-07-01").deadline, date(2026, 7, 1))

    def test_non_dates_return_none(self):
        for token in ("Rolling", "rolling", "Unknown", "", "Varies", "July 1"):
            self.assertIsNone(make(token).deadline, token)

    def test_days_until(self):
        self.assertEqual(make("2026-06-10").days_until(date(2026, 6, 4)), 6)
        self.assertEqual(make("2026-05-01").days_until(date(2026, 6, 4)), -34)
        self.assertIsNone(make("Rolling").days_until(date(2026, 6, 4)))

    def test_is_active(self):
        self.assertTrue(make(status="FOUND").is_active)
        for s in ("CLOSED", "INELIGIBLE", "SUBMITTED", "RESULT"):
            self.assertFalse(make(status=s).is_active, s)

    def test_load_rows_parses_quoted_commas(self):
        rows = load_rows(FIXTURE)
        self.assertEqual(len(rows), 5)
        local = next(r for r in rows if r.name == "Example Local Grant")
        self.assertEqual(local.eligibility, "Test row, local, low competition")

    def test_load_missing_file_returns_empty(self):
        self.assertEqual(load_rows(Path("does-not-exist.csv")), [])

    def test_load_rows_strips_utf8_bom(self):
        import os
        import tempfile
        data = (
            "﻿Name,Sponsor,Award $,Deadline,Eligibility match notes,"
            "Requirements,Source URL,Est. odds,Status\n"
            "BOM Award,S,100,2026-07-01,x,Essay,https://example.org/b,High,FOUND\n"
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".csv", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(data)
            path = fh.name
        try:
            rows = load_rows(path)
            self.assertEqual(rows[0].name, "BOM Award")  # header not "﻿Name"
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] Run it, see it fail: `python -m unittest tests.test_tracker`
  Expected: `ModuleNotFoundError: No module named 'tracker'`.

- [ ] Create `tools/tracker.py`:

```python
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
```

- [ ] Run: `python -m unittest tests.test_tracker` → `Ran 7 tests ... OK`.
- [ ] Commit: `feat(tools): shared tracker model with deadline urgency`

---

## Phase 2 — ICS generator (TDD)

- [ ] Write `tests/test_build_ics.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from tracker import Scholarship, load_rows  # noqa: E402
import build_ics  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_scholarships.csv"


def physical_lines(ics: str):
    return ics.split("\r\n")


class BuildIcsTest(unittest.TestCase):
    def setUp(self):
        self.rows = load_rows(FIXTURE)
        self.ics = build_ics.build_ics(self.rows)

    def test_event_count_excludes_closed_and_undated(self):
        # STEM + Local + Past = 3; Rolling undated, Closed inactive.
        self.assertEqual(self.ics.count("BEGIN:VEVENT"), 3)

    def test_valarm_reminders_present(self):
        self.assertIn("TRIGGER:-P7D", self.ics)
        self.assertIn("TRIGGER:-P1D", self.ics)
        self.assertEqual(self.ics.count("BEGIN:VALARM"), 6)  # 2 per event

    def test_dtstart_value_date_format(self):
        self.assertIn("DTSTART;VALUE=DATE:20260701", self.ics)

    def test_dtend_is_day_after_start(self):
        self.assertIn("DTEND;VALUE=DATE:20260702", self.ics)  # exclusive end

    def test_text_is_escaped(self):
        one = build_ics.build_ics([Scholarship(
            name="A; B, C", sponsor="S", award="", deadline_raw="2026-07-01",
            eligibility="", requirements="", url="", odds="", status="FOUND")])
        self.assertIn("A\\; B\\, C", one)

    def test_uid_is_stable_across_runs(self):
        a = build_ics.build_ics(self.rows)
        b = build_ics.build_ics(self.rows)
        uids_a = sorted(l for l in physical_lines(a) if l.startswith("UID:"))
        uids_b = sorted(l for l in physical_lines(b) if l.startswith("UID:"))
        self.assertEqual(uids_a, uids_b)
        self.assertTrue(uids_a)

    def test_long_lines_are_folded(self):
        long = build_ics.build_ics([Scholarship(
            name="X" * 200, sponsor="S", award="", deadline_raw="2026-07-01",
            eligibility="", requirements="", url="", odds="", status="FOUND")])
        for line in physical_lines(long):
            self.assertLessEqual(len(line.encode("utf-8")), 75, line[:40])


if __name__ == "__main__":
    unittest.main()
```

- [ ] Run, see fail: `python -m unittest tests.test_build_ics` → `ModuleNotFoundError: No module named 'build_ics'`.

- [ ] Create `tools/build_ics.py`:

```python
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
```

- [ ] Run: `python -m unittest tests.test_build_ics` → `Ran 7 tests ... OK`.
- [ ] Smoke: `python tools/build_ics.py --csv tests/fixtures/sample_scholarships.csv --out /tmp/d.ics` → `Wrote 3 deadline event(s) to /tmp/d.ics`.
- [ ] Commit: `feat(tools): scholarships.csv -> deadlines.ics with reminders`

---

## Phase 3 — HTML dashboard (TDD)

- [ ] Write `tests/test_build_dashboard.py`:

```python
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from tracker import Scholarship, load_rows  # noqa: E402
import build_dashboard  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_scholarships.csv"
TODAY = date(2026, 6, 4)


class BuildDashboardTest(unittest.TestCase):
    def setUp(self):
        self.rows = load_rows(FIXTURE)
        self.html = build_dashboard.build_html(self.rows, TODAY)

    def test_header_counts(self):
        self.assertIn("4 active", self.html)
        self.assertIn("5 total", self.html)

    def test_row_classes(self):
        self.assertIn('class="urgent"', self.html)   # Local, 6 days
        self.assertIn('class="overdue"', self.html)  # Past
        self.assertIn('class="rolling"', self.html)  # Rolling
        self.assertIn('class="closed"', self.html)   # Closed

    def test_overdue_sorts_before_urgent(self):
        self.assertLess(
            self.html.index("Example Past Award"),
            self.html.index("Example Local Grant"),
        )

    def test_html_escaping(self):
        risky = build_dashboard.build_html([Scholarship(
            name="A & B <script>", sponsor="S", award="", deadline_raw="Rolling",
            eligibility="", requirements="", url="", odds="", status="FOUND")], TODAY)
        self.assertIn("A &amp; B &lt;script&gt;", risky)
        self.assertNotIn("<script>", risky.split("<table")[1])

    def test_link_rendering(self):
        self.assertIn('href="https://example.org/stem"', self.html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] Run, see fail: `python -m unittest tests.test_build_dashboard` → `ModuleNotFoundError: No module named 'build_dashboard'`.

- [ ] Create `tools/build_dashboard.py`:

```python
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
```

- [ ] Run: `python -m unittest tests.test_build_dashboard` → `Ran 5 tests ... OK`.
- [ ] Smoke: `python tools/build_dashboard.py --csv tests/fixtures/sample_scholarships.csv --out /tmp/s.html` → `Wrote dashboard with 5 row(s) to /tmp/s.html`.
- [ ] Full suite: `python -m unittest discover -s tests` → `Ran 19 tests ... OK`.
- [ ] Commit: `feat(tools): scholarships.csv -> scholarships.html dashboard`

---

## Phase 4 — Scheduled sweep automation

- [ ] Create `tools/run-sweep.sh`:

```bash
#!/usr/bin/env bash
# Unattended weekly sweep. Requires a complete profile.md; never auto-applies.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
stamp=$(date +%Y-%m-%d_%H%M)
log="logs/sweep_$stamp.log"

if [ ! -f profile.md ]; then
  echo "no profile.md — run /intake first; skipping sweep" | tee -a "$log"
else
  claude -p "/sweep" --model sonnet --permission-mode acceptEdits \
    --allowedTools "WebSearch,WebFetch,Read,Write,Edit,Bash" >>"$log" 2>&1 \
    || echo "claude sweep exited non-zero; rebuilding views from existing CSV" >>"$log"
fi

python3 tools/build_ics.py       >>"$log" 2>&1 || echo "build_ics failed" >>"$log"
python3 tools/build_dashboard.py >>"$log" 2>&1 || echo "build_dashboard failed" >>"$log"
echo "done $stamp" >>"$log"
```

- [ ] Create `tools/run-sweep.ps1`:

```powershell
# Unattended weekly sweep. Requires a complete profile.md; never auto-applies.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$log = "logs/sweep_$stamp.log"

if (-not (Test-Path "profile.md")) {
  "no profile.md - run /intake first; skipping sweep" | Tee-Object -FilePath $log -Append
} else {
  claude -p "/sweep" --model sonnet --permission-mode acceptEdits `
    --allowedTools "WebSearch,WebFetch,Read,Write,Edit,Bash" *>> $log
}
python tools/build_ics.py        *>> $log
python tools/build_dashboard.py  *>> $log
"done $stamp" | Out-File -FilePath $log -Append -Encoding utf8
```

- [ ] Verify the **error path** (no profile), Windows: `powershell -ExecutionPolicy Bypass -File tools/run-sweep.ps1` → confirm `logs/sweep_*.log` shows the "no profile.md" skip line and that `deadlines.ics` + `scholarships.html` still regenerated.
- [ ] Verify the **happy path + that `claude -p` resolves the slash command** (do this manually, not in CI — it spends credits): create a throwaway `profile.md` (`"NAME: Test`\n`LOCATION: Austin, TX`\n`MAJOR: CS"`), run the wrapper once, confirm the log shows the sweep actually executed `/sweep` (not "unknown command"), then delete the throwaway `profile.md`. If the command doesn't resolve in headless mode, fall back to inlining the `/sweep` body as the `-p` prompt.
- [ ] **Pre-flight the scheduler context** before trusting the weekly job: Task Scheduler/cron run without your interactive shell, so confirm `claude` is auth'd and on PATH there. If not, use the full path (`C:\Users\Kevin\.local\bin\claude.exe`) in the `schtasks` action and run the task **as the logged-in user** so the CLI session is available.
- [ ] Register the schedule (documented, user runs once):
  - Windows: `schtasks /create /tn "ScholarshipSweep" /tr "powershell -ExecutionPolicy Bypass -File C:\Users\Kevin\scholarship-search\tools\run-sweep.ps1" /sc weekly /d SUN /st 08:00`
  - cron: `0 8 * * 0 /path/to/scholarship-search/tools/run-sweep.sh`
- [ ] Commit: `feat(tools): unattended weekly sweep wrappers (ps1 + sh)`

---

## Phase 5 — Wire commands, docs, gitignore

- [ ] Create `.claude/commands/sync.md`:

```markdown
---
description: Rebuild deadlines.ics and scholarships.html from the tracker
---

The CSV is the source of truth. After any change to `scholarships.csv`, regenerate the
derived views by running:

- `python tools/build_ics.py`        (-> deadlines.ics — import into your calendar)
- `python tools/build_dashboard.py`  (-> scholarships.html — open in your browser)

Report how many events and rows were written. Do not edit the .ics or .html by hand.
```

- [ ] Append a final step to `.claude/commands/sweep.md` (after the Report step):

```markdown
7. **Rebuild views.** After updating the tracker, run `python tools/build_ics.py` and
   `python tools/build_dashboard.py` so `deadlines.ics` and `scholarships.html` stay current.
```

- [ ] Edit `CLAUDE.md` — in **Tracking System**, add after the columns block:
  `Deadline format: ISO **YYYY-MM-DD**. Use \`Rolling\` / \`Unknown\` when there's no fixed date (these are excluded from calendar reminders).`

- [ ] Edit `CLAUDE.md` — add a **Derived Views** subsection under Tracking System:

```markdown
### Derived views (free, generated from the CSV)

`scholarships.csv` is the single source of truth. Two stdlib scripts render it — never
hand-edit their output:

- `python tools/build_ics.py` → `deadlines.ics`: import into Google/Apple/Outlook for
  deadline reminders (alarms fire 7 days and 1 day before). Re-import after each sweep;
  UIDs are stable so events update in place rather than duplicating.
- `python tools/build_dashboard.py` → `scholarships.html`: an urgency-sorted dashboard
  (closing-soon, overdue, rolling, closed color-coded). Open in a browser.

Run both after any tracker change (or use `/sync`). They take no tokens and need no API.
Scheduled sweeps (`tools/run-sweep.ps1` / `.sh` via Task Scheduler or cron) run `/sweep`
then rebuild these — search + log only; never auto-apply.
```

- [ ] Edit `CLAUDE.md` Project Layout table — add rows: `tools/` + tests (committed); `deadlines.ics`, `scholarships.html`, `logs/` (gitignored).

- [ ] Edit `.gitignore` — append:

```
# Derived views (regenerated from the tracker) + automation logs
deadlines.ics
scholarships.html
logs/

# Python
__pycache__/
*.pyc
```

- [ ] Edit `README.md` — add **Deadlines & dashboard** and **Automate weekly sweeps** sections covering `/sync`, importing `deadlines.ics`, opening `scholarships.html`, and the `schtasks`/cron one-liners; add `tools/` and the derived files to the file list.
- [ ] Verify: `python -m unittest discover -s tests` still `OK`; `python tools/build_ics.py --csv tests/fixtures/sample_scholarships.csv --out /tmp/d.ics` and dashboard smoke both succeed.
- [ ] Commit: `docs: wire /sync, derived-views + automation docs, ignore generated files`

---

## Self-review

**Requirement coverage**
- Deadline reminders (Google Calendar) → Phase 2 `build_ics.py` emits RFC 5545 `.ics` with `-P7D`/`-P1D` alarms; free, no Google API. Import path documented (Phase 5). ✓
- Scheduled periodic `/sweep` → Phase 4 `run-sweep.{ps1,sh}` + scheduler registration; scoped to search+log, never auto-apply. ✓
- Ergonomic tracker upgrade → Phase 3 `build_dashboard.py` → color-coded urgency `scholarships.html` (no Notion/Sheets connector needed). ✓
- Builds on shipped work → reuses `scholarships.csv` schema, `/sweep` + `/intake`; adds `/sync`; no change to the WebFetch+Jina fetch policy. ✓

**Placeholder scan** — every script and test is shown in full; every command lists expected output; no "TBD"/"similar to". ✓

**Type/name consistency** — `Scholarship`, `load_rows`, `build_ics`, `build_html`, `_row_class`, `URGENT_DAYS`, `CLOSED_STATUSES`, `NON_DATE_DEADLINES` defined in Phase 1–3 and referenced consistently; tests import only those symbols. `_event` relies on `s.deadline is not None`, guaranteed by the `build_ics` filter loop. ✓

**Risks / decisions**
- ICS includes active rows with *past* dates (harmless past calendar entries); the agent is expected to mark expired awards `CLOSED`, which excludes them. Deliberate: keeps `build_ics` deterministic and `today`-independent for stable tests.
- Headless sweep can't ask clarifying questions; gated on `profile.md` existing. A thin profile yields a thin sweep — acceptable; interactive `/sweep` remains the primary path.
- `tests/fixtures/sample_scholarships.csv` holds synthetic "Example …" rows — test data, not logged awards; does not violate the no-invented-scholarship rule.

---

## Handoff
Plan saved to `docs/plans/2026-06-04-deadlines-dashboard-automation.md`. Execute via:
- **`xvant-execute`** — this session, checkpointed per task; or
- **subagent-driven** — a fresh subagent per phase.

Tell me which and I'll start.

---

## Plan Review — HOLD SCOPE (eng rigor)

Posture: **HOLD SCOPE** — accepted the planned scope, hunted failure modes at max rigor (no cathedral detour; matches review→execute intent). The four **must-fix** items below are already folded into the tasks above; three note-only items are documented, not blocking.

### Fixed in-plan (must-fix)
1. **Silent BOM/encoding failure.** Excel commonly saves CSV as UTF-8-with-BOM or Windows-1252. Reading as plain `utf-8` makes the BOM corrupt the `Name` header → `r.get("Name")` is `None` → *every row silently dropped* → empty `.ics`/`.html` with no error. → `load_rows` now reads `utf-8-sig` via `io.StringIO`, and raises a **named** `SystemExit` (not a silent crash) on non-UTF-8. *[tracker.py]*
2. **Invalid all-day VEVENT.** RFC 5545 DTEND is exclusive; `DTEND == DTSTART` is zero-length and some calendars reject or misplace it. → DTEND is now `deadline + 1 day`. *[build_ics.py]*
3. **Headless rebuild blocked.** `/sweep` step 7 runs `python …` (needs the Bash tool), but the wrapper's `--allowedTools` omitted Bash → step-7 rebuild would fail/hang in headless mode. → added `Bash` to the allowlist; the wrapper's own post-sweep rebuild stays as an idempotent backstop. *[run-sweep.*]*
4. **Link injection.** Logged URLs come from scraped pages; a `javascript:`/`data:` href could land in the local dashboard. → only `http(s)://` URLs render as links. *[build_dashboard.py]*

### Note-only (documented, not blocking)
5. **Google Calendar drops VALARM on import.** Imported `.ics` reminders are honored by Apple Calendar/Outlook, but Google applies its *account-default* notifications instead. The events import fine; the 7d/1d alarms are best-effort. README should say so; for reliable Google reminders the user sets a default notification on the imported calendar (or subscribes by URL if they later host the file).
6. **Scheduled-run auth / PATH / cost.** Task Scheduler & cron run without your interactive shell — `claude` must be auth'd and on PATH (or referenced by full path). Verify before trusting the weekly job (Phase 4 now covers this). Cost: an unattended **Opus** sweep every week is real spend → the wrapper pins `--model sonnet` (ample for search+log; override if desired). Consistent with your reject-Firecrawl-on-cost instinct.
7. **UID stability.** Calendar dedupe holds only while name+sponsor+url are unchanged; renaming an award yields a new event on the next import. Acceptable.

### Verified sound
- Token discipline unchanged — renderers are deterministic, **0 tokens**.
- Privacy: `.ics` / `.html` / `logs/` are gitignored — pipeline + eligibility notes never reach the public repo. ✓
- Line folding is byte-correct; CSV quoting handled; closed/rolling exclusion logic correct.
- Scope guard intact: automation searches + logs, never auto-applies.

**Verdict: ship it** after the four fixes (folded in). No architectural change warranted — CSV-as-source-of-truth + deterministic stdlib renderers is the right free, low-token design. Test count after fixes: **19** (tracker 7, ics 7, dashboard 5).
