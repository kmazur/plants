#!/bin/bash

BITRATE="48000"
BITRATE_K="$((BITRATE / 1000))"

AUDIO_FILE="audio.wav"
DURATION_SECONDS="$((24 * 60 * 60))"
SPLIT_SECONDS="$((60))"

arecord --max-file-time "$SPLIT_SECONDS" -d "$DURATION_SECONDS" -D dmic_hw -c 2 -r "$BITRATE" -f S32_LE -t wav "$AUDIO_FILE"
