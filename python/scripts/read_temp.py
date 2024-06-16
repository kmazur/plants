import adafruit_ahtx0
import board

i2c = board.I2C()  # uses board.SCL and board.SDA
sensor = adafruit_ahtx0.AHTx0(i2c)
temp = sensor.temperature
humidity = sensor.relative_humidity
print(str(temp))
print(str(humidity))