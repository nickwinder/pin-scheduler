---
name: pin-scheduler
description: Prep and schedule Pinterest video pins via the organic pin-creation-tool. Use when asked to "prep pins", "schedule pins", "post to Pinterest", or process a folder of videos into scheduled pin drafts.
---

# pin-scheduler

Batch-prepare Pinterest video pins in a dedicated agent-browser session. Two
phases: **prep** (transcribe + generate copy into `manifest.csv` for review)
and **post** (fill the pin form, set the schedule, leave it as a draft).
Pinterest's own scheduler does the timed publishing.

## Paths

- **Plugin scripts** live at `${CLAUDE_PLUGIN_ROOT}/scripts/`. If
  `CLAUDE_PLUGIN_ROOT` is unset (running from a checkout of this repo), use
  the repo root instead.
- **State lives in the user's content directory** (the current working
  directory): `config.yaml`, `manifest.csv`, `videos/inbox/`,
  `videos/scheduled/`, `.cache/`. Run all commands from there.
- **The browser profile** lives at `~/.pin-scheduler-browser` (machine-level,
  shared across content directories).

`manifest.csv` is the single source of truth; never schedule anything that
isn't an `approved` row in it.

## Drafts-only policy (non-negotiable default)

The post phase fills **every** field — including the "Publish at a later
date" toggle, date, and time — and then **STOPS. It never clicks the red
Publish/Schedule button.** Terminal state per pin: all fields verified +
"Changes stored!" in the editor header + the draft visible in the
"Pin drafts (N)" rail. The user clicks **Schedule** on each draft in
Pinterest themselves.

- `auto_schedule: false` in config.yaml is the default. Only if the user has
  set it to `true` **and** explicitly confirms in the current session may the
  Schedule button be clicked. Never flip this yourself; never infer consent.
- Manifest status `scheduled` means "slot claimed, Pinterest draft fully
  prepared". In drafts-only mode the user still has to click Schedule.
- Pinterest drafts **expire in 30 days** — remind the user.

**The above describes the storyboard composer.** The standard **pin-builder**
composer (some accounts only have this — see "Composer variants") has **no
draft state at all**: nothing autosaves, and a filled-but-uncommitted pin is
lost on navigation. There, the only way to schedule is to click the red
**Schedule** button. So pin-builder is supported **only** when
`auto_schedule: true` **and** the user confirms in-session — same consent bar,
no exceptions. With `auto_schedule: false` (the default), the tool **cannot**
use pin-builder and must **STOP** and tell the user (a fill-and-stop draft is
impossible there). Still never flip `auto_schedule` yourself; never infer
consent.

## Setup (once)

In the user's content directory:

```bash
cp "${CLAUDE_PLUGIN_ROOT}/config.example.yaml" config.yaml   # then edit: link, alt_text, tags, board, window
mkdir -p videos/inbox videos/scheduled
```

- `agent-browser` must be on $PATH (`npm i -g agent-browser`; the daemon
  auto-starts).
- `uv` and `ffmpeg` installed (whisper transcription needs ffmpeg).
- First post run only: the dedicated browser needs a one-time Pinterest
  login (see "Browser session" below).

## Browser session (agent-browser)

The post phase drives a **dedicated headed browser with a persistent
profile** — not the user's everyday Chrome:

```bash
agent-browser --profile ~/.pin-scheduler-browser --headed open "https://www.pinterest.com/pin-creation-tool/"
agent-browser wait --load networkidle
# Wait for the editor (or a definitive failure signal) to actually render
# before classifying — the React dropzone hydrates a beat after the page
# shell, so a too-early check reads as a false login wall:
agent-browser wait --fn "!!document.querySelector('#storyboard-upload-input') || (document.querySelector('h1')?.textContent||'').includes('for ad') || /Log in|Sign up/.test(document.body?.innerText||'')"
agent-browser screenshot /tmp/pin-check.png
# Classify what loaded by the EDITOR, not the URL — Pinterest routes the
# organic composer to a different URL per account cohort (see "Which URL"):
agent-browser eval "document.querySelector('#storyboard-upload-input') ? 'storyboard' : ((document.querySelector('h1')?.textContent||'').includes('for ad') ? 'ad' : ((/Create Pin/.test(document.querySelector('h1')?.textContent||'') && document.querySelector('input[type=file]')) ? 'pin-builder' : 'other'))"
```

