---
description: Rebuild deadlines.ics and scholarships.html from the tracker
---

The CSV is the source of truth. After any change to `scholarships.csv`, regenerate the
derived views by running:

- `python tools/build_ics.py`        (-> deadlines.ics — import into your calendar)
- `python tools/build_dashboard.py`  (-> scholarships.html — open in your browser)

Report how many events and rows were written. Do not edit the .ics or .html by hand.
