#!/bin/bash

PROCESS_NAME="report-humidity-temp-sensor"
LOG_FILE="$LOGS_DIR/$PROCESS_NAME.log"

python "$REPO_DIR/python/reporting/report-humidity-temp-sensor.py" "$*" &>> "$LOG_FILE"