import datetime
import influxdb_client
import re
import sys
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

bucket = "main"
org = "Main"
token = "PpiZnl05o52wyUEfVyykXe0bpJ7GL52aXAeWa6ZEe702bGuz6mCvsesrBroBSZwi6DkQUQGlthiL2bRV7vBrmQ=="
url = "http://34.133.13.235:8086"
machine_name = "birdbox-ctrl"

client = influxdb_client.InfluxDBClient(
    url=url,
    token=token,
    org=org
)

write_api = client.write_api(write_options=SYNCHRONOUS)


# Volume data
volume_levels_per_second = {}
line_regex = re.compile(r"(\d+\.\d+)\|(-?\d+\.\d+)")

stub = sys.argv[1]

nanos = 0
with open(f"{stub}.txt", "r") as f:
    for line in f:
        nanos = int(line)

if nanos == 0:
    raise "Nanos == 0!"

millis = nanos / 1000000
epoch_seconds = millis / 1000

# Read the FFmpeg output and aggregate volume levels
with open(f"{stub}.pts", "r") as f:
    second = 0
    timestamp = 0.0
    volume_level = 0.0
    first = True
    for line in f:
        if first:
            first = False
            timestamp = float(line)
            second = int(timestamp)
        else:
            first = True
            volume_level = float(line)

            if second not in volume_levels_per_second:
                volume_levels_per_second[second] = [volume_level]
            else:
                volume_levels_per_second[second].append(volume_level)


for second, volume_levels in volume_levels_per_second.items():
    if second < 15:
        continue

    min_volume = min(volume_levels)
    max_volume = max(volume_levels)
    mean_volume = sum(volume_levels) / len(volume_levels)
    last_volume = volume_levels[-1]

    # Convert second to timestamp
    real_timestamp = start + datetime.timedelta(seconds=second)
    timestamp = datetime.datetime.utcfromtimestamp(real_timestamp.timestamp())

    point = Point("audio_analysis") \
        .tag("location", "Warsaw") \
        .tag("machine_name", machine_name) \
        .field("min_volume_level", min_volume) \
        .field("max_volume_level", max_volume) \
        .field("mean_volume_level", mean_volume) \
        .field("volume_level", last_volume) \
        .time(timestamp, WritePrecision.S)
    write_api.write(bucket=bucket, org=org, record=point)

# Close client
client.close()

os.remove(f"{stub}.pts")
os.remove(f"{stub}.txt")