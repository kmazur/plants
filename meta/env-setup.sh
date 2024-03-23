#!/bin/bash

echo "UPDATING SSH"
mkdir -p ~/.ssh

echo "UPDATING SYSTEM: update & upgrade"
sudo apt-get update
sudo apt-get -y upgrade

echo "INSTALLING:"
echo "-git"
sudo apt-get install git

wget https://raw.githubusercontent.com/kmazur/plants/main/meta/git-update.sh
chmod +x git-update.sh
./git-update.sh
rm git-update.sh

cp -f "$WORK_DIR/workspace/plants/shell/.profile" "$HOME"
source "$HOME/.profile"


echo "CREATING DIR STRUCTURE:"
mkdir -p "$WORK_DIR"
mkdir -p "$TMP_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOCKS_DIR"
mkdir -p "$WORKSPACE_DIR"
mkdir -p "$REPO_DIR"
mkdir -p "$CAMERA_DIR"
mkdir -p "$VIDEO_DIR"
mkdir -p "$LOGS_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$USER_BIN_DIR"

ARCH=$(uname -a)
if [ ! -f "$CONFIG_INI" ]; then
  echo "name=UNKNOWN" > "$CONFIG_INI"
  if [[ "$ARCH" == *"aarch64"* ]]; then
    echo "camera.width=4608" >>"$CONFIG_INI"
    echo "camera.height=2592" >>"$CONFIG_INI"
    echo "camera.vflip=0" >>"$CONFIG_INI"
    echo "camera.hflip=0" >>"$CONFIG_INI"
  else
    echo "camera.width=2592" >>"$CONFIG_INI"
    echo "camera.height=1944" >>"$CONFIG_INI"
    echo "camera.vflip=0" >>"$CONFIG_INI"
    echo "camera.hflip=0" >>"$CONFIG_INI"
  fi
fi





echo "INSTALLING:"
echo "- git"
echo "- vim"
echo "- htop"
echo "- pigpio"
echo "- screen"
echo "- imagemagick"
echo "- libcamera-tools"
echo "- python3-opencv"
echo "- jq"
echo "- motion"
echo "- openjdk-17-jdk"
sudo apt-get -y install git vim htop pigpio screen imagemagick libcamera-tools python3-opencv jq
sudo apt-get -y install motion
sudo apt-get -y install openjdk-17-jdk
sudo apt-get -y install python3-pip


echo "INSTALLING mediamtx"
sudo apt-get install libfreetype6 libcamera0
ARCH=$(uname -a)

MEDIAMTX_DIR="$BIN_DIR/mediamtx"
mkdir -p "$MEDIAMTX_DIR"
cd "$MEDIAMTX_DIR"
if [[ "$ARCH" == *"armv7"* ]]; then
  wget https://github.com/bluenviron/mediamtx/releases/download/v1.6.0/mediamtx_v1.6.0_linux_armv7.tar.gz
else
  # TODO: switch to arm64 version
  wget https://github.com/bluenviron/mediamtx/releases/download/v1.6.0/mediamtx_v1.6.0_linux_armv7.tar.gz
fi

tar xzvf mediamtx_v*.tar.gz
rm mediamtx_v*.tar.gz 2> /dev/null
ln -s "$MEDIAMTX_DIR/mediamtx" "$USER_BIN_DIR/mediamtx"
cp "$REPO_DIR/meta/files/mediamtx/mediamtx.yml" "$HOME"



#echo "INSTALLING:"
#echo "- signal"
#export VERSION=0.11.9.1
#wget https://github.com/AsamK/signal-cli/releases/download/v"${VERSION}"/signal-cli-"${VERSION}"-Linux.tar.gz
#sudo tar xf signal-cli-"${VERSION}"-Linux.tar.gz -C /opt
#sudo ln -sf /opt/signal-cli-"${VERSION}"/bin/signal-cli /usr/local/bin/

# echo "INSTALLING: "
# echo "- python lib: w1thermsensor"
# sudo pip3 install w1thermsensor

echo "- python lib: influxdb-client"
sudo pip3 install influxdb-client

# echo "- python lib: python-tsl2591"
# sudo pip3 install python-tsl2591

# echo "- python lib: adafruit-circuitpython-tsl2591"
# sudo pip3 install adafruit-circuitpython-tsl2591

# echo "- python lib: Adafruit I2S MEMS Microphone"
# sudo pip3 install --upgrade adafruit-python-shell
# wget https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/i2smic.py
# sudo python3 i2smic.py

# echo "INSTALLING DRIVE-CLI"
# if [ -d "$WORK_DIR/workspace/drive-cli" ]; then
#   echo "drive-cli is installed at: $WORK_DIR/workspace/drive-cli"
#   cd "$GIT_REPO_DIR" || exit 1
#   git reset --hard HEAD
#   git clean -x -f
#   git pull
# else
#   cd "$WORK_DIR/workspace" &&
#   git clone https://github.com/nurdtechie98/drive-cli.git &&
#   cd drive-cli &&
#   pip3 install -e .
# fi

# sudo apt-get install postfix