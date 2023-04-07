import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import subprocess
import time
import os

bucket = "main"
org = "Main"
token = os.environ['INFLUX_DB_TOKEN']
url="http://34.122.138.205:8086"

client = influxdb_client.InfluxDBClient(
   url=url,
   token=token,
   org=org
)

write_api = client.write_api(write_options=SYNCHRONOUS)

def getCpuTemp():
    with subprocess.Popen(["vcgencmd", "measure_temp"], stdout=subprocess.PIPE) as proc:
        output = str(proc.stdout.read())

        start = output.index("=") + 1
        end = output.index("'")
        temp = output[start:end]
        return float(temp)


while True:
    try:
        temp = getCpuTemp()
        print ("Current CPU temperature: " + str(temp))
        p = influxdb_client.Point("cpu_measurement").tag("location", "Warsaw").tag("model", "RaspberryPi 4 B").field("cpu_temperature", temp)
        write_api.write(bucket=bucket, org=org, record=p)
        time.sleep(10)
    except Exception as e:
        print("Exception!")
        print(e)
        continue
