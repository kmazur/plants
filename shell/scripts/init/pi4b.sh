#!/bin/bash

source "/home/user/WORK/workspace/plants/shell/.profile"
# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

log "Initializing '$MACHINE_NAME'"

if ! grep "dtoverlay=imx477,vcm" "$CONFIG_FILE" &> /dev/null; then
  cd ~
  rm -rf imx477_dtb_test &> /dev/null
  mkdir imx477_dtb_test

  cd imx477_dtb_test
  wget https://github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/Arducam_pivariety_v4l2_v1.0/imx477_rpi_dtoverlay.tar.gz
  tar xzvf imx477_rpi_dtoverlay.tar.gz
  cd imx477_rpi_dtoverlay/
  ./build_and_install.sh
  cd ~

  CONFIG_FILE="/boot/config.txt"
  sudo sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' "$CONFIG_FILE"
  echo "dtoverlay=imx477,vcm" | sudo tee -a "$CONFIG_FILE" > /dev/null
fi

