
import sys
import types
import os
pkg_resources = types.ModuleType('pkg_resources')
pkg_resources.resource_filename = lambda p, r: os.path.join(os.path.dirname(sys.modules[p].__file__), r)
sys.modules['pkg_resources'] = pkg_resources


import webbrowser
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import cv2
import base64
import re
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yapay_zeka import yuz_tanima as yz
from veritabani import database as db

load_dotenv()

app = Flask(__name__)
app.secret_key = "super_gizli_guvenlik_anahtari"

SISTEM_SIFRESI = "5252"

db_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'veritabani', 'kapi_sistemi.db')
if not os.path.exists(db_yolu):
    print("[SİSTEM] Veritabanı bulunamadı, yeni tablolar oluşturuluyor...")
    db.tablolari_olustur()

kamera_index = int(os.getenv("KAMERA_INDEX", 1))

# Yeni kişilerin vesikalık fotoğraflarının kaydedileceği klasör
YUZLER_KLASORU = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yapay_zeka', 'kayitli_yuzler')
os.makedirs(YUZLER_KLASORU, exist_ok=True)


def temiz_dosya_adi(isim, nfc_uid):
    """Kullanıcının yazdığı isimden (örn: Mustafa Ceceli) harika bir dosya ismi (mustafaceceli_111.jpg) üretir"""
    ceviriler = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    isim = isim.translate(ceviriler).lower()
    
    isim = re.sub(r'[^a-z0-9]', '', isim)
    return f"{isim}_{nfc_uid}.jpg"


@app.route('/', methods=['GET', 'POST'])
def login():
    hata_mesaji = None
    if request.method == 'POST':
        girilen_sifre = request.form.get('sifre')
        if girilen_sifre == SISTEM_SIFRESI:
            session['giris_basarili'] = True
            return redirect(url_for('dashboard'))
        else:
            hata_mesaji = "Hatalı Şifre! Lütfen tekrar deneyin."
    return render_template('login.html', hata=hata_mesaji)

@app.route('/logout')
def logout():
    session.pop('giris_basarili', None)
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if not session.get('giris_basarili'):
        return redirect(url_for('login'))
        
    return render_template('index.html')


# ------- DİNAMİK KULLANICI YÖNETİMİ & KULLANICI LİSTESİ -------
@app.route('/kullanici_yonetimi', methods=['GET', 'POST'])
def kullanici_yonetimi():
    if not session.get('giris_basarili'):
        return redirect(url_for('login'))
        
    mesaj = None
    
    if request.method == 'POST':
        ad_soyad = request.form.get('ad_soyad')
        nfc_uid = request.form.get('nfc_uid')
        fotograf_b64 = request.form.get('fotograf_base64')
        
        if ad_soyad and nfc_uid and fotograf_b64:
            mevcut_kullanici = db.kart_sorgula(nfc_uid)
            if mevcut_kullanici:
                mesaj = "HATA: Bu NFC Kartı sistemde zaten başka birine tanımlı!"
            else:
                dosya_adi = temiz_dosya_adi(ad_soyad, nfc_uid)
                kayit_yolu = os.path.join(YUZLER_KLASORU, dosya_adi)
                
                if "," in fotograf_b64:
                    fotograf_b64 = fotograf_b64.split(",")[1]
                resim_verisi = base64.b64decode(fotograf_b64)
                
                with open(kayit_yolu, "wb") as f:
                    f.write(resim_verisi)
                
                db_foto_yolu = f"yapay_zeka/kayitli_yuzler/{dosya_adi}"
                db.kullanici_ekle(ad_soyad, nfc_uid, db_foto_yolu)
                mesaj = f" BAŞARILI: {ad_soyad} sisteme '{dosya_adi}' adıyla kaydedildi!"
        else:
            mesaj = "Lütfen tüm alanları doldurun ve fotoğrafınızı çekin!"

    # ---- KULLANICI TABLOSU VE FİLTRELEME ----
    durum_filtre = request.args.get('filtre', 'tumu')
    baglanti = db.veritabani_baglantisi_al()
    imlec = baglanti.cursor()
    
    if durum_filtre == 'aktif':
        imlec.execute("SELECT * FROM kullanicilar WHERE aktif_mi = 1 ORDER BY id DESC")
    elif durum_filtre == 'pasif':
        imlec.execute("SELECT * FROM kullanicilar WHERE aktif_mi = 0 ORDER BY id DESC")
    else:
        imlec.execute("SELECT * FROM kullanicilar ORDER BY id DESC")
        
    kullanicilar = imlec.fetchall()
    baglanti.close()
            
    return render_template('kullanici_yonetimi.html', mesaj=mesaj, kullanicilar=kullanicilar, aktif_filtre=durum_filtre)


# ------- YENİ: YETKİ AÇ/KAPA API'Sİ -------
@app.route('/api/yetki_degistir', methods=['POST'])
def yetki_degistir():
    data = request.json
    nfc_uid = data.get('uid')
    yeni_durum = data.get('durum') # 1 (Aktif) veya 0 (Pasif)
    
    if nfc_uid and (yeni_durum == 0 or yeni_durum == 1):
        db.kullanici_yetki_guncelle(nfc_uid, yeni_durum)
        durum_metni = "AKTİF" if yeni_durum == 1 else "PASİF"
        db.log_kaydet(f"Yetki Değişimi: {nfc_uid} kartı {durum_metni} yapıldı.", "SİSTEM_AYARI")
        return jsonify({"durum": "BASARILI"})
    return jsonify({"durum": "HATA"})


