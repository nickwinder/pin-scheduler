# Pin Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Claude Code skill that preps video pins (whisper transcription → Claude-generated titles/descriptions → reviewable CSV) and batch-schedules them through Pinterest's pin-builder using browser-harness and Pinterest's native "Publish at a later date" scheduler.

**Architecture:** Claude orchestrates two conversational phases (`prep`, `post`) defined in `SKILL.md`. State lives in `manifest.csv` only; fixed fields live in `config.yaml`. Two small Python modules (`manifest.py`, `slots.py`) handle state transitions and slot computation; everything browser-facing is a documented browser-harness playbook, not code.

**Tech Stack:** Python 3.11+ via `uv` (pyyaml, pytest), `uvx openai-whisper` for transcription, `ffmpeg`/`say` for test fixtures, browser-harness for Chrome automation.

**Spec:** `docs/superpowers/specs/2026-06-11-pin-scheduler-design.md`

---

### Task 1: Pin-builder exploration session

⚠️ **Requires the user present, logged in to Pinterest in Chrome.** This task de-risks the whole project (spec: "implementation step #1"). Do it inline with the user, not via subagent.

**Files:**
- Create: `docs/exploration/pin-builder-field-map.md`
- Create: `.cache/fixtures/sample.mp4` (untracked test fixture)

- [ ] **Step 1: Create a test video fixture**

```bash
mkdir -p .cache/fixtures
say -o .cache/fixtures/sample.aiff "This is a barefoot running shoe review covering comfort, ground feel, and durability on rocky trails."
ffmpeg -y -f lavfi -i "color=c=teal:s=720x1280:d=8" -i .cache/fixtures/sample.aiff \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest .cache/fixtures/sample.mp4
```

Expected: `.cache/fixtures/sample.mp4` exists, ~8 s, 720×1280 (9:16).

- [ ] **Step 2: Open pin-builder and confirm session**

```bash
browser-harness -c '
new_tab("https://www.pinterest.com/pin-builder/")
wait_for_load()
print(page_info())
capture_screenshot()
'
```

Expected: pin-builder composer visible, logged in. If redirected to login: stop, ask the user to log in.

- [ ] **Step 3: Test the upload method (primary: CDP file input)**

First read `interaction-skills/uploads.md` in the browser-harness repo. Then locate the file input and set it directly:

```bash
browser-harness -c '
print(js("JSON.stringify([...document.querySelectorAll(\"input[type=file]\")].map(e => ({id: e.id, name: e.name, accept: e.accept, hidden: e.hidden})))"))
'
```

Use the uploads.md recipe (CDP `DOM.setFileInputFiles`) to attach `.cache/fixtures/sample.mp4` to that input. Screenshot to verify Pinterest starts processing the video. If React rejects it (no preview appears), fall back to clicking the upload area + the AppleScript file-picker flow from the Instagram project, and record which method worked.

- [ ] **Step 4: Map every field while the test pin is open**

With the video uploaded, walk the form and record for each field — how to focus it, whether typing or clipboard-paste sticks (check by clicking elsewhere then screenshotting), and any character limits shown in the UI:

1. Title (expected limit 100)
2. Description (expected limit 800)
3. ALT text (find the toggle/button that reveals it; note its label)
4. Destination link
5. Tagged topics (type a tag, screenshot the autocomplete, click a suggestion, verify the chip appears; note exact behavior)
6. Board selector (open dropdown, note how options render)
7. "Publish at a later date" toggle — note the date picker format and **the time picker increments** (5 min? 15? 30?)

- [ ] **Step 5: Verify the queue cap empirically**

Check Pinterest's UI for the scheduled-pins view (profile → pins → scheduled, or the message shown when scheduling). Record what the UI says the cap is — help docs say 10 queued pins; some sources say 100. If nothing is displayed, note "cap not displayed; assume 10 until hit" — do NOT schedule 11 test pins to find out.

- [ ] **Step 6: Abandon the test pin**

Close the tab WITHOUT publishing (discard the draft if prompted). Screenshot to confirm nothing was posted.

- [ ] **Step 7: Write the field map doc**

Create `docs/exploration/pin-builder-field-map.md` with this structure, filled with findings:

