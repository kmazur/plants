#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

SCHEDULER_FILE="$(get_orchestrator_requests_file)"
MAX_TEMP=78
MIN_TEMP=50
BASE_TOKENS=100
SLEEP_INTERVAL=10
TEMP_IMPACT_FILE="$(get_orchestrator_dir)/CPU_IMPACT.txt"

ensure_file_exists "$SCHEDULER_FILE"
ensure_file_exists "$TEMP_IMPACT_FILE"

function parse_scheduler_file() {
    local file="$1"
    local -n ref_entries="$2"
    ref_entries=()
    while IFS= read -r line; do
        if [[ "$line" =~ ^([^=]+)+=([^\:]+)\:([0-9]+)\:([0-9]{4}[0-9]{2}[0-9]{2}_[0-9]{2}[0-9]{2}[0-9]{2})$ ]]; then
            local process="${BASH_REMATCH[1]}"
            local tokens="${BASH_REMATCH[2]}"
            local sleep_pid="${BASH_REMATCH[3]}"
            local datetime="${BASH_REMATCH[4]}"
            local timestamp="$(date_compact_to_epoch "$datetime")"
            ref_entries+=("$process:$tokens:$timestamp:$sleep_pid")
        fi
    done < "$file"
}

function wake_up_process() {
    local PID="$1"
    kill -SIGUSR1 "$PID" 2>/dev/null
}

function calculate_dynamic_tokens() {
    local temp="$1"
    if (( $(echo "$temp < $MIN_TEMP" | bc -l) )); then
        echo "$BASE_TOKENS"
    elif (( $(echo "$temp >= $MAX_TEMP" | bc -l) )); then
        echo 0
    else
        local tokens=$(echo "$BASE_TOKENS * ($MAX_TEMP - $temp) / ($MAX_TEMP - $MIN_TEMP)" | bc)
        echo "$tokens"
    fi
}

function record_temp_impact() {
    local process="$1"
    local temp_increase="$2"
    echo "$process:$temp_increase" >> "$TEMP_IMPACT_FILE"
}

function estimate_tokens() {
    local process="$1"
    local total_temp_increase=0
    local count=0
    while IFS= read -r line; do
        if [[ "$line" =~ ^$process:([0-9]+\.[0-9]+)$ ]]; then
            local temp_increase="${BASH_REMATCH[1]}"
            total_temp_increase=$(echo "$total_temp_increase + $temp_increase" | bc)
            count=$((count + 1))
        fi
    done < "$TEMP_IMPACT_FILE"
    if (( count > 0 )); then
        local avg_temp_increase=$(echo "$total_temp_increase / $count" | bc -l)
        local estimated_tokens=$(echo "$BASE_TOKENS / (1 + $avg_temp_increase)" | bc)
        echo "$estimated_tokens"
    else
        echo "$BASE_TOKENS"
    fi
}

function run_scheduler() {
  local entries=()
  parse_scheduler_file "$SCHEDULER_FILE" entries

  # Sort processes by datetime to prevent starvation
  IFS=$'\n' sorted=($(sort -t: -k3 <<<"${entries[*]}"))
  unset IFS
  entries=("${sorted[@]}")

  local active_processes=()
  local total_tokens=0

  local current_temp=$(get_cpu_temp)
  local available_tokens=$(calculate_dynamic_tokens "$current_temp")

  for entry in "${entries[@]}"; do
    #entries+=("$process:$tokens:$timestamp:$sleep_pid")
    local process=$(echo "$entry" | cut -d: -f1)
    local tokens=$(echo "$entry" | cut -d: -f2)
    local timestamp=$(echo "$entry" | cut -d: -f3)
    local pid=$(echo "$entry" | cut -d: -f4)
    local estimated_tokens="$tokens"

    if (( total_tokens + estimated_tokens <= available_tokens )); then
      log "Running $process with $tokens/$available_tokens requested at $timestamp with pid $pid"
      remove_config "$process" "$SCHEDULER_FILE"
      wake_up_process "$pid"
      active_processes+=("$entry")
      total_tokens=$((total_tokens + estimated_tokens))
    elif (( available_tokens <= 0 )); then
      log "No more tokens available"
      break
    fi
  done

  # Record the temperature after running processes
  local temp_after=$(get_cpu_temp)

  # Calculate temperature increase
  local temp_increase=$(echo "$temp_after - $current_temp" | bc)

#  # Record the temperature impact for all running processes
#  for entry in "${active_processes[@]}"; do
#    local process=$(echo "$entry" | cut -d: -f1)
#    record_temp_impact "$process" "$temp_increase"
#  done
}

while true; do
    run_scheduler
    sleep "$SLEEP_INTERVAL"
done