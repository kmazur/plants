#!/usr/bin/python3

import time
from datetime import datetime

import numpy as np
from libcamera import controls
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, Quality
from picamera2.outputs import CircularOutput


def current_time_str():
    current_time = datetime.now()
    current_date_str = current_time.strftime("%Y%m%d_%H%M%S")
    return current_date_str


fps = 56

dur = 3
micro = int((1 / fps) * 1000000)

# msize = (2304, 1296)
# msize = (1920, 1080)
msize = (1536, 864)
lsize = (1536, 864)
# lsize = msize
picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": msize, "format": "RGB888"},
                                                 lores={"size": lsize, "format": "YUV420"})

video_config['controls']['FrameDurationLimits'] = (micro, micro)
picam2.configure(video_config)

picam2.set_controls({
    "FrameRate": fps,
    "AfMode": controls.AfModeEnum.Continuous,
    # "AfMode": controls.AfModeEnum.Manual,
    # "LensPosition": 0,
    "AfMetering": controls.AfMeteringEnum.Auto,
    "AfRange": controls.AfRangeEnum.Full,
    "AfSpeed": controls.AfSpeedEnum.Fast,
    "FrameDurationLimits": (micro, micro)
})

buffersize = int(fps * (dur + 0.2))
output = CircularOutput(buffersize=buffersize)

encoder = H264Encoder(1000000, repeat=True)
encoder._setup(Quality.VERY_HIGH)
encoder.output = output
# picam2.encoder = encoder
picam2.start()
picam2.start_encoder(encoder)

w, h = lsize
prev = None
encoding = False
ltime = 0

start_t = 12
activation_threshold = 5
activation_encoding_threshold = 2
duration = 3


def auto_focus():
    success = picam2.autofocus_cycle()
    picam2.set_controls({"AfTrigger": controls.AfTriggerEnum.Start})
    # pass


auto_focus()

vid_time = None
times = []
thresholds = []
mses = []


def add_mse(mses, mse):
    mses.append(mse)
    if len(mses) > 60 * 10:
        mses.pop(0)


def calculate_thresholds(mses):
    return 6.5
    if len(mses) == 0:
        return 5
    val = 1 + sum(mses) / len(mses)
    if val > 12:
        return 12
    return val


vid_time_str = current_time_str()
activated_count = 0
while True:
    cur_time = time.time()
    cur = picam2.capture_buffer("lores")
    cur = cur[:w * h].reshape(h, w)
    if prev is not None:
        # Measure pixels differences between current and
        # previous frame
        mse = np.square(np.subtract(cur, prev)).mean()
        add_mse(mses, mse)
        start_t = calculate_thresholds(mses)

        if encoding:
            times.append(cur_time)
            thresholds.append(mse)

        if mse > start_t:
            activated_count = activated_count + 1
            if activated_count > activation_threshold:
                activated_count = activation_threshold

            if activated_count >= activation_threshold:
                if not encoding:
                    auto_focus()
                    vid_time = cur_time
                    vid_time_str = current_time_str()
                    filename = f"{vid_time_str}.h264"
                    output.fileoutput = filename
                    output.start()
                    encoding = True
                    print("New Motion", mse)
            if activated_count >= activation_encoding_threshold:
                ltime = time.time()
        else:
            activated_count = activated_count - 1
            if activated_count <= 0:
                activated_count = 0
            if encoding and time.time() - ltime > duration:
                print("End capture")
                output.stop()
                with open(f'{vid_time_str}.txt', 'w') as f:
                    for i in range(len(times)):
                        t = times[i]
                        tr = thresholds[i]
                        f.write(f'{t},{tr}\n')
                times = []
                thresholds = []
                encoding = False

        if encoding:
            print(
                f'mse = {mse:.4f}/{start_t:.2f}, encoding=True,  activations={activated_count}/{activation_encoding_threshold}')
        else:
            print(
                f'mse = {mse:.4f}/{start_t:.2f}, encoding=False, activations={activated_count}/{activation_threshold}')

    prev = cur
    time.sleep(0.1)
