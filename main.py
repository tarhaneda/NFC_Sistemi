import cv2
import asyncio
import os
import sys
from dotenv import load_dotenv


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from veritabani import database
import telegram_logger

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

async def sistem_testi():
    print("--- SISTEM TESTI BASLIYOR ---")
    hatalar = []


    try:
        print("[1/3] Veritabani baglantisi kontrol ediliyor...")
        database.tablolari_olustur()
        print("[BASARILI] Veritabani baglantisi sorunsuz!")
    except Exception as e:
        hatalar.append(f"Veritabani Hatasi: {e}")
        print(f"[HATA] Veritabani Hatasi: {e}")

    try:
        kamera_index = int(os.getenv("KAMERA_INDEX", 1))
        print(f"[2/3] Kamera (Index: {kamera_index}) baglantisi kontrol ediliyor...")
        
        kamera = cv2.VideoCapture(kamera_index) 
        if kamera.isOpened():
            ret, frame = kamera.read()
            if ret:
                print(f"[BASARILI] Kamera (Index: {kamera_index}) baglantisi ve goruntu alma sorunsuz!")
            else:
                hatalar.append(f"Kamera (Index {kamera_index}) baglandi fakat goruntu alinamiyor.")
                print("[HATA] Kamera goruntu vermiyor.")
            kamera.release()
        else:
            hatalar.append(f"Kamera (Index {kamera_index}) bulunamadi. Lutfen USB kamerayi takin veya index'i .env icinden degistirin.")
            print("[HATA] Kamera acilamadi.")
    except Exception as e:
        hatalar.append(f"Kamera Hatasi: {e}")
        print(f"[HATA] Kamera Hatasi: {e}")

    try:
        print("[3/3] Telegram bot baglantisi kontrol ediliyor...")
        if len(hatalar) == 0:
            mesaj = "[BASARILI] SISTEM TESTI TAMAMLANDI!\nVeritabani ve Harici Kamera sorunsuz calisiyor. Sistem uyanik."
        else:
            hata_mesaji = "\n".join(hatalar)
            mesaj = f"[UYARI] SISTEM TESTINDE HATALAR VAR:\n{hata_mesaji}"
            
        await telegram_logger.mesaj_gonder(mesaj)
        print("[BASARILI] Telegram bildirimi gonderildi!")
    except Exception as e:
        print(f"[HATA] Telegram Hatasi (Internet baglantisi veya Token yanlis olabilir): {e}")

    print("\n--- SISTEM TESTI BITTI ---")
    if len(hatalar) > 0:
        print("Lutfen yukaridaki hatalari cozmeden sistemi canliya almayin.")
    else:
        print("Her sey mukemmel! Sonraki adima gecebiliriz.")

if __name__ == "__main__":
    asyncio.run(sistem_testi())
