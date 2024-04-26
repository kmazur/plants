import os
import sys

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from utils.OsProcess import OsProcess

DEFAULT_ROOT_PATH = '/home/user/WORK'


class Config:
    def __init__(self, root_dir=DEFAULT_ROOT_PATH):
        self.data = {}
        self.data["root_dir"] = root_dir
        self.data["config_dir"] = f'{root_dir}/config'
        self.data["workspace_dir"] = f'{root_dir}/workspace'
        self.data["tmp_dir"] = f'{root_dir}/tmp'
        self.data["camera_dir"] = f'{self.data["tmp_dir"]}/camera'
        self.data["drive_dir"] = f'{self.data["tmp_dir"]}/Monitoring'
        self.data["user"] = "user"
        self.data["host"] = OsProcess.get_ip_address()

        with open(f'{root_dir}/config/config.ini') as f:
            lines = f.readlines()
            for line in lines:
                if len(line.strip()) == 0:
                    continue
                index = line.find("=")
                key = line[0:index].strip()
                value = line[index+1:].strip()
                self.data[key] = value

        self.root_dir = self.data["root_dir"]
        self.config_dir = self.data["config_dir"]
        self.workspace_dir = self.data["workspace_dir"]
        self.tmp_dir = self.data["tmp_dir"]
        self.camera_dir = self.data["camera_dir"]
        self.drive_dir = self.data["drive_dir"]
        self.user = self.data["user"]
        self.host = self.data["host"]

        print("CONFIG:")
        for key in self.data:
            value = self.data[key]
            print(key + "=" + value)

    def get(self, key, default_value=None):
        if key in self.data:
            return self.data[key]
        else:
            return default_value

    def set(self, key, value):
        prev = self.data[key]
        self.data[key] = value
        return prev

    def get_scale(self):
        scale = int(100)
        with open(f'{self.config_dir}/scale.ini') as f:
            lines = f.readlines()
            for line in lines:
                stripped = line.strip()
                if len(stripped) == 0:
                    continue
                scale = int(stripped)
                break
        return scale

    def is_suspended(self):
        scale = self.get_scale()
        return scale == 0

    def get_scaled_inverse_value(self, min, max):
        scale = self.get_scale()

        diff = max - min
        scaled_diff = (scale * diff / 100)
        sub = min + scaled_diff
        return int(min + (max - sub))
