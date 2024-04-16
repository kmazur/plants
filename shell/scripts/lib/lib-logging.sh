#!/bin/bash

LOG_DATETIME_FORMAT="+%Y-%m-%dT%H:%M:%S%Z"

function log() {
  local MESSAGE="$1"
  local LOG_DATETIME="$(date "$LOG_DATETIME_FORMAT")"
  local LOG_LEVEL="${2:-INFO}"
  echo "[$LOG_DATETIME][$LOG_LEVEL] $MESSAGE"
}

function log_error() {
  local MESSAGE="[\$?]=$? $1"
  log "$MESSAGE" "ERROR"
}

function log_warn() {
  local MESSAGE="$1"
  log "$MESSAGE" "WARN"
}

function fatal_error() {
  local MESSAGE="$1"
  log "$MESSAGE" "FATAL"
  exit 1
}