- **`storyboard`** → logged in on the organic composer with the upload
  dropzone. **Proceed** with the per-pin playbook. This is the proven path, and
  the landing URL may be `/pin-creation-tool/` **or** `/idea-pin-builder/`
  (same editor, see "Which URL" below); do not gate on it.
- **`ad`** → Pinterest dropped you in the **"Create Pin for ad"** composer
  (different fields, ad limits, uploads silently ignored). This skill does not
  drive the ad flow. **STOP** — see the `/pin-builder/` note in step 1 of the
  per-pin playbook.
- **`pin-builder`** → the **standard Pin composer** (an account with no ad
  access serves this at `/pin-builder/`, and possibly at `/pin-creation-tool/`
  if its storyboard editor is deprecated). Supported via its **own per-pin
  playbook** (different field map), but **only** with `auto_schedule: true` +
  in-session consent — it has no draft state. See "Composer variants" routing.
- **`other`** → no usable editor. Read the screenshot to tell two cases apart:
  - **Login wall** — screenshot shows Log in / Sign up and the marketing
    landing page (Pinterest bounced you off the composer). **STOP and ask the
    user to log into Pinterest in the agent-browser window** — never type
    credentials yourself. The persistent profile keeps the session for every
    later run, so this happens once.
  - **Editor heading "Create Pin" present but the dropzone never rendered**
    (body nearly empty, no `#storyboard-*` elements, not the ad flow) — a
    partial load or a **tripped bot challenge**, not a login problem. This page
    has a hidden reCAPTCHA and **rapid-fire reloads trip it** (see gotchas).
    Pace human-like, wait ~30 s, and re-`open` **once**; if it persists, STOP
    and ask the user to check the window. Do not hammer the page.

### Which URL — account-cohort redirects (verified 2026-06-13)

The organic storyboard composer is **the same editor** whether Pinterest
serves it at `/pin-creation-tool/` or `/idea-pin-builder/`; which URL you land
on depends only on the account. On this machine's business account
`/pin-creation-tool/` stays put and `/idea-pin-builder/` redirects *to* it;
on other accounts it is the reverse (a customer reported
`/pin-creation-tool/` → `/idea-pin-builder/`). Either way the `#storyboard-*`
field map below applies unchanged. **Verify the composer, never the URL.**

`https://www.pinterest.com/pin-builder/` is a **different** composer — the
**"Create Pin for ad"** flow on business accounts (the `ad` state above) with
a different, unstable field map and silently-ignored uploads. This skill does
not target it; never switch the open URL to `/pin-builder/`.

### Composer variants — routing

