---
name: pin-scheduler
description: Prep and schedule Pinterest video pins via the organic pin-creation-tool. Use when asked to "prep pins", "schedule pins", "post to Pinterest", or process a folder of videos into scheduled pin drafts.
---

# pin-scheduler

Batch-prepare Pinterest video pins in the user's logged-in Chrome via
browser-harness. Two phases: **prep** (transcribe + generate copy into
`manifest.csv` for review) and **post** (fill the pin form, set the schedule,
leave it as a draft). Pinterest's own scheduler does the timed publishing.

All commands run from the repo root. `manifest.csv` is the single source of
truth; never schedule anything that isn't an `approved` row in it.

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

## Setup (once)

```bash
cp config.example.yaml config.yaml   # then edit: link, alt_text, tags, board, window
mkdir -p videos/inbox videos/scheduled
```


- Chrome must be running and logged into the target Pinterest account.
- `browser-harness` must be on $PATH (the daemon auto-starts).
- `uv` and `ffmpeg` installed (whisper transcription needs ffmpeg).

## Prep phase ("prep pins")

1. List videos in `videos/inbox/` whose basename is not already a `filename`
   in `manifest.csv`.
2. For each new video:
   - Transcribe: `scripts/transcribe.sh videos/inbox/<file>` (cached in
     `.cache/transcripts/`; prints the transcript).
   - Generate, in-session, from filename + transcript:
     - **Title** ≤100 chars, leading keywords first.
     - **Description** ≤800 chars, natural sentences, keyword-rich, no
       hashtag spam.
     - Enforce the limits yourself — the UI has no counters.
   - Append: `uv run python scripts/manifest.py add "<file>" "<title>" "<description>"`
3. Tell the user to review `manifest.csv` and approve rows. On "approve all":
   for **each** row with status `draft`, run one invocation per row —
   `uv run python scripts/manifest.py mark "<filename>" approved` — there is
   no bulk subcommand.

## Post phase ("schedule pins")

1. Capacity check: read `queue_cap` from `config.yaml`, then run
   `uv run python scripts/manifest.py capacity --cap <queue_cap>` (substitute
   the value; default is 10). If 0: stop cleanly, report "queue full, N
   approved pins remaining — run again later".
2. Take `N = min(capacity, number of approved rows)`.
3. Get slots: `uv run python scripts/slots.py --count N` — prints one naive
   local ISO datetime per line (e.g. `2026-06-12T09:00`).
4. For each approved row + slot, run the per-pin playbook below. Only after
   the final verification screenshot:
   ```bash
   uv run python scripts/manifest.py mark "<file>" scheduled --time "<slot-iso>"
   mv "videos/inbox/<file>" "videos/scheduled/<file>"
   ```
   `mark <file> scheduled` **requires** `--time` (it raises without it). Pass
   the slot exactly as slots.py printed it — naive local ISO, no timezone.
5. **Pacing:** a few seconds between actions, 30–60 s between pins. The page
   has a hidden reCAPTCHA — human-paced batch sessions only.
6. Report: which pins were prepared with which slots, any skipped tags, and
   remind the user to click **Schedule** on each draft in the Pin drafts rail
   (drafts expire in 30 days).

## Per-pin playbook

Slot conversion first: from the ISO slot, date is `MM/DD/YYYY`
(`%m/%d/%Y`), time label is zero-padded 12-hour (`%I:%M %p`, e.g.
`2026-06-12T09:00` → `06/12/2026` + `09:00 AM`). The time picker only has
30-minute increments, which the slot generator already respects.

**1. Open the organic composer.** The target is
`https://www.pinterest.com/pin-creation-tool/`. Never use `/pin-builder/` —
on business accounts that is the **ad** composer (different limits, unstable
ids, `setFileInputFiles` silently ignored).

```bash
browser-harness -c '
new_tab("https://www.pinterest.com/pin-creation-tool/")
wait_for_load()
capture_screenshot()
'
```

Verify the screenshot shows the editor with the upload dropzone. If it shows
a login wall: **STOP the batch and ask the user** — never type credentials.

**2. Upload via CDP** (objectId variant on `#storyboard-upload-input`).
This is the proven primary; no native picker needed.

```bash
browser-harness -c '
r = cdp("Runtime.evaluate", expression="document.querySelector(\"#storyboard-upload-input\")")
cdp("DOM.setFileInputFiles",
    files=["/absolute/path/to/videos/inbox/FILE.mp4"],
    objectId=r["result"]["objectId"])
print(js("document.querySelector(\"#storyboard-upload-input\") === null"))
'
```

The input being **removed from the DOM** (`True` above) = upload started.
Video must be mp4 < 200 MB in this flow. Fallback only if CDP fails: click
the dropzone, then drive the native macOS picker via AppleScript (activate,
delay 2, Cmd+Shift+G, delay 2, type folder path, Return, delay 4, type
filename, delay 1.5).

