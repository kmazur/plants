import RPi.GPIO as GPIO

servo_pin = 18
servo_freq = 50
pi_pwm = None

try:
    GPIO.setwarnings(True)  # disable warnings
    GPIO.setmode(GPIO.BCM)  # set pin numbering system
    GPIO.setup(servo_pin, GPIO.OUT)
    pi_pwm = GPIO.PWM(servo_pin, servo_freq)  # create PWM instance with frequency
    pi_pwm.start(0)  # start PWM of required Duty Cycle
    while True:
        duty_cycle = float(input("Enter Duty Cycle:"))
        pi_pwm.ChangeDutyCycle(duty_cycle)
except KeyboardInterrupt:
    pass
finally:
    print("end")
    pi_pwm.stop()
    GPIO.cleanup()
