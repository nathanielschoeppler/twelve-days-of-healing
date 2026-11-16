#!/usr/bin/env bash
# One-time setup for the studio pipeline (Ubuntu/Debian). Safe to run again.
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -q >/dev/null
apt-get install -y -q ffmpeg fluidsynth rubberband-cli musescore-general-soundfont-lossless avldrums.lv2-soundfont >/dev/null
python3 -m pip install -q --break-system-packages numpy scipy soundfile pyworld mido faster-whisper 2>/dev/null \
  || python3 -m pip install -q numpy scipy soundfile pyworld mido faster-whisper
echo "studio ready"
