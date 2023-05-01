#!/usr/bin/env bash

CURRENT_DATE=$(date +%Y%m%d)
CURRENT_DATE_DASH=$(date +%Y-%m-%d)
CURRENT_DATE_UNDERSCORE=$(date +%Y_%m_%d)
MONITORING_DIR="$HOME/WORK/tmp/Monitoring"

DRIVE_CMD="/home/user/.local/bin/drive"

MY_IP=$(/usr/sbin/ifconfig wlan0 | grep inet | tr ' ' "\n" | grep 192 | head -n 1)

# 192.168.0.45 - RaspberryPi Zero - timelapse
# 192.168.0.206 - RaspberryPi 2B+ - Videos
# 192.168.0.80 - RaspberryPi 4B+ - timelapse

SOURCE_NAME="RaspberryPi"
if [ "$MY_IP" = "192.168.0.45" ]; then
  SOURCE_NAME="PiZero"
elif [ "$MY_IP" = "192.168.0.206" ]; then
  SOURCE_NAME="RaspberryPi2"
elif [ "$MY_IP" = "192.168.0.80" ]; then
  SOURCE_NAME="RaspberryPi"
fi

function ensure_directory() {
    if [ ! -d "$1" ]; then
      mkdir -p "$1";
    fi
}

PHOTO_SOURCE_DIR="$HOME/WORK/tmp/camera/$CURRENT_DATE_DASH"
PHOTO_DEST_DIR="$MONITORING_DIR/$SOURCE_NAME/$CURRENT_DATE_DASH"

VID_SOURCE_DIR="$HOME/WORK/tmp/vid"
VID_DEST_DIR="$MONITORING_DIR/$SOURCE_NAME/$CURRENT_DATE_DASH"

ensure_directory "$PHOTO_DEST_DIR"
ensure_directory "$VID_DEST_DIR"

if [ "$MY_IP" = "192.168.0.45" ]; then
  if [ -d "$PHOTO_SOURCE_DIR" ]; then
    mkdir -p "$PHOTO_DEST_DIR"
    cd "$PHOTO_SOURCE_DIR"
    ls -1athr | grep "$CURRENT_DATE_UNDERSCORE" | grep jpg | xargs -I {} cp -n {} "$PHOTO_DEST_DIR"
    cd "$MONITORING_DIR"
    $DRIVE_CMD push
  fi
elif [ "$MY_IP" = "192.168.0.206" ]; then
  if [ -d "$VID_SOURCE_DIR" ]; then
    mkdir -p "$VID_DEST_DIR"
    cd "$VID_SOURCE_DIR"
    ls -1athr | grep "$CURRENT_DATE" | grep mkv | xargs -I {} cp -n {} "$VID_DEST_DIR"
    cd "$MONITORING_DIR"
    $DRIVE_CMD push
  fi
elif [ "$MY_IP" = "192.168.0.80" ]; then
  if [ -d "$PHOTO_SOURCE_DIR" ]; then
    mkdir -p "$PHOTO_DEST_DIR"
    cd "$PHOTO_SOURCE_DIR"
    ls -1athr | grep "$CURRENT_DATE_UNDERSCORE" | grep jpg | xargs -I {} cp -n {} "$PHOTO_DEST_DIR"
    cd "$MONITORING_DIR"
    $DRIVE_CMD push
  fi
fi
