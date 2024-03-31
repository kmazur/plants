#!/bin/bash

function upload_file() {
  local FILE_PATH="$1"
  local FILE_NAME="$2"
  local FILE_TYPE="${3:-image/jpg}"

  ensure_env
  local HTTP_AUTH="$(get_required_config "http.token")"
  cd "$FILE_PATH"

  curl -XPOST "http://34.133.13.235:8089/tmp/$FILE_NAME?auth=$HTTP_AUTH" --form "file=@$FILE_NAME;type=$FILE_TYPE"
}