# pin-scheduler

A Claude Code plugin that batch-prepares Pinterest video pins so you never
fill the pin form by hand again. Drop videos into a folder, say **"prep
pins"**, review a CSV of generated titles and descriptions, say **"schedule
pins"** — and Claude drives a dedicated logged-in browser (via
[agent-browser](https://agent-browser.dev)) through Pinterest's organic
composer (`pinterest.com/pin-creation-tool/`, which some accounts serve at
`pinterest.com/idea-pin-builder/` — same editor): uploads each video, fills
title, description, link, ALT text, board, and tags, and sets "Publish at a
later date" to the next free slot in your posting window.

**By default it never publishes anything.** On the storyboard composer every
pin stops as a fully-prepared draft; you review and click **Schedule** in
Pinterest yourself. Pinterest's native scheduler then does the timed publishing
— no machine needs to stay awake. (The exception: accounts whose composer is
the standard **pin-builder** have no draft mode, so scheduling there requires
`auto_schedule: true` and your explicit per-run consent — only then does the
tool click Schedule for you. See `docs/exploration/standard-pin-builder.md`.)

## Quickstart

### 1. Install the prerequisites (one time)

- [Claude Code](https://claude.com/claude-code)
- [Node.js](https://nodejs.org), then [agent-browser](https://agent-browser.dev):
  `npm i -g agent-browser`
- [uv](https://docs.astral.sh/uv/) — the Python scripts and whisper run
  through it, nothing to pip-install
- ffmpeg (`brew install ffmpeg`) — whisper needs it for audio extraction

That's everything: agent-browser downloads its own browser on first use, and
uv fetches Python and whisper on demand (the first "prep pins" run spends an
extra minute downloading the whisper model).

### 2. Install the plugin

```
/plugin marketplace add nickwinder/pin-scheduler
/plugin install pin-scheduler@pin-scheduler-marketplace
```

(Or from a local checkout: `/plugin marketplace add /path/to/pin-scheduler`,
then install the same way.)

### 3. Set up your content directory (one time)

The plugin keeps all state in whatever directory you run Claude Code from —
your "content directory". Pick or create one, then in Claude Code just say:

> set up pin-scheduler in this folder

Claude copies `config.example.yaml` to `config.yaml` and creates the folders.
Then edit `config.yaml` with your values — these are the fields that are the
same for every pin:

```yaml
link: https://www.your-site.com      # destination link for every pin
alt_text: "..."                      # ALT text for every pin
tags:                                # tag searches (closest Pinterest match is picked)
  - running shoes
  - barefoot running
board: "Your Board Name"             # must exist on your account
window:
  start: "08:00"                     # first slot of the day
  end: "20:00"                       # last slot of the day
interval_minutes: 60                 # spacing: 60 → 13 slots/day, 30 → 25 slots/day
margin_minutes: 20                   # never schedule closer than this to now
queue_cap: 10                        # Pinterest's queued-pin cap (help-docs value)
auto_schedule: false                 # keep false: drafts only, you click Schedule
```

### 4. Log into Pinterest (one time)

The first time you say "schedule pins", agent-browser opens a visible
dedicated browser window, hits Pinterest's login wall, and Claude stops and
asks you to log in. Type your credentials into that window yourself — the
automation never touches them. The persistent profile at
`~/.pin-scheduler-browser` keeps the session for every future run.

(Pinterest may ask for a verification email or captcha the first time it
sees the new browser — that's expected, and you're at the keyboard for this
step anyway.)

Why a dedicated browser instead of your everyday Chrome: macOS Chrome 144+
gates every automation client behind an "Allow remote debugging?" consent
popup, and when that gate is pending, agent-browser silently falls back to a
fresh logged-out browser — a failure mode you don't want mid-batch. A
persistent dedicated profile is deterministic; the skill verifies the login
state with a screenshot before every batch either way.

### 5. Use it

Drop videos in, "prep pins", approve, "schedule pins", then click
**Schedule** on the drafts in Pinterest — see [Daily use](#daily-use).

Good to know:

- Developed and tested on macOS; agent-browser, uv, whisper, and ffmpeg are
  all cross-platform, but no one has run this on Linux or Windows yet.
- Claude Code will ask permission for `agent-browser` and `uv` commands
  until you allow them for the project.

## Daily use

1. **Drop videos** (`.mp4`, < 200 MB each — the composer's limit) into
   `videos/inbox/`.

2. **Say "prep pins".** Each video's audio is transcribed (whisper, cached)
   and Claude writes an SEO title (≤100 chars) and description (≤800 chars)
   per video into `manifest.csv` with status `draft`.

3. **Review `manifest.csv`.** Edit any titles/descriptions you don't like,
   then say **"approve all"** (or flip individual rows' status to
   `approved` yourself).

4. **Say "schedule pins".** Claude checks remaining queue capacity, computes
   the next free time slots, and runs the verified per-pin playbook — every
   action is confirmed by a screenshot or DOM readback before the next one.
   Each finished pin is marked `scheduled` in the CSV and its video moves to
   `videos/scheduled/`. If it hits a login wall or anything unexpected, it
   stops and tells you rather than guessing. (First run only: log into
   Pinterest in the agent-browser window when asked — the profile remembers
   it from then on.)

5. **Open Pinterest and click Schedule** on each draft in the "Pin drafts"
   rail. That's the one step the automation never does for you. Drafts
   expire after 30 days, so don't let them sit.

At 15–20 pins/day (set `interval_minutes: 30`), Pinterest's ~10-queued-pin
cap means a morning and an afternoon "schedule pins" run.

## The drafts-only safety default

The automation fills **everything** — including the schedule date and time —
and then stops at "Changes stored!". It never clicks the red
Publish/Schedule button. That keeps a human's eyes and hand on the final,
irreversible step. `auto_schedule: true` exists as an opt-out, and even then
Claude must confirm with you in-session before clicking.

## A note on Pinterest policy

This automates *your own hands* on *your own account* at human scale: the
batch session is human-paced, volumes are normal power-user pinning, and
Pinterest's own scheduler performs the actual timed publishing. No
engagement automation, no scraping, no third-party accounts.

That said, the unambiguous routes are Pinterest's official API with
[standard access](https://developers.pinterest.com/) (app review required,
and it has no scheduling endpoint) or an approved partner like Tailwind. If
you need certainty, use those. This project exists because the API can't
schedule and the review hurdle is real — make your own call.

## Troubleshooting

- **"Login wall" stop** — log into Pinterest in the agent-browser window
  (the headed browser it opened), then tell Claude to continue. The
  persistent profile keeps the session afterwards.
- **agent-browser commands time out with `os error 35`** — the daemon is
  wedged; run `pkill -f agent-browser-darwin`, delete
  `~/.agent-browser/default.{sock,pid,stream}`, and retry.
- **A row is marked `failed`** — fix the cause (the `error` column says
  why; a screenshot is in `.cache/failures/`), edit its status back to
  `approved`, and run "schedule pins" again. `scheduled` rows are never
  re-posted, so re-runs are always safe.
- **Tags come out different from your config** — Pinterest only accepts its
  own tag vocabulary; the closest suggestion is picked (e.g. "barefoot
  running" → "Trail Running") and any unmatched tag is skipped and reported.
- **Pinterest changed their UI** — the playbook self-verifies every step and
  fail-stops instead of flailing. The selector map in
  `docs/exploration/pin-builder-field-map.md` is the single place to update.

## Plugin layout

- `.claude-plugin/` — plugin + marketplace manifests
- `skills/pin-scheduler/SKILL.md` — the skill: phases, per-pin playbook,
  failure policy, field reference
- `config.example.yaml` — template for your content directory's `config.yaml`
- `scripts/manifest.py` — CSV state machine (`draft → approved → scheduled`, `failed`)
- `scripts/slots.py` — next-free-slot computation (unit-tested)
- `scripts/transcribe.sh` — whisper wrapper with caching
- `scripts/inspect-composer.sh` — dumps the live composer's field map as JSON
  (run on a target account to verify selectors / stage pin-builder support)
- `docs/exploration/pin-builder-field-map.md` — the empirically verified UI
  map (selectors, input methods, gotchas); the source of truth for the playbook
- `docs/exploration/standard-pin-builder.md` — verified field map for the
  standard `/pin-builder/` composer (the second composer variant) and its
  no-draft constraint (auto_schedule-only)
- `tests/` — `uv run pytest` (17 tests)