```markdown
# Pin-builder field map (explored 2026-06-11)

## Upload
- Method that worked: [CDP setFileInputFiles | AppleScript picker]
- File input selector: [...]
- Processing indicator: [what the UI shows while transcoding; what "done" looks like]

## Fields
| Field | How to focus | Input method | Limit | Notes |
|---|---|---|---|---|
| Title | ... | paste/type | 100 | ... |
| Description | ... | ... | 800 | ... |
| ALT text | via "..." toggle | ... | ... | ... |
| Link | ... | ... | — | ... |
| Tags | ... | type + click suggestion | max N tags | autocomplete quirks |
| Board | ... | ... | — | ... |

## Scheduling
- Toggle label: [...]
- Date format: [...]
- Time increments: [...] minutes
- Minimum lead time enforced by Pinterest: [...]
- Queue cap observed: [...]

## Publish confirmation
- What success looks like: [toast text / redirect]
```

- [ ] **Step 8: Commit**

```bash
git add docs/exploration/pin-builder-field-map.md
git commit -m "docs: pin-builder exploration field map"
```

---

### Task 2: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `config.example.yaml`
- Modify: `.gitignore`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "pin-scheduler"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6"]

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
pythonpath = ["scripts"]
testpaths = ["tests"]
```

- [ ] **Step 2: Write `config.example.yaml`**

```yaml
# Copy to config.yaml and fill in your values. config.yaml is gitignored.
link: https://www.example.com          # destination URL for every pin
alt_text: "Describe what is visible in the video"
tags:                                  # tagged topics, same for every pin
  - barefoot running
  - minimalist shoes
board: "My Board"
window:
  start: "08:00"                       # local time, first slot of the day
  end: "20:00"                         # last slot of the day (inclusive)
interval_minutes: 60                   # spacing between pins (30 or 60)
margin_minutes: 20                     # never schedule closer than this to now
queue_cap: 10                          # Pinterest max queued pins (see field map doc)
```

- [ ] **Step 3: Extend `.gitignore`**

Append:

```
.cache/
.venv/
__pycache__/
videos/
config.yaml
manifest.csv
```

- [ ] **Step 4: Verify uv resolves**

Run: `uv run python -c "import yaml; print('ok')"`
Expected: `ok` (uv creates `.venv` and `uv.lock`).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml config.example.yaml .gitignore uv.lock
git commit -m "chore: scaffold uv project, example config, gitignore"
```

---

### Task 3: `manifest.py` — state transitions (TDD)

**Files:**
- Create: `scripts/manifest.py`
- Test: `tests/test_manifest.py`

Manifest columns: `filename, title, description, status, scheduled_time, error`.
Statuses: `draft → approved → scheduled`, plus `failed`. `scheduled_time` is a local ISO datetime like `2026-06-12T09:00`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_manifest.py
from datetime import datetime

import pytest

from manifest import append_row, mark, read_rows, remaining_capacity


def test_read_missing_file_returns_empty(tmp_path):
    assert read_rows(tmp_path / "manifest.csv") == []


def test_append_creates_draft_row(tmp_path):
    path = tmp_path / "manifest.csv"
    append_row(path, "a.mp4", "Title A", "Desc A")
    rows = read_rows(path)
    assert rows == [{
        "filename": "a.mp4", "title": "Title A", "description": "Desc A",
        "status": "draft", "scheduled_time": "", "error": "",
    }]


def test_mark_updates_matching_row(tmp_path):
    path = tmp_path / "manifest.csv"
    append_row(path, "a.mp4", "T", "D")
    append_row(path, "b.mp4", "T2", "D2")
    mark(path, "b.mp4", "scheduled", scheduled_time="2026-06-12T09:00")
    rows = read_rows(path)
    assert rows[0]["status"] == "draft"
    assert rows[1]["status"] == "scheduled"
    assert rows[1]["scheduled_time"] == "2026-06-12T09:00"


def test_mark_unknown_filename_raises(tmp_path):
    path = tmp_path / "manifest.csv"
    append_row(path, "a.mp4", "T", "D")
    with pytest.raises(KeyError):
        mark(path, "missing.mp4", "scheduled")


def test_capacity_counts_only_future_scheduled():
    now = datetime(2026, 6, 12, 12, 0)
    rows = [
        {"status": "scheduled", "scheduled_time": "2026-06-12T10:00"},  # already published
        {"status": "scheduled", "scheduled_time": "2026-06-12T14:00"},  # still queued
        {"status": "approved", "scheduled_time": ""},
        {"status": "draft", "scheduled_time": ""},
    ]
    assert remaining_capacity(rows, now=now, cap=10) == 9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manifest'`

