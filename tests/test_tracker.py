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
