from machine import I2C, Pin

from tsl2591 import TSL2591

i2c = I2C(0, scl=Pin(1), sda=Pin(0))
tsl = TSL2591(i2c=i2c)


def get_lux():
    lux = tsl.lux
    print(f"{lux} lux")
    return lux
