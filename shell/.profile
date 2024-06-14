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

export BASE_DIR="/home/$USER"
export WORK_DIR="$BASE_DIR/WORK"
export TMP_DIR="$WORK_DIR/tmp"
export CONFIG_DIR="$WORK_DIR/config"
export LOCKS_DIR="$TMP_DIR/locks"
export WORKSPACE_DIR="$WORK_DIR/workspace"
export REPO_DIR="$WORKSPACE_DIR/plants"
export CAMERA_DIR="$TMP_DIR/camera"
export VIDEO_DIR="$TMP_DIR/vid"
export VIDEO_SEGMENT_DIR="$TMP_DIR/vid_segment"
export AUDIO_DIR="$TMP_DIR/audio"
export AUDIO_SEGMENT_DIR="$TMP_DIR/audio_segments"
export LOGS_DIR="$WORK_DIR/logs"
export BIN_DIR="$WORK_DIR/bin"
export REPO_DIR="$WORK_DIR/workspace/plants"
export INIT_DIR="$REPO_DIR/shell/scripts/init"
export INFLUX_DIR="$TMP_DIR/influx"
export PIPELINE_DIR="$TMP_DIR/pipeline"

export CONFIG_INI="$CONFIG_DIR/config.ini"
export LIB_INIT_FILE="$REPO_DIR/shell/scripts/lib/lib.sh"


function _create_env_dirs() {
    local DIRS="$(env | grep "_DIR" | grep "/home/user/" | cut -d '=' -f 2)"
    for DIR in $DIRS; do
        if [ ! -d "$DIR" ]; then
            mkdir -p "$DIR" &> /dev/null
        fi
    done
}
_create_env_dirs

export MACHINE_NAME="$(grep "name=" "$CONFIG_DIR/config.ini" | cut -f 2 -d='')"

# set PATH so it includes WORK bin if it exists
if [ -d "$BIN_DIR" ] ; then
    PATH="$BIN_DIR:$PATH"
fi

export ENV_INITIALIZED="true"

export PS1="\[\e[32m\][$MACHINE_NAME][\w][$?]\$\[\e[m\] "

function setup_shell() {
    local MACHINE_NAME="$1"
    local IP="$(/usr/sbin/ifconfig wlan0 | grep inet | tr ' ' "\n" | grep 192 | head -n 1 2> /dev/null)"
    echo -ne "\033]0;$MACHINE_NAME ($IP)\007"
}
setup_shell "$MACHINE_NAME"

# Fix for 8bit colors in vim colorscheme
if [ "$TERM" = xterm ]; then
    TERM="xterm-256color";
fi

shopt -s direxpand

function update_repo() {
    "$REPO_DIR/meta/git-update.sh"
    cp -f "$WORK_DIR/workspace/plants/shell/.profile" "$HOME"
    cp -f "$REPO_DIR/meta/files/vim/.vimrc" "$HOME"
    source "$HOME/.profile"
}

function compile_native() {
    "$REPO_DIR/meta/compile.sh"
}

source "$LIB_INIT_FILE"

function goto() {
    local WHAT="$1"
    if [[ "$WHAT" == "192.168.0.80" || "$WHAT" == "pi4b" ]]; then
        ssh "192.168.0.80"
    elif [[ "$WHAT" == "192.168.0.199" || "$WHAT" == "ctrl" ]]; then
        ssh "192.168.0.199"
    elif [[ "$WHAT" == "192.168.0.18" || "$WHAT" == "ir" ]]; then
        ssh "192.168.0.18"
    fi
}

alias cdll="cd \$(get_logs_dir)"