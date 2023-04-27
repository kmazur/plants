#!/bin/bash

sudo apt-get update
sudo apt-get upgrade -y

sudo apt-get -y install gcc git

echo "REBOOT NOW if run for the first time!"

sudo apt-get -y install dkms

mkdir tmp-tp-link
cd tmp-tp-link

git clone https://github.com/lwfinger/rtl8188eu

cd rtl8188eu/

sudo apt-get -y install make
sudo make all

sudo make install

echo "REBOOT now"
sudo modprobe -r 8188eu
echo "blacklist 8188eu" >> /etc/modprobe.d/blacklist-8188eu.conf
sudo modprobe r8188eu