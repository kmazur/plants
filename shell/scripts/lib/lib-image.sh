#!/bin/bash

function draw_text_bl() {
  local INPUT_IMAGE="$1"
  local OUTPUT_IMAGE="$2"
  local TEXT="$3"
  local FONT_SIZE="${4:-90}"
  local FONT_COLOR="${5:-yellow}"
  local QUALITY="${6:-1}"

  local PADDING="$((FONT_SIZE / 3))"

  ffmpeg -y -i "$INPUT_IMAGE" -vf "drawtext=text=\'$TEXT\':x=$PADDING:y=H-th-$PADDING:fontsize=$FONT_SIZE:fontcolor=$FONT_COLOR" -q:v "$QUALITY" "$OUTPUT_IMAGE"
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

function get_timelapse_upload_image() {
  local MACHINE_NAME="$(get_required_config "name")"
  echo "$TMP_DIR/${MACHINE_NAME}_timelapse.jpg"
}

function get_timelapse_image() {
  local MACHINE_NAME="$(get_required_config "name")"
  local DATE="$(get_current_date_compact)"
  echo "$TMP_DIR/${MACHINE_NAME}_${DATE}_timelapse.jpg"
}

function create_hour_base_image() {
  local TIMELAPSE_IMAGE_FILE="$(get_timelapse_image)"
  if [ ! -f "$TIMELAPSE_IMAGE_FILE" ]; then
    create_blank_image "$(get_timelapse_image)" "$((TIMELAPSE_IMAGE_WIDTH * 5))" "$((TIMELAPSE_IMAGE_HEIGHT * 5))"
  else
    local FILE_SIZE="$(stat --printf="%s" "$TIMELAPSE_IMAGE_FILE")"
    if [[ "$FILE_SIZE" == "0" ]]; then
      create_blank_image "$(get_timelapse_image)" "$((TIMELAPSE_IMAGE_WIDTH * 5))" "$((TIMELAPSE_IMAGE_HEIGHT * 5))"
    fi
  fi
}

function embed_hour_image() {
  create_hour_base_image

  local DATE="$(get_current_date_compact)"
  local HOUR="$(get_current_hour)"
  if [[ "$HOUR" == "0"* ]]; then
    HOUR="${HOUR:1}"
  fi

  local HOUR_IMAGE="$TMP_DIR/${DATE}_${HOUR}.jpg"
  local HOUR_IMAGE_ANNOTATED="$TMP_DIR/${DATE}_${HOUR}_annotated.jpg"

  if [ -f "$HOUR_IMAGE_ANNOTATED" ]; then
    return 0
  fi

  local X="$(( (HOUR % 5) * TIMELAPSE_IMAGE_WIDTH ))"
  local Y="$(( (HOUR / 5) * TIMELAPSE_IMAGE_HEIGHT ))"
  local CONFIG_FILE="$(get_required_config "image-config-file")"

  libcamera-still -c "$CONFIG_FILE" -o "$HOUR_IMAGE" -n -t 1 --mode "$TIMELAPSE_IMAGE_WIDTH:$TIMELAPSE_IMAGE_HEIGHT" &> /dev/null
  draw_text_bl "$HOUR_IMAGE" "$HOUR_IMAGE_ANNOTATED" "$HOUR" "60"

  embed_image "$(get_timelapse_image)" "$HOUR_IMAGE_ANNOTATED" "$X" "$Y" "$TIMELAPSE_IMAGE_WIDTH" "$TIMELAPSE_IMAGE_HEIGHT"

  rm "$HOUR_IMAGE"
  rm "$HOUR_IMAGE_ANNOTATED"
}