**3. Wait for processing.** Poll `capture_screenshot()` every ~10 s until the
video preview (with play button) renders. Timeout: **3 minutes** → mark this
row `failed` with reason "processing timeout" and continue with the next pin
(the one exception to fail-stop).

**4. Fill the text fields** — coordinate click + `Input.insertText`. No
clipboard. Coordinates come from `getBoundingClientRect()` via `js()`, never
from screenshot pixels.

```bash
browser-harness -c '
import json

def fill(sel, text):
    q = "document.querySelector(" + json.dumps(sel) + ")"
    js(q + ".scrollIntoView({block: \"center\"})")
    r = json.loads(js("JSON.stringify(" + q + ".getBoundingClientRect())"))
    click_at_xy(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)
    cdp("Input.insertText", text=text)

fill("#storyboard-selector-title", TITLE)               # from manifest row
fill("div[contenteditable=true]", DESCRIPTION)          # Draft.js editor
fill("#WebsiteField", LINK)                             # from config.yaml

# Readback verification — required before moving on:
print(js("document.querySelector(\"#storyboard-selector-title\").value"))
print(js("document.querySelector(\"div[contenteditable=true]\").textContent"))
print(js("document.querySelector(\"#WebsiteField\").value"))
'
```

Each printed value must match what you sent (description verifies via
`textContent`). Mismatch → failure policy.

**5. Board.** Click the "Choose a board" dropdown (rect via `js()`), then
click the configured board name in the list (it has a search box if the list
is long). Screenshot-verify the dropdown button now shows the board name.

**6. Tags** — one at a time, from `config.yaml`:

- Click `#combobox-storyboard-interest-tags`; if it holds leftover text,
  select-all first (`Input.dispatchKeyEvent` keyDown `a` with
  `commands=["selectAll"]`), then `Input.insertText` the tag.
- Wait ~2 s. Suggestions are **`[role=option]` elements** (they contain
  child spans — do NOT filter for leaf divs; that finds nothing):
  ```python
  js("JSON.stringify([...document.querySelectorAll(\"[role=option]\")].map(e => e.textContent.trim()))")
  ```
- Pinterest's vocabulary rarely matches config tags verbatim — pick the
  closest option (e.g. config "barefoot running" → "Trail Running",
  "running shoes" → "Running Shoes"). Click it via `getBoundingClientRect`
  on the matching `[role=option]` element.
- Verify the "Tagged topics (N)" counter incremented:
  ```python
  js("(document.body.innerText.match(/Tagged topics \\((\\d+)\\)/) || [])[1]")
  ```
- **Empty options list → skip the tag** and note it in the final report. A
  skipped tag is not a batch failure.

**7. ALT text.** Click the "More options" expander (bottom of the form),
then fill `#storyboardAltText` ("Describe your Pin's visual details") with
`alt_text` from config — same click + `Input.insertText` + readback pattern
as step 4. ("More options" also holds comment/product toggles — leave them.)

