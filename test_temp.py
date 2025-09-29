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
VREF = 3.3
DO_MAX = 20.0
PH_M = 3.4091
PH_C = 0.182
JSON_FILE = "/tmp/sensor_data.json"
SERVER_URL = "https://railwayreal555-production-5be4.up.railway.app/data"  # เปลี่ยนเป็น ngrok ของ backend
POND_ID = 1   # <<< ตั้งค่า pond_id ของบ่อที่อ่านค่า

# === INIT SENSORS ===
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
do_channel = AnalogIn(ads, ADS.P1)
ph_channel = AnalogIn(ads, ADS.P2)
temp_sensor = W1ThermSensor()

# === CONVERSION FUNCTIONS ===
def voltage_to_do(voltage):
    return (voltage / VREF) * DO_MAX

def voltage_to_ph(voltage):
    return PH_M * voltage + PH_C

# === MAIN LOOP ===
print("เริ่มอ่านค่า DO, pH และอุณหภูมิ พร้อมส่งไปยังเซิร์ฟเวอร์...")

try:
    while True:
        # อ่านเซนเซอร์
        do_voltage = do_channel.voltage
        ph_voltage = ph_channel.voltage
        temperature = temp_sensor.get_temperature()

        do_value = voltage_to_do(do_voltage)
        ph_value = voltage_to_ph(ph_voltage)

        # สร้างข้อมูล JSON แบบเดียวกับที่ backend ต้องการ
        data = {
            "pond_id": POND_ID,
            "ph": round(ph_value, 2),
            "temperature": round(temperature, 2),
            "do": round(do_value, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # บันทึกไฟล์ใน Raspi (ไฟล์เดียวล่าสุด)
        try:
            with open(JSON_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[ERROR] บันทึกไฟล์ JSON ล้มเหลว: {e}")

        # ส่งไปยัง Server
        try:
            r = requests.post(SERVER_URL, json=data, timeout=3)
            if r.status_code == 200:
                print(f"[OK] ส่งข้อมูลสำเร็จ -> {data}")
            else:
                print(f"[WARN] ส่งข้อมูลไม่สำเร็จ: {r.status_code} {r.text}")
        except Exception as e:
            print(f"[ERROR] ส่งข้อมูลไม่สำเร็จ: {e}")

        time.sleep(5)  # ส่งทุกๆ 5 วินาที

except KeyboardInterrupt:
    print("\nหยุดการวัดเซนเซอร์แล้ว")
