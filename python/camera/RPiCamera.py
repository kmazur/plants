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
        return self.take_picture_out(
            os.path.join(self.config.camera_dir, self.get_current_date_str()),
            int(self.config.get("camera.width")),
            int(self.config.get("camera.height")),
            int(self.config.get("camera.hflip")),
            int(self.config.get("camera.vflip"))
        )

    def take_picture_out(self, output_dir, width, height, hflip, vflip):
        output_file = self.get_current_date_time_str() + '.jpg'
        return self.take_picture_all(output_dir, output_file, width, height, hflip, vflip)

    def take_picture_all(self, output_dir, output_file, width, height, hflip, vflip, timestamped=True):
        self.picam = Picamera2()
        config = self.picam.create_still_configuration(main={"size": (width, height)})
        config["transform"] = libcamera.Transform(hflip=hflip, vflip=vflip)
        self.picam.configure(config)

        path = os.path.join(output_dir, output_file)

        self.picam.start()
        time.sleep(1)
        self.picam.capture_file(path)
        self.picam.close()

        if timestamped:
            current_time = datetime.now()
            timestamp_message = current_time.strftime("%Y-%m-%d %H:%M:%S")
            timestamp_command = '/usr/bin/convert ' + path + f" -pointsize 72 -fill yellow -annotate +{width - 750}+{height - 100} '" + timestamp_message + "' " + path
            call([timestamp_command], shell=True)
        return path
