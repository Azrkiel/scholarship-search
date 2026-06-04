---
description: Run a verified scholarship search sweep and update the tracker
argument-hint: [optional focus, e.g. "nursing + Texas + first-gen"]
---

Run the **Operating Workflow** from `CLAUDE.md` as a search sweep.

Optional focus for this sweep: $ARGUMENTS

Steps:

1. **Session start.** Establish today's date from context. Load `profile.md` (if
   missing, tell the user to run `/intake` first). Load `scholarships.csv` /
   `scholarships.md` (create from templates if missing) so you don't re-log duplicates.
2. **Search & triage.** Use **WebSearch** with narrow, intersectional queries built
   from the profile (field × identity × location × level × affiliation). If a focus
   was given above, lead with it but don't stop there. Cover aggregators *and* the
   higher-odds sources students miss (local foundations, the user's college
   departmental aid, field associations, parent-employer programs, civic/religious
   orgs, identity funds). **Shortlist plausible, open awards from the search snippets
   — don't fetch yet.** Dedupe by sponsor + award name first.
3. **Verify only the shortlist** with **WebFetch** — free tools only, no paid scrapers.
   Prefer the sponsor's own page over aggregators. Use a tight extraction prompt
   ("return only deadline, amount, eligibility, sponsor, required materials"). If a
   page comes back as an empty shell or bot wall, retry via `https://r.jina.ai/<url>`;
   if that also fails, skip it. Confirm: working URL, deadline still in the future vs.
   today, user genuinely eligible, real sponsor, not already in the tracker. Flag
   scams; never log them.
4. **Log** passing awards to `scholarships.csv` and `scholarships.md`. Use `MAYBE`
   with the open question when eligibility is uncertain.
5. **Prioritize** by effort-to-odds (amount, narrowness of fit, application burden,
   deadline urgency).
6. **Report**: how many found, the top picks, and any deadlines closing soon.
7. **Rebuild views.** After updating the tracker, run `python tools/build_ics.py` and
   `python tools/build_dashboard.py` so `deadlines.ics` and `scholarships.html` stay current.

Do not invent scholarships. Cite the source URL for each one.
