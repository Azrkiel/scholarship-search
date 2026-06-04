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
2. **Search.** Use **WebSearch** with narrow, intersectional queries built from the
   profile (field × identity × location × level × affiliation). If a focus was given
   above, lead with it but don't stop there. Cover aggregators *and* the higher-odds
   sources students miss (local foundations, the user's college departmental aid,
   field associations, parent-employer programs, civic/religious orgs, identity funds).
3. **Verify every candidate** with **WebFetch** before logging — fetch the real page
   and confirm: working URL, deadline still in the future vs. today, user genuinely
   eligible, real sponsor, not already in the tracker. Flag scams; never log them.
4. **Log** passing awards to `scholarships.csv` and `scholarships.md`. Use `MAYBE`
   with the open question when eligibility is uncertain.
5. **Prioritize** by effort-to-odds (amount, narrowness of fit, application burden,
   deadline urgency).
6. **Report**: how many found, the top picks, and any deadlines closing soon.

Do not invent scholarships. Cite the source URL for each one.
