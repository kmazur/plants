#!/bin/bash

function set_terminal_title() {
  local PROMPT="$1"
  echo -ne "\033]0;$PROMPT\007"
}