#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/video_segments_annotated"
OUTPUT_STAGE="video/video_segments_overlay"
# INPUT:
# - video/video_segments_annotated/video_segment_annotated_20240505_101501_0.3333_5.1000.mp4
# OUTPUT:
# - video/video_segments_overlay/video_segment_overlay_20240505_101501_0.3333_5.1000.mp4

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  CAMERA_CONFIG_DIR="$REPO_DIR/shell/scripts/video/config"
  MOTION_DETECTION_CONFIG_FILE="$CAMERA_CONFIG_DIR/motion-config-$MACHINE_NAME.txt"
  VIDEO_CONFIG_FILE="$CAMERA_CONFIG_DIR/video-config-$MACHINE_NAME.txt"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "video_segment_annotated_")"
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi
  log "Processing: $LATEST_NOT_PROCESSED_PATH"

  FILE_DATETIME_AND_SEGMENT="$(strip "$LATEST_NOT_PROCESSED_FILE" "video_segment_annotated_" ".mp4")"
  FILE_DATETIME="$(echo "$FILE_DATETIME_AND_SEGMENT" | cut -d '_' -f 1,2)"
  SEGMENT_START="$(echo "$FILE_DATETIME_AND_SEGMENT" | cut -d '_' -f 3)"
  SEGMENT_END="$(echo "$FILE_DATETIME_AND_SEGMENT" | cut -d '_' -f 4)"
  DURATION=$(calc "$SEGMENT_END - $SEGMENT_START")

  FILE_NAME="video_segment_overlay_${FILE_DATETIME_AND_SEGMENT}.mp4"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  log "Starting video segment area of interest overlying"
  request_cpu_time "${PROCESS}-area-of-interest" "20"

  polygon="$(get_config "polygon" "" "$MOTION_DETECTION_CONFIG_FILE")"
  coords="$(echo "$polygon" | tr ';' ' ')"

  # Create the polygon image using ImageMagick
  polygonImage="$OUTPUT_STAGE_DIR/polygon.png"
  VIDEO_WIDTH=$(get_config "width" "" "$VIDEO_CONFIG_FILE")
  VIDEO_HEIGHT=$(get_config "height" "" "$VIDEO_CONFIG_FILE")
  command="convert -size ${VIDEO_WIDTH}x${VIDEO_HEIGHT} xc:transparent -fill none -stroke red -draw \"polygon $coords\" $polygonImage"
  log "Creating polygon image: $command"
  eval $command

  if [ $? -ne 0 ]; then
      log "Error creating polygon image."
      continue
  fi

  request_cpu_time "${PROCESS}-area-of-interest" "60"
  command="ffmpeg -threads 1 -y -i \"$LATEST_NOT_PROCESSED_PATH\" -i $polygonImage -filter_complex \"overlay\" -an \"$FILE_PATH\""
  log "Overlaying polygon on video: $command"
  eval $command

  if [ $? -ne 0 ]; then
      log "Error overlaying polygon on video segment: $LATEST_NOT_PROCESSED_PATH"
      return 1
  else
      log "Video segment with polygon created: $FILE_PATH"
      echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
  fi

  rm -f "$polygonImage"

done
