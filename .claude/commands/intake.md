---
description: Create or update the applicant profile for scholarship matching
---

Run the **Intake** workflow from `CLAUDE.md`.

1. If `profile.md` does not exist, copy `profile.template.md` to `profile.md` (it is
   gitignored — personal data stays local on this public repo).
2. Read the current `profile.md`. Identify blank or stale fields.
3. Ask the user to fill them in **small batches, one focused question at a time**.
   Prioritize the high-value, often-blank fields: LOCATION (city/county/state/ZIP),
   IDENTITY FACTORS, and AFFILIATIONS (employer, parent's employer, clubs, civic/
   religious orgs) — these unlock the least-competitive awards.
4. Write each answer back into `profile.md` as it comes in.
5. When the profile is reasonably complete, confirm a short summary and offer to run
   `/sweep`.

Do not commit `profile.md`. Never store SSN, bank details, or passwords.
