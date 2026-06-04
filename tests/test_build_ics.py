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
