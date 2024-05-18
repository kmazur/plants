import os
import subprocess
import time

STORAGE_PATH_WIN = "C:" + os.sep + os.path.join("WORK", "tmp")
STORAGE_PATH_GIT_BASH = "/c/WORK/tmp"
GIT_BASH_EXECUTABLE = "C:" + os.sep + os.path.join("Program Files", "Git", "git-bash.exe")
PRIV_KEY_PATH = '$HOME/.ssh/id_rsa_pi'

DEFAULT_USER = "user"
DEFAULT_RSYNC_ROOT_PATH = f"/home/{DEFAULT_USER}/WORK/tmp/camera"

while True:
    command = "python C:\\Users\\mazur\\IdeaProjects\\plants\\python\\fetch\\fetch.py"
    print(command)
    pipe = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).stdout
    output = pipe.read().decode()
    print(output)
    pipe.close()
    time.sleep(5)
