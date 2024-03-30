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

WORK_DIR="/home/$USER/WORK"
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
mkdir -p "$AUDIO_DIR"
mkdir -p "$LOGS_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$USER_BIN_DIR"
mkdir -p "$INFLUX_DIR"

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


# sudo apt-get -y install software-properties-common
# sudo apt-get -y install autoconf
# sudo apt-get -y install libtool
#
# if [ ! -d "$BIN_DIR/mp4fpsmod" ]; then
#   cd "$BIN_DIR"
#   git clone https://github.com/nu774/mp4fpsmod.git
#   cd "mp4fpsmod"
#   ./bootstrap.sh
#   ./configure
#   make
#   strip mp4fpsmod
#   sudo make install
# fi


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
echo "- bc"
sudo apt-get -y install git vim htop pigpio screen imagemagick libcamera-tools python3-opencv jq
sudo apt-get -y install motion
sudo apt-get -y install openjdk-17-jdk
sudo apt-get -y install python3-pip
sudo apt-get -y install bc
sudo apt-get -y install vorbis-tools
sudo apt-get -y install lame
sudo apt-get -y install libopencv-dev


echo "Set timezone to Europe/Warsaw"
sudo timedatectl set-timezone Europe/Warsaw



echo "CONFIGURING VIM"

echo "VIM: Installing autoloader: pathogen"
mkdir -p ~/.vim/autoload ~/.vim/bundle

if [ ! -f "$HOME/.vim/autoload/pathogen.vim" ]; then
  curl -LSso ~/.vim/autoload/pathogen.vim https://tpo.pe/pathogen.vim
fi

function install_vim() {
  local REPO="$1"
  local NAME="$2"
  local DESTINATION="$HOME/.vim/bundle/$NAME"

  if [ -d "$DESTINATION" ]; then
    cd "$DESTINATION" && git reset --hard HEAD && git pull
  else
    git clone "$REPO" "$DESTINATION"
  fi
}
echo "VIM: Installing theme: monokai"
install_vim "https://github.com/sainnhe/sonokai" "sonokai"
mkdir -p "$HOME/.vim/colors" && cp -r "$HOME/.vim/bundle/sonokai/colors" "$HOME/.vim"

echo "VIM: Installing plugin: NERDTree"
install_vim "https://github.com/preservim/nerdtree.git" "nerdtree"
echo "VIM: Installing plugin: EasyMotion"
install_vim "https://github.com/easymotion/vim-easymotion" "vim-easymotion"

echo "VIM: Configuring .vimrc"
cp -f "$REPO_DIR/meta/files/vim/.vimrc" "$HOME"




# echo "INSTALLING mediamtx"
# sudo apt-get install libfreetype6 libcamera0
# ARCH=$(uname -a)

# MEDIAMTX_DIR="$BIN_DIR/mediamtx"
# if [ ! -d "$MEDIAMTX_DIR" ]; then
#   mkdir -p "$MEDIAMTX_DIR"
#   cd "$MEDIAMTX_DIR"
#   if [[ "$ARCH" == *"armv7"* ]]; then
#     wget https://github.com/bluenviron/mediamtx/releases/download/v1.6.0/mediamtx_v1.6.0_linux_armv7.tar.gz
#   else
#     # TODO: switch to arm64 version
#     wget https://github.com/bluenviron/mediamtx/releases/download/v1.6.0/mediamtx_v1.6.0_linux_armv7.tar.gz
#   fi
#
#   tar xzvf mediamtx_v*.tar.gz
#   rm mediamtx_v*.tar.gz 2> /dev/null
#   ln -s "$MEDIAMTX_DIR/mediamtx" "$USER_BIN_DIR/mediamtx"
# fi
# cp -f "$REPO_DIR/meta/files/mediamtx/mediamtx.yml" "$HOME"



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

"$REPO_DIR/meta/compile.sh"

sudo cp -f "$REPO_DIR/meta/files/root/rc.local" "/etc/rc.local"