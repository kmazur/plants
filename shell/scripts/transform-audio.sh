#!/bin/bash

function get_audio_levels() {
  local INPUT="$1"
  ffprobe -f lavfi -i amovie=$INPUT,astats=metadata=1:reset=1 -show_entries frame=pkt_pts_time:frame_tags=lavfi.astats.Overall.RMS_level -of default=noprint_wrappers=1:nokey=1 2> /dev/null
}

function get_birth_txt() {
	local FILE="$1"
	stat "$FILE" | grep "Birth" | cut -c 9-
}

function get_birth_nanos() {
	local FILE="$1"
	local TXT="$(get_birth_txt "$FILE")"
	local NANOS=$(date -d "$TXT" +%s.%N | tr -d '.')
	echo "$NANOS"
}

while true; do
  declare FILES="$(ls -1tr | grep -P '^audio-\d+\.wav$' | head -n -2)"
  declare FILE_COUNT="$(echo -n "$FILES" | wc -l)"

  for FILE in $FILES; do
    declare -i NANOS="$(get_birth_nanos "$FILE")"
    echo "$NANOS" > "$FILE.txt"
    lame -S --bitwidth 32 -r -s 48 --preset standard "$FILE" "$FILE.mp3" && rm "$FILE"
    get_audio_levels "$FILE.mp3" > "$FILE.pts"
  done

  sleep 10
done