| Classifier result | Composer | What to do |
|---|---|---|
| `storyboard` | organic storyboard editor (`pin-creation-tool` / `idea-pin-builder`) | **Proceed** with the storyboard per-pin playbook (default, drafts-only). Proven path. |
| `pin-builder` | standard Pin composer — heading "Create Pin", no "for ad" (accounts without ad access, e.g. the customer's) | **Proceed** with the **pin-builder per-pin playbook** — but only if `auto_schedule: true` + in-session consent (no draft state, so it must click Schedule). Otherwise **STOP** and tell the user (see Drafts-only policy). |
| `ad` | "Create Pin for ad" (`pin-builder` on accounts **with** ad access, e.g. this repo's) | **STOP.** Wrong intent — that's the *paid ad* composer; it creates ads, not organic pins. (Its field map is the same as pin-builder, but we don't post ads.) |
| `other` | login wall / partial load | **STOP** and ask the user (see Browser session). |

The pin-builder field map is **verified** (2026-06-14) — full table, selectors,
and the time-picker quirk in `docs/exploration/standard-pin-builder.md`; the
per-pin steps are in "Per-pin playbook — pin-builder composer" below. Two
caveats carried from that doc:

- **No draft state** → pin-builder runs only under `auto_schedule` + consent
  (above). This is the one composer where the tool clicks Schedule.
- Verified on the *ad* variant (same components/selectors as the standard one).
  On a **standard** (non-ad) account, confirm once with
  `./scripts/inspect-composer.sh` that the heading is "Create Pin" (not "for
  ad") and the `[id^=pin-draft-*]` selectors match before the first real run.
  The **board** and **ALT** steps and the final **Schedule** click were not
  exercised on the test account (would post an ad) — verify them on the first
  consented run.

Why not attach to the user's running Chrome: macOS Chrome 144+ gates every
new CDP client behind an in-browser "Allow remote debugging?" consent popup.
While that popup is pending, the agent-browser daemon wedges, its CLI times
out — and then **commands silently fall back to a freshly auto-launched,
logged-out browser**, which looks like a working session but isn't. Chrome
profile *snapshots* (`--profile <name>`) don't carry logins on macOS either:
cookies are keychain-encrypted and Chrome for Testing can't decrypt them.
The dedicated persistent profile avoids all of it. (`agent-browser connect
<ws-url>` to the real Chrome does work if the user clicks Allow — treat it
as an advanced option, and never trust a "connected" session until a
screenshot proves the login state.)

## Prep phase ("prep pins")

1. List videos in `videos/inbox/` whose basename is not already a `filename`
   in `manifest.csv`.
2. For each new video:
   - Transcribe: `"${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.sh" videos/inbox/<file>`
     (cached in `.cache/transcripts/`; prints the transcript).
   - Generate, in-session, from filename + transcript:
     - **Title** ≤100 chars, leading keywords first.
     - **Description** ≤800 chars, natural sentences, keyword-rich, no
       hashtag spam.
     - Enforce the limits yourself — the UI has no counters.
   - Append: `uv run --no-project "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" add "<file>" "<title>" "<description>"`
3. Tell the user to review `manifest.csv` and approve rows. On "approve all":
   for **each** row with status `draft`, run one invocation per row —
   `uv run --no-project "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" mark "<filename>" approved`
   — there is no bulk subcommand.

## Post phase ("schedule pins")

1. Capacity check: read `queue_cap` from `config.yaml`, then run
   `uv run --no-project "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" capacity --cap <queue_cap>`
   (substitute the value; default is 10). If 0: stop cleanly, report "queue
   full, N approved pins remaining — run again later".
2. Take `N = min(capacity, number of approved rows)`.
3. Get slots: `uv run --no-project "${CLAUDE_PLUGIN_ROOT}/scripts/slots.py" --count N`
   — prints one naive local ISO datetime per line (e.g. `2026-06-12T09:00`).
4. For each approved row + slot, run the per-pin playbook. **Step 1 classifies
   the composer** and picks the matching playbook: `storyboard` (default,
   drafts-only) or `pin-builder` (auto_schedule + consent only — see its
   playbook's consent gate). Only after the final verification screenshot:
   ```bash
   uv run --no-project "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" mark "<file>" scheduled --time "<slot-iso>"
   mv "videos/inbox/<file>" "videos/scheduled/<file>"
   ```
   `mark <file> scheduled` **requires** `--time` (it raises without it). Pass
   the slot exactly as slots.py printed it — naive local ISO, no timezone.
5. **Pacing:** a few seconds between actions (`agent-browser wait 2000`
   inside batches), 30–60 s between pins. The page has a hidden reCAPTCHA —
   human-paced batch sessions only.
6. Report: which pins were prepared with which slots, any skipped tags, and —
   for the **storyboard** composer — remind the user to click **Schedule** on
   each draft in the Pin drafts rail (drafts expire in 30 days). For
   **pin-builder**, the pins were already scheduled (no draft stage), so report
   them as scheduled rather than as drafts to finish.

## Per-pin playbook — storyboard composer (default)

For the `storyboard` composer (`pin-creation-tool` / `idea-pin-builder`). If
the classifier returned `pin-builder`, use the next section instead.

Slot conversion first: from the ISO slot, date is `MM/DD/YYYY`
(`%m/%d/%Y`), time label is zero-padded 12-hour (`%I:%M %p`, e.g.
`2026-06-12T09:00` → `06/12/2026` + `09:00 AM`). The time picker only has
30-minute increments, which the slot generator already respects.

**1. Open the organic composer.** Open
`https://www.pinterest.com/pin-creation-tool/`. Pinterest may redirect it to
`/idea-pin-builder/` on some accounts — that is the **same** editor, fine to
proceed (see "Which URL"). Never switch to `/pin-builder/` — on business
accounts that is the **ad** composer (different limits, unstable ids,
file-input uploads silently ignored).

```bash
agent-browser --profile ~/.pin-scheduler-browser --headed open "https://www.pinterest.com/pin-creation-tool/"
agent-browser wait --load networkidle
agent-browser wait --fn "!!document.querySelector('#storyboard-upload-input') || (document.querySelector('h1')?.textContent||'').includes('for ad') || /Log in|Sign up/.test(document.body?.innerText||'')"
agent-browser screenshot /tmp/pin-step1.png
agent-browser eval "document.querySelector('#storyboard-upload-input') ? 'storyboard' : ((document.querySelector('h1')?.textContent||'').includes('for ad') ? 'ad' : ((/Create Pin/.test(document.querySelector('h1')?.textContent||'') && document.querySelector('input[type=file]')) ? 'pin-builder' : 'other'))"
```

The eval must print **`storyboard`** and the screenshot must show the editor
with the upload dropzone — regardless of whether the URL is
`/pin-creation-tool/` or `/idea-pin-builder/`. `ad` = the wrong (ad) composer
(**STOP**); `pin-builder` = the standard Pin composer — switch to its own
playbook ("Per-pin playbook — pin-builder composer"), which runs only under
`auto_schedule` + consent; `other` = login wall or a partial/bot-challenged
load (**STOP** and ask the user). See "Browser session" / "Composer variants"
for the routing.

**2. Upload.** `agent-browser upload` handles the hidden input directly:

```bash
agent-browser upload "#storyboard-upload-input" "/absolute/path/to/videos/inbox/FILE.mp4"
agent-browser wait 3000
agent-browser eval "document.querySelector('#storyboard-upload-input') === null"
```

The input being **removed from the DOM** (`true` above) = upload started.
Video must be mp4 < 200 MB in this flow.

**3. Wait for processing.**

```bash
agent-browser wait --fn "!!document.querySelector('video')"
agent-browser screenshot /tmp/pin-step3.png    # preview with play button
```

Timeout: **3 minutes** → mark this row `failed` with reason "processing
timeout" and continue with the next pin (the one exception to fail-stop).

**4. Fill the text fields.** Plain `fill` works on all three — including the
Draft.js description editor. Readback after each; pace between fields.

```bash
agent-browser fill "#storyboard-selector-title" "TITLE"          # from manifest row
agent-browser wait 2000
agent-browser fill "div[contenteditable=true]" "DESCRIPTION"     # from manifest row
agent-browser wait 2000
agent-browser fill "#WebsiteField" "LINK"                        # from config.yaml

# Readback verification — required before moving on:
agent-browser get value "#storyboard-selector-title"
agent-browser get text "div[contenteditable=true]"
agent-browser get value "#WebsiteField"
```

Each printed value must match what you sent. Mismatch → failure policy.

**5. Board.** The dropdown only opens reliably when it's in view, and a
click's "✓ Done" does not prove it opened — verify, retry once if needed:

```bash
agent-browser snapshot -i -c        # find ref of button "Choose a board Open dropdown", e.g. @e24
agent-browser batch "scrollintoview @e24" "wait 1000" "click @e24" "wait 1200" "screenshot /tmp/pin-step5.png"
# screenshot must show the board list; if not, click the ref again
agent-browser find text "BOARD_NAME" click --exact      # board from config.yaml
agent-browser wait 1500
agent-browser snapshot -i -c        # dropdown button must now show the board name
```

**6. Tags** — one at a time, from `config.yaml`:

```bash
agent-browser fill "#combobox-storyboard-interest-tags" "TAG"
agent-browser wait 2500
agent-browser eval "JSON.stringify([...document.querySelectorAll('[role=option]')].map(e => e.textContent.trim()))"
```

- Pinterest's vocabulary rarely matches config tags verbatim — pick the
  closest option (e.g. config "barefoot running" → "Trail Running",
  "running shoes" → "Running Shoes"). An empty list is common for specific
  phrases: retry once with a broader query (e.g. "barefoot running" →
  "running"), then pick the closest suggestion.
- Click the option and **verify the counter** — option clicks can silently
  no-op when the option sits outside the dropdown's visible scroll area:
  ```bash
  agent-browser find role option click --name "OPTION_TEXT" --exact
  agent-browser wait 1500
  agent-browser eval "(document.body.innerText.match(/Tagged topics \((\d+)\)/) || [])[1]"
  ```
  If the counter did not increment, scroll the option into view via `eval`
  (`...scrollIntoView({block:'center'})` on the matching `[role=option]`)
  and click again. Still no increment after one retry → failure policy.
- **No usable suggestions → skip the tag** and note it in the final report.
  A skipped tag is not a batch failure.

**7. ALT text.** `#storyboardAltText` is **not in the DOM** until "More
options" is expanded:

```bash
agent-browser snapshot -i -c        # find ref of button "More options ..." , e.g. @e17
agent-browser batch "scrollintoview @e17" "click @e17" "wait 1500"
agent-browser fill "#storyboardAltText" "ALT_TEXT"               # from config.yaml
agent-browser get value "#storyboardAltText"
```

("More options" also holds comment/product toggles — leave them.)

**8. Schedule toggle.**

```bash
agent-browser check "#pin-draft-switch-group"
agent-browser wait 1500
agent-browser is checked "#pin-draft-switch-group"               # must print true
```

The date/time fields appear and the red Publish button now reads
**Schedule** — that is the button you must NOT click.

**9. Date field.**

```bash
agent-browser fill "input[id^=pin-draft-schedule-date-field]" "06/12/2026"   # MM/DD/YYYY from slot
agent-browser wait 1200
agent-browser press Escape                                       # close the calendar popup
agent-browser get value "input[id^=pin-draft-schedule-date-field]"   # must equal the date
```

Scheduling window is 30 days out, max — slots.py never exceeds that in
normal use, but a stale manifest could; a disabled calendar date means the
slot is out of range.

**10. Time field** — typing is ignored; **must pick from the dropdown**
(48 options, 30-minute increments, 12-hour labels). Playwright auto-scrolls
the option inside the dropdown's inner container:

```bash
agent-browser click "input[id^=pin-draft-schedule-time-field]"   # opens dropdown
agent-browser wait 1500
agent-browser find text "09:00 AM" click --exact                 # %I:%M %p from slot
agent-browser wait 1200
agent-browser get value "input[id^=pin-draft-schedule-time-field]"   # must equal the label
```

**11. Final verification, then STOP.**

```bash
agent-browser eval "document.body.innerText.includes('Changes stored!')"     # true
agent-browser eval "(document.body.innerText.match(/Pin drafts \((\d+)\)/) || [])[1]"
agent-browser snapshot -i -c     # button "Schedule" present; toggle checked=true; fields hold values
agent-browser screenshot /tmp/pin-step11.png
```

Confirm: title, description, link, board, tags, toggle on, date, and time
all show the expected values; the header shows **"Changes stored!"**; the
drafts count incremented. Do **not** click Publish/Schedule (see drafts-only
policy). Then update the manifest and move the file (post phase step 4),
wait 30–60 s, and start the next pin with the "Create new" button or a fresh
`open`.

## Per-pin playbook — pin-builder composer

For the `pin-builder` composer (standard Pin composer, heading "Create Pin",
on accounts without ad access). Field map verified 2026-06-14 on the ad variant
(same components); selectors use stable `[id^=pin-draft-*]` prefixes.

**0. Consent gate — before anything.** Pin-builder has **no draft state**, so
this playbook **clicks Schedule** (it cannot leave a draft). Run it **only** if
**both**: `auto_schedule: true` in config.yaml **and** the user explicitly
confirmed in this session. If either is missing, **STOP** and tell the user:
"this account's composer is pin-builder, which has no draft mode — to schedule
here the tool must click Schedule for you; set `auto_schedule: true` and
confirm, or schedule manually." Never flip the flag, never infer consent.

Slot conversion is identical to the storyboard playbook (`MM/DD/YYYY` +
`%I:%M %p`).

**1. Open + classify.** Same as storyboard step 1, but the eval must print
**`pin-builder`** (heading "Create Pin", file input present, not "for ad"). If
it prints `ad`, **STOP** — that's the paid composer, wrong intent.

**2. Upload.** Verified: `agent-browser upload` works (input removed + `<video>`
appears).

```bash
agent-browser upload "input[aria-label='File upload']" "/absolute/path/to/videos/inbox/FILE.mp4"
agent-browser wait 3000
agent-browser eval "!document.querySelector('input[aria-label=\"File upload\"]')"   # true = upload started
```

**3. Wait for processing.** `agent-browser wait --fn "!!document.querySelector('video')"`
(3-min timeout → mark row `failed` "processing timeout", continue — same
exception as storyboard).

**4. Fill text fields** (verified). Readback after each.

```bash
agent-browser fill "textarea[id^=pin-draft-title]" "TITLE"
agent-browser wait 1500
agent-browser fill "div[aria-label='Tell everyone what your Pin is about']" "DESCRIPTION"
agent-browser wait 1500
agent-browser fill "textarea[id^=pin-draft-link]" "LINK"
agent-browser get value "textarea[id^=pin-draft-title]"      # must match
agent-browser get text  "div[aria-label='Tell everyone what your Pin is about']"
agent-browser get value "textarea[id^=pin-draft-link]"
```

**5. Board** (mirror storyboard; not exercised on the test account — verify on
first run). Click the board button (top-right, shows the current board), then
`find text "BOARD_NAME" click --exact`; verify the button shows the board name.

**6. Tags.** The pin-builder composer may **not** expose interest tags (the
capture found none). If there's no tag combobox, **skip tags** and note it.

**7. ALT text** (mirror storyboard; not exercised — verify on first run). Use
the "Add alt text" button to reveal the field, `fill`, and `get value`.

**8. Schedule — select "Publish at a later date"** (verified; it's a **radio**,
not the storyboard toggle).

```bash
agent-browser find text "Publish at a later date" click --exact
agent-browser wait 1500
agent-browser eval "(document.querySelector('input[id^=pin-draft-schedule-publish-later]')||{}).checked"   # true
```

**9. Date** (verified; same selector as storyboard).

```bash
agent-browser fill "input[id^=pin-draft-schedule-date-field]" "06/12/2026"
agent-browser wait 1200
agent-browser press Escape
agent-browser get value "input[id^=pin-draft-schedule-date-field]"   # must equal the date
```

**10. Time** (verified). The dropdown options are plain `<div>`s (no
`role=option`); `find role option` / `find text` no-op. Use a text-matched JS
click with scroll:

```bash
agent-browser click "input[id^=pin-draft-schedule-time-field]"
agent-browser wait 1500
agent-browser eval "(() => { const d = [...document.querySelectorAll('div')].find(e => e.children.length===0 && e.textContent.trim()==='09:00 AM'); if(!d) return 'not found'; d.scrollIntoView({block:'center'}); d.click(); return 'clicked'; })()"
agent-browser wait 1200
agent-browser get value "input[id^=pin-draft-schedule-time-field]"   # must equal the label
```

**11. Verify everything, then — only past the consent gate — click Schedule.**
Re-confirm via screenshot + readbacks that upload, title, description, link,
board, date, and time all hold the expected values (there is no "Changes
stored!" here — pin-builder doesn't autosave). Then:

```bash
agent-browser screenshot /tmp/pb-final.png      # eyeball before committing
agent-browser find text "Schedule" click --exact   # the red button — NOT exercised on the test account; verify it on first run
agent-browser wait 3000
agent-browser screenshot /tmp/pb-scheduled.png  # confirm a success state / the pin left the composer
```

This is the one composer where the tool clicks Schedule. If the post-click
screenshot does not show a clear success (scheduled confirmation / composer
reset), treat it as a failure (failure policy) — do **not** re-click blindly.
Then update the manifest and move the file (post phase step 4), wait 30–60 s,
and start the next pin.

## Verification discipline

Act → verify, **before** continuing. Every text field gets a `get value` /
`get text` readback; every click gets a state check proving the visible
result (dropdown opened, "Tagged topics (N)" incremented, `is checked`,
screenshot). A command's "✓ Done" only means the call returned — never that
the page did what you wanted.

## Failure policy

- **Fail-stop, not fail-skip.** Any step that fails verification:
  1. Save a screenshot to `.cache/failures/` (`mkdir -p .cache/failures`):
     `agent-browser screenshot .cache/failures/<file>-<step>.png`
  2. `uv run --no-project "${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py" mark "<file>" failed --error "<reason>"`
  3. **STOP the whole batch** and report. A mid-batch failure usually means
     UI drift or a session problem; continuing risks cascading damage.
- **Exception:** video processing timeout (step 3) — mark that row `failed`,
  continue with the next pin.
- `failed` rows need a human to edit the status back to `approved`; never
  retry them automatically.
- Re-runs are safe: only `approved` rows are considered; `scheduled` rows
  are never touched again.

## Agent-browser gotchas (field-tested on this page)

- **Silent fallback browser.** Any command issued without a live session
  auto-launches a fresh, logged-out browser. If a page that should be logged
  in shows the Pinterest landing page, you may be in the wrong browser —
  re-check how the session was started before blaming cookies.
- **Refs go stale.** `@eN` refs are only valid for the most recent
  `snapshot`. Re-snapshot after any click that changes the page before
  reusing refs.
- **"✓ Done" is not verification.** Clicks on dropdown options can silently
  no-op when the option is outside the dropdown's visible scroll area (board
  list, tag suggestions). Always verify the resulting state; scroll the
  option into view and retry once on failure.
- **Open dropdowns near the fold.** Scroll the trigger into view
  (`scrollintoview`) before clicking it, and keep scroll+click+verify in one
  `batch`.
- `find text` matches substrings — pass `--exact` (e.g. "Barefoot Running"
  also matches "Barefoot Running Shoes"). For options use
  `find role option click --name "..." --exact`.
- `eval` is expression-style; optional chaining (`?.`) and `??` work for
  null-safe probes.
- **Daemon wedge recovery:** repeated `✗ Failed to read: Resource
  temporarily unavailable (os error 35)` means the daemon is stuck —
  `pkill -f agent-browser-darwin`, remove
  `~/.agent-browser/default.{sock,pid,stream}`, start again.
- The page scrolls in an inner container — `window.scrollTo` does nothing;
  use `scrollintoview` / `element.scrollIntoView({block:"center"})`.
- A hidden reCAPTCHA (`g-recaptcha-response`) textarea exists on the organic
  page. Human-paced interaction only; no rapid-fire automation.
- **Symptom of tripping that defense:** re-`open`ing `pin-creation-tool`
  many times in quick succession degrades it to a non-hydrating shell — the
  `h1` still says "Create Pin" but the body is nearly empty, no `#storyboard-*`
  elements ever appear, and `screenshot` may start wedging the daemon
  (`os error 35`). It is **not** a logout. Stop reloading, wait, and let the
  session settle before retrying. (Field-tested 2026-06-13 while verifying the
  composer-detection change.)

## Field reference (organic pin-creation-tool, verified 2026-06-11)

| Field | Selector | Input method | Notes |
|---|---|---|---|
| Upload | `#storyboard-upload-input` | `agent-browser upload` | input removed from DOM = upload started; mp4 < 200 MB |
| Title | `#storyboard-selector-title` | `fill` + `get value` | plain input, no maxlength attr — enforce ≤100 yourself |
| Description | `div[contenteditable=true]` | `fill` + `get text` | Draft.js editor; `fill` works directly; enforce ≤800 |
| Link | `#WebsiteField` | `fill` + `get value` | `type=url` |
| Board | button "Choose a board Open dropdown" (snapshot ref) | scrollintoview + click → `find text <board> click --exact` | shows "All boards" + Create board; verify button shows board name |
| Tags | `#combobox-storyboard-interest-tags` | `fill` → wait ~2 s → `find role option click --name ... --exact` | suggestions are `[role=option]`; verify counter "Tagged topics (N)"; broaden query if empty |
| Schedule toggle | `#pin-draft-switch-group` (checkbox) | `check` + `is checked` | label "Publish at a later date"; Publish button becomes "Schedule" |
| Schedule date | `input[id^=pin-draft-schedule-date-field]` | `fill` MM/DD/YYYY → `press Escape` → `get value` | calendar popup; 30-day window |
| Schedule time | `input[id^=pin-draft-schedule-time-field]` | click → `find text <label> click --exact` → `get value` | typing ignored; 48 options, 30-min increments, 12-hour labels |
| AI disclosure | `input[id^=pin-draft-ai-disclosure]` | click if needed | "Mark as AI-Modified" |
| ALT text | `#storyboardAltText` | expand "More options" first → `fill` + `get value` | **not in DOM until expanded**; placeholder "Describe your Pin's visual details" |
| Comments / products toggles | `#CommentSwitch`, `#stelaSwitch` | leave untouched | under "More options" |
