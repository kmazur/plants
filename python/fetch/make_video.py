import glob
import os
import subprocess
import sys

filenames = glob.glob('*.jpg')
current_path = os.path.abspath("").replace("\\", "/")
output_file_name = "output"

print(current_path)
fps = 30
if len(sys.argv) > 1:
    fps = int(sys.argv[1])
duration = 1.0 / fps

with open("ffmpeg_input.txt", "wb") as outfile:
    for filename in filenames:
        outfile.write(f"file '{current_path}/{filename}'\n".encode())
        outfile.write(f"duration {duration}\n".encode())

command_line = f"ffmpeg -y -f {fps} -f concat -safe 0 -i ffmpeg_input.txt -c:v libx265 -pix_fmt yuv420p {current_path}\\{output_file_name}.mp4"
print(command_line)

pipe = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout
output = pipe.read().decode()
pipe.close()


# "ffmpeg -i input.avi -s 720x480 -c:a copy output.mkv"
command_line = f"ffmpeg -y -i {current_path}\\{output_file_name}.mp4 -s 720x480 -c:a copy {current_path}\\{output_file_name}_scaled.mp4"
print(command_line)

pipe = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout
output = pipe.read().decode()
pipe.close()
