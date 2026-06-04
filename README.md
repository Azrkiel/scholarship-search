# scholarship-search

A Claude Code project that turns Claude into a **scholarship-sourcing agent**. Point it at your profile and it sweeps the web for real, currently-open scholarships you're eligible for, verifies each one against the live source page, tracks them in a pipeline, and drafts applications for you to review and submit.

It will not invent awards and it will not submit anything for you — you stay in control.

---

## What it does

- **Sources** scholarships across national aggregators *and* the higher-odds places students miss (local foundations, your college's departmental aid, your field's professional associations, parent-employer programs, civic/religious orgs, identity-specific funds).
- **Verifies** every candidate before logging it: fetches the actual page, confirms the deadline is still in the future, and checks you genuinely meet the eligibility.
- **Tracks** everything in `scholarships.csv` / `scholarships.md` through a status pipeline: `FOUND → VETTED → MATERIALS NEEDED → DRAFTING → READY FOR REVIEW → SUBMITTED → RESULT`.
- **Drafts** essays and pre-fills applications in your authentic voice, from true facts only.
- **Flags scams** — anything that charges a fee, "guarantees" a win, or asks for your SSN/bank info.

The full agent behavior lives in [`CLAUDE.md`](./CLAUDE.md), which Claude Code loads automatically when you open this folder.

---

## ⚠️ Privacy — read this first

**This repository is public.** Your personal data must never be committed here.

The project keeps committed **templates** separate from your local **working files**:

| Committed (safe, generic) | Local only — gitignored (your data) |
|---------------------------|-------------------------------------|
| `profile.template.md`     | `profile.md`                        |
| `scholarships.template.csv` / `.md` | `scholarships.csv` / `scholarships.md` |
| —                         | `applications/<award>/…` (drafts)   |

The included [`.gitignore`](./.gitignore) already excludes the working files. Do not remove those rules, and never paste your name, address, financials, SSN, or logins into a commit. If you'd rather keep everything private, fork this into a **private** repo.

---

## Quickstart

1. **Get the project**
   ```bash
   git clone https://github.com/Azrkiel/scholarship-search.git
   cd scholarship-search
   ```
2. **Open it in Claude Code** (`claude` in this folder, the desktop app, or the IDE extension). `CLAUDE.md` loads automatically. Make sure web access is available — the agent uses the **WebSearch** and **WebFetch** tools to find and verify awards.
3. **Set up your profile** — run the slash command:
   ```
   /intake
   ```
   Claude copies `profile.template.md` → `profile.md` and walks you through filling it in, a few questions at a time. The more it knows about your location, identity factors, and affiliations, the better the matches.
4. **Run a sweep**
   ```
   /sweep
   ```
   Optionally focus it: `/sweep nursing + Texas + first-gen`. Claude searches, verifies, logs to `scholarships.csv` / `scholarships.md`, and reports what it found with deadlines flagged.
5. **Review & apply.** Claude drafts essays and assembles materials under `applications/<award>/` and moves them to `READY FOR REVIEW`. You read, edit, and submit.

Re-run `/sweep` regularly — new scholarships post constantly and deadlines roll.

---

## Commands

| Command | What it does |
|---------|--------------|
| `/intake` | Create or update your applicant profile |
| `/sweep [optional focus]` | Run a verified scholarship search and update the tracker |

You can also just talk to Claude in plain language — the commands are shortcuts into the workflow defined in `CLAUDE.md`.

---

## Files

```
CLAUDE.md                  # agent behavior spec (auto-loaded by Claude Code)
profile.template.md        # blank intake form  → copy to profile.md
scholarships.template.csv  # tracker header     → copy to scholarships.csv
scholarships.template.md   # readable tracker   → copy to scholarships.md
applications/              # per-award draft folders (gitignored)
.claude/commands/          # /intake and /sweep slash commands
.gitignore                 # keeps your personal data out of git
```

---

## Notes

- Claude prepares and pre-fills; **you** review and submit. It won't auto-submit.
- Every logged scholarship has a real, fetched source URL and a future deadline — no invented awards.
- Legitimate scholarships are always free to apply for.
