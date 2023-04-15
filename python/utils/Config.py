import os
import sys

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from utils.OsProcess import OsProcess

DEFAULT_ROOT_PATH = '/home/user/WORK'

class Config:
    def __init__(self, root_dir=DEFAULT_ROOT_PATH):
        self.root_dir = root_dir
        self.config_dir = f'{root_dir}/config'
        self.workspace_dir = f'{root_dir}/workspace'
        self.tmp_dir = f'{root_dir}/tmp'
        self.camera_dir = f'{self.tmp_dir}/camera'

        self.user = "user"
        self.host = OsProcess.get_ip_address()

        self.data = {}
        with open(f'{self.config_dir}/config.ini') as f:
            lines = f.readlines()
            for line in lines:
                tokens = line.split('=')
                self.data[tokens[0].strip()] = tokens[1].strip()

    def get(self, key):
        return self.data[key]

    def set(self, key, value):
        prev = self.data[key]
        self.data[key] = value
        return prev
