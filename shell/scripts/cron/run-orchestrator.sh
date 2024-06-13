#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

SCHEDULER_FILE="$(get_orchestrator_requests_file)"
MAX_TEMP=80
MIN_TEMP=50
BASE_TOKENS=100
MAX_TOKENS=100
REPLENISH_RATE=10  # tokens per second
RESERVE_THRESHOLD=10  # Threshold wait time (seconds) to start reserving tokens
SLEEP_INTERVAL=0.1

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
    available_tokens=$(echo "$available_tokens + $tokens_to_add" | bc)

    if (( $(echo "$available_tokens > $MAX_TOKENS" | bc -l) )); then
        available_tokens=$MAX_TOKENS
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
            fi
        fi

        # If process hasn't reached threshold, allocate tokens normally
        if (( wait_time <= RESERVE_THRESHOLD )); then
            if (( $(echo "$estimated_tokens <= $available_tokens" | bc -l) )); then
                available_tokens=$(echo "$available_tokens - $estimated_tokens" | bc)
                wake_up_process "$pid"
                remove_config "$process" "$SCHEDULER_FILE"
            fi
        fi
    done

    # Log waiting processes and their accumulated tokens
    for process in "${!accumulated_tokens[@]}"; do
        log "Process: $process, Accumulated Tokens: ${accumulated_tokens[$process]}"
    done
}

while true; do
    # Adjust replenish rate based on current temperature
    current_temp=$(get_cpu_temp)
    adjust_replenish_rate "$current_temp"

    # Replenish tokens based on elapsed time
    replenish_tokens

    # Run the scheduler
    run_scheduler

    # Log available tokens and replenish rate
    log "Available tokens: $available_tokens, Replenish rate: $replenish_rate"

    sleep "$SLEEP_INTERVAL"
done
