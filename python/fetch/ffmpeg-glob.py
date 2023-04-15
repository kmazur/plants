import subprocess
import glob
import os
import sys

filenames = glob.glob('*.jpg')
current_path = os.path.abspath("").replace("\\", "/")
print(current_path)
fps = 30
if len(sys.argv) > 1:
    fps = int(sys.argv[1])
duration = 1.0/fps

with open("ffmpeg_input.txt", "wb") as outfile:
    for filename in filenames:
        outfile.write(f"file '{current_path}/{filename}'\n".encode())
        outfile.write(f"duration {duration}\n".encode())

command_line = f"ffmpeg -f {fps} -f concat -safe 0 -i ffmpeg_input.txt -c:v libx265 -pix_fmt yuv420p {current_path}\\output.mp4"
print(command_line)

pipe = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout
output = pipe.read().decode()
pipe.close()
