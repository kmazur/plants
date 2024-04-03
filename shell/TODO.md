- Zestawić kamerę na budkę z zewnątrz
- Audio recording:
  - [V] zapisać skrypty recordingowe
  - [V] poprawić skoki przy włączaniu (długie nagrania?) -> automatic segment in arecord
  - [V] zmienić bitrate - optymalniejszy
  - usuwać gdzie nie wykryto żadnych dźwięków (lub bardzo ciche)
  - usunąć inicjalny skok dźwięku
  - [V] rollować / crontab -e skrypt record-audio
  - wykrywać dźwięki i je wycinać - nie brać pod uwagę skoków z błędów nagrywania
  - Rollować per dzień audio -> record only today & process today & yesterday
- Video recording - CTRL
  - Fix focus - try different lens-position
- Video recording - IR
- Video recording - general
  - [V] włączać i wyłączać IR vs CTRL nocą
  - [V] Zapisywać widoczną jasność - i uploadować do grafany
  - Automatyczne wykrywanie eventów na AORUS
  - Dodać rolowanie per dzień
- Shell/env improvements
  - [V] zintegrować skrypty crontab się z lib.sh
  - [V] automatycznie ustawiać datę + timezone
    - [V] sudo timedatectl set-timezone Europe/Warsaw
- Reporting
  - Dodać wykryte eventy do grafany jako alerty?
    - Może dodać jako heatmap/timemap?
  - Wrzucać do "kolejki" / pliku co do wysłania jest do influxdb i okresowo wysyłać batchami 
  - scale publication to grafana
  - move cpu freq reporting to cpu measurements & cpu temp reporting script
- Control
  - Force video disable/enable
  - Force video publish by mediamtx (remotely as well?)
  - [V] Take screenshot

- General
  - Update git repo & reinitialize (env + processes) when detected changes
  - restart cron processes easily (bash auto complete support? / choice?)
  - setup rsync
  - All metrics monitoring -> https://grafana.com/docs/grafana-cloud/monitor-infrastructure/integrations/integration-reference/integration-raspberry-pi-node/
    - Report on the disk/io/netstat/memory,freq,etc. from Raspberry Pi
  - [V] Lower sampling rate for taking temp measurements etc.
  - Wypróbować Rusta vs C / C++
  - [V] Reboot on > 80 C temperature
    - Improve reboot on 80 C temp -> when it persists for several cycles or breaches some threshold / increasing
  - [V] Reboot automatically every night
  - UPGRADE influxdb & Grafana -> use docker?
  - alert / events reporting on reboots
  - Init
    - [V] Setup init rc.local 
    - [V] Cron fill
  - Improve logging
    - common to bash & python
    - kibana logs?
  - https://github.com/mcguirepr89/BirdNET-Pi




#Disable Power LED (Red)
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=off
#Disable Activity LED (Green)
dtparam=act_led_trigger=none
dtparam=act_led_activelow=on
#Disable LAN LEDs
dtparam=eth_led0=14
dtparam=eth_led1=14
