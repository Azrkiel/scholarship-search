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
