import time
import json
import requests
from datetime import datetime
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from w1thermsensor import W1ThermSensor

# === CONFIG ===
VREF = 5
DO_MAX = 20.0

# === INIT SENSORS ===
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
do_channel = AnalogIn(ads, ADS.P1)

# === CONVERSION FUNCTIONS ===
def voltage_to_do(voltage):
    return (voltage / VREF) * DO_MAX

try:
    while True:
        # อ่านเซนเซอร์
        do_voltage = do_channel.voltage
        do_value = voltage_to_do(do_voltage)

        print(f"Vcc : {do_voltage}, Value  : {do_value}")
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nหยุดการวัดเซนเซอร์แล้ว")
