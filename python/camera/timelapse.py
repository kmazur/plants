from subprocess import call

path = '/home/user/WORK/workspace/plants/python/camera'
executable = 'take_picture_timestamped.py'
command = path + '/' + executable

while True:
    call([command], shell=True)
