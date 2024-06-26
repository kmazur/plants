#!/bin/bash

function upload_file() {
  local FILE="$1"
  local FILE_TYPE="${2:-image/jpg}"

  local FILENAME="$(echo "$FILE" | rev | cut -d '/' -f 1 | rev)"
  local FILEPATH="$(echo "$FILE" | rev | cut -d '/' -f 2- | rev)"

  local HTTP_AUTH="$(get_required_config "http.token")"
  echo "Executing command: "
  echo "curl -XPOST \"http://34.133.13.235:8089/upload?auth_code=$HTTP_AUTH\" --form \"file=@$FILENAME;type=$FILE_TYPE\" --connect-timeout 10 --max-time 30"

  cd "$FILEPATH" && curl -XPOST "http://34.133.13.235:8089/upload?auth_code=$HTTP_AUTH" --form "file=@$FILENAME;type=$FILE_TYPE" \
    --connect-timeout 10 \
    --max-time 30
}