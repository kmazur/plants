import glob
import os
import sys
from datetime import datetime

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from utils.OsProcess import OsProcess


def try_remove(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)


width = 1920
height = 1080

if len(sys.argv) != 3:
    raise AssertionError("Pass 2 params: year & month")

year = sys.argv[1]
month = sys.argv[2]

glob_pattern = f"{year}*"
print(f"Glob pattern: {glob_pattern}")
glob_filenames = glob.glob(glob_pattern)
month_dirs = sorted(glob_filenames, key=os.path.dirname, reverse=False)
print(f"Month dirs: {month_dirs}")
month_dirs = month_dirs[4:]

ffmpeg_files = []
ffmpeg_files_days = []

for day_dir in month_dirs:
    glob_pattern = f"{day_dir}/*.jpg"
    glob_filenames = glob.glob(glob_pattern)
    day_files = sorted(glob_filenames, key=os.path.getmtime)

    this_day_files = []
    for file in day_files:
        filename_date = file
        include = True
        if file.startswith(f"{day_dir}\\test"):
            modification_time = os.path.getctime(file)
            filename_date = datetime.fromtimestamp(modification_time).strftime('%Y-%m-%d.jpg')
            include = True
        else:
            hour = int(filename_date[-12:-10])
            minute = int(filename_date[-9:-7])
            seconds = int(filename_date[-6:-4])
            day_seconds = seconds + minute * 60 + hour * 60 * 60
            # 4:00 -> 20:30
            if 14400 <= day_seconds <= 73800:
                include = True
            else:
                include = False

        include = True
        if include:
            print(file)
            ffmpeg_files.append(file)
            this_day_files.append(file)
    ffmpeg_files_days.append(this_day_files)

SECONDS_PER_DAY = 10
days_count = len(month_dirs)
movie_seconds = days_count * SECONDS_PER_DAY

ffmpeg_files_result = ffmpeg_files

# override with FPS
fps = 24
ffmpeg_files_result = []
max_files = SECONDS_PER_DAY * fps
for day_files in ffmpeg_files_days:
    ratio = float(len(day_files)) / max_files
    for i in range(0, max_files):
        index = int(i * ratio)
        if index >= len(day_files):
            continue
        file = day_files[index]
        ffmpeg_files_result.append(file)

files_count = len(ffmpeg_files_result)
seconds_per_file = float(movie_seconds) / files_count

current_path = os.path.abspath("").replace("\\", "/")
output_file_name = "output"

files_file = "ffmpeg_input.txt"
full_files_file = f"{current_path}/{files_file}"
try_remove(full_files_file)
with open(files_file, "wb") as outfile:
    for filename in ffmpeg_files_result:
        outfile.write(f"file '{current_path}/{filename}'\n".encode())
        outfile.write(f"duration {seconds_per_file}\n".encode())

full_video_path = f"{current_path}/{output_file_name}.mp4"
command_line = f"ffmpeg -y -r {fps} -f concat -safe 0 -i {files_file} -c:v libx265 -pix_fmt yuv420p {full_video_path}"
print(command_line)
OsProcess.execute(command_line)

# "ffmpeg -i input.avi -s 720x480 -c:a copy output.mkv"
full_scaled_video_path = f"{current_path}\\{output_file_name}_scaled.mp4"
command_line = f"ffmpeg -y -i {full_video_path} -s {width}x{height} -c:a copy {full_scaled_video_path}"
print(command_line)
#OsProcess.execute(command_line)

try_remove(full_files_file)
