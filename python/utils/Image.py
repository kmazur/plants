import os
import sys
from datetime import datetime

import cv2
import numpy as np

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from utils.OsProcess import OsProcess


class Image:
    def __init__(self, path):
        self.img = cv2.imread(path)
        self.path = path

    def get_ratio(self, threshold):
        return np.sum(self.img < threshold) / np.sum(self.img >= threshold)

    def add_text(self, text, x, y, fill="yellow", pointsize=72):
        command = '/usr/bin/convert ' + self.path + f" -pointsize {pointsize} -fill {fill} -annotate +{x}+{y} '" + text + "' " + self.path
        OsProcess.execute(command)

    def add_text_bottom_right(self, text, x, y, fill="yellow", pointsize=72):
        height, width = self.img.shape[:2]
        command = '/usr/bin/convert ' + self.path + f" -pointsize {pointsize} -fill {fill} -annotate +{width - x}+{height - y} '" + text + "' " + self.path
        OsProcess.execute(command)

    def add_timestamp(self):
        current_time = datetime.now()
        timestamp_message = current_time.strftime("%Y-%m-%d %H:%M:%S")
        self.add_text_bottom_right(timestamp_message, 750, 100)
