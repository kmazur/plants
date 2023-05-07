import os
import sys
import time
from datetime import datetime
from subprocess import call

import libcamera
from picamera2 import Picamera2

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from utils.Config import Config


class RPiCamera:
    def __init__(self):
        self.config = Config()

    def get_current_date_time_str(self):
        current_time = datetime.now()
        return current_time.strftime("%Y_%m_%d_%H_%M_%S")

    def get_current_date_str(self):
        current_time = datetime.now()
        return current_time.strftime("%Y-%m-%d")

    def take_picture(self):
        cam_config = {
            "camera.width": self.config.get("camera.width"),
            "camera.height": self.config.get("camera.height"),
            "camera.hflip": self.config.get("camera.hflip"),
            "camera.vflip": self.config.get("camera.vflip"),
            "camera.afmode": self.config.get("camera.afmode"),
            "camera.afrange": self.config.get("camera.afrange"),
            "camera.afmetering": self.config.get("camera.afmetering"),
            "camera.lensposition": self.config.get("camera.lensposition")
        }
        return self.take_picture_out(
            os.path.join(self.config.camera_dir, self.get_current_date_str()),
            cam_config
        )

    def take_picture_out(self, output_dir, cam_config):
        output_file = self.get_current_date_time_str() + '.jpg'
        cam_config["camera.outputfile"] = output_file
        return self.take_picture_all(output_dir, cam_config)

    def _get_conf(self, cam_config, key, default_value):
        if key in cam_config:
            value = cam_config[key]
            if value is None:
                return default_value
            return value
        else:
            return default_value

    def take_picture_all(self, output_dir, cam_config):
        self.picam = Picamera2()

        width = int(self._get_conf(cam_config, "camera.width", "2592"))
        height = int(self._get_conf(cam_config, "camera.height", "1944"))
        hflip = int(self._get_conf(cam_config, "camera.hflip", "0"))
        vflip = int(self._get_conf(cam_config, "camera.vflip", "0"))
        afmode = self._get_conf(cam_config, "camera.afmode", "Auto")
        afrange = self._get_conf(cam_config, "camera.afrange", "Normal")
        afmetering = self._get_conf(cam_config, "camera.afmetering", "Auto")
        lensposition = self._get_conf(cam_config, "camera.lensposition", None)
        output_file = self._get_conf(cam_config, "camera.outputfile", self.get_current_date_time_str() + '.jpg')

        config = self.picam.create_still_configuration(main={"size": (width, height)})
        config["transform"] = libcamera.Transform(hflip=hflip, vflip=vflip)
        self.picam.configure(config)

        path = os.path.join(output_dir, output_file)

        self.picam.start()
        if afmode == "Auto":
            afmode = libcamera.controls.AfModeEnum.Auto
        elif afmode == "Continuous":
            afmode = libcamera.controls.AfModeEnum.Continuous
        elif afmode == "Manual":
            afmode = libcamera.controls.AfModeEnum.Manual
        else:
            afmode = libcamera.controls.AfModeEnum.Auto

        if afrange == "Normal":
            afrange = libcamera.controls.AfRangeEnum.Normal
        elif afrange == "Macro":
            afrange = libcamera.controls.AfRangeEnum.Macro
        elif afrange == "Full":
            afrange = libcamera.controls.AfRangeEnum.Full
        else:
            afrange = libcamera.controls.AfRangeEnum.Normal

        if afmetering == "Auto":
            afmetering = libcamera.controls.AfMeteringEnum.Auto
        elif afmetering == "Windows":
            afmetering = libcamera.controls.AfMeteringEnum.Windows
        else:
            afmetering = libcamera.controls.AfMeteringEnum.Auto

        if lensposition is not None:
            lensposition = int(lensposition)
            self.picam.set_controls({"LensPosition": lensposition})

        self.picam.set_controls({"AfMode": afmode})
        self.picam.set_controls({"AfRange": afrange})
        self.picam.set_controls({"AfMetering": afmetering})

        time.sleep(0.2)
        self.picam.capture_file(path)
        self.picam.close()

        return path
