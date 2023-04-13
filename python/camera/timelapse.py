import picamera
from subprocess import call
from datetime import datetime
from time import sleep


currentTime = datetime.now()
picTime = currentTime.strftime("%Y.%m.%d_%H%M%S")
picName = picTime + '.jpg'

path = './' + picName

with picamera.PiCamera() as camera:
    camera.capture(path)
    print('Taken picture')

timestampMessage = currentTime.strftime("%Y-%m-%d %H%M%S")
timestampCommand = '/usr/bin/convert' + path + " -pointsize 36 -fil yellow -annotate +700+650 '" + timestampMessage + "' " + path
call([timestampCommand], shell=True)
print('Annotated picture with: ' + timestampMessage)
