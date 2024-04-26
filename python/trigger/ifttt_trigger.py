import os
import sys

import requests

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from utils.Config import Config

conf = Config()
key = conf.get("ifttt.motion.key")
event_name = "motion_detected"
requests.post(f"https://maker.ifttt.com/trigger/{event_name}/with/key/{key}")
