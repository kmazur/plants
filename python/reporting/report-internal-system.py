import os
import subprocess
import sys
import time

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


def get_cpu_temp():
    with subprocess.Popen(["vcgencmd", "measure_temp"], stdout=subprocess.PIPE) as proc:
        output = str(proc.stdout.read())

        start = output.index("=") + 1
        end = output.index("'")
        temp = output[start:end]
        return float(temp)


while True:
    try:
        temp = get_cpu_temp()
        print("Current CPU temperature: " + str(temp))
        p = influxdb_client.Point("cpu_measurement").tag("location", "Warsaw").tag("machine_name", machine_name).field("cpu_temperature", temp)
        write_api.write(bucket=bucket, org=org, record=p)
        time.sleep(10)
    except Exception as e:
        print("Exception!")
        print(e)
        continue
