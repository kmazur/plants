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
export AUDIO_DIR="$TMP_DIR/audio"
export LOGS_DIR="$WORK_DIR/logs"
export BIN_DIR="$WORK_DIR/bin"
export USER_BIN_DIR="$HOME/bin"
export REPO_DIR="$WORK_DIR/workspace/plants"

export CONFIG_INI="$CONFIG_DIR/config.ini"
export LIB_INIT_FILE="$REPO_DIR/shell/scripts/lib/lib.sh"

export ENV_INITIALIZED="true"

MACHINE_NAME="$(grep "name=" "$CONFIG_DIR/config.ini" | cut -f 2 -d='')"

export PS1="\[\e[32m\][$MACHINE_NAME][\w]\$\[\e[m\] "

set_terminal_title() {
    echo -ne "\033]0;"$1"\007"
}
function get_wlan_ip() {
    /usr/sbin/ifconfig wlan0 | grep inet | tr ' ' "\n" | grep 192 | head -n 1
}
set_terminal_title "$MACHINE_NAME ($(get_wlan_ip))"

# Fix for 8bit colors in vim colorscheme
if [ "$TERM" = xterm ]; then
    TERM="xterm-256color";
fi