@app.route('/api/kamera_cek', methods=['GET'])
def kamera_cek():
    kamera = cv2.VideoCapture(kamera_index)
    basarili, kare = kamera.read()
    kamera.release()
    
    if not basarili:
        return jsonify({"durum": "HATA", "mesaj": "Kamera donanımına ulaşılamadı!"})
        
    _, buffer = cv2.imencode('.jpg', kare)
    resim_b64 = base64.b64encode(buffer).decode('utf-8')
    return jsonify({"durum": "BASARILI", "foto": "data:image/jpeg;base64," + resim_b64})


# ------- FİLTRELİ PROFESYONEL LOGLAR -------
@app.route('/loglar')
def loglar():
    if not session.get('giris_basarili'):
        return redirect(url_for('login'))
        
    sayfa_no = request.args.get('page', 1, type=int)
    secili_durum = request.args.get('durum', 'tumu')
    baslangic_tarihi = request.args.get('baslangic', '')
    bitis_tarihi = request.args.get('bitis', '')
    
    sayfa_basi_kayit = 50 
    atlama_miktari = (sayfa_no - 1) * sayfa_basi_kayit
    
    baglanti = db.veritabani_baglantisi_al()
    imlec = baglanti.cursor()
    
    # Dinamik SQL Sorgusu Oluşturma
    sorgu_kriterleri = []
    parametreler = []
    
    if secili_durum != 'tumu':
        sorgu_kriterleri.append("durum = ?")
        parametreler.append(secili_durum)
        
    if baslangic_tarihi != '':
        sorgu_kriterleri.append("date(olay_tarihi) >= ?")
        parametreler.append(baslangic_tarihi)
        
    if bitis_tarihi != '':
        sorgu_kriterleri.append("date(olay_tarihi) <= ?")
        parametreler.append(bitis_tarihi)
        
    where_cumlesi = ""
    if len(sorgu_kriterleri) > 0:
        where_cumlesi = "WHERE " + " AND ".join(sorgu_kriterleri)
    
    # 1. Filtrelere uyan toplam kayıt sayısını bul (Sayfalama için)
    imlec.execute(f"SELECT COUNT(*) FROM kayitlar {where_cumlesi}", parametreler)
    toplam_kayit = imlec.fetchone()[0]
    toplam_sayfa = max(1, (toplam_kayit + sayfa_basi_kayit - 1) // sayfa_basi_kayit)
    
    # 2. Sadece ilgili sayfayı çek
    parametreler.extend([sayfa_basi_kayit, atlama_miktari])
    imlec.execute(f"SELECT * FROM kayitlar {where_cumlesi} ORDER BY id DESC LIMIT ? OFFSET ?", parametreler)
    kayitlar = imlec.fetchall()
    baglanti.close()
    
    return render_template('loglar.html', kayitlar=kayitlar, su_anki_sayfa=sayfa_no, toplam_sayfa=toplam_sayfa, secili_durum=secili_durum, baslangic=baslangic_tarihi, bitis=bitis_tarihi)


@app.route('/api/nfc_okutuldu', methods=['POST'])
def nfc_okutuldu():
    data = request.json
    nfc_uid = data.get('uid')
    
    kullanici = db.kart_sorgula(nfc_uid)
    if not kullanici:
        db.log_kaydet(f"Yabancı Kart: {nfc_uid}", "YABANCI_KART")
        return jsonify({"durum": "HATA", "mesaj": "Sisteme kayıtlı olmayan yabancı bir kart okutuldu!"})
        
    # ---KULLANICI PASİF Mİ? ---
    if kullanici['aktif_mi'] == 0:
        db.log_kaydet(f"{kullanici['ad_soyad']} pasif kartla girmeye çalıştı!", "YETKİSİZ_GİRİŞ_DENEMESİ")
        return jsonify({"durum": "HATA", "mesaj": f"Geçiş Reddedildi! Sayın {kullanici['ad_soyad']}, yetkiniz dondurulmuş."})
        
    print(f"[SİSTEM] {kullanici['ad_soyad']} için kart okutuldu. Kamera uyanıyor...")
    kamera = cv2.VideoCapture(kamera_index)
    basarili, kare = kamera.read()
    kamera.release()
    
    if not basarili:
        return jsonify({"durum": "HATA", "mesaj": "Kamera ulaşılamadı!"})
        
    foto_yolu = kullanici['yuz_fotograf_yolu'] 
    dogrulandi_mi, mesaj, islenmis_kare = yz.yuz_dogrula(kare, foto_yolu)
    
    _, buffer = cv2.imencode('.jpg', islenmis_kare)
    resim_b64 = base64.b64encode(buffer).decode('utf-8')
    
    if dogrulandi_mi:
        db.log_kaydet(f"{kullanici['ad_soyad']} giriş yaptı", "BAŞARILI_GİRİŞ")
        return jsonify({"durum": "BASARILI", "mesaj": f"Hoş Geldin, {kullanici['ad_soyad']}! Kapı açıldı.", "foto": resim_b64})
    else:
        db.log_kaydet(f"{kullanici['ad_soyad']} adına başarısız deneme!", "İHLAL_GİRİŞİMİ")
        return jsonify({"durum": "HATA", "mesaj": f"Güvenlik İhlali: {mesaj}", "foto": resim_b64})


@app.route('/kapi_ac', methods=['POST'])
def kapi_ac():
    print("KAPI MANUEL OLARAK AÇILDI!")
    db.log_kaydet("Manuel butonla kapı açıldı", "BAŞARILI_GİRİŞ")
    return "OK"

if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)
