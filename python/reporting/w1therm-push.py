import os
import sys
import time

import RPi.GPIO as GPIO
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from w1thermsensor import W1ThermSensor, Sensor

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from utils.Config import Config

config = Config()

# TODO: move this to Config.py
bucket = "main"
org = "Main"
token = config.get("influx.token")
url = "http://34.122.138.205:8086"

client = influxdb_client.InfluxDBClient(
    url=url,
    token=token,
    org=org
)

write_api = client.write_api(write_options=SYNCHRONOUS)

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

try:

    while True:
        try:
            sensors = W1ThermSensor.get_available_sensors([Sensor.DS18B20])
            print("Detected " + str(len(sensors)) + " sensors")
            for sensor in sensors:
                temp = sensor.get_temperature()
                print("Current temperature on sensor: " + str(sensor.id) + " is " + str(temp))

                p = influxdb_client.Point("temp_measurement").tag("sensor_group", "DS18B20").tag("sensor_id",
                                                                                                 str(sensor.id)).tag(
                    "location", "Warsaw").tag("model", "RaspberryPi 4 B").field("temperature", temp)
                write_api.write(bucket=bucket, org=org, record=p)

            time.sleep(10)
        except KeyboardInterrupt:
            print('KeyboardInterrupt detected')
            break
        except Exception as e:
            print('Other error detected - skip: ' + str(e))
            continue

except KeyboardInterrupt:
    print('Koniec')
    GPIO.cleanup()
finally:
    GPIO.cleanup()
