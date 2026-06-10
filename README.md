# pin-scheduler

Prep and schedule 15–20 Pinterest video pins a day without filling a single
form field by hand.

Drop videos into a folder, say "prep pins", review a CSV of generated titles
and descriptions, say "schedule pins" — and Claude drives your own logged-in
Chrome through Pinterest's organic pin composer
(`pinterest.com/pin-creation-tool/`): uploads each video, fills title,
description, link, board, and tags, and sets "Publish at a later date" to the
next free slot in your posting window. Pinterest's native scheduler then does
the timed publishing every 30–60 minutes — no machine needs to stay awake.

## How it works

1. **Prep** — videos in `videos/inbox/` are transcribed (whisper); Claude
   generates an SEO title (≤100 chars) and description (≤800 chars) per video
   into `manifest.csv` with status `draft`.
2. **Review** — you edit/approve rows in the CSV (or say "approve all").
3. **Post** — Claude checks remaining queue capacity (Pinterest caps queued
   pins), computes the next free slots, and runs a verified per-pin playbook:
   every action is followed by a screenshot or DOM readback before the next
   one. Successful pins are marked `scheduled` and the video moves to
   `videos/scheduled/`.
4. **You click Schedule** — see below.

## The drafts-only safety default

By default the automation **never clicks the Publish/Schedule button**. It
fills everything — including the schedule date and time — and stops at a
fully-prepared Pinterest draft ("Changes stored!", visible in the
"Pin drafts" rail). You review each draft in Pinterest and click **Schedule**
yourself. That keeps a human's eyes and hand on the final irreversible step.

You can opt out by setting `auto_schedule: true` in `config.yaml`, and even
then Claude must confirm with you in-session before clicking. Note Pinterest
drafts expire after 30 days.

## Requirements

- macOS (the fallback upload path and pacing assumptions are macOS-specific)
- Chrome, logged into your Pinterest account
- [Claude Code](https://claude.com/claude-code) with a CDP browser harness —
  any tool that lets the agent click, type, screenshot, and set file inputs
  in your real running Chrome (this repo was built with a small private
  harness; the playbook in `SKILL.md` only assumes those four primitives plus
  raw CDP access)
- [uv](https://docs.astral.sh/uv/) (Python scripts and whisper run through it)
- ffmpeg (for transcription)

## Setup

```bash
git clone <this repo> && cd pin-scheduler
cp config.example.yaml config.yaml   # edit: link, alt text, tags, board, posting window
mkdir -p videos/inbox videos/scheduled
```

Drop `.mp4` files (< 200 MB — the organic composer's limit) into
`videos/inbox/`, open Claude Code in the repo, and say "prep pins".

## A note on Pinterest policy

This automates *your own hands* on *your own account* at human scale —
15–20 pins a day is normal power-user pinning, the batch session is
human-paced, and Pinterest's own scheduler performs the actual timed
publishing. No engagement automation, no scraping, no third-party accounts.

That said, the unambiguous routes are Pinterest's official API with
[standard access](https://developers.pinterest.com/) (app review required,
and it has no scheduling endpoint) or an approved partner like Tailwind. If
you need certainty, use those. This project exists because the API can't
schedule and the review hurdle is real — make your own call.

## Project layout

- `SKILL.md` — the Claude Code skill: phases, per-pin playbook, failure policy
- `config.example.yaml` — fixed fields: link, ALT text, tags, board, window
- `scripts/manifest.py` — CSV state machine (`draft → approved → scheduled`, `failed`)
- `scripts/slots.py` — next-free-slot computation (unit-tested)
- `scripts/transcribe.sh` — whisper wrapper with caching
- `docs/superpowers/specs/2026-06-11-pin-scheduler-design.md` — approved design
- `docs/exploration/pin-builder-field-map.md` — the empirically verified UI
  map (selectors, input methods, gotchas); the source of truth for the playbook
