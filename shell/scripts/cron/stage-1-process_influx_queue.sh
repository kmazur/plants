#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE=""
OUTPUT_STAGE="influx/publish"
# INPUT:
# - $INFLUX_DIR/main.queue
# OUTPUT:
# - none

PROCESS="$OUTPUT_STAGE"

while true; do
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"

  request_cpu_time "${PROCESS}-temp_read" "4"

  log "Publishing main influx queue"
  PROCESSED="$(publish_main_queue)"
  echo "Published $PROCESSED entries"
  notify_work_completed "${PROCESS}-temp_read"
done
