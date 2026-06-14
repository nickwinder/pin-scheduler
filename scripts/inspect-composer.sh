#!/usr/bin/env bash
# inspect-composer.sh — dump the currently-loaded Pinterest composer's field
# map as JSON, so the playbook's selectors can be verified against whatever
# composer THIS account actually serves.
#
# Why this exists: the organic storyboard composer (pin-creation-tool /
# idea-pin-builder) and the standard Pin composer (pin-builder) are different
# DOMs, and which one an account gets is account-dependent. This script reads
# the live DOM and reports the real selectors + the upload mechanism, instead
# of guessing.
#
# Usage:
#   1. Open the composer in the dedicated agent-browser session, e.g.
#        agent-browser --profile ~/.pin-scheduler-browser --headed open \
#          "https://www.pinterest.com/pin-builder/"
#        agent-browser wait --load networkidle
#   2. Run this script. It prints JSON to stdout (redirect to a file to share).
#
#   ./inspect-composer.sh > /tmp/composer-map.json
set -euo pipefail

agent-browser eval --stdin <<'JS'
(() => {
  const q = (s) => { try { return document.querySelector(s); } catch (e) { return null; } };
  const all = (s) => { try { return [...document.querySelectorAll(s)]; } catch (e) { return []; } };
  const txt = (el) => (el && el.textContent || '').trim().replace(/\s+/g, ' ');

  // Best stable selector for an element: id > data-test-id > unique attr > tag.
  const sel = (el) => {
    if (!el) return null;
    if (el.id) return '#' + el.id;
    const dt = el.getAttribute('data-test-id');
    if (dt) return `[data-test-id="${dt}"]`;
    const nm = el.getAttribute('name');
    if (nm) return `${el.tagName.toLowerCase()}[name="${nm}"]`;
    return el.tagName.toLowerCase();
  };
  const describe = (el) => el ? ({
    selector: sel(el),
    tag: el.tagName.toLowerCase(),
    id: el.id || null,
    name: el.getAttribute('name') || null,
    type: el.getAttribute('type') || null,
    placeholder: el.getAttribute('placeholder') || null,
    ariaLabel: el.getAttribute('aria-label') || null,
    dataTestId: el.getAttribute('data-test-id') || null,
    role: el.getAttribute('role') || null,
    contentEditable: el.getAttribute('contenteditable') || null,
    accept: el.getAttribute('accept') || null,
  }) : null;

  const heading = txt(q('h1'));
  const lower = heading.toLowerCase();

  return {
    url: location.href,
    title: document.title,
    heading,
    composer:
      q('#storyboard-upload-input') ? 'storyboard'
      : lower.includes('for ad') ? 'pin-builder-ad'
      : (q('input[type=file]') || /Create Pin/i.test(heading)) ? 'pin-builder-standard?'
      : 'unknown',
    // Upload: which file input exists, and a guess at whether setInputFiles
    // will work (a real <input type=file> that is in the DOM) vs needing the
    // native picker (no usable file input -> click the dropzone).
    fileInputs: all('input[type=file]').map(describe),
    uploadHint: all('input[type=file]').length
      ? 'file input present — try: agent-browser upload <selector> <path>'
      : 'NO file input — upload likely needs the native picker (click dropzone)',
    // Every text-bearing field, so the title/description/link/alt mapping can
    // be read off placeholders/aria-labels rather than guessed.
    textFields: all('input:not([type=file]), textarea, [contenteditable=true]').map(describe),
    // Schedule controls.
    scheduleControls: {
      laterDateLabelPresent: /Publish at a later date/i.test(document.body.innerText || ''),
      publishImmediatelyPresent: /Publish immediately/i.test(document.body.innerText || ''),
      toggleOrSwitch: describe(q('#pin-draft-switch-group, [role=switch], input[type=checkbox]')),
      dateField: describe(q('input[id*=schedule-date], input[id^=pin-draft-schedule-date-field]')),
      timeField: describe(q('input[id*=schedule-time], input[id^=pin-draft-schedule-time-field]')),
      publishButtonLabel: txt([...all('button')].find(b => /^(Publish|Schedule)$/i.test(txt(b)))),
    },
    // Board + tags entry points (by visible text, since ids vary).
    boardButton: txt([...all('button, [role=button]')].find(b => /board/i.test(txt(b)))),
    tagsCombobox: describe(q('#combobox-storyboard-interest-tags, input[id*=interest-tags], input[aria-label*=tag i]')),
    // Short list of notable buttons to eyeball the flow.
    notableButtons: [...new Set(all('button, [role=button]').map(txt).filter(t => t && t.length < 40))].slice(0, 40),
  };
})()
JS
