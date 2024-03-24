import os
import subprocess
import sys
import time
import board
import adafruit_ahtx0

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from utils.Config import Config

config = Config()

bucket = "main"
org = "Main"
token = config.get("influx.token")
url = config.get("influx.url")
machine_name = config.get("name")

client = influxdb_client.InfluxDBClient(
    url=url,
    token=token,
    org=org
)

write_api = client.write_api(write_options=SYNCHRONOUS)


# Create sensor object, communicating over the board's default I2C bus
i2c = board.I2C()  # uses board.SCL and board.SDA
sensor = adafruit_ahtx0.AHTx0(i2c)

while True:
    try:
        temp = sensor.temperature
        humidity = sensor.relative_humidity
        print("Current sensor temperature: " + str(temp))
        print("Current sensor humidity: " + str(humidity))
        p = influxdb_client.Point("temp_measurement").tag("location", "Warsaw").tag("machine_name", machine_name).field("temperature", temp)
        write_api.write(bucket=bucket, org=org, record=p)
        p = influxdb_client.Point("humidity_measurement").tag("location", "Warsaw").tag("machine_name", machine_name).field("humidity", humidity)
        write_api.write(bucket=bucket, org=org, record=p)
        time.sleep(10)
    except Exception as e:
        print("Exception!")
        print(e)
