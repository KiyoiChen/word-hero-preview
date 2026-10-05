#!/usr/bin/env bash
set -euo pipefail

mkdir -p output

ffmpeg -y \
  -loop 1 -framerate 15 -i assets/base.jpg \
  -i voice.wav \
  -vf "subtitles=captions.ass" \
  -c:v libx264 \
  -preset ultrafast \
  -tune stillimage \
  -crf 24 \
  -pix_fmt yuv420p \
  -c:a aac \
  -b:a 128k \
  -shortest \
  -movflags +faststart \
  output/prototype_001.mp4

echo "Created output/prototype_001.mp4"
