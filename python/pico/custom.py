from tsl import get_lux
from web_server import WebServer
from machine import Pin

pico_led = Pin("LED", Pin.OUT)

ssid = 'UPC3639547'
password = ''

def handler(request):
    return "response"

web_server = WebServer(handler, ssid, password)

try:
    web_server.start()
except KeyboardInterrupt:
    machine.reset()

