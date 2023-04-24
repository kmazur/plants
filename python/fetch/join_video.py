import glob
import os
import subprocess
import sys
from datetime import datetime

current_time = datetime.now()
current_date_str = current_time.strftime("%Y%m%d")

glob_pattern = f'*{current_date_str}*.mp4'
filenames = glob.glob(glob_pattern)
current_path = os.path.abspath("").replace("\\", "/")
print(glob_pattern)
print(current_path)

files_file = "ffmpeg_join_input.txt"
with open(files_file, "wb") as outfile:
    for filename in filenames:
        outfile.write(f"file '{current_path}/{filename}'\n".encode())

command_line = f"ffmpeg -safe 0 -f concat -i {files_file} -c copy {current_path}\\output.mp4"
print(command_line)

pipe = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout
output = pipe.read().decode()
pipe.close()
