from subprocess import call
import time

path = '/home/user/WORK/workspace/plants/python/camera'
executable = 'take_picture_timestamped.py'
command = 'python ' + path + '/' + executable

while True:
    call([command], shell=True)
    time.sleep(10)
