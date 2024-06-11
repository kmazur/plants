#!/bin/bash

function strip_leading() {
  local TEXT="$1"
  local TO_REMOVE="$2"
  echo "${TEXT#$TO_REMOVE}"
}

function strip_trailing() {
  local TEXT="$1"
  local TO_REMOVE="$2"
  echo "${TEXT%$TO_REMOVE}"
}

function strip() {
  local TEXT="$1"
  local TO_REMOVE_LEADING="$2"
  local TO_REMOVE_TRAILING="$3"

  local WITHOUT_LEADING="$(strip_leading "$TEXT" "$TO_REMOVE_LEADING")"
  local WITHOUT_TRAILING="$(strip_trailing "$WITHOUT_LEADING" "$TO_REMOVE_TRAILING")"

  echo "$WITHOUT_TRAILING"
}