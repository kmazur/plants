#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

# Update crontab
add_crontab_entry '0 0 * * * sudo reboot -h now'
add_crontab_entry '*/5 * * * * /home/user/WORK/workspace/plants/shell/cron/run_periodic_check.sh "cleanup" 300 1800'
add_crontab_entry '*/5 * * * * /home/user/WORK/workspace/plants/shell/cron/run_periodic_check.sh "temp-fail-safe" 20 60'
add_crontab_entry '*/5 * * * * /home/user/WORK/workspace/plants/shell/cron/run_periodic_check.sh "report-cpu-temp" 20 120'
add_crontab_entry '*/5 * * * * /home/user/WORK/workspace/plants/shell/cron/run_periodic_check.sh "process-influx-queue" 10 500'

