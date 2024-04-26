from python_tsl2591 import tsl2591
import os
import subprocess
import time

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

bucket = "main"
org = "Main"
token = os.environ['INFLUX_DB_TOKEN']
url = "http://34.122.138.205:8086"

client = influxdb_client.InfluxDBClient(
    url=url,
    token=token,
    org=org
)

write_api = client.write_api(write_options=SYNCHRONOUS)

tsl = tsl2591()


while True:
    try:
        # {'lux': 514.892736, 'full': 19038, 'ir': 7761, 'gain': 16, 'integration_time': 1}
        data = tsl.get_current()
        print("Current Light measurement: " + str(data))
        p = influxdb_client.Point("light_measurement").tag("location", "Warsaw").tag("model", "RaspberryPi Zero W").field("light_lux", data["lux"])
        write_api.write(bucket=bucket, org=org, record=p)
        p = influxdb_client.Point("light_measurement").tag("location", "Warsaw").tag("model", "RaspberryPi Zero W").field("light_full", data["full"])
        write_api.write(bucket=bucket, org=org, record=p)
        p = influxdb_client.Point("light_measurement").tag("location", "Warsaw").tag("model", "RaspberryPi Zero W").field("light_ir", data["ir"])
        write_api.write(bucket=bucket, org=org, record=p)
        time.sleep(5)
    except Exception as e:
        print("Exception!")
        print(e)
        continue
