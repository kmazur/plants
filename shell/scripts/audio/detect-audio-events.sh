#!/bin/bash

source "$LIB_INIT_FILE"
ensure_env

# Input files
STUB="$1"

mp3_file="$STUB.mp3"
pts_file="$STUB.influx"
NANOS="$(cat "$STUB.txt")"
EPOCH_SECONDS="$(( NANOS / 1000000000 ))"


# Output file
output_file="${STUB}_concat.mp3"

# Temporary files
segment_list=$(mktemp)
filtered_segments=$(mktemp)
segment_dir=$(mktemp -d)

# Parse the PTS file and identify segments with volume changes > 3 dB
echo "OUTPUT: $segment_list"
echo "OUTPUT: $filtered_segments"

prev_max=0
index=0
while IFS=' ' read -r LINE; do
  declare -a ARR=($LINE)
  echo "$LINE"
  echo "${ARR[@]}"

  declare SECOND="${ARR[0]}"
  declare MIN_VAL="${ARR[1]}"
  declare MAX_VAL="${ARR[2]}"
  declare MEAN_VAL="${ARR[3]}"
  declare LAST_VAL="${ARR[4]}"
  declare DIFF_VAL="${ARR[5]}"

  declare EPOCH="$(( EPOCH_SECONDS + SECOND ))"

  declare timestamp="$SECOND"
  declare min="$MIN_VAL"
  declare max="$MAX_VAL"

  if [ ! -z "$prev_max" ]; then
    diff=$(echo "$max - $prev_max" | bc)
    diff=${diff#-} # Absolute value
    if (( $(echo "$diff > 3" | bc -l) )); then
      # Add 2 seconds before and after
      start=$(date -u -d @"$SECOND" +'%H:%M:%S')
      ffmpeg -nostdin -i "$mp3_file" -ss "$SECOND" -t 5 -c copy "${segment_dir}/segment_${index}.mp3"
      echo "file '${segment_dir}/segment_${index}.mp3'" >> "$segment_list"
      index=$((index + 1))
    fi
  fi
  prev_max=$max
done < "$pts_file"

ffmpeg -y -f concat -safe 0 -i "$segment_list" -c copy "$output_file"

# Cleanup
rm -r "$segment_dir"