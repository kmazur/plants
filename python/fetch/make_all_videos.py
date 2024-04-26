import glob
import os
import sys

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

glob_pattern = '*'
directories = sorted(glob.glob(glob_pattern), key=os.path.basename)
current_path = os.path.abspath("").replace("\\", "/")

for directory in directories:
    full_dir_path = os.path.join(current_path, directory)
    command = f"cd {full_dir_path} && {PYTHON_EXE} {LOCAL_REPO_PATH}/python/fetch/make_video.py"
    print(command)
    OsProcess.execute(command)
