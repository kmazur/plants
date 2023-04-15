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
sudo apt-get -y install git vim htop pigpio screen imagemagick

echo "INSTALLING: "
echo "- python lib: w1thermsensor"
echo "- python lib: influxdb-client"
echo "- python lib: python-tsl2591"
sudo pip3 install w1thermsensor
sudo pip3 install influxdb-client
sudo pip3 install python-tsl2591

echo "MAKING DIR STRUCTURE:"
WORK_DIR="$HOME/WORK"
mkdir -p "$WORK_DIR/tmp"
mkdir -p "$WORK_DIR/config"
mkdir -p "$WORK_DIR/workspace"
touch "$WORK_DIR/config/config.ini"

wget https://raw.githubusercontent.com/kmazur/plants/main/meta/git-update.sh
chmod +x git-update.sh
./git-update.sh
rm git-update.sh