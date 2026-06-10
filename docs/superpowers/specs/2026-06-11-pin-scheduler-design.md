# Pin Scheduler — Design

- **Date:** 2026-06-11
- **Status:** Approved
- **Origin:** Reader request following the [Instagram publishing via Claude browser automation](https://www.nickwinder.com/blog/instagram-publishing-claude-browser-automation) blog post.

## Problem

A reader posts 15–20 video pins per day through Pinterest's pin builder
(`https://www.pinterest.com/pin-builder/`), manually. Every pin uses the same
destination link, ALT text, and tags; only the video, title, and description
change. Titles and descriptions are currently written with ChatGPT and
copy-pasted. Pins are spaced every 30–60 minutes. The process takes a long
time, and the reader wants it automated in a way that behaves like a human and
does not run afoul of Pinterest's anti-spam rules.

Regular pins (pin builder) outperform idea pins for this account. Pinterest's
CSV bulk upload creates idea pins, so it is explicitly out.

**Audience:** built first for Nick's own machine and Pinterest account as a
working demo and blog post; structured so the reader (or anyone) can adopt it
by editing one config file and running one exploration session.

## Verified platform constraints (researched 2026-06-11)

| Constraint | Finding |
|---|---|
| API trial access | Pins are sandbox entities, visible only to the creator — unusable for real posting |
| API standard access | Requires app review with a demo video; OAuth setup per user |
| API scheduling | No scheduling endpoint — `POST /v5/pins` publishes immediately only |
| Native pin-builder scheduler | "Publish at a later date": up to 30 days ahead, **max 10 pins queued at a time**, video supported |
| Scheduled pin editing | Date/title/board/description/link editable after scheduling; media is not |

The 10-pin queue cap and time-picker increments must be re-verified
empirically during the exploration session — help docs drift.

## Chosen approach

**Browser automation via browser-harness driving pin-builder in the user's
logged-in Chrome, combined with Pinterest's native scheduler.** Claude runs a
daily batch (twice daily when >10 pins are needed, due to the queue cap),
fills each pin, and sets "Publish at a later date" so Pinterest itself does
the timed publishing every 30–60 minutes. No machine needs to stay awake; no
app review; the flow mirrors exactly what the reader already does by hand.

Rejected alternatives:

- **Real-time poster** (cron fires every 30–60 min, posts immediately):
  machine awake all day, 15–20 browser sessions daily, many more failure
  points.
- **Official API with standard access**: most robust and unambiguously
  ToS-compliant, but the app review plus OAuth setup is a real hurdle, and
  the lack of a scheduling endpoint forces an always-on worker anyway.
  Documented in the blog post as the "official" alternative, alongside
  approved partners (Tailwind etc.).

## Goals

1. `prep` phase: scan a videos folder, transcribe audio, generate SEO
   titles/descriptions into a reviewable CSV manifest.
2. `post` phase: schedule approved pins through pin-builder with full
   verification, spacing them via Pinterest's native scheduler.
3. All fixed fields (link, ALT, tags, board, posting window) in one config
   file.
4. Safe to re-run at any time; nothing is ever double-posted.

## Non-goals

- Idea pins or CSV bulk upload.
- Engagement automation (likes, follows, comments) or scraping.
- Multi-account support.
- Windows/Linux support (macOS first; clipboard and fallback upload path are
  macOS-specific).
- API integration (documented as an alternative only).

## Architecture

Form factor: a Claude Code skill repo. Claude is the orchestrator — no
daemon, no app. Two phases invoked conversationally.

```
pin-scheduler/
  SKILL.md            # the skill: workflow phases, field-by-field pin-builder playbook
  config.yaml         # fixed fields: link, ALT text, tags, board, posting window + interval
  manifest.csv        # single source of truth: filename, title, description, status, scheduled_time
  videos/
    inbox/            # user drops videos here
    scheduled/        # moved here after successful scheduling
  scripts/
    transcribe.sh     # whisper wrapper (reuse video-subtitle-cutter machinery)
    slots.py          # next-free-slot computation (pure, unit-testable)
```

### Config (`config.yaml`)

```yaml
link: https://example.com            # destination URL for every pin
alt_text: "..."                      # same ALT for every pin
tags: [tag1, tag2, ...]              # tagged topics, same for every pin
board: "Board Name"
window: { start: "08:00", end: "20:00" }
interval_minutes: 60                 # 30 or 60; must align with picker increments
timezone: local
```

### Manifest (`manifest.csv`)

Columns: `filename, title, description, status, scheduled_time, error`

Status lifecycle: `draft → approved → scheduled`, with `failed` (+ reason in
`error`) as the off-ramp. `failed` rows require a manual reset to `approved`.
`scheduled` rows are never touched again.

### Prep phase

1. Scan `videos/inbox/` for files not present in the manifest.
2. Transcribe audio with whisper (`scripts/transcribe.sh`).
3. Claude generates, in-session (no external LLM API): SEO title (≤100 chars,
   Pinterest's limit) and description (≤800 chars) from filename + transcript,
   keyword-aware.
4. Append rows with `status=draft`.
5. User reviews/edits the CSV and flips rows to `approved` (or tells Claude
   "approve all").

### Post phase

1. Read `approved` rows, up to the remaining queue capacity: 10 minus the
   number of `scheduled` rows whose `scheduled_time` is still in the future
   (the cap applies to pins currently queued on Pinterest, not per run).
2. Compute next free slots via `slots.py`.
3. For each row, run the per-pin playbook (below); on verified success, mark
   `scheduled` with the slot time and move the file to `videos/scheduled/`.
4. On queue-full: stop cleanly and report how many remain for a later run.

## Per-pin interaction playbook (browser-harness)

1. `new_tab("https://www.pinterest.com/pin-builder/")` → `wait_for_load()` →
   screenshot to confirm the builder rendered and the session is logged in.
   Auth wall → stop and ask the user.
2. **Upload:** primary — CDP `DOM.setFileInputFiles` on the file input (fires
   real change events at the browser level; React typically accepts it).
   Fallback — click the upload area and drive the native macOS file picker
   via AppleScript (proven in the Instagram project). The exploration session
   decides which becomes the documented primary.
3. **Processing wait:** poll with screenshots until the video preview
   renders; bounded timeout.
4. **Text fields** (title, description, ALT via its toggle, destination
   link): clipboard paste (`pbcopy` + Cmd+V) — the proven path through
   React-managed inputs.
5. **Tags:** type each tag into the "Tagged topics" autocomplete, screenshot,
   click the matching suggestion, verify it stuck. Unconfirmed tags silently
   drop.
6. **Board:** select the configured board from the dropdown; verify.
7. **Scheduling:** toggle "Publish at a later date"; set date and time to the
   computed slot (slots are constrained to the picker's increments).
8. **Publish** → screenshot-verify the confirmation before updating the
   manifest.
9. **Pacing:** a few seconds between actions, ~30–60 s between pins. No
   theatrical randomization — a batch session is what a human power-user does
   anyway.

## Slot computation (`slots.py`)

Pure function. Inputs: posting window, interval, the set of already-taken
`scheduled_time`s from the manifest, current time. Output: the next N free
slots, each ≥ now + safety margin, aligned to interval boundaries, spilling
past the window end into the next day's window. This is the unit-tested core.

## Error handling

- **Fail-stop, not fail-skip.** Any unverified step aborts the batch with a
  screenshot saved and the row marked `failed` + reason. Mid-batch failures
  usually mean a UI change or session problem; continuing risks cascading
  failures or malformed published pins.
- **Exception:** video processing timeout marks that row `failed` and
  continues — that is usually a per-file problem.
- **Queue full:** clean stop with a "N remaining, run again later" report.
- **Idempotency:** re-runs only consider `approved` rows; `scheduled` rows
  are never re-posted.

## Testing

1. **Exploration session (implementation step #1):** one assisted run against
   the real pin-builder to map every field, settle the upload method, and
   empirically verify the 10-pin queue cap and time-picker increments.
2. **Dry-run mode:** fill everything, stop before Publish, screenshot for
   review. Doubles as the blog post's screenshot source.
3. **Unit tests (TDD):** `slots.py` and manifest parsing.
4. **Acceptance:** schedule 2 real pins to a test board; confirm they appear
   in Pinterest's scheduled list and publish at the right times.

## Policy stance

Own account, own content, human-scale volume (15–20 pins/day is normal
power-user pinning), human-paced batch sessions, and Pinterest's own
scheduler performs the timed publishing. No engagement automation, no
scraping. SKILL.md and the blog post state plainly that the unambiguous
routes are API standard access or an approved partner (e.g. Tailwind), and
that this approach automates your own hands rather than running a bot farm —
the same stance as the Instagram post.

## Risks & open questions

- **UI drift:** Pinterest can change pin-builder at any time. Mitigation:
  screenshot-verify every step, fail-stop, and keep the playbook in SKILL.md
  easy to amend.
- **Queue cap:** if the cap turns out to be higher than 10 (some sources say
  100), the twice-daily run collapses to once daily — strictly better.
- **Field limits:** title 100 / description 800 / ALT limit to be confirmed
  in the UI during exploration.
- **Whisper variant:** whisper.cpp vs mlx-whisper vs OpenAI whisper CLI —
  decided during implementation planning based on what video-subtitle-cutter
  already uses.
- **Demo account:** the blog demo needs a Pinterest business account with
  video content (barefoot running clips from the reel-generator pipeline are
  a natural fit).
