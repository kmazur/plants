from machine import I2C,Pin
from tsl2591 import TSL2591
import network
import socket
from time import sleep

i2c = I2C(0, scl=Pin(5), sda=Pin(4))
tsl = TSL2591( i2c = i2c )
print( "%s lux" % tsl.lux )
