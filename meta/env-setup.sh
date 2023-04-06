#!/bin/bash

echo "INSTALLING:"
echo "- vim"
echo "- htop"
echo "- pigpio"
echo "- screen"
sudo apt-get -y install vim htop pigpio screen

echo "INSTALLING: "
echo "- python lib: w1thermsensor"
sudo pip3 install w1thermsensor

wget https://raw.githubusercontent.com/kmazur/plants/main/meta/git-update.sh
chmod +x git-update.sh
./git-update.sh
rm git-update.sh