- [ ] **Step 3: Implement `scripts/manifest.py`**

```python
"""Read and update manifest.csv — the single source of truth for pin state.

CLI:
    uv run python scripts/manifest.py add <filename> <title> <description>
    uv run python scripts/manifest.py mark <filename> <status> [--time ISO] [--error MSG]
    uv run python scripts/manifest.py capacity
"""
import argparse
import csv
from datetime import datetime
from pathlib import Path

FIELDS = ["filename", "title", "description", "status", "scheduled_time", "error"]
STATUSES = ["draft", "approved", "scheduled", "failed"]
QUEUE_CAP = 10


def read_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def append_row(path, filename, title, description):
    rows = read_rows(path)
    rows.append({
        "filename": filename, "title": title, "description": description,
        "status": "draft", "scheduled_time": "", "error": "",
    })
    write_rows(path, rows)


def mark(path, filename, status, scheduled_time="", error=""):
    rows = read_rows(path)
    for row in rows:
        if row["filename"] == filename:
            row["status"] = status
            row["scheduled_time"] = scheduled_time
            row["error"] = error
            write_rows(path, rows)
            return
    raise KeyError(f"{filename} not in manifest")


def remaining_capacity(rows, now, cap=QUEUE_CAP):
    queued = [
        r for r in rows
        if r["status"] == "scheduled"
        and r["scheduled_time"]
        and datetime.fromisoformat(r["scheduled_time"]) > now
    ]
    return cap - len(queued)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="manifest.csv")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add")
    p_add.add_argument("filename")
    p_add.add_argument("title")
    p_add.add_argument("description")
    p_mark = sub.add_parser("mark")
    p_mark.add_argument("filename")
    p_mark.add_argument("status", choices=STATUSES)
    p_mark.add_argument("--time", default="")
    p_mark.add_argument("--error", default="")
    sub.add_parser("capacity")
    args = parser.parse_args()

    if args.cmd == "add":
        append_row(args.manifest, args.filename, args.title, args.description)
    elif args.cmd == "mark":
        mark(args.manifest, args.filename, args.status, args.time, args.error)
    elif args.cmd == "capacity":
        print(remaining_capacity(read_rows(args.manifest), now=datetime.now()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: 5 passed.

- [ ] **Step 5: Smoke the CLI**

```bash
uv run python scripts/manifest.py --manifest /tmp/m.csv add a.mp4 "T" "D" && cat /tmp/m.csv && rm /tmp/m.csv
```

Expected: CSV with header + one draft row.

- [ ] **Step 6: Commit**

```bash
git add scripts/manifest.py tests/test_manifest.py
git commit -m "feat: manifest state module with CLI"
```

---

### Task 4: `slots.py` — slot computation (TDD)

**Files:**
- Create: `scripts/slots.py`
- Test: `tests/test_slots.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slots.py
from datetime import datetime, time, timedelta

from slots import next_slots

WINDOW = dict(
    window_start=time(8, 0),
    window_end=time(20, 0),
    interval=timedelta(minutes=60),
)


def test_first_slot_respects_margin():
    now = datetime(2026, 6, 12, 8, 50)
    slots = next_slots(**WINDOW, taken=set(), now=now, count=1)
    # earliest allowed is 9:10, so 9:00 is skipped
    assert slots == [datetime(2026, 6, 12, 10, 0)]


def test_skips_taken_slots():
    now = datetime(2026, 6, 12, 7, 0)
    taken = {datetime(2026, 6, 12, 8, 0)}
    slots = next_slots(**WINDOW, taken=taken, now=now, count=2)
    assert slots == [datetime(2026, 6, 12, 9, 0), datetime(2026, 6, 12, 10, 0)]


def test_window_end_is_inclusive():
    now = datetime(2026, 6, 12, 19, 30)
    slots = next_slots(**WINDOW, taken=set(), now=now, count=1)
    assert slots == [datetime(2026, 6, 12, 20, 0)]


def test_rolls_over_to_next_day():
    now = datetime(2026, 6, 12, 19, 45)
    slots = next_slots(**WINDOW, taken=set(), now=now, count=2)
    assert slots == [datetime(2026, 6, 13, 8, 0), datetime(2026, 6, 13, 9, 0)]


