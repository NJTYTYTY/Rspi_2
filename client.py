import cv2
import requests
import time
import threading
from datetime import datetime
import RPi.GPIO as GPIO
import os

# === CONFIG ===
POND_ID = 1  # ตั้งค่า pond_id ตามบ่อ
BACKEND_URL = "https://railwayreal555-production-5be4.up.railway.app/process"
CLOUD_API_URL = "https://rspi1-production.up.railway.app"  # URL ของ cloud app
JOB_CHECK_INTERVAL = 1  # ตรวจสอบงานทุก 1 วินาที
REGULAR_CAPTURE_INTERVAL = 10  # ถ่ายรูปปกติทุก 10 วินาที

# ฟังก์ชันสำหรับเวลาตาม format เดียวกับ backend
def timestamp_now():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

# === SETUP GPIO ===
relay_pin = 26
GPIO.setmode(GPIO.BCM)
GPIO.setup(relay_pin, GPIO.OUT)

# === SETUP DIRECTORIES ===
BASE_DIR = "/home/iq/control"
IMAGE_DIR = os.path.join(BASE_DIR, "image")
os.makedirs(IMAGE_DIR, exist_ok=True)

# === THREAD SAFETY ===
camera_lock = threading.Lock()  # ป้องกันการใช้กล้องพร้อมกัน
gpio_lock = threading.Lock()   # ป้องกันการใช้ GPIO พร้อมกัน

# === CAMERA SETUP ===
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌ ไม่สามารถเปิดกล้องได้")
    exit()

