import cv2
import requests
import time
from datetime import datetime
import RPi.GPIO as GPIO
import os

url = "https://railwayreal555-production-5be4.up.railway.app/process"
POND_ID = 1  # ตั้งค่า pond_id ตามบ่อ

# ฟังก์ชันสำหรับเวลาตาม format เดียวกับ backend
def timestamp_now():
    return datetime.now().strftime("%Y%m%d_%H%M%S")
    
relay_pin = 26
GPIO.setmode(GPIO.BCM)
GPIO.setup(relay_pin, GPIO.OUT)

BASE_DIR = "/home/iq/control"
IMAGE_DIR = os.path.join(BASE_DIR, "image")
os.makedirs(IMAGE_DIR, exist_ok=True)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌ ไม่สามารถเปิดกล้องได้")
    exit()

try:
    while True:
        # ถ่ายภาพทุก 3600 วินาที (1 ชั่วโมง)
        GPIO.output(relay_pin, GPIO.LOW)
        time.sleep(5)
        ret, frame = cap.read()
        time.sleep(5)
        if not ret:
            print("❌ ถ่ายภาพไม่สำเร็จ")
            continue
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        cap.set(cv2.CAP_PROP_EXPOSURE, -6)

        ts = timestamp_now()

        # --- สร้างไฟล์ 2 แบบ ---
        float_name = f"shrimp_float_pond{POND_ID}_{ts}.jpg"
        water_name = f"water_pond{POND_ID}_{ts}.jpg"
        
        
        float_path = os.path.join(IMAGE_DIR, float_name)
        water_path = os.path.join(IMAGE_DIR, water_name)

        
        cv2.imwrite(float_path, frame)
        cv2.imwrite(water_path, frame)
        GPIO.output(relay_pin, GPIO.HIGH)

        # --- ส่งภาพไป API ---
        for fname in [float_path, water_path]:
            with open(fname, "rb") as f:
                files = {"files": (os.path.basename(fname), f, "image/jpeg")}
                try:
                    response = requests.post(url, files=files)
                    if response.status_code == 200:
                        print(f"send {fname} complete")
                        os.remove(fname)
                    else:
                        print(f"sent {fname} fail:", response.status_code, response.text)
                except Exception as e:
                    print(f"?? Error ??? {fname}:", e)
        time.sleep(10)

except KeyboardInterrupt:
    print("🛑 หยุดโปรแกรม")

finally:
    cap.release()
