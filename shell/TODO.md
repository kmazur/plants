- Zestawić kamerę na budkę z zewnątrz
- Audio recording:
  - zapisać skrypty recordingowe
  - poprawić skoki przy włączaniu (długie nagrania?) -> automatic segment in arecord
  - zmienić bitrate - optymalniejszy
  - usuwać gdzie nie wykryto żadnych dźwięków (lub bardzo ciche)
- Video recording - CTRL
  - Fix focus - try different lens-position
  - 
- Video recording - IR
- Video recording - general
  - włączać i wyłączać IR vs CTRL nocą
  - Zapisywać widoczną jasność - i uploadować do grafany
  - Automatyczne wykrywanie eventów na AORUS
- Shell/env improvements
  - zintegrować skrypty crontab się z lib.sh
  - automatycznie ustawiać datę + timezone
    - sudo timedatectl set-timezone Australia/Sydney
- Reporting
  - Dodać wykryte eventy do grafany jako alerty?
    - Może dodać jako heatmap/timemap?
  - 
- Control
  - Force video disable/enable
  - Force video publish by mediamtx (remotely as well?)
  - Take screenshot

- General
  - Lower sampling rate for taking temp measurements etc.







#Disable Power LED (Red)
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=off
#Disable Activity LED (Green)
dtparam=act_led_trigger=none
dtparam=act_led_activelow=on
#Disable LAN LEDs
dtparam=eth_led0=14
dtparam=eth_led1=14