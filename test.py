import serial
import time

PORT = "COM5"
BAUD_RATE = 115200

print(f"{PORT} portuna bağlanmaya çalışılıyor...")

try:
    seri_port = serial.Serial()
    seri_port.port = PORT
    seri_port.baudrate = BAUD_RATE
    seri_port.timeout = 1
    # NodeMCU Koma Engelleyici
    seri_port.setDTR(False)
    seri_port.setRTS(False)
    
    seri_port.open()
    print("✅ Bağlantı BAŞARILI! Lütfen fiziksel kartınızı okutun...")
    
    while True:
        if seri_port.in_waiting > 0:
            satir = seri_port.readline().decode('utf-8', errors='ignore').strip()
            if satir:
                print(f"📡 GELEN SAF VERİ: {satir}")
        time.sleep(0.1)
        
except Exception as e:
    print(f"❌ HATA: {e}")
