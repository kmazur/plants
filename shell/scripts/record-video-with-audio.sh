#!/bin/bash

SECONDS="8"
MILLIS=$((SECONDS * 1000))
AUDIO_OUTPUT_FILE="audio"
VIDEO_OUTPUT_FILE="video"

AUDIO_FORMAT="wav"
AUDIO_FORMAT_2="mp3"
VIDEO_FORMAT="h264"

OUTPUT_FILE="output.mp4"


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

function capture_video() {
	local FILE="$1"
	local MILLIS="$2"
	libcamera-vid --nopreview -t "$MILLIS" --save-pts "$FILE.pts" --autofocus-mode continuous --width 1280 --height 720 --framerate 50 -o "$FILE"
}

function fix_framerate_video() {
	local INPUT_FILE="$1"
	local INPUT_FILE_PTS="$2"
	local OUTPUT_FILE="$3"
	mkvmerge -o "$OUTPUT_FILE" --timecodes 0:"$INPUT_FILE_PTS" "$INPUT_FILE"
}

function get_vid_duration_txt() {
	local FILE="$1"
	ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$FILE"
}

function get_vid_duration_us() {
	local FILE="$1"
	get_vid_duration_txt "$FILE" | tr -d '.'
}

echo "Capturing video & audio simultaneously for $SECONDS seconds"
echo "Script start date: $(date)"

rm "$VIDEO_OUTPUT_FILE.$VIDEO_FORMAT" 2> /dev/null
rm "$AUDIO_OUTPUT_FILE.$AUDIO_FORMAT" 2> /dev/null
rm "${AUDIO_OUTPUT_FILE}2.$AUDIO_FORMAT" 2> /dev/null
rm "${AUDIO_OUTPUT_FILE}.$AUDIO_FORMAT_2" 2> /dev/null
rm "$OUTPUT_FILE" 2> /dev/null

echo "Running audio & video recording commands: $(date)"

AUD_FILE="$AUDIO_OUTPUT_FILE.$AUDIO_FORMAT"
arecord -D plughw:0 -c1 -r 48000 -f S32_LE -t wav -V mono -v "$AUD_FILE" &
sleep 1
AUDIO_PID="$(ps aux | grep arecord | grep -v "grep" | tr -s ' ' | cut -d ' ' -f 2)"

VID_FILE="video.h264"
capture_video "$VID_FILE" "$MILLIS"

echo "Finished recording"
kill "$AUDIO_PID"

VIDEO_START_NS=$(get_birth_nanos "$VID_FILE")
AUDIO_START_NS=$(get_birth_nanos "$AUDIO_OUTPUT_FILE.$AUDIO_FORMAT")

VID_FILE2="video.mkv"
fix_framerate_video "$VID_FILE" "$VID_FILE".pts "$VID_FILE2"

DURATION=$(get_vid_duration_txt "$VID_FILE2")
echo "Video duration is: $DURATION s $(get_vid_duration_us "$VID_FILE2")"

START_DIFF_NS="$((VIDEO_START_NS - AUDIO_START_NS))"
START_DIFF_MS="$((START_DIFF_NS / 1000000))"
START_DIFF_S="$((START_DIFF_MS / 1000))"
START_DIFF_MS_TOTAL="$(($START_DIFF_MS - $START_DIFF_S*1000))"

VIDEO_DURATION_US=$(get_vid_duration_us "$VID_FILE2")
VIDEO_DURATION_MS=$((VIDEO_DURATION_US / 1000))
VIDEO_DURATION_S=$((VIDEO_DURATION_MS / 1000))
VIDEO_DURATION_MS_TOTAL=$((VIDEO_DURATION_MS - $VIDEO_DURATION_S*1000))

echo "Diff in millis: $START_DIFF_MS with duration of $VIDEO_DURATION_S,$VIDEO_DURATION_MS_TOTAL -> cutting audio from this millis"

ffmpeg -i "$AUDIO_OUTPUT_FILE.$AUDIO_FORMAT" -ss "$START_DIFF_S"."$START_DIFF_MS_TOTAL" -t "$VIDEO_DURATION_S"."$VIDEO_DURATION_MS_TOTAL" -c copy "${AUDIO_OUTPUT_FILE}2.$AUDIO_FORMAT"

ffmpeg -y -i "${AUDIO_OUTPUT_FILE}2.$AUDIO_FORMAT" -vn -ar 44100 -ac 2 -b:a 192k "$AUDIO_OUTPUT_FILE.$AUDIO_FORMAT_2"
ffmpeg -y -i "$VID_FILE2" -i "$AUDIO_OUTPUT_FILE.$AUDIO_FORMAT_2" -acodec copy -vcodec copy "$OUTPUT_FILE"
echo "Done"



