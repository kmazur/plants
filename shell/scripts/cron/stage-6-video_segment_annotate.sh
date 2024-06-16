#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/video_segments"
INPUT2_STAGE="video/segments"
OUTPUT_STAGE="video/video_segments_annotated"
# INPUT:
# - video/segments/scores_20240505_101501_0.3333_5.1000.txt
# - video/video_segments/video_segment_20240505_101501_0.3333_5.1000.mp4
# OUTPUT:
# - video/video_segments_annotated/video_segment_annotated_20240505_101501_0.3333_5.1000.mp4

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  INPUT2_STAGE_DIR="$(ensure_stage_dir "$INPUT2_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "video_segment_")"
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi
  log "Processing: $LATEST_NOT_PROCESSED_PATH"

  FILE_DATETIME_AND_SEGMENT="$(strip "$LATEST_NOT_PROCESSED_FILE" "video_segment_" ".mp4")"
  FILE_DATETIME="$(echo "$FILE_DATETIME_AND_SEGMENT" | cut -d '_' -f 1,2)"
  SEGMENT_START="$(echo "$FILE_DATETIME_AND_SEGMENT" | cut -d '_' -f 3)"
  SEGMENT_END="$(echo "$FILE_DATETIME_AND_SEGMENT" | cut -d '_' -f 4)"
  DURATION=$(calc "$SEGMENT_END - $SEGMENT_START")

  FILE_NAME="video_segment_annotated_${FILE_DATETIME_AND_SEGMENT}.mp4"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  SCORES_FILE_NAME="scores_${FILE_DATETIME_AND_SEGMENT}.txt"
  SCORES_FILE_PATH="$INPUT2_STAGE_DIR/$SCORES_FILE_NAME"

  if [ ! -f "$SCORES_FILE_PATH" ]; then
    echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
    log "Scores file: $SCORES_FILE_PATH does not exist! Skipping"
    continue
  fi

  log "Starting video segment annotation"
  request_cpu_time "${PROCESS}-motion-segments-build" "4"

  MOTION_DATA_LIST=()
  while IFS= read -r LINE; do
      FRAME=$(echo "$LINE" | cut -d' ' -f 1)
      TIME=$(echo "$LINE" | cut -d' ' -f 2)
      ADJUSTED_TIME="$(calc "$TIME - $SEGMENT_START")"
      SCORE=$(echo "$LINE" | cut -d' ' -f 3)
      MOTION_DATA_LIST+=("$ADJUSTED_TIME" "$SCORE")
  done < "$SCORES_FILE_PATH"

  VIDEO_START_TIME_TIMESTAMP="$(date_compact_to_epoch "$FILE_DATETIME")"

  DRAWTEXT_COMMAND=""
  SIZE=${#MOTION_DATA_LIST[@]}
  for (( I=0; I<SIZE; I+=2 )); do
      TIME="${MOTION_DATA_LIST[$I]}"
      SCORE="${MOTION_DATA_LIST[$((I+1))]}"
      NEXT_TIME="${MOTION_DATA_LIST[$((I+2))]}"
      [ -z "$NEXT_TIME" ] && NEXT_TIME=$(echo "$TIME + 1" | bc)

      TIME_TEXT=$(date -d@"$(calc "$VIDEO_START_TIME_TIMESTAMP + $TIME")" "+%Y-%m-%d %H\\:%M\\:%S")

      DRAWTEXT_COMMAND+="drawtext=fontfile=/path/to/font.ttf:text='$TIME_TEXT motion\\: $SCORE':x=10:y=h-50:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=5:enable='between(t,$TIME,$NEXT_TIME)',"
  done

  DRAWTEXT_COMMAND="${DRAWTEXT_COMMAND%,}"

  COMMAND="ffmpeg -threads 1 -y -i \"$LATEST_NOT_PROCESSED_PATH\" -vf \"$DRAWTEXT_COMMAND\" -codec:a copy \"$FILE_PATH\""
  echo "Executing FFmpeg command for annotating: $COMMAND"

  request_cpu_time "${PROCESS}-motion-segments-execute" "8"
  eval "$COMMAND"

  if [ $? -ne 0 ]; then
      echo "Error overlaying text on video segment: $LATEST_NOT_PROCESSED_FILE"
  else
      log "Done video segment annotating"
      echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
  fi

done