def test_thirty_minute_interval():
    now = datetime(2026, 6, 12, 7, 0)
    slots = next_slots(
        window_start=time(8, 0), window_end=time(20, 0),
        interval=timedelta(minutes=30), taken=set(), now=now, count=3,
    )
    assert slots == [
        datetime(2026, 6, 12, 8, 0),
        datetime(2026, 6, 12, 8, 30),
        datetime(2026, 6, 12, 9, 0),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slots.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'slots'`

- [ ] **Step 3: Implement `scripts/slots.py`**

```python
"""Compute the next free posting slots from config.yaml and manifest.csv.

CLI:
    uv run python scripts/slots.py --count 5
Prints one local ISO datetime per line.
"""
import argparse
from datetime import datetime, time, timedelta

import yaml

from manifest import read_rows


def next_slots(*, window_start, window_end, interval, taken, now, count,
               margin=timedelta(minutes=20)):
    earliest = now + margin
    slots = []
    day = now.date()
    while len(slots) < count:
        candidate = datetime.combine(day, window_start)
        day_end = datetime.combine(day, window_end)
        while candidate <= day_end and len(slots) < count:
            if candidate >= earliest and candidate not in taken:
                slots.append(candidate)
            candidate += interval
        day += timedelta(days=1)
    return slots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--manifest", default="manifest.csv")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    taken = {
        datetime.fromisoformat(r["scheduled_time"])
        for r in read_rows(args.manifest)
        if r["status"] == "scheduled" and r["scheduled_time"]
    }
    slots = next_slots(
        window_start=time.fromisoformat(cfg["window"]["start"]),
        window_end=time.fromisoformat(cfg["window"]["end"]),
        interval=timedelta(minutes=cfg["interval_minutes"]),
        taken=taken,
        now=datetime.now(),
        count=args.count,
        margin=timedelta(minutes=cfg.get("margin_minutes", 20)),
    )
    for slot in slots:
        print(slot.isoformat(timespec="minutes"))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all manifest + slots tests pass (10 total).

- [ ] **Step 5: Commit**

```bash
git add scripts/slots.py tests/test_slots.py
git commit -m "feat: free-slot computation with window rollover"
```

---

### Task 5: `transcribe.sh` — whisper wrapper

**Files:**
- Create: `scripts/transcribe.sh`

- [ ] **Step 1: Write `scripts/transcribe.sh`**

```bash
#!/usr/bin/env bash
# Transcribe a video's audio to text. Caches results in .cache/transcripts/.
# Usage: scripts/transcribe.sh <video-file>   (prints transcript to stdout)
set -euo pipefail

video="$1"
out_dir=".cache/transcripts"
base="$(basename "${video%.*}")"
txt="$out_dir/$base.txt"

mkdir -p "$out_dir"
if [[ ! -f "$txt" ]]; then
  uvx --python 3.12 --from openai-whisper whisper "$video" \
    --model base --output_format txt --output_dir "$out_dir" --fp16 False >/dev/null
fi
cat "$txt"
```

Then: `chmod +x scripts/transcribe.sh`

- [ ] **Step 2: Smoke test against the fixture**

(Reuses `.cache/fixtures/sample.mp4` from Task 1; recreate with the Task 1 Step 1 commands if missing.)

Run: `scripts/transcribe.sh .cache/fixtures/sample.mp4`
Expected: prints a transcript containing "barefoot running shoe review". First run downloads torch + the base model (~minutes); second run is instant (cache hit).

- [ ] **Step 3: Commit**

```bash
git add scripts/transcribe.sh
git commit -m "feat: whisper transcription wrapper with cache"
```

---

### Task 6: `SKILL.md`, `README.md`, `CLAUDE.md`

**Files:**
- Create: `SKILL.md`
- Create: `README.md`
- Create: `CLAUDE.md`
- Reference: `docs/exploration/pin-builder-field-map.md` (from Task 1)

- [ ] **Step 1: Write `SKILL.md`**

Write the following, then replace the `## Field map` section body by transcribing the verified values from `docs/exploration/pin-builder-field-map.md` (upload method, focus targets, limits, picker increments, confirmation text):

