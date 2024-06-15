#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

SCHEDULER_FILE="$(get_orchestrator_requests_file)"
MAX_TEMP="$(get_or_set_config "orchestrator.max_temperature" "79")"
MIN_TEMP="$(get_or_set_config "orchestrator.min_temperature" "50")"
BASE_TOKENS="$(get_or_set_config "orchestrator.initial_tokens" "0")"
MAX_TOKENS="$(get_or_set_config "orchestrator.max_tokens" "100")"
REPLENISH_RATE="$(get_or_set_config "orchestrator.replenish_rate" "10")"  # tokens per second
RESERVE_THRESHOLD="$(get_or_set_config "orchestrator.accumulation_threshold_seconds" "60")"  # Threshold wait time (seconds) to start reserving tokens
SLEEP_INTERVAL="$(get_or_set_config "orchestrator.run_interval" "5")"

declare -A accumulated_tokens

ensure_file_exists "$SCHEDULER_FILE"

available_tokens=$BASE_TOKENS
replenish_rate=$REPLENISH_RATE
last_replenish_time=$(date +%s.%N)

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
            local wait_time=$(( $(date +%s) - $timestamp ))
            ref_entries+=("$process:$tokens:$timestamp:$sleep_pid:$wait_time")
        fi
    done < "$file"
}

function wake_up_process() {
    local PID="$1"
    kill -SIGUSR1 "$PID" 2>/dev/null
}

function adjust_replenish_rate() {
    local temp="$1"
    if (( $(echo "$temp < $MIN_TEMP" | bc -l) )); then
        replenish_rate=$REPLENISH_RATE
    elif (( $(echo "$temp >= $MAX_TEMP" | bc -l) )); then
        replenish_rate=0.0
    else
        replenish_rate=$(echo "scale=2; $REPLENISH_RATE - (($temp - $MIN_TEMP) / ($MAX_TEMP - $MIN_TEMP))" | bc)
    fi
}

function replenish_tokens() {
    local current_time=$(date +%s.%N)
    local elapsed_time=$(echo "$current_time - $last_replenish_time" | bc)
    local tokens_to_add=$(echo "$elapsed_time * $replenish_rate" | bc)
    local total_accumulated_tokens=0

    for tokens in "${accumulated_tokens[@]}"; do
        total_accumulated_tokens=$(echo "$total_accumulated_tokens + $tokens" | bc)
    done

    local available_capacity=$(echo "$MAX_TOKENS - $total_accumulated_tokens" | bc)
    if (( $(echo "$tokens_to_add + $available_tokens > $available_capacity" | bc -l) )); then
        tokens_to_add=$(echo "$available_capacity - $available_tokens" | bc)
    fi

    if (( $(echo "$tokens_to_add > 0" | bc -l) )); then
        available_tokens=$(echo "$available_tokens + $tokens_to_add" | bc)
    fi

    last_replenish_time=$current_time
}

function run_scheduler() {
    local entries=()
    parse_scheduler_file "$SCHEDULER_FILE" entries

    # Sort processes by wait time (highest first) to prevent starvation
    IFS=$'\n' sorted=($(sort -t: -k5 -nr <<<"${entries[*]}"))
    unset IFS
    entries=("${sorted[@]}")

    local num_processes=${#entries[@]}

    unset run_pass
    declare -A run_pass

    for entry in "${entries[@]}"; do
        # entries+=("$process:$tokens:$timestamp:$sleep_pid:$wait_time")
        local process=$(echo "$entry" | cut -d: -f1)
        local tokens=$(echo "$entry" | cut -d: -f2)
        local timestamp=$(echo "$entry" | cut -d: -f3)
        local pid=$(echo "$entry" | cut -d: -f4)
        local wait_time=$(echo "$entry" | cut -d: -f5)
        local estimated_tokens="$tokens"

        # Check if we can immediately fulfill the token request
        if (( $(echo "$available_tokens + ${accumulated_tokens[$process]:-0} >= $estimated_tokens" | bc -l) )); then
            run_pass[$process]="RUN (r: $tokens/${accumulated_tokens[$process]:-0}, a: $available_tokens)"
            available_tokens=$(echo "$available_tokens - ($estimated_tokens - ${accumulated_tokens[$process]:-0})" | bc)
            wake_up_process "$pid"
            unset accumulated_tokens[$process]
            remove_config "$process" "$SCHEDULER_FILE"
        else
            # Accumulate tokens for processes waiting longer than the threshold
            if (( wait_time > RESERVE_THRESHOLD )); then
                local accumulation_factor=$(echo "scale=2; 0.1 + (0.9 * ($available_tokens / $MAX_TOKENS))" | bc)
                local tokens_to_accumulate=$(echo "$available_tokens * $accumulation_factor / $num_processes" | bc -l)
                accumulated_tokens[$process]=$(echo "${accumulated_tokens[$process]:-0} + $tokens_to_accumulate" | bc)
                available_tokens=$(echo "$available_tokens - $tokens_to_accumulate" | bc)

                run_pass[$process]="ACCUMULATE (r: $tokens/${accumulated_tokens[$process]:-0}, a: $available_tokens)"
            else
                run_pass[$process]="SKIP (r: $tokens/${accumulated_tokens[$process]:-0}, a: $available_tokens)"
            fi
        fi
    done

    for process in "${!run_pass[@]}"; do
      printf "%50s: %s\n" "$process" "${run_pass[$process]}"
    done
}



while true; do
  CONFIG="$(load_config)"
  MAX_TEMP="$(get_loaded_config "$CONFIG" "orchestrator.max_temperature" "79")"
  MIN_TEMP="$(get_loaded_config "$CONFIG" "orchestrator.min_temperature" "50")"
  BASE_TOKENS="$(get_loaded_config "$CONFIG" "orchestrator.initial_tokens" "0")"
  MAX_TOKENS="$(get_loaded_config "$CONFIG" "orchestrator.max_tokens" "100")"
  REPLENISH_RATE="$(get_loaded_config "$CONFIG" "orchestrator.replenish_rate" "10")"  # tokens per second
  RESERVE_THRESHOLD="$(get_loaded_config "$CONFIG" "orchestrator.accumulation_threshold_seconds" "60")"  # Threshold wait time (seconds) to start reserving tokens
  SLEEP_INTERVAL="$(get_loaded_config "$CONFIG" "orchestrator.run_interval" "5")"

  # Adjust replenish rate based on current temperature
  current_temp=$(get_cpu_temp_int)
  adjust_replenish_rate "$current_temp"

  # Replenish tokens based on elapsed time
  replenish_tokens

  # Run the scheduler
  run_scheduler

  # Log available tokens and replenish rate
  log "Available tokens: $available_tokens, Replenish rate: $replenish_rate"

  sleep "$SLEEP_INTERVAL"
done
