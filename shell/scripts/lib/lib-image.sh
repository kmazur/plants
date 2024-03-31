#!/bin/bash

function draw_text_bl() {
  local INPUT_IMAGE="$1"
  local OUTPUT_IMAGE="$2"
  local TEXT="$3"
  local FONT_SIZE="${4:-90}"
  local FONT_COLOR="${5:-yellow}"

  local PADDING="$((FONT_SIZE / 3))"

  ffmpeg -y -i "$INPUT_IMAGE" -vf "drawtext=text=\'$TEXT\':x=$PADDING:y=H-th-$PADDING:fontsize=$FONT_SIZE:fontcolor=$FONT_COLOR" -codec:a copy "$OUTPUT_IMAGE"
}