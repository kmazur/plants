#!/bin/bash

echo "UPDATING SYSTEM: update & upgrade"
sudo apt-get update
sudo apt-get -y upgrade

echo "INSTALLING:"
echo "- git"
echo "- vim"
echo "- htop"
echo "- pigpio"
echo "- screen"
echo "- imagemagick"
echo "- libcamera-tools"
echo "- python3-opencv"
echo "- motion"
sudo apt-get -y install git vim htop pigpio screen imagemagick libcamera-tools python3-opencv
sudo apt-get -y install motion

echo "INSTALLING: "
echo "- python lib: w1thermsensor"
echo "- python lib: influxdb-client"
echo "- python lib: python-tsl2591"
echo "- python lib: adafruit-circuitpython-tsl2591"
sudo pip3 install w1thermsensor
sudo pip3 install influxdb-client
sudo pip3 install python-tsl2591
sudo pip3 install adafruit-circuitpython-tsl2591

echo "MAKING DIR STRUCTURE:"
WORK_DIR="$HOME/WORK"
mkdir -p "$WORK_DIR/tmp"
mkdir -p "$WORK_DIR/config"
mkdir -p "$WORK_DIR/workspace"
mkdir -p "$WORK_DIR/tmp/Monitoring"

CONFIG_INI="$WORK_DIR/config/config.ini"
touch "$CONFIG_INI"

ARCH=$(uname -a)
if [[ "$ARCH" == *"aarch64"* ]]; then
  camera.width=4608
  camera.height=2592
  camera.hflip=1
  camera.vflip=1
  echo "camera.width=4608" >"$CONFIG_INI"
  echo "camera.height=2592" >>"$CONFIG_INI"
  echo "camera.vflip=1" >>"$CONFIG_INI"
  echo "camera.hflip=1" >>"$CONFIG_INI"
else
  echo "camera.width=2592" >"$CONFIG_INI"
  echo "camera.height=1944" >>"$CONFIG_INI"
  echo "camera.vflip=0" >>"$CONFIG_INI"
  echo "camera.hflip=0" >>"$CONFIG_INI"
fi

wget https://raw.githubusercontent.com/kmazur/plants/main/meta/git-update.sh
chmod +x git-update.sh
./git-update.sh
rm git-update.sh


echo "INSTALLING DRIVE-CLI"
if [ -d "$WORK_DIR/workspace/drive-cli" ]; then
  echo "drive-cli is installed at: $WORK_DIR/workspace/drive-cli"
  cd "$GIT_REPO_DIR" || exit 1
  git reset --hard HEAD
  git clean -x -f
  git pull
else
  cd "$WORK_DIR/workspace" &&
  git clone https://github.com/nurdtechie98/drive-cli.git &&
  cd drive-cli &&
  pip install -e .
fi
