#!/usr/bin/env bash

LOCK_FILE="$HOME/WORK/tmp/drive.lock"
if [ -f "$LOCK_FILE" ]; then
  echo "Lock file exists: $LOCK_FILE. Exiting!"
  exit 0
fi
touch "$LOCK_FILE"

function finally_func() {
  echo "Cleaning up the lock file: $LOCK_FILE"
  rm -f "$LOCK_FILE"
}
trap finally_func EXIT

source "$HOME/.profile"

MONITORING_DIR="$HOME/WORK/tmp/Monitoring"
DRIVE_CMD="/home/user/.local/bin/drive"
SOURCE_NAME="$(get_machine_name)"

MONITORING_PARENT_ID=""
if [ "$SOURCE_NAME" = "RaspberryPi2" ]; then
  MONITORING_PARENT_ID="1gw5b8r24j5lnMCiRyqlrubarOxi6sofD"
elif [ "$SOURCE_NAME" = "RaspberryPi4" ]; then
  MONITORING_PARENT_ID="1ea_XDoMjxhwp28rlv7gpiPd80PTfmgge"
elif [ "$SOURCE_NAME" = "PiZero" ]; then
  MONITORING_PARENT_ID="1PXmC1nkxR2sQtzUvIR4p2UIILaDSWq6w"
else
  exit 1
fi

ensure_directory_exists "$MONITORING_DIR"

if [ -d "$MONITORING_DIR/$SOURCE_NAME" ]; then
  echo "Machine directory exists: $MONITORING_DIR/$SOURCE_NAME"
else
  echo "Machine directory does not exist: $MONITORING_DIR/$SOURCE_NAME"
  cd "$MONITORING_DIR" || exit 2
  drive clone $MONITORING_PARENT_ID
  if [ -d "$MONITORING_DIR/$SOURCE_NAME" ]; then
    echo "Cloned parent successfully"
  else
    echo "Error cloning parent"
    exit 3
  fi
fi

function get_photo_source_dir() {
  CURRENT_DATE_DASH=$1
  echo "$HOME/WORK/tmp/camera/$CURRENT_DATE_DASH"
}

function get_photo_destination_dir() {
  CURRENT_DATE_DASH=$1
  echo "$MONITORING_DIR/$SOURCE_NAME/$CURRENT_DATE_DASH"
}

function get_video_source_dir() {
  echo "$HOME/WORK/tmp/vid"
}

function get_video_destination_dir() {
  CURRENT_DATE_DASH=$1
  echo "$MONITORING_DIR/$SOURCE_NAME/$CURRENT_DATE_DASH"
}

CURRENT_DATE_DASH=$(get_current_date_dash)
YEAR=$(extract_year_from_date "$CURRENT_DATE_DASH" "-")
MONTH=$(extract_month_from_date "$CURRENT_DATE_DASH" "-")
DAY=$(extract_day_from_date "$CURRENT_DATE_DASH" "-")
CURRENT_DATE_UNDERSCORE=$YEAR'_'$MONTH'_'$DAY
CURRENT_DATE_COMPACT=$YEAR$MONTH$DAY

PHOTO_SOURCE_DIR=$(get_photo_source_dir "$CURRENT_DATE_DASH")
PHOTO_DESTINATION_DIR=$(get_photo_destination_dir "$CURRENT_DATE_DASH")
VIDEO_SOURCE_DIR=$(get_video_source_dir "$CURRENT_DATE_DASH")
VIDEO_DESTINATION_DIR=$(get_video_destination_dir "$CURRENT_DATE_DASH")

if [ -d "$PHOTO_SOURCE_DIR" ]; then
  if [ -d "$PHOTO_DESTINATION_DIR" ]; then
    echo "Date directory exists: $PHOTO_DESTINATION_DIR"
  else
    ensure_directory_exists "$PHOTO_DESTINATION_DIR"
    cd "$PHOTO_DESTINATION_DIR" || exit 2
    $DRIVE_CMD add_remote --pid "$MONITORING_PARENT_ID"
  fi

  cd "$PHOTO_SOURCE_DIR" || exit 2
  ls -1athr | grep "$CURRENT_DATE_UNDERSCORE" | grep ".jpg" | xargs -I {} cp -n {} "$PHOTO_DESTINATION_DIR"
  cd "$MONITORING_DIR/$SOURCE_NAME" || exit 2
  $DRIVE_CMD push
fi

if [ -d "$VIDEO_SOURCE_DIR" ]; then
  if [ -d "$VIDEO_DESTINATION_DIR" ]; then
    echo "Date directory exists: $VIDEO_DESTINATION_DIR"
  else
    ensure_directory_exists "$VIDEO_DESTINATION_DIR"
    cd "$VIDEO_DESTINATION_DIR" || exit 2
    $DRIVE_CMD add_remote --pid "$MONITORING_PARENT_ID"
  fi

  cd "$VIDEO_SOURCE_DIR" || exit 2
  ls -1athr | grep "$CURRENT_DATE_COMPACT" | grep ".mkv" | xargs -I {} cp -n {} "$VIDEO_DESTINATION_DIR"
  cd "$MONITORING_DIR/$SOURCE_NAME" || exit 2
  $DRIVE_CMD push
fi
