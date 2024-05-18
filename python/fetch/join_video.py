import glob
import os
import sys
from datetime import datetime

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from utils.OsProcess import OsProcess

# motion - captured video resolution
width = 640
height = 480

current_time = datetime.now()
year = current_time.strftime("%Y")
month = current_time.strftime("%m")
day = current_time.strftime("%d")

current_date_str_out = f"{year}_{month}_{day}"
if len(sys.argv) == 4:
    year = sys.argv[1]
    month = sys.argv[2]
    day = sys.argv[3]
    current_date_str_out = f"{year}_{month}_{day}"

day = 21
glob_pattern = f'*{year}?{month}?{day}*'
if len(sys.argv) == 2:
    glob_pattern = f'*.mkv'

glob_pattern = f'{year}{month}{day}_*.h264'

filenames = sorted(glob.glob(glob_pattern), key=os.path.getmtime)
current_path = os.path.abspath("").replace("\\", "/")
print(glob_pattern)
print(current_path)

def try_remove(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

files_file = "ffmpeg_join_input.txt"
full_files_file = f"{current_path}/{files_file}"
try_remove(full_files_file)
with open(files_file, "wb") as outfile:
    for filename in filenames:
        if "_scaled" in filename or "_dedup" in filename or ".ts" in filename:
            continue
        outfile.write(f"file '{current_path}/{filename}.ts'\n".encode())
        # ffmpeg -i file1.mp4 -c copy -bsf:v h264_mp4toannexb -f mpegts fileIntermediate1.ts
        if not os.path.exists(f"{current_path}/{filename}.ts"):
            command_line = f"ffmpeg -i {filename} -c copy -bsf:v h264_mp4toannexb -f mpegts {filename}.ts"
            OsProcess.execute(command_line)

# ffmpeg -i "concat:fileIntermediate1.ts|fileIntermediate2.ts" -c copy -bsf:a aac_adtstoasc mergedVideo.mp4
full_joined_video_path = f"{current_path}/{current_date_str_out}.mp4"
command_line = f"ffmpeg -y -safe 0 -f concat -i {files_file} -c copy -bsf:a aac_adtstoasc {full_joined_video_path}"
print(command_line)
OsProcess.execute(command_line)

# "ffmpeg -i input.avi -s 720x480 -c:a copy output.mkv"
full_scaled_video_path = f"{current_path}/{current_date_str_out}_scaled.mp4"
command_line = f"ffmpeg -y -i {full_joined_video_path} -s {width}x{height} -c:a copy {full_scaled_video_path}"
print(command_line)
#OsProcess.execute(command_line)
#try_remove(full_joined_video_path)

# "ffmpeg -i input.mp4 -vf mpdecimate -vsync vfr out.mp4"
full_dedup_video_path = f"{current_path}/{current_date_str_out}_scaled_dedup.mp4"
#command_line = f"ffmpeg -y -i {full_scaled_video_path} -vf mpdecimate -fps_mode vfr {full_dedup_video_path}"
command_line = f"ffmpeg -y -i {full_joined_video_path} -vf mpdecimate -fps_mode vfr {full_dedup_video_path}"
print(command_line)
#OsProcess.execute(command_line)
#try_remove(full_scaled_video_path)

for filename in filenames:
    if "_scaled" in filename or "_dedup" in filename:
        continue
    ts_file = f"{current_path}/{filename}.ts"
    try_remove(ts_file)

try_remove(full_files_file)
