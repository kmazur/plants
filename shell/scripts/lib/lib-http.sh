#!/bin/bash

function upload_file() {
  local FILE="$1"
  local FILE_TYPE="${2:-image/jpg}"

  local FILENAME="$(echo "$FILE" | rev | cut -d '/' -f 1 | rev)"
  local FILEPATH="$(echo "$FILE" | rev | cut -d '/' -f 2- | rev)"

  local HTTP_AUTH="$(get_required_config "http.token")"
  cd "$FILEPATH"
  curl -XPOST "http://34.133.13.235:8089/tmp/?auth=$HTTP_AUTH" --form "file=@$FILENAME;type=$FILE_TYPE"
}