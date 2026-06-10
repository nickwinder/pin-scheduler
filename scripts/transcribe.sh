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
