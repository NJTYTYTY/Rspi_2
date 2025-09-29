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
PH_M = -13.04   # slope
PH_C = 14.43    # intercept

def voltage_to_ph(voltage):
    return PH_M * voltage + PH_C

# === INIT SENSORS ===
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ph_channel = AnalogIn(ads, ADS.P2)

try:
    while True:
        ph_voltage = ph_channel.voltage
        ph_value = voltage_to_ph(ph_voltage)
        
        print(f"Vcc : {ph_voltage}, Value  : {ph_value}")
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nหยุดการวัดเซนเซอร์แล้ว")
