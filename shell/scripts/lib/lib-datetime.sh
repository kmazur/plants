#!/bin/bash


function get_current_year() {
    date +%Y
}
function get_current_month() {
    date +%m
}
function get_current_day() {
    date +%d
}


function get_current_date_compact() {
    date +%Y%m%d
}
function get_current_date_time_compact() {
  date +%Y%m%d_%H%M%S
}
function get_current_date_time_dashed() {
  date +%Y-%m-%dT%H:%M:%S
}
function get_current_date_dashed() {
    date +%Y-%m-%d
}
function get_current_date_underscore() {
    date +%Y_%m_%d
}