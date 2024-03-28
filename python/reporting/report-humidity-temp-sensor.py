import os
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

min_period = 30
if len(sys.argv) > 1:
    min_period = int(sys.argv[1])

max_period = 300
if len(sys.argv) > 2:
    max_period = int(sys.argv[2])

period = config.get_scaled_inverse_value(min_period, max_period)

while True:
    try:
        if not config.is_suspended():
            temp = sensor.temperature
            humidity = sensor.relative_humidity
            print("Current sensor temperature: " + str(temp))
            print("Current sensor humidity: " + str(humidity))
            p1 = influxdb_client.Point("temp_measurement").tag("location", "Warsaw").tag("machine_name", machine_name).field("temperature", temp)
            p2 = influxdb_client.Point("humidity_measurement").tag("location", "Warsaw").tag("machine_name", machine_name).field("humidity", humidity)
            write_api.write(bucket=bucket, org=org, record=[p1, p2])
        else:
            print("Sensor measurements are suspended")

        period = config.get_scaled_inverse_value(min_period, max_period)
        time.sleep(period)
    except Exception as e:
        print("Exception!")
        print(e)
        break
