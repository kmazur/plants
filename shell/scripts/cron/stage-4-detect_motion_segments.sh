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

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "scores_")"

  notify_work_completed "${PROCESS}-scan"
  if [ -z "$NOT_PROCESSED_FILES" ]; then
    continue
  fi

  echo "$NOT_PROCESSED_FILES" | while IFS= read -r LATEST_NOT_PROCESSED_FILE; do
    request_cpu_time "${PROCESS}-motion-segments" "10"

    LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"
    log "Processing: $LATEST_NOT_PROCESSED_PATH"

    FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "scores_" ".txt")"
    FILE_NAME="scores_${FILE_DATETIME}.txt"
    FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

    log "Starting motion segment detection"

    input_file="$LATEST_NOT_PROCESSED_PATH"
    # Configuration variables
    motion_threshold="$(get_config "motion_threshold" "2.5" "$MOTION_DETECTION_CONFIG_FILE")"
    pre_motion_time="$(get_config "seconds_before" "1" "$MOTION_DETECTION_CONFIG_FILE")"
    post_motion_time="$(get_config "seconds_after" "1" "$MOTION_DETECTION_CONFIG_FILE")"
    motion_end_buffer_time="$(get_or_set_config "motion_end_buffer_time" "5")"
    motion_video_start_seconds_ignore="$(get_or_set_config "start_seconds_ignore" "1")"

    # Initialize variables
    prefix="scores_"
    in_motion=false
    motion_start_time=0
    motion_end_time=0
    last_motion_time=0

    # Read the maximum seconds value from the last line of the file
    max_seconds=$(tail -n 1 "$input_file" | awk '{print $2}')

    # Process the input file line by line
    while read -r line; do
      frame_index=$(echo "$line" | cut -d ' ' -f 1)
      seconds=$(echo "$line" | cut -d ' ' -f 2)
      motion_score=$(echo "$line" | cut -d ' ' -f 3)

      if [ "$in_motion" = true ]; then
        echo "$line" >> "$segment_file"
      fi

      if (( $(echo "$seconds < $motion_video_start_seconds_ignore" | bc -l) )); then
        continue
      fi

      if (( $(echo "$motion_score >= $motion_threshold" | bc -l) )); then
        if [ "$in_motion" = false ]; then
          in_motion=true
          motion_start_time=$(calc "$seconds - $pre_motion_time")
          if (( $(echo "$motion_start_time < 0" | bc -l) )); then
            motion_start_time=0.0
          fi
          segment_file="$OUTPUT_STAGE_DIR/${prefix}${FILE_DATETIME}_${motion_start_time}_${motion_end_time}.txt"
          echo "$line" >> "$segment_file"
        fi
        last_motion_time=$seconds
      else
        if [ "$in_motion" = true ]; then
          elapsed_since_last_motion=$(calc "$seconds - $last_motion_time")
          if (( $(echo "$elapsed_since_last_motion >= $motion_end_buffer_time" | bc -l) )); then
            in_motion=false
            motion_end_time=$(calc "$last_motion_time + $post_motion_time")
            if (( $(echo "$motion_end_time > $max_seconds" | bc -l) )); then
              motion_end_time=$max_seconds
            fi
            mv "$segment_file" "$OUTPUT_STAGE_DIR/${prefix}${FILE_DATETIME}_${motion_start_time}_${motion_end_time}.txt"
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
      mv "$segment_file" "$OUTPUT_STAGE_DIR/${prefix}${FILE_DATETIME}_${motion_start_time}_${motion_end_time}.txt"
    fi

    log "Done motion score detection"
    echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"

    notify_work_completed "${PROCESS}-motion-segments"
  done

done