````markdown
---
name: pin-scheduler
description: Prep and schedule Pinterest video pins via pin-builder. Use when asked to "prep pins", "schedule pins", "post to Pinterest", or process a folder of videos into scheduled pins.
---

# pin-scheduler

Two phases. State lives in `manifest.csv`; fixed fields in `config.yaml`. Never touch rows with status `scheduled`.

## Setup (once)

1. `cp config.example.yaml config.yaml` and fill in real values.
2. `mkdir -p videos/inbox videos/scheduled`
3. Chrome logged in to the Pinterest account. browser-harness available.

## Prep phase ("prep pins")

1. List videos in `videos/inbox/` not present in `manifest.csv` (compare filename column: `uv run python -c` or read the CSV directly).
2. For each new video:
   a. Transcribe: `scripts/transcribe.sh videos/inbox/<file>`
   b. Generate from filename + transcript: an SEO title (≤100 chars, leading keywords) and description (≤800 chars, keyword-rich, natural sentences, no hashtag spam).
   c. `uv run python scripts/manifest.py add "<file>" "<title>" "<description>"`
3. Tell the user: "N drafts added to manifest.csv — review/edit, then say 'approve all' or flip statuses to approved yourself."
4. On "approve all": `uv run python scripts/manifest.py mark "<file>" approved` for each draft row.

## Post phase ("schedule pins")

1. Capacity check: `uv run python scripts/manifest.py capacity` → if 0, report "queue full, run again after some pins publish" and stop.
2. Take min(capacity, number of approved rows) rows. Get slots: `uv run python scripts/slots.py --count <N>`.
3. For each (row, slot), run the per-pin playbook below. After EACH verified success:
   - `uv run python scripts/manifest.py mark "<file>" scheduled --time "<slot>"`
   - `mv "videos/inbox/<file>" videos/scheduled/`
4. Pace: wait 30–60 s between pins.
5. Report: pins scheduled with times, rows remaining, when to run next.

## Per-pin playbook

Follow `docs/exploration/pin-builder-field-map.md` for exact targets. Every step: act → screenshot → verify before continuing.

1. `new_tab("https://www.pinterest.com/pin-builder/")` → `wait_for_load()` → screenshot. Login wall → STOP, ask user.
2. Upload the video using the verified method from the field map. Poll with screenshots until the preview renders (timeout: 3 minutes).
3. Title, description, ALT (reveal via its toggle first), link: clipboard-paste each (`printf '%s' "..." | pbcopy`, click field, Cmd+V), then screenshot-verify the text stuck.
4. Tags: for each config tag — type it, screenshot the autocomplete, click the matching suggestion, verify the chip appeared. A tag without a chip did not stick.
5. Board: select the configured board; verify it shows as selected.
6. Toggle "Publish at a later date"; set date and time to the slot; verify both render correctly.
7. Click Publish. Screenshot-verify the success confirmation (see field map) BEFORE updating the manifest.

## Failure policy

- Any unverified step: screenshot to `.cache/failures/`, `mark "<file>" failed --error "<reason>"`, STOP the whole batch, report to user. Do not continue — mid-batch failures usually mean a UI change.
- Exception: video processing timeout → mark that row failed, continue with the next row.
- `failed` rows need a human: fix the cause, then mark them `approved` again.

## Dry-run mode

When asked for a dry run: execute playbook steps 1–6, screenshot the completed form, then close the tab WITHOUT publishing and discard the draft. Mark nothing.

## Field map

