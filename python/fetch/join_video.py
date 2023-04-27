import glob
import os
import subprocess
import sys
from datetime import datetime

width = 640
height = 480

current_time = datetime.now()
current_date_str = current_time.strftime("%Y%m%d")
current_date_str_out = current_time.strftime("%Y_%m_%d")
if len(sys.argv) > 1:
    current_date_str = sys.argv[1] + "" + sys.argv[2] + "" + sys.argv[3]
    current_date_str_out = sys.argv[1] + "_" + sys.argv[2] + "_" + sys.argv[3]

glob_pattern = f'*{current_date_str}*.mp4'
filenames = glob.glob(glob_pattern)
current_path = os.path.abspath("").replace("\\", "/")
print(glob_pattern)
print(current_path)

files_file = "ffmpeg_join_input.txt"
os.remove(f"{current_path}/{files_file}")
with open(files_file, "wb") as outfile:
    for filename in filenames:
        if "_scaled" in filename or "_dedup" in filename:
            continue
        outfile.write(f"file '{current_path}/{filename}.ts'\n".encode())
        # ffmpeg -i file1.mp4 -c copy -bsf:v h264_mp4toannexb -f mpegts fileIntermediate1.ts
        if not os.path.exists(f"{current_path}/{filename}.ts"):
            command_line = f"ffmpeg -i {filename} -c copy -bsf:v h264_mp4toannexb -f mpegts {filename}.ts"
            pipe = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout
            output = pipe.read().decode()
            pipe.close()


# ffmpeg -i "concat:fileIntermediate1.ts|fileIntermediate2.ts" -c copy -bsf:a aac_adtstoasc mergedVideo.mp4
command_line = f"ffmpeg -y -safe 0 -f concat -i {files_file} -c copy -bsf:a aac_adtstoasc {current_path}\\{current_date_str_out}.mp4"
print(command_line)

pipe = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout
output = pipe.read().decode()
pipe.close()

# "ffmpeg -i input.avi -s 720x480 -c:a copy output.mkv"
command_line = f"ffmpeg -y -i {current_path}\\{current_date_str_out}.mp4 -s {width}x{height} -c:a copy {current_path}\\{current_date_str_out}_scaled.mp4"
print(command_line)

pipe = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout
output = pipe.read().decode()
pipe.close()

# "ffmpeg -i input.mp4 -vf mpdecimate -vsync vfr out.mp4"
command_line = f"ffmpeg -y -i {current_path}\\{current_date_str_out}_scaled.mp4 -vf mpdecimate -vsync vfr {current_path}\\{current_date_str_out}_scaled_dedup.mp4"
print(command_line)

pipe = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout
output = pipe.read().decode()
pipe.close()

for filename in filenames:
    if "_scaled" in filename or "_dedup" in filename:
        continue
    os.remove(f"{current_path}/{filename}.ts")

os.remove(f"{current_path}/{files_file}")