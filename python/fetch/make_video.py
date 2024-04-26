import glob
import os
import sys

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from utils.OsProcess import OsProcess

width = 1024
height = 768

glob_pattern = '*.jpg'
glob_filenames = glob.glob(glob_pattern)
filenames = sorted(glob_filenames, key=os.path.getmtime)
#filenames = glob_filenames
current_path = os.path.abspath("").replace("\\", "/")
# TODO: output with date
output_file_name = "output"

print(current_path)
fps = 30
if len(sys.argv) > 1:
    fps = int(sys.argv[1])
duration = 1.0 / fps


def try_remove(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)


files_file = "ffmpeg_input.txt"
full_files_file = f"{current_path}/{files_file}"
try_remove(full_files_file)
with open(files_file, "wb") as outfile:
    for filename in filenames:
        size = os.path.getsize(filename)
        if size > 0:
            outfile.write(f"file '{current_path}/{filename}'\n".encode())
            outfile.write(f"duration {duration}\n".encode())

full_video_path = f"{current_path}/{output_file_name}.mp4"
command_line = f"ffmpeg -y -f concat -safe 0 -i {files_file} -c:v libx265 -pix_fmt yuv420p {full_video_path}"
print(command_line)
OsProcess.execute(command_line)

scaled = True
if scaled:
    # "ffmpeg -i input.avi -s 720x480 -c:a copy output.mkv"
    full_scaled_video_path = f"{current_path}\\{output_file_name}_scaled.mp4"
    command_line = f"ffmpeg -y -i {full_video_path} -s {width}x{height} -c:a copy {full_scaled_video_path}"
    print(command_line)
    OsProcess.execute(command_line)

try_remove(full_files_file)