# === CLOUD API FUNCTIONS ===
def check_for_job():
    """ตรวจสอบว่ามีงานจาก cloud หรือไม่"""
    try:
        response = requests.get(f"{CLOUD_API_URL}/job-rspi2/{POND_ID}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("has_job", False), data.get("job_data")
        else:
            print(f"❌ ตรวจสอบงานล้มเหลว: {response.status_code}")
            return False, None
    except Exception as e:
        print(f"⚠️ ไม่สามารถเชื่อมต่อ cloud: {e}")
        return False, None

def complete_job(result_data):
    """แจ้ง cloud ว่าเสร็จงานแล้ว"""
    try:
        response = requests.post(
            f"{CLOUD_API_URL}/job-rspi2/{POND_ID}/complete",
            json=result_data,
            timeout=5
        )
        if response.status_code == 200:
            print("✅ แจ้งงานเสร็จเรียบร้อย")
            return True
        else:
            print(f"❌ แจ้งงานเสร็จล้มเหลว: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️ ไม่สามารถแจ้งงานเสร็จ: {e}")
        return False

# === CAPTURE FUNCTIONS ===
def capture_images(job_type="regular"):
    """ถ่ายรูปและส่งไป backend (Thread Safe)"""
    print(f"📷 เริ่มถ่ายรูป ({job_type})...")
    
    # ใช้ Lock เพื่อป้องกันการทำงานพร้อมกัน
    with camera_lock:
        print(f"🔒 ได้ Lock สำหรับถ่ายรูป ({job_type})")
        
        try:
            # ใช้ GPIO Lock เพื่อป้องกันการควบคุมไฟพร้อมกัน
            with gpio_lock:
                GPIO.output(relay_pin, GPIO.LOW)
                print(f"💡 เปิดไฟ LED ({job_type})")
            
            time.sleep(5)
            
            # อ่านภาพจากกล้อง
            ret, frame = cap.read()
            time.sleep(5)
            
            if not ret:
                print("❌ ถ่ายภาพไม่สำเร็จ")
                with gpio_lock:
                    GPIO.output(relay_pin, GPIO.HIGH)
                return False
                
            # ตั้งค่ากล้อง
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap.set(cv2.CAP_PROP_EXPOSURE, -6)

            ts = timestamp_now()

            # สร้างไฟล์ 2 แบบ
            float_name = f"shrimp_float_pond{POND_ID}_{ts}.jpg"
            water_name = f"water_pond{POND_ID}_{ts}.jpg"
            
            float_path = os.path.join(IMAGE_DIR, float_name)
            water_path = os.path.join(IMAGE_DIR, water_name)

            # บันทึกภาพ
            cv2.imwrite(float_path, frame)
            cv2.imwrite(water_path, frame)
            
            # ปิดไฟ LED
            with gpio_lock:
                GPIO.output(relay_pin, GPIO.HIGH)
                print(f"💡 ปิดไฟ LED ({job_type})")

            # ส่งภาพไป API
            success_count = 0
            for fname in [float_path, water_path]:
                with open(fname, "rb") as f:
                    files = {"files": (os.path.basename(fname), f, "image/jpeg")}
                    try:
                        response = requests.post(BACKEND_URL, files=files)
                        if response.status_code == 200:
                            print(f"✅ ส่ง {fname} สำเร็จ ({job_type})")
                            os.remove(fname)
                            success_count += 1
                        else:
                            print(f"❌ ส่ง {fname} ล้มเหลว ({job_type}):", response.status_code, response.text)
                    except Exception as e:
                        print(f"❌ Error ส่ง {fname} ({job_type}):", e)
            
            print(f"📤 ส่งภาพเสร็จ ({success_count}/2 ไฟล์) - {job_type}")
            return success_count > 0
            
        except Exception as e:
            print(f"🔥 Error ในการถ่ายรูป ({job_type}): {e}")
            with gpio_lock:
                GPIO.output(relay_pin, GPIO.HIGH)
            return False
        finally:
            print(f"🔓 ปล่อย Lock สำหรับถ่ายรูป ({job_type})")

def execute_job_capture(job_data=None):
    """ทำงานถ่ายรูปเมื่อมีงานจาก cloud"""
    print(f"🔧 เริ่มทำงานถ่ายรูปจากงาน: {job_data}")
    
    # ถ่ายรูป
    success = capture_images("job")
    
    # สร้างผลลัพธ์
    result_data = {
        "status": "success" if success else "error",
        "pond_id": POND_ID,
        "action": "cam_side",
        "timestamp": datetime.now().isoformat(),
        "job_data": job_data,
        "capture_success": success
    }
    
    # แจ้งงานเสร็จ
    complete_job(result_data)
    
    return result_data

# === THREAD FUNCTIONS ===
def job_checker_thread():
    """Thread สำหรับตรวจสอบงานจาก cloud"""
    print("🔍 เริ่มตรวจสอบงานจาก cloud...")
    
    while True:
        try:
            has_job, job_data = check_for_job()
            
            if has_job:
                print(f"📋 พบงานใหม่: {job_data}")
                execute_job_capture(job_data)
                print("✅ งานเสร็จสิ้น รองานใหม่...")
            else:
                print("😴 ไม่มีงานจาก cloud รอ...")
            
            time.sleep(JOB_CHECK_INTERVAL)
            
        except Exception as e:
            print(f"🔥 Error ใน job checker: {e}")
            time.sleep(JOB_CHECK_INTERVAL)

def regular_capture_thread():
    """Thread สำหรับถ่ายรูปปกติทุก 10 วินาที"""
    print("📷 เริ่มถ่ายรูปปกติทุก 10 วินาที...")
    
    while True:
        try:
            capture_images("regular")
            time.sleep(REGULAR_CAPTURE_INTERVAL)
            
        except Exception as e:
            print(f"🔥 Error ใน regular capture: {e}")
            time.sleep(REGULAR_CAPTURE_INTERVAL)

# === MAIN ===
if __name__ == "__main__":
    print("🚀 เริ่มโปรแกรม RSPI2 Client")
    print(f"🌐 Cloud API: {CLOUD_API_URL}")
    print(f"🔄 ตรวจสอบงานทุก {JOB_CHECK_INTERVAL} วินาที")
    print(f"📷 ถ่ายรูปปกติทุก {REGULAR_CAPTURE_INTERVAL} วินาที")
    
    try:
        # เริ่ม thread ทั้ง 2 ตัว
        job_thread = threading.Thread(target=job_checker_thread, daemon=True)
        capture_thread = threading.Thread(target=regular_capture_thread, daemon=True)
        
        job_thread.start()
        capture_thread.start()
        
        print("✅ Thread ทั้งหมดเริ่มทำงานแล้ว")
        
        # รอให้ thread ทำงาน
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("🛑 หยุดโปรแกรมโดยผู้ใช้")
    except Exception as e:
        print(f"🔥 ERROR: {e}")
    finally:
        cap.release()
        GPIO.cleanup()
        print("🔚 เคลียร์ทรัพยากรแล้ว")
