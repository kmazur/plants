import os
import subprocess
from datetime import datetime, timedelta

STORAGE_PATH_WIN = "C:" + os.sep + os.path.join("WORK", "tmp")
STORAGE_PATH_GIT_BASH = "/c/WORK/tmp"
GIT_BASH_EXECUTABLE = "C:" + os.sep + os.path.join("Program Files", "Git", "git-bash.exe")
PRIV_KEY_PATH = '$HOME/.ssh/id_rsa_pi'

DEFAULT_USER = "user"
DEFAULT_RSYNC_ROOT_PATH = f"/home/{DEFAULT_USER}/WORK/tmp/camera"
SOURCES = [
    {"name": "RaspberryPi", "host": "192.168.0.80", "user": DEFAULT_USER, "rsync": DEFAULT_RSYNC_ROOT_PATH + "/{date}", "to": "."},
    # {"name": "PiZero", "host": "192.168.0.45", "user": DEFAULT_USER, "rsync": DEFAULT_RSYNC_ROOT_PATH + "/{date}", "to": "."},
    {"name": "RaspberryPi2", "host": "192.168.0.206", "user": DEFAULT_USER, "rsync": f"/home/{DEFAULT_USER}/WORK/tmp/vid/", "to": "{date}"}
]

currentTime = datetime.now()
currentDateStr = currentTime.strftime("%Y-%m-%d")

yesterday = datetime.today() - timedelta(days=1)
dayBeforeYesterday = datetime.today() - timedelta(days=2)
yesterdayStr = yesterday.strftime("%Y-%m-%d")
dayBeforeYesterdayStr = yesterday.strftime("%Y-%m-%d")


for i in range(0, 1):
    currentTime = datetime.now()
    currentDateStr = currentTime.strftime("%Y-%m-%d")
    idate = datetime.today() - timedelta(days=i)
    date = idate.strftime("%Y-%m-%d")

    for source in SOURCES:
        name = source["name"]
        fullStoragePath = os.path.join(STORAGE_PATH_WIN, name, date)
        command_line = f"mkdir {fullStoragePath}"
        print(command_line)
        pipe = subprocess.Popen(command_line, shell=True, stdout=subprocess.PIPE).stdout
        pipe.close()

    # rsync + git-bash command:
    for source in SOURCES:
        name = source["name"]
        user = source["user"]
        host = source["host"]
        rsyncRoot = source["rsync"]
        rsyncTo = source["to"]

        fullStoragePath = f'{STORAGE_PATH_GIT_BASH}/{name}'
        if rsyncTo != ".":
            fullStoragePath = f'{STORAGE_PATH_GIT_BASH}/{name}/{rsyncTo}'

        rsyncDir = rsyncRoot.replace("{date}", date)
        fullStoragePath = fullStoragePath.replace("{date}", date)

        rsyncCommand = f'cd {fullStoragePath}; rsync -Pav --include="*{date}*" -e \\\"ssh -i {PRIV_KEY_PATH}\\\" {user}@{host}:{rsyncDir} ./'
        command = f'"{GIT_BASH_EXECUTABLE}" -c "{rsyncCommand}"'
        print("Command to rsync: " + command)

        pipe = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).stdout
        output = pipe.read().decode()
        print(output)
        pipe.close()
