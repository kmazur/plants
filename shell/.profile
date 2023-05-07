# ~/.profile: executed by the command interpreter for login shells.
# This file is not read by bash(1), if ~/.bash_profile or ~/.bash_login
# exists.
# see /usr/share/doc/bash/examples/startup-files for examples.
# the files are located in the bash-doc package.

# the default umask is set in /etc/profile; for setting the umask
# for ssh logins, install and configure the libpam-umask package.
#umask 022

# if running bash
if [ -n "$BASH_VERSION" ]; then
    # include .bashrc if it exists
    if [ -f "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi

# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/bin" ] ; then
    PATH="$HOME/bin:$PATH"
fi

# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

export WORK_DIR="$HOME/WORK"
export TMP_DIR="$WORK_DIR/tmp"
export CONFIG_DIR="$WORK_DIR/config"
export LOCKS_DIR="$TMP_DIR/locks"
export WORKSPACE_DIR="$WORK_DIR/workspace"
export REPO_DIR="$WORKSPACE_DIR/plants"
export CAMERA_DIR="$TMP_DIR/camera"
export VIDEO_DIR="$TMP_DIR/vid"
export LOGS_DIR="$WORK_DIR/logs"

function get_current_year() {
    echo $(date +%Y)
}
function get_current_month() {
    echo $(date +%m)
}
function get_current_day() {
    echo $(date +%d)
}

function extract_year_from_date() {
    DATE=$1
    DELIMITER=$2
    echo $DATE | cut -d "$DELIMITER" -f 1
}

function extract_month_from_date() {
    DATE=$1
    DELIMITER=$2
    echo $DATE | cut -d "$DELIMITER" -f 2
}

function extract_day_from_date() {
    DATE=$1
    DELIMITER=$2
    echo $DATE | cut -d "$DELIMITER" -f 3
}

function join_date() {
    YEAR=$1
    MONTH=$2
    DAY=$3
    DELIMITER=$4
    echo "$YEAR$DELIMITER$MONTH$DELIMITER$DAY"
}

function get_current_date_compact() {
    echo $(date +%Y%m%d)
}
function get_current_date_dash() {
    echo $(date +%Y-%m-%d)
}
function get_current_date_underscore() {
    echo $(date +%Y_%m_%d)
}

function get_wlan_ip() {
    echo $(/usr/sbin/ifconfig wlan0 | grep inet | tr ' ' "\n" | grep 192 | head -n 1)
}

function get_machine_name() {
    MY_IP=$(get_wlan_ip)
    if [ "$MY_IP" = "192.168.0.45" ]; then
        echo "PiZero"
    elif [ "$MY_IP" = "192.168.0.206" ]; then
        echo "RaspberryPi2"
    elif [ "$MY_IP" = "192.168.0.80" ]; then
        echo "RaspberryPi4"
    else
        echo "Unknown"
    fi
}

function ensure_directory_exists() {
    if [ ! -d "$1" ]; then
      mkdir -p "$1";
    fi
}
