# Pin creation field map (explored 2026-06-11)

## Which flow to use — CRITICAL

`https://www.pinterest.com/pin-builder/` on a business account lands in the
**Paid → "Create Pin for ad"** composer (header says "Create Pin for ad").
The organic flow the reader means lives at:

    https://www.pinterest.com/pin-creation-tool/

(Reachable via header hamburger → Create content → Organic → "Create Pin".)
All automation targets **pin-creation-tool**. Differences that matter:

| | pin-builder (ad flow) | pin-creation-tool (organic) |
|---|---|---|
| Video limit | mp4 < 2 GB | **mp4 < 200 MB** |
| CDP `DOM.setFileInputFiles` | ❌ silently ignored | ✅ **works** |
| Field ids | UUID-suffixed | **stable** (`#storyboard-*`, `#WebsiteField`) |
| Draft autosave | did not persist across navigation | ✅ "Changes stored!", draft rail, **expires in 30 days** |
| Tags vocabulary | rigid taxonomy ("Sport > Running") | friendly autocomplete ("Running Shoes", "Running For Beginners") |

## Upload (organic flow)

- Method that works: **CDP `DOM.setFileInputFiles`** on `#storyboard-upload-input`
  (use the `objectId` variant via `Runtime.evaluate` → `DOM.setFileInputFiles`).
  No native picker, no AppleScript needed.
- The input is removed from the DOM once the upload starts — that's the
  success signal; the video preview (with play button) renders when processing
  is done. Our 67 KB fixture processed in ~5 s.
- Fallback (proven in the ad flow): click the dropzone → native macOS picker →
  AppleScript: frontmost, delay 2, Cmd+Shift+G, delay 2, type folder path,
  Return, delay 4, type filename, delay 1.5 → picker confirmed the selection
  without an explicit "Open" click.
- Editor header shows "Changes stored!" / "Saving…" — autosave to a draft.

## Fields (organic flow) — all verified

| Field | Selector | Input method | Notes |
|---|---|---|---|
| Title | `#storyboard-selector-title` | click + CDP `Input.insertText` | plain input, no maxlength attr |
| Description | `div[contenteditable=true]` | click + `Input.insertText` | Draft.js editor; value verified via `textContent` |
| Link | `#WebsiteField` | click + `Input.insertText` | `type=url` |
| Board | "Choose a board" dropdown | click → search box + board list → click board name | shows "All boards" + Create board |
| Tags | `#combobox-storyboard-interest-tags` | click + `Input.insertText` → wait ~2 s → click `[role=option]` | suggestions are `[role=option]` elements with child spans (leaf-div filters find nothing); vocabulary is Pinterest's own — pick closest match; counter "Tagged topics (N)"; chip with × appears |
| Schedule toggle | `#pin-draft-switch-group` (checkbox) | click | label "Publish at a later date" |
| Schedule date | `input[id^=pin-draft-schedule-date-field]` | click → select-all (CDP keyDown 'a' + `commands:["selectAll"]`) → `insertText` "MM/DD/YYYY" | calendar popup opens; typed value accepted; Escape closes |
| Schedule time | `input[id^=pin-draft-schedule-time-field]` | click → **must pick from dropdown** (typing ignored): scrollIntoView the option div matching e.g. "09:00 AM", click it | 48 options, **30-minute increments**, 12-hour labels |
| AI disclosure | `input[id^=pin-draft-ai-disclosure]` | click if needed | "Mark as AI-Modified" + "AI-generated person" checkbox |
| ALT text | `#storyboardAltText` | expand "More options" → click + `Input.insertText` | placeholder "Describe your Pin's visual details"; verified in dry-run 2026-06-11. "More options" also holds `#CommentSwitch` and `#stelaSwitch` toggles |

No character counters surfaced; enforce title ≤100 / description ≤800 in the
generator rather than relying on the UI.

## Scheduling

- Toggle label: "Publish at a later date" (toggle in organic flow; radio in ad flow)
- Date format: `MM/DD/YYYY`, defaults to tomorrow; typed entry works
- Time: dropdown-only, 30-minute increments (`12:00 AM` … `11:30 PM`)
- **Scheduling window: 30 days** — verified in the calendar: with today
  2026-06-11, July 1–10 selectable, July 11+ disabled
- When the toggle is ON, the red **Publish button becomes "Schedule"**
- Queue cap: **not verified** (would require actually scheduling pins — out of
  bounds for this session). Help docs say 10 queued pins; assume 10 until a
  real run observes otherwise.

## Publish / confirmation

Not exercised — **user instruction: drafts only, never publish/schedule
automatically.** The workflow stops at a fully-filled draft with the schedule
toggle set; the draft autosaves ("Changes stored!"). Success criterion for
automation: all fields verified filled + "Changes stored!" + draft visible in
the "Pin drafts (N)" rail.

## Draft management

- Drafts rail (left, expandable «/»): "Pin drafts (N)", each with thumbnail,
  title, "30 days until expiration", and a "…" menu → Duplicate / Delete
  (Delete shows a "Delete your draft?" confirm dialog).
- "Create new" button starts a fresh draft (equivalent to the left-rail "+").

## Browser-harness gotchas (field-tested)

- `cdp()` takes params as **kwargs**, not a dict: `cdp("DOM.querySelector", nodeId=n, selector="...")`.
- `js()` expressions containing the keyword `return` silently evaluate to
  `None` — use expression-style arrow functions / comma operators instead.
- Screenshots are 2× device pixels; divide by 2 for `click_at_xy` CSS coords.
  Get exact targets from `getBoundingClientRect()` via `js()` instead of
  reading pixels off the image.
- The page scrolls in an inner container — `window.scrollTo` does nothing;
  use `element.scrollIntoView({block:"center"})`.
- A hidden reCAPTCHA (`g-recaptcha-response`) textarea exists on the organic
  page. Human-paced interaction only; no rapid-fire automation.

## Other observations

- macOS `say` with the default voice produced a broken 5 ms file; use an
  explicit voice: `say -v Samantha -o out.aiff "..."`.
- Board dropdown remembers the last-used board in the ad flow (auto-selected
  "Barefoot Running Shoes" once).
- Organic flow also offers "Save from URL" in the empty state, and a video
  cover-image picker (`#video-cover-upload-input` in ad flow, "Edit cover" in
  organic).
