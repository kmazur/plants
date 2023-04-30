import os
import sys
from datetime import datetime, timedelta

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from utils.OsProcess import OsProcess

if os.name == 'nt':
    STORAGE_PATH = "C:/WORK/tmp"
    LOCAL_REPO_PATH = "C:/Users/mazur/IdeaProjects/plants"
    PYTHON_EXE = "C:/Python/Python311/python.exe"
else:
    STORAGE_PATH = "/home/user/WORK/tmp"
    LOCAL_REPO_PATH = "/home/user/WORK/workspace/plants"
    PYTHON_EXE = "/usr/bin/python"

current_time = datetime.now()
yesterday = datetime.today() - timedelta(days=1)
current_date_str = current_time.strftime("%Y%m%d")
current_date_str_out = current_time.strftime("%Y-%m-%d")

OsProcess.execute(f"{PYTHON_EXE} {LOCAL_REPO_PATH}/python/fetch/fetch.py")

for source in ["RaspberryPi", "PiZero"]:
    today_path = f"{STORAGE_PATH}/{source}/{current_date_str_out}"
    today_path = today_path.replace("/", "\\")
    print(today_path)
    command = f"cd {today_path} && {PYTHON_EXE} {LOCAL_REPO_PATH}/python/fetch/make_video.py"
    print(command)
    OsProcess.execute(command)
