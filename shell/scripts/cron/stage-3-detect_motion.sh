#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/motion_scores"
OUTPUT_STAGE="video/segments"
# INPUT:
# - video/motion_scores/scores_20240505_101501.txt
# OUTPUT:
# - video/segments/scores_20240505_101501_0.3333_5.1000.txt

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  CAMERA_CONFIG_DIR="$REPO_DIR/shell/scripts/video/config"
  MOTION_DETECTION_CONFIG_FILE="$CAMERA_CONFIG_DIR/motion-config-$MACHINE_NAME.txt"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"
  touch "$PROCESSED_PATH"

  NOT_PROCESSED_FILES=$(diff --new-line-format="" --unchanged-line-format="" --old-line-format="%L" <(ls -1 "$INPUT_STAGE_DIR" | grep "scores_") <(cat "$PROCESSED_PATH"))
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi
  log "Processing: $LATEST_NOT_PROCESSED_PATH"

  FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "scores_" ".txt")"
  FILE_NAME="scores_${FILE_DATETIME}.txt"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  log "Starting motion segment detection"

  request_cpu_time "${PROCESS}-motion-segments" "10"


  input_file="$LATEST_NOT_PROCESSED_PATH"
  # Configuration variables
  motion_threshold="$(get_config "motion_threshold" "2.5" "$MOTION_DETECTION_CONFIG_FILE")"
  pre_motion_time="$(get_config "seconds_before" "1" "$MOTION_DETECTION_CONFIG_FILE")"
  post_motion_time="$(get_config "seconds_after" "1" "$MOTION_DETECTION_CONFIG_FILE")"
  motion_end_buffer_time="$(get_or_set_config "motion_end_buffer_time" "5")"

  # Initialize variables
  in_motion=false
  motion_start_time=0
  last_motion_time=0
  segment_counter=0

  # Read the maximum seconds value from the last line of the file
  max_seconds=$(tail -n 1 "$input_file" | awk '{print $2}')

  # Process the input file line by line
  while read -r line; do
    frame_index=$(echo "$line" | cut -d ' ' -f 1)
    seconds=$(echo "$line" | cut -d ' ' -f 2)
    motion_score=$(echo "$line" | cut -d ' ' -f 3)

    if (( $(echo "$motion_score >= $motion_threshold" | bc -l) )); then
      if [ "$in_motion" = false ]; then
        in_motion=true
        motion_start_time=$(echo "$seconds - $pre_motion_time" | bc)
        if (( $(echo "$motion_start_time < 0" | bc -l) )); then
          motion_start_time=0.0
        fi
      fi
      last_motion_time=$seconds
    else
      if [ "$in_motion" = true ]; then
        elapsed_since_last_motion=$(echo "$seconds - $last_motion_time" | bc)
        if (( $(echo "$elapsed_since_last_motion >= $motion_end_buffer_time" | bc -l) )); then
          in_motion=false
          motion_end_time=$(echo "$last_motion_time + $post_motion_time" | bc)
          if (( $(echo "$motion_end_time > $max_seconds" | bc -l) )); then
            motion_end_time=$max_seconds
          fi
          segment_counter=$((segment_counter + 1))
          segment_file="${prefix}${date}_${time}_${motion_start_time}_${motion_end_time}.txt"
          echo "$motion_start_time $motion_end_time" > "$segment_file"
        fi
      fi
    fi
  done < "$input_file"

  # Handle case where motion is still in progress at the end of the file
  if [ "$in_motion" = true ]; then
    motion_end_time=$(echo "$last_motion_time + $post_motion_time" | bc)
    if (( $(echo "$motion_end_time > $max_seconds" | bc -l) )); then
      motion_end_time=$max_seconds
    fi
    segment_counter=$((segment_counter + 1))
    segment_file="${prefix}${date}_${time}_${motion_start_time}_${motion_end_time}.txt"
    echo "$motion_start_time $motion_end_time" > "$segment_file"
  fi

  log "Done motion score detection"
  echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"

done
