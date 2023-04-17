import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from utils.Config import Config
from utils.OsProcess import OsProcess
from camera.RPiCamera import RPiCamera

sleepSeconds = 25
if len(sys.argv) > 1:
    sleepSeconds = int(sys.argv[1])

config = Config()
camera = RPiCamera()


def ensure_date_dir(config):
    current_time = datetime.now()
    current_date_str = current_time.strftime("%Y-%m-%d")
    directory = os.path.join(config.camera_dir, current_date_str)
    OsProcess.execute(f"mkdir -p {directory}")
    return directory

def black_ratio(img, threshold):
    return np.sum(img < threshold) / np.sum(img >= threshold)


while True:
    output_dir = ensure_date_dir(config)
    path = camera.take_picture()
    print(f"Taken picture: {path}")

    img = cv2.imread(path)
    ratio = black_ratio(img, 30)
    print(f"Black ratio: {path} -> {ratio}")

    time.sleep(sleepSeconds)
