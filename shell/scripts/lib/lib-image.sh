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

function create_blank_image() {
  local FILE="$1"
  local WIDTH="$2"
  local HEIGHT="$3"
  convert -size "${WIDTH}x${HEIGHT}" xc:black "$FILE"
}

function embed_image() {
  local BASE_FILE="$1"
  local IMAGE_FILE="$2"
  local X="$3"
  local Y="$4"
  local WIDTH="$5"
  local HEIGHT="$6"

  local TMP_OUTPUT="$(mktemp "$TMP_DIR/embed.XXXX.jpg")"
  ffmpeg -i "$BASE_FILE" -i "$IMAGE_FILE" -filter_complex \
       "[1:v] scale=$WIDTH:$HEIGHT [scaled]; [0:v][scaled] overlay=x=$X:y=$Y" \
       -y "$TMP_OUTPUT"

  cp "$TMP_OUTPUT" "$BASE_FILE"
  rm "$TMP_OUTPUT"
}

declare TIMELAPSE_IMAGE_WIDTH="1280"
declare TIMELAPSE_IMAGE_HEIGHT="720"

function get_timelapse_image() {
  local DATE="$(get_current_date_compact)"
  echo "$TMP_DIR/$DATE.jpg"
}

function create_hour_base_image() {
  create_blank_image "$(get_timelapse_image)" "$((TIMELAPSE_IMAGE_WIDTH * 5))" "$((TIMELAPSE_IMAGE_HEIGHT * 5))"
}

function embed_hour_image() {
  local DATE="$(get_current_date_compact)"
  local HOUR="$(get_current_hour)"
  local X="$(( (HOUR % 5) * TIMELAPSE_IMAGE_WIDTH ))"
  local Y="$(( (HOUR / 5) * TIMELAPSE_IMAGE_HEIGHT ))"
  local CONFIG_FILE="$(get_required_config "video-config-file")"

  local HOUR_IMAGE="$TMP_DIR/${DATE}_${HOUR}.jpg"
  libcamera-still -c "$CONFIG_FILE" -o "$HOUR_IMAGE" -n -t 1 --mode "$TIMELAPSE_IMAGE_WIDTH:$TIMELAPSE_IMAGE_HEIGHT" &> /dev/null

  embed_image "$(get_timelapse_image)" "$HOUR_IMAGE" "$X" "$Y" "$TIMELAPSE_IMAGE_WIDTH" "$TIMELAPSE_IMAGE_HEIGHT"
}