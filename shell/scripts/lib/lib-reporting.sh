#!/bin/bash

# Read the temperature and convert from millidegrees to degrees
# Assume 6 digits for fast processing
function get_cpu_temp_int() {
  TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
  echo "${TEMP:0:2}"
}

