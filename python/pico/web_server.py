import socket
from time import sleep

import network


class WebServer:
    def __init__(self, handler, ssid, password, port=80):
        self.handler = handler
        self.ssid = ssid
        self.password = password
        self.port = port

        self.wlan = None
        self.connection = None

    def start(self):
        self._connect()
        self._open_socket(self.ip, self.port)
        self._serve()

    def _connect(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.password)
        while not self.wlan.isconnected():
            print('Waiting for connection...')
            sleep(1)
        self.ip = self.wlan.ifconfig()[0]
        print(f'Connected on {self.ip}')
        return self.ip

    def _open_socket(self, ip, port=80):
        self.address = (ip, port)
        self.connection = socket.socket()
        self.connection.bind(self.address)
        self.connection.listen(1)

    def _serve(self):
        while True:
            client, addr = self.connection.accept()
            print('Client connected from:', addr)
            data = str(client.recv(1024))
            request = None
            try:
                s = data.split()
                request = {
                    "method": str(s[0].split("'")[1]),
                    "path": str(s[1]),
                    "httpVersion": str(s[2].split("\\r")[0]),
                    "host": s[3].split("\\r")[0],
                    "raw": data[2:len(data) - 1].split("\\r\\n")
                }
            except IndexError:
                pass

            response = self.handler(request)

            client.send('HTTP/1.1 200 OK\r\nContent-type: text/html\r\n\r\n')
            client.send(response)
            client.close()
