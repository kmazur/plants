#!/bin/bash

# Request token - scheduler distributing / signalling work based on CPU TEMP
# Definition of stages
#

# Raw data save to (SOURCE)_STAGE_RAW

# Video pipeline
# Camera -> VIDEO_STAGE_RAW -> output: video_(date)_(time).h264
# RAW -> convert to mp4
# mp4 -> create annotation srt
# mp4 -> extract first frame
