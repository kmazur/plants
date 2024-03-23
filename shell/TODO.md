1. Zrobić 2 otwory na kamery
2. Zrobić 2 otwory na IR LED
3. Zaplanować rozwiązanie
4. Jak przyczepić mocno rozwiązanie?
5. Wywiercić otwory z tyłu do kabla
6. Zabezpieczyć otwory i RPi, etc. przed wilgocią
7. Zlutować rozwiązanie
8. Zrobić 50 fps video


#Disable Power LED (Red)
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=off
#Disable Activity LED (Green)
dtparam=act_led_trigger=none
dtparam=act_led_activelow=on
#Disable LAN LEDs
dtparam=eth_led0=14
dtparam=eth_led1=14