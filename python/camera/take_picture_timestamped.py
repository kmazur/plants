import time, libcamera
from picamera2 import Picamera2, Preview
from subprocess import call
from datetime import datetime

picam = Picamera2()

config = picam.create_still_configuration(main={"size": (4608, 2592)})
config["transform"] = libcamera.Transform(hflip=0, vflip=1)
picam.configure(config)

currentTime = datetime.now()
picTime = currentTime.strftime("%Y_%m_%d_%H_%M_%S")
picName = picTime + '.jpg'

path = './' + picName

picam.start()
time.sleep(1)
picam.capture_file(path)
picam.close()
print('Taken picture')

timestampMessage = currentTime.strftime("%Y-%m-%d %H:%M:%S")
timestampCommand = '/usr/bin/convert ' + path + " -pointsize 72 -fill yellow -annotate +3850+2500 '" + timestampMessage + "' " + path
call([timestampCommand], shell=True)
print('Annotated picture with: ' + timestampMessage)