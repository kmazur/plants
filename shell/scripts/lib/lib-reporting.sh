#!/bin/bash

function get_cpu_temp() {
  vcgencmd measure_temp | cut -f 2 -d '=' | cut -f 1 -d "'"
}

function get_cpu_temp_int() {
  vcgencmd measure_temp | cut -f 2 -d '=' | cut -f 1 -d "'" | cut -d'.' -f 1
}