(Transcribed from docs/exploration/pin-builder-field-map.md — keep in sync when Pinterest's UI changes.)
````

- [ ] **Step 2: Write `CLAUDE.md`**

```markdown
@SKILL.md
```

- [ ] **Step 3: Write `README.md`**

```markdown
# pin-scheduler

Schedule 15–20 Pinterest video pins a day without clicking through
pin-builder by hand. Claude Code + browser automation fill the form the way
you would; Pinterest's own "Publish at a later date" scheduler does the
timed publishing — your machine doesn't stay on.

## How it works

1. **Prep** — drop videos in `videos/inbox/`, say "prep pins". Audio is
   transcribed (whisper) and Claude writes SEO titles/descriptions into
   `manifest.csv` for your review.
2. **Approve** — edit the CSV if you like, then approve.
3. **Post** — say "schedule pins". Claude drives pin-builder in your
   logged-in Chrome: uploads each video, fills title/description/ALT/link/
   tags/board from `config.yaml`, and schedules each pin 30–60 min apart.
   Pinterest caps the queue at ~10 pins, so 15–20/day = a morning and an
   afternoon run.

## Requirements

- macOS, Chrome logged in to your Pinterest account
- [Claude Code](https://claude.com/claude-code) with a CDP browser
  automation harness (this project uses browser-harness; any tool that can
  click, type, screenshot, and set file inputs in your real Chrome works)
- `uv`, `ffmpeg` (`brew install uv ffmpeg`)

## Setup

    cp config.example.yaml config.yaml   # your link, ALT, tags, board, posting window
    mkdir -p videos/inbox videos/scheduled

## A note on Pinterest policy

This automates *your own hands* on *your own account* at human scale, using
Pinterest's own scheduler for timing. It does no engagement automation and
no scraping. The unambiguous routes are the official API (standard access)
or an approved partner like Tailwind — see the design doc in
`docs/superpowers/specs/` for why those didn't fit this workflow.

Design: `docs/superpowers/specs/2026-06-11-pin-scheduler-design.md`
```

(Fix the browser-harness link to wherever it actually lives before committing — check with the user; use plain text "browser-harness" with no link if unpublished.)

- [ ] **Step 4: Commit**

```bash
git add SKILL.md README.md CLAUDE.md
git commit -m "feat: pin-scheduler skill, README, project CLAUDE.md"
```

---

### Task 7: Dry-run end-to-end

⚠️ **Requires the user present, logged in to Pinterest.**

**Files:** none created (validation task; fixture + manifest are gitignored).

- [ ] **Step 1: Stage the fixture as a real inbox video**

```bash
mkdir -p videos/inbox videos/scheduled
cp .cache/fixtures/sample.mp4 videos/inbox/
cp config.example.yaml config.yaml
```

Edit `config.yaml` with the user's real board name and link (ask the user; a secret test board is fine).

- [ ] **Step 2: Run the prep phase**

Follow SKILL.md prep phase on `videos/inbox/sample.mp4`.
Expected: transcript mentions "barefoot running shoe review"; one `draft` row in `manifest.csv` with a ≤100-char title and ≤800-char description.

- [ ] **Step 3: Approve and dry-run the post phase**

Mark the row approved, then execute the playbook in dry-run mode (steps 1–6, screenshot the filled form, discard without publishing).
Expected: screenshot shows title, description, ALT, link, tags chips, board, and the scheduled date/time all filled correctly. Manifest row still `approved`.

- [ ] **Step 4: Fix any playbook drift**

If any step needed improvisation, update `SKILL.md` and/or `docs/exploration/pin-builder-field-map.md` to match reality, and commit:

```bash
git add SKILL.md docs/exploration/pin-builder-field-map.md
git commit -m "fix: align playbook with observed pin-builder behavior"
```

---

### Task 8: Real acceptance — schedule 2 pins

⚠️ **Requires the user present and their explicit go-ahead: this publishes real (secret-board) pins.**

- [ ] **Step 1: Confirm target board with the user**

Use a **secret board** so test pins are not public. Confirm `config.yaml` points at it.

- [ ] **Step 2: Schedule 2 pins for real**

Stage a second fixture copy (`cp .cache/fixtures/sample.mp4 videos/inbox/sample2.mp4`), prep + approve both rows, then run the full post phase (no dry-run).
Expected: both pins publish-scheduled at the next two free slots; manifest rows `scheduled` with times; files moved to `videos/scheduled/`.

- [ ] **Step 3: Verify on Pinterest**

Navigate to the scheduled-pins view (per field map doc) and screenshot.
Expected: both pins listed at the expected times.

- [ ] **Step 4: Verify capacity math**

Run: `uv run python scripts/manifest.py capacity`
Expected: `8`.

- [ ] **Step 5: Wait for the first slot to pass, then confirm publication**

After the first scheduled time, check the secret board for the published pin. Then (with the user) delete the test pins from Pinterest and reset local state:

```bash
rm -f videos/scheduled/sample.mp4 videos/scheduled/sample2.mp4 manifest.csv
```

- [ ] **Step 6: Final commit & wrap-up**

```bash
git add -A
git commit -m "docs: acceptance-tested against live pin-builder" --allow-empty
```

Report to the user: what works, observed limits (queue cap, lead time), and that the system is ready for real videos.
