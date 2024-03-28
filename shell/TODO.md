- Zestawić kamerę na budkę z zewnątrz
- Audio recording:
  - [V] zapisać skrypty recordingowe
  - [V] poprawić skoki przy włączaniu (długie nagrania?) -> automatic segment in arecord
  - [V] zmienić bitrate - optymalniejszy
  - usuwać gdzie nie wykryto żadnych dźwięków (lub bardzo ciche)
  - usunąć inicjalny skok dźwięku
  - [V] rollować / crontab -e skrypt record-audio
- Video recording - CTRL
  - Fix focus - try different lens-position
  - 
- Video recording - IR
- Video recording - general
  - [V] włączać i wyłączać IR vs CTRL nocą
  - Zapisywać widoczną jasność - i uploadować do grafany
  - Automatyczne wykrywanie eventów na AORUS
- Shell/env improvements
  - zintegrować skrypty crontab się z lib.sh
  - automatycznie ustawiać datę + timezone
    - [V] sudo timedatectl set-timezone Australia/Sydney
- Reporting
  - Dodać wykryte eventy do grafany jako alerty?
    - Może dodać jako heatmap/timemap?
  - Wrzucać do "kolejki" / pliku co do wysłania jest do influxdb i okresowo wysyłać batchami 
- Control
  - Force video disable/enable
  - Force video publish by mediamtx (remotely as well?)
  - Take screenshot

- General
  - [V] Lower sampling rate for taking temp measurements etc.
  - Wypróbować Rusta vs C / C++
  - [V] Reboot on > 80 C temperature
  - Reboot automatically every night
  - UPGRADE influxdb & Grafana -> use docker?
  - 80+ C problem
    - scale publication to grafana
  - Report on the disk/io/netstat/etc. from Raspberry Pi
  - Init
    - Cron fill




#Disable Power LED (Red)
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=off
#Disable Activity LED (Green)
dtparam=act_led_trigger=none
dtparam=act_led_activelow=on
#Disable LAN LEDs
dtparam=eth_led0=14
dtparam=eth_led1=14