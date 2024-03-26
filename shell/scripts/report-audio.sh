#!/bin/bash


function get_current_date_time_compact() {
  date +%Y%m%d_%H%M%S
}

function get_audio_levels() {
        local INPUT="$1"
        ffprobe -f lavfi -i amovie=$INPUT,astats=metadata=1:reset=1 -show_entries frame=pkt_pts_time:frame_tags=lavfi.astats.Overall.RMS_level -of default=noprint_wrappers=1:nokey=1 2> /dev/null
}


function record_audio() {
        local OUTPUT="$1"
        arecord -D plughw:0 -c1 -r 48000 -f S32_LE -t wav -V mono -v "$OUTPUT" &
        sleep 1
        AUDIO_PID="$(ps aux | grep arecord | grep -v "grep" | tr -s ' ' | cut -d ' ' -f 2)"
        echo "$AUDIO_PID"
}


AUDIO_LENGTH_SECONDS="$((30 * 60))"
while true; do
  declare FILES="$(ls -1tr | grep -P '^audio-.*\.pts$')"

  for PTS_FILE in $FILES; do
    declare STUB="${PTS_FILE%.pts}"
    declare NANOS="$(cat "$STUB.txt")"
    python parse_audio_levels.py "$NOW" &
  done
done