**8. Schedule toggle.** Click `#pin-draft-switch-group` ("Publish at a later
date"), verify `checked` is true via `js()`. The red Publish button now reads
**Schedule** — that is the button you must NOT click.

**9. Date field** (`input[id^=pin-draft-schedule-date-field]`):

```bash
browser-harness -c '
import json
q = "document.querySelector(\"input[id^=pin-draft-schedule-date-field]\")"
js(q + ".scrollIntoView({block: \"center\"})")
r = json.loads(js("JSON.stringify(" + q + ".getBoundingClientRect())"))
click_at_xy(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)
cdp("Input.dispatchKeyEvent", type="keyDown", key="a", commands=["selectAll"])
cdp("Input.insertText", text="06/12/2026")              # MM/DD/YYYY from slot
cdp("Input.dispatchKeyEvent", type="keyDown", key="Escape")  # close calendar
cdp("Input.dispatchKeyEvent", type="keyUp", key="Escape")
print(js(q + ".value"))                                  # must equal the date
'
```

Scheduling window is 30 days out, max — slots.py never exceeds that in
normal use, but a stale manifest could; a disabled calendar date means the
slot is out of range.

**10. Time field** (`input[id^=pin-draft-schedule-time-field]`): typing is
ignored — **must pick from the dropdown** (48 options, 30-minute increments,
12-hour labels). The dropdown scrolls in an inner container, so use
`scrollIntoView` on the option, not window scrolling.

```bash
browser-harness -c '
import json
SLOT_LABEL = "09:00 AM"                                  # %I:%M %p from slot
q = "document.querySelector(\"input[id^=pin-draft-schedule-time-field]\")"
js(q + ".scrollIntoView({block: \"center\"})")
r = json.loads(js("JSON.stringify(" + q + ".getBoundingClientRect())"))
click_at_xy(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)   # opens dropdown
opt = ("[...document.querySelectorAll(\"div\")].find(d => "
       "d.childElementCount === 0 && d.textContent.trim() === "
       + json.dumps(SLOT_LABEL) + ")")
js(opt + ".scrollIntoView({block: \"center\"})")
r = json.loads(js("JSON.stringify(" + opt + ".getBoundingClientRect())"))
click_at_xy(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)
print(js(q + ".value"))                                  # must equal SLOT_LABEL
'
```

**11. Final verification, then STOP.** Take a full screenshot and confirm:
title, description, link, board, tags, toggle on, date, and time all show
the expected values; the header shows **"Changes stored!"**; the left rail
shows the draft under **"Pin drafts (N)"**. Do **not** click
Publish/Schedule (see drafts-only policy). Then update the manifest and move
the file (post phase step 4), wait 30–60 s, and start the next pin with
"Create new" or a fresh `new_tab`.

## Verification discipline

Act → screenshot → verify, **before** continuing. Every text field gets a
`js()` readback; every click gets a screenshot confirming the visible result
(dropdown opened, chip appeared, toggle flipped). Never assume an action
worked because the call returned.

## Failure policy

- **Fail-stop, not fail-skip.** Any step that fails verification:
  1. Save a screenshot to `.cache/failures/` (`mkdir -p .cache/failures`),
     named `<file>-<step>.png`.
  2. `uv run python scripts/manifest.py mark "<file>" failed --error "<reason>"`
  3. **STOP the whole batch** and report. A mid-batch failure usually means
     UI drift or a session problem; continuing risks cascading damage.
- **Exception:** video processing timeout (step 3) — mark that row `failed`,
  continue with the next pin.
- `failed` rows need a human to edit the status back to `approved`; never
  retry them automatically.
- Re-runs are safe: only `approved` rows are considered; `scheduled` rows
  are never touched again.

## Browser-harness gotchas (field-tested on this page)

- `cdp()` takes params as **kwargs**, not a dict:
  `cdp("DOM.querySelector", nodeId=n, selector="...")`.
- `js()` expressions containing the keyword `return` silently evaluate to
  `None` — use expression-style arrow functions / comma operators instead.
- Screenshots are 2x device pixels; divide by 2 for `click_at_xy` CSS
  coords. Better: get exact targets from `getBoundingClientRect()` via
  `js()` instead of reading pixels off the image.
- The page scrolls in an inner container — `window.scrollTo` does nothing;
  use `element.scrollIntoView({block:"center"})`.
- A hidden reCAPTCHA (`g-recaptcha-response`) textarea exists on the organic
  page. Human-paced interaction only; no rapid-fire automation.

## Field reference (organic pin-creation-tool, verified 2026-06-11)

| Field | Selector | Input method | Notes |
|---|---|---|---|
| Upload | `#storyboard-upload-input` | CDP `DOM.setFileInputFiles` (objectId variant) | input removed from DOM = upload started; mp4 < 200 MB |
| Title | `#storyboard-selector-title` | click + `Input.insertText` | plain input, no maxlength attr — enforce ≤100 yourself |
| Description | `div[contenteditable=true]` | click + `Input.insertText` | Draft.js editor; verify via `textContent`; enforce ≤800 |
| Link | `#WebsiteField` | click + `Input.insertText` | `type=url` |
| Board | "Choose a board" dropdown | click → board list (has search box) → click board name | shows "All boards" + Create board |
| Tags | `#combobox-storyboard-interest-tags` | click + `insertText` → wait ~2 s → click `[role=option]` | suggestions are `[role=option]` (not leaf divs); counter "Tagged topics (N)"; chip with × appears |
| Schedule toggle | `#pin-draft-switch-group` (checkbox) | click | label "Publish at a later date"; Publish button becomes "Schedule" |
| Schedule date | `input[id^=pin-draft-schedule-date-field]` | click → select-all (keyDown `a` + `commands=["selectAll"]`) → `insertText` MM/DD/YYYY → Escape | calendar popup; 30-day window |
| Schedule time | `input[id^=pin-draft-schedule-time-field]` | click → pick from dropdown (typing ignored) | 48 options, 30-min increments, 12-hour labels |
| AI disclosure | `input[id^=pin-draft-ai-disclosure]` | click if needed | "Mark as AI-Modified" |
| ALT text | `#storyboardAltText` | expand "More options" → click + `Input.insertText` | placeholder "Describe your Pin's visual details"; verified working |
| Comments / products toggles | `#CommentSwitch`, `#stelaSwitch` | leave untouched | under "More options" |
