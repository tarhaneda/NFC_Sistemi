from datetime import datetime
import sqlite3
import sqlite3
import os
import datetime
import asyncio
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import telegram_logger

DB_yolu=os.path.join(os.path.dirname(__file__), "kapi_sistemi.db")
import threading 
db_kilit=threading.Lock()

def veritabani_baglantisi_al():
    baglanti=sqlite3.connect(DB_yolu, check_same_thread=False)
    baglanti.row_factory=sqlite3.Row
    return baglanti
    

def tablolari_olustur():
    baglanti=veritabani_baglantisi_al()
    imlec=baglanti.cursor()

    imlec.execute('''
    CREATE TABLE IF NOT EXISTS kullanicilar(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad_soyad TEXT NOT NULL,
        nfc_uid TEXT NOT NULL UNIQUE,
        aktif_mi INTEGER Default 1,
        rol TEXT DEFAULT 'PERSONEL',
        yuz_fotograf_yolu TEXT,
        kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    imlec.execute('''
    CREATE TABLE IF NOT EXISTS kayitlar(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        olay_detayi TEXT NOT NULL,
        durum TEXT NOT NULL,
        kamera_fotograf_yolu TEXT,
        olay_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        
    ''')
    try:
     imlec.execute("ALTER TABLE kullanicilar ADD COLUMN rol TEXT DEFAULT 'PERSONEL'")
    except sqlite3.OperationalError:
        pass

    baglanti.commit()
    baglanti.close()
    print("veritabanı ve tablolar başarıyla kuruldu")

def kullanici_ekle(ad_soyad, nfc_uid, yuz_fotograf_yolu="", rol="PERSONEL"):
    """Sisteme yeni bir kart ve kulanıcı kaydeder."""
    try: 
        baglanti=veritabani_baglantisi_al()
        imlec=baglanti.cursor()
        imlec.execute('''
        INSERT INTO kullanicilar (ad_soyad, nfc_uid, yuz_fotograf_yolu,rol, kayit_tarihi)
        VALUES(?,?,?,?, datetime('now', 'localtime'))
        ''',(ad_soyad, nfc_uid, yuz_fotograf_yolu,rol))

        baglanti.commit()
        print(f"Başarılı: '{ad_soyad}' sisteme eklendi.")

    except sqlite3.IntegrityError:
        print(f"Hata: '{nfc_uid}' NFC ID sistemde zaten kayıtlı!")
    finally:
        baglanti.close()

def kart_sorgula(nfc_uid):
    """Okutulan NFC kartını veritabanında arar"""
    baglanti=veritabani_baglantisi_al()
    imlec=baglanti.cursor()
    imlec.execute("SELECT * FROM kullanicilar WHERE nfc_uid =?", (nfc_uid,))
    kullanici=imlec.fetchone()
    baglanti.close()

    if kullanici:
        return dict(kullanici)

    else:
        return None

def formatli_mesaj_olustur(olay_detayi, durum):
    zaman=datetime.datetime.now().strftime("%d-%m-%y %H:%M")

    if durum=="BAŞARILI_GİRİŞ":
        kisi=olay_detayi.replace("giriş yaptı", "")
        mesaj=f"👤 Kişi: {kisi}\n⏰ Zaman: {zaman}\n🔄 İşlem: Geçiş Yapıldı\n✅ Durum: BAŞARILI (Kart Doğrulandı)"
    elif durum == "YETKİSİZ_GİRİŞ_DENEMESİ":
        mesaj = f"👤 Kişi: {olay_detayi}\n⏰ Zaman: {zaman}\n🔄 İşlem: Geçiş Denemesi\n❌ Durum: BAŞARISIZ (Yetkisi Dondurulmuş Kart!)"
    elif durum == "SİSTEM_AYARI":  
        mesaj = f"⚙️ SİSTEM BİLGİSİ\n⏰ Zaman: {zaman}\n🔄 İşlem: Yetki Güncellemesi\nℹ️ Detay: {olay_detayi}"    
    else: # İHLAL_GİRİŞİMİ veya YABANCI_KART
        mesaj = f"👤 Kişi: Bilinmeyen Kullanıcı\n⏰ Zaman: {zaman}\n🔄 İşlem: Geçiş Denemesi\n❌ Durum: BAŞARISIZ ({olay_detayi})"
        
    return mesaj

def log_kaydet(olay_detayi, durum, kamera_fotograf_yolu=""):
    """Sistemdeki olayları 'kayitlar' tablosuna kaydeder."""
    #iki thread aynı anda gelğrse biri diğerini bekler
    with db_kilit:
        baglanti=veritabani_baglantisi_al()
        imlec=baglanti.cursor()
        imlec.execute('''
        INSERT INTO kayitlar(olay_detayi, durum, kamera_fotograf_yolu,olay_tarihi)
        VALUES(?,?,?,datetime('now','localtime'))
        ''',(olay_detayi, durum, kamera_fotograf_yolu))
        baglanti.commit()
        baglanti.close()

    sik_mesaj = formatli_mesaj_olustur(olay_detayi, durum)
    
    try:
        if kamera_fotograf_yolu != "":
            asyncio.run(telegram_logger.fotograf_gonder(kamera_fotograf_yolu, sik_mesaj))
        else:
            asyncio.run(telegram_logger.mesaj_gonder(sik_mesaj))
    except Exception as e:
        print("Telegram'a atılırken hata oluştu (İnternet yok vb.)")

def kullanici_yetki_guncelle(nfc_uid, yeni_durum):
    
    baglanti=veritabani_baglantisi_al()
    imlec=baglanti.cursor()
    imlec.execute("UPDATE kullanicilar SET aktif_mi = ? WHERE nfc_uid= ?",(yeni_durum,nfc_uid))
    baglanti.commit()
    baglanti.close()

    durum_metni="AKTİF" if yeni_durum==1  else "DONDURULDU"
    print(f"Yetki GÜncellendi: {nfc_uid} kartı {durum_metni} yapıldı")

def istatistik_tarih_filtreli(baslangic_tarihi, bitis_tarihi, olay_durumu):
    baglanti=veritabani_baglantisi_al()
    imlec=baglanti.cursor()
    sorgu="SELECT COUNT(*) FROM kayitlar WHERE date(olay_tarihi) BETWEEN ? AND ? AND durum= ?"
    imlec.execute(sorgu,(baslangic_tarihi,bitis_tarihi,olay_durumu))

    sayi=imlec.fetchone()[0]
    baglanti.close()
    return sayi

def kullanici_getir(kullanici_id):
    baglanti=veritabani_baglantisi_al()
    imlec=baglanti.cursor()
    imlec.execute("SELECT * FROM kullanicilar WHERE id=?",(kullanici_id,))
    kisi=imlec.fetchone()
    baglanti.close()
    return dict(kisi) if kisi else None

def kullanici_guncelle(kullanici_id, ad_soyad, nfc_uid, rol="PERSONEL"):
    try:
        baglanti=veritabani_baglantisi_al()
        imlec=baglanti.cursor()
        imlec.execute('''UPDATE kullanicilar SET ad_soyad =?, nfc_uid =? ,rol=? WHERE id=?''',(ad_soyad,nfc_uid,rol,kullanici_id))
        baglanti.commit()
        return True, "Kullanıcı başarıyla güncellendi"
    except sqlite3.IntegrityError:
        return False, "Hata: Bu NFC ID başka bir kullanıcıya ait"
    finally:
        baglanti.close()
if __name__=="__main__":
    tablolari_olustur()
