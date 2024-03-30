#!/bin/bash

# Disable BlueTooth
BLUETOOTH_DISABLE="$(sudo cat "/boot/config.txt" | grep "dtoverlay=pi3-disable-bt")"
if [ -z "$BLUETOOTH_DISABLE" ]; then
  echo "dtoverlay=pi3-disable-bt" | sudo tee -a "/boot/config.txt"
fi

# Disable POWER LED

ACT_LED_TRIGGER="$(sudo cat "/boot/config.txt" | grep "dtparam=act_led_trigger=")"
if [ -z "$ACT_LED_TRIGGER" ]; then
  echo "dtparam=act_led_trigger=none" | sudo tee -a "/boot/config.txt"
fi

ACT_LED_ACTIVELOW="$(sudo cat "/boot/config.txt" | grep "dtparam=act_led_activelow=")"
if [ -z "$ACT_LED_ACTIVELOW" ]; then
  echo "dtparam=act_led_activelow=on" | sudo tee -a "/boot/config.txt"
fi

# Disable HDMI
sudo /usr/bin/tvservice -o
# ENABLE:
# sudo /usr/bin/tvservice -p


# Disable LAN/USB
echo '1-1' |sudo tee /sys/bus/usb/drivers/usb/unbind
# ENABLE:
# echo '1-1' |sudo tee /sys/bus/usb/drivers/usb/bind


# Update crontab
add_crontab_entry '0 0 * * * sudo reboot -h now'
add_crontab_entry '*/5 * * * * /home/user/WORK/workspace/plants/shell/cron/run_periodic_check.sh "temp-fail-safe" 20 60'
add_crontab_entry '*/5 * * * * /home/user/WORK/workspace/plants/shell/cron/run_periodic_check.sh "report-cpu-temp" 20 120'
