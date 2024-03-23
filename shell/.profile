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
export BIN_DIR="$WORK_DIR/bin"
export USER_BIN="$HOME/bin"

export CONFIG_INI="$CONFIG_DIR/config.ini"

export ENV_INITIALIZED="true"

MACHINE_NAME="$(grep "name=" "$CONFIG_DIR/config.ini" | cut -f 2 -d='')"

export PS1="\e[0;32m[$MACHINE_NAME][\w]\$ \e[0m"