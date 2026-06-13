# Standard Pin composer (`/pin-builder/`) — field map + the draft problem

**Status: field map verified end-to-end on 2026-06-14** (against the
`/pin-builder/` composer on this repo's business account — the "Create Pin for
ad" variant). **One blocking caveat** for the drafts-only policy, see below.

## Why this exists

`pinterest.com/pin-creation-tool/` and `pinterest.com/idea-pin-builder/` are
the **same** organic *storyboard* editor (`#storyboard-*` field map, see
`pin-builder-field-map.md`); the URL an account lands on is just a cohort
redirect. `/pin-builder/` is a **different composer**:

- On accounts **with an ad account** (this repo's account), it renders as the
  **"Create Pin for ad"** flow.
- On accounts **without ad access** (a customer, Fred, schedules pins here
  daily and confirmed it is *not* an ad flow for him), the same URL is the
  **standard organic Pin composer** — same React components, the heading drops
  "for ad".

Field ids are `pin-draft-*-<UUID>` — the **UUID suffix differs per session and
per account**, so all selectors below use the **`[id^=pin-draft-*]` prefix**
form, which is stable across both variants. (Verified: the same prefixes appear
across reloads; they match the storyboard flow's `pin-draft-schedule-*` too.)

## Field map — verified

| Field | Selector | Method | Verified |
|---|---|---|---|
| Upload | `input[aria-label="File upload"]` (accepts `video/mp4,…`) | `agent-browser upload` | ✅ input removed from DOM + `<video>` appears (same signal as storyboard). Contradicts the old "setInputFiles silently ignored" note — that no longer holds. |
| Title | `textarea[id^=pin-draft-title]` (placeholder "Add your title") | `fill` + `get value` | ✅ |
| Description | `div[aria-label="Tell everyone what your Pin is about"]` (contenteditable combobox) | `fill` + `get text` | ✅ |
| Link | `textarea[id^=pin-draft-link]` (placeholder "Add a destination link") | `fill` + `get value` | ✅ |
| Board | board button top-right (shows current board) | click → pick | ⚠️ not exercised (would change the account's board) — mirror the storyboard board step |
| ALT text | "Add alt text" button → field | click + `fill` | ⚠️ not exercised |
| Schedule | radio — click label **"Publish at a later date"** (or `input[id^=pin-draft-schedule-publish-later]`) | `find text "Publish at a later date" click --exact` | ✅ a **radio**, not the storyboard checkbox toggle; reveals date+time fields |
| Date | `input[id^=pin-draft-schedule-date-field]` | `fill` MM/DD/YYYY → `press Escape` → `get value` | ✅ identical to storyboard |
| Time | `input[id^=pin-draft-schedule-time-field]` | click to open, then pick (see note) | ✅ |
| Publish/Schedule | red button (becomes "Schedule" when later-date chosen) | — | see "draft problem" |

### Time picker differs from storyboard

The pin-builder time dropdown options are **plain `<div>`s** (obfuscated
classes, no `id`, **no `role=option`**) — so `find role option` and even
`find text … click` no-op (the target sits outside the dropdown's scroll
viewport). The reliable method is a text-matched JS click with scroll:

```bash
agent-browser click "input[id^=pin-draft-schedule-time-field]"
agent-browser wait 1500
agent-browser eval "(() => { const d = [...document.querySelectorAll('div')].find(e => e.children.length===0 && e.textContent.trim()==='09:00 AM'); if(!d) return 'not found'; d.scrollIntoView({block:'center'}); d.click(); return 'clicked'; })()"
agent-browser wait 1200
agent-browser get value "input[id^=pin-draft-schedule-time-field]"   # must equal the label
```

Labels are 30-minute increments, 12-hour (`12:00 AM` … `11:30 PM`) — same as
the slot generator already produces.

## The draft problem — BLOCKING for the drafts-only policy

**Pin-builder has no draft state.** Verified 2026-06-14: with all fields +
video + schedule filled, then navigating away and back, the form came back
**empty** (`title` empty, no video). There is:

- **no** "Changes stored!" autosave indicator,
- **no** "Pin drafts (N)" rail,
- **no** "Save as draft" action anywhere in the composer or its menus.

The **only** way to commit a pin-builder pin is to click the red
**Schedule/Publish** button. This is the opposite of the storyboard flow, whose
entire safety model is "fill → Pinterest autosaves a draft (30-day expiry) →
the user clicks Schedule later, on their own time."

**Consequences for this skill (the drafts-only policy is non-negotiable):**

- The storyboard terminal state ("filled draft + Changes stored! + draft in
  rail; user clicks Schedule whenever") **cannot be reproduced on pin-builder.**
- Two honest options, both require an explicit decision (do not pick silently):
  1. **Fill-and-stop (interactive):** the tool fills every field and STOPS,
     leaving the composer on screen for the user to review and click Schedule
     **in that session**. Faithful to "the tool never publishes," but the work
     is **lost if the user doesn't click Schedule before navigating** — there
     is no draft to return to, so this can't be a batch-prepare-now /
     review-later flow.
  2. **auto_schedule (the tool clicks Schedule):** only with `auto_schedule:
     true` **and** explicit in-session consent (the existing flag). The tool
     commits the schedule itself. This is real publishing-to-schedule — never
     the default, never inferred.

This is why pin-builder support is gated on a policy decision, not just a field
map. The field map is done; the terminal step is a product/safety call.

## Finalization checklist (once the terminal-step policy is decided)

1. ✅ Field map verified (above).
2. Decide terminal step: fill-and-stop vs auto_schedule (see "draft problem").
3. Exercise the **board** and **ALT** steps once (mirror the storyboard steps;
   they were left untouched here to avoid changing the test account's board).
4. Confirm on a **standard (non-ad)** account that the heading is "Create Pin"
   (not "for ad") and the `[id^=pin-draft-*]` selectors match — run
   `scripts/inspect-composer.sh` there; expected `composer: "pin-builder…"`.
5. Write the pin-builder per-pin steps into `SKILL.md` under composer-adaptive
   routing, reusing the storyboard date logic and the time-picker note above.
