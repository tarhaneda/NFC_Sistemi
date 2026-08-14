


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
import threading 

import time 
from queue import Queue, Empty 
from flask import Response 
import socket  

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from veritabani.database import veritabani_baglantisi_al
from yapay_zeka import yuz_tanima as yz
from veritabani import database as db
import telegram_logger
import requests  

SON_CANLI_BILDIRIM= {"id": 0, "mesaj":"Sistem Başlatıldı"}

load_dotenv()

app = Flask(__name__)

def udp_dinleyici_baslat():
    UDP_IP="0.0.0.0"
    UDP_PORT=5555

    sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP,UDP_PORT))
    print(f"[SİSTEM] UDP Keşif Alanı {UDP_PORT} portunda NodeMCU'ları bekliyor...")

    while True:
        try:
            data,addr=sock.recvfrom(1024)
            mesaj=data.decode("utf-8").strip()

            if mesaj=="NFC_SERVER_NERDESIN":
                s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                try:
                    s.connect(('10.255.255.255',1))
                    benim_ip=s.getsockname()[0]
                except Exception:
                    benim_ip='127.0.0.1'
                finally:
                    s.close()

                cevap=f"BEN_BURADAYIM:{benim_ip}"
                sock.sendto(cevap.encode('utf-8'), addr)
                print(f"[UDP] {addr[0]} adresindeki NodeMCU'ya güncel IP ({benim_ip}) fısıldandı")
        except Exception as e:
            print(f"[UDP HATA] {e}")
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))






SISTEM_SIFRESI = os.getenv("SISTEM_SIFRESI")

bekleyen_analizler={}

db_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'veritabani', 'kapi_sistemi.db')
if not os.path.exists(db_yolu):
    print("[SİSTEM] Veritabanı bulunamadı, yeni tablolar oluşturuluyor...")
    db.tablolari_olustur()

kamera_index = int(os.getenv("KAMERA_INDEX", 1))


YUZLER_KLASORU = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yapay_zeka', 'kayitli_yuzler')
os.makedirs(YUZLER_KLASORU, exist_ok=True)


def temiz_dosya_adi(isim, nfc_uid):
    """Kullanıcının yazdığı isimden (örn: Mustafa Ceceli) harika bir dosya ismi (mustafaceceli_111.jpg) üretir"""
    ceviriler = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    isim = isim.translate(ceviriler).lower()

    
    isim = re.sub(r'[^a-z0-9]', '', isim)
    nfc_uid = nfc_uid.replace(":", "")

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



@app.route('/kullanici_yonetimi', methods=['GET', 'POST'])
def kullanici_yonetimi():
    if not session.get('giris_basarili'):
        return redirect(url_for('login'))
        
    mesaj = None
    
    if request.method == 'POST':
        ad_soyad = request.form.get('ad_soyad')
        nfc_uid = request.form.get('nfc_uid')
        rol=request.form.get('rol', 'PERSONEL')
        gecerlilik_tarihi=request.form.get('gecerlilik_tarihi', '')
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
                db.kullanici_ekle(ad_soyad, nfc_uid, db_foto_yolu, rol,gecerlilik_tarihi)
                mesaj = f" BAŞARILI: {ad_soyad} sisteme '{dosya_adi}' adıyla kaydedildi!"
        else:
            mesaj = "Lütfen tüm alanları doldurun ve fotoğrafınızı çekin!"

    durum_filtre=request.args.get('filtre','tumu')
    arama_ad=request.args.get('arama_ad', '')
    arama_nfc=request.args.get('arama_nfc','')
    baslangic=request.args.get('baslangic','')
    bitis=request.args.get('bitis', '')
    
    baglanti=db.veritabani_baglantisi_al()
    imlec=baglanti.cursor()

    sorgu_kriterleri=[]
    parametreler=[]

    if durum_filtre=='aktif':
        sorgu_kriterleri.append("aktif_mi=1")
    elif durum_filtre=='pasif':
        sorgu_kriterleri.append("aktif_mi=0")

    if arama_ad != '':
        sorgu_kriterleri.append("ad_soyad LIKE ?")
        parametreler.append(f"%{arama_ad}%")
    
    if arama_nfc != '':
        sorgu_kriterleri.append("nfc_uid LIKE ?")
        parametreler.append(f"%{arama_nfc}%")

    if baslangic != '':
        sorgu_kriterleri.append("date(kayit_tarihi) >= ?")
        parametreler.append(baslangic)

    if bitis != '':
        sorgu_kriterleri.append("date(kayit_tarihi) <= ?")
        parametreler.append(bitis)

    where_cumlesi = ""
    if len(sorgu_kriterleri) > 0:
        where_cumlesi = "WHERE " + " AND ".join(sorgu_kriterleri)

    imlec.execute(f"SELECT * FROM kullanicilar {where_cumlesi} ORDER BY id DESC", parametreler)
    kullanicilar = imlec.fetchall()
    baglanti.close()

    return render_template('kullanici_yonetimi.html', 
                           mesaj=mesaj, 
                           kullanicilar=kullanicilar, 
                           aktif_filtre=durum_filtre,
                           arama_ad=arama_ad,
                           arama_nfc=arama_nfc,
                           baslangic=baslangic,
                           bitis=bitis)

API_SECRET_KEY = os.getenv("API_SECRET_KEY")
NODEMCU_IP=None
nfc_arayuz_dinleyicileri = []


        
@app.route('/kullanici_duzenle/<int:id>', methods=['GET', 'POST'])
def kullanici_duzenle(id):
    if not session.get('giris_basarili'):
        return redirect(url_for('login'))
        
    mevcut_kisi = db.kullanici_getir(id)
    if not mevcut_kisi:
        return redirect(url_for('kullanici_yonetimi'))

    mesaj = ""
    if request.method == 'POST':
        ad_soyad = request.form.get('ad_soyad')
        nfc_uid = request.form.get('nfc_uid')
        fotograf_base64 = request.form.get('fotograf_base64')
        rol=request.form.get('rol', 'PERSONEL')
        gecerlilik_tarihi=request.form.get('gecerlilik_tarihi','')
        
        eski_foto_yolu = mevcut_kisi['yuz_fotograf_yolu']
        
       
        if fotograf_base64 and len(fotograf_base64) > 100:
            import base64
            try:
                header, encoded = fotograf_base64.split(",", 1)
                resim_verisi = base64.b64decode(encoded)
                with open(eski_foto_yolu, "wb") as f:
                    f.write(resim_verisi)  
                    
               
                import yapay_zeka.yuz_tanima as yt
                if eski_foto_yolu in yt.Hafiza_Cache:
                    del yt.Hafiza_Cache[eski_foto_yolu]
                    print(f"[{ad_soyad}] için yapay zeka hafızası SIFIRLANDI! İlk geçişinde yeniden yüz öğrenecek.")
                    
            except Exception as e:
                mesaj = f"HATA: Fotoğraf güncellenemedi: {str(e)}"
                return render_template('kullanici_duzenle.html', kisi=mevcut_kisi, mesaj=mesaj)

        
        basarili, guncelleme_mesaji = db.kullanici_guncelle(id, ad_soyad, nfc_uid,rol,gecerlilik_tarihi)
        
        if basarili:
            mevcut_kisi = db.kullanici_getir(id) 
            mesaj = "✅ " + guncelleme_mesaji
        else:
            mesaj = "❌ " + guncelleme_mesaji
        
    return render_template('kullanici_duzenle.html', kisi=mevcut_kisi, mesaj=mesaj)

                
               
        
    



@app.route('/api/yetki_degistir', methods=['POST'])
def yetki_degistir():
    if not session.get('giris_basarili'):
        return jsonify({"durum": "HATA", "mesaj": "Yetkisiz Erişim!"}), 403
    data = request.json
    nfc_uid = data.get('uid')
    yeni_durum = data.get('durum')
    
    if nfc_uid and (yeni_durum == 0 or yeni_durum == 1):
        
        eski_kullanici = db.kart_sorgula(nfc_uid)
        isim = eski_kullanici['ad_soyad'] if eski_kullanici else nfc_uid
        
       
        db.kullanici_yetki_guncelle(nfc_uid, yeni_durum)
        
       
        if eski_kullanici and eski_kullanici['aktif_mi'] == 2 and yeni_durum == 1:
            db.log_kaydet(f"{isim} - Kart blokesi kaldırıldı.", "SİSTEM_AYARI")
        else:
            durum_metni = "AKTİF" if yeni_durum == 1 else "PASİF"
            db.log_kaydet(f"Yetki Değişimi: {isim} kartı {durum_metni} yapıldı.", "SİSTEM_AYARI")
            
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
    
   
    imlec.execute(f"SELECT COUNT(*) FROM kayitlar {where_cumlesi}", parametreler)
    toplam_kayit = imlec.fetchone()[0]
    toplam_sayfa = max(1, (toplam_kayit + sayfa_basi_kayit - 1) // sayfa_basi_kayit)
    
    
    parametreler.extend([sayfa_basi_kayit, atlama_miktari])
    imlec.execute(f"SELECT * FROM kayitlar {where_cumlesi} ORDER BY id DESC LIMIT ? OFFSET ?", parametreler)
    kayitlar = imlec.fetchall()
    baglanti.close()
    
    return render_template('loglar.html', kayitlar=kayitlar, su_anki_sayfa=sayfa_no, toplam_sayfa=toplam_sayfa, secili_durum=secili_durum, baslangic=baslangic_tarihi, bitis=bitis_tarihi)

@app.route('/api/bekleyen_kart_stream')
def bekleyen_kart_stream():
    def event_stream():
        q = Queue()
        nfc_arayuz_dinleyicileri.append(q) 
        try:
            while True:
                try:
                    uid = q.get(timeout=1)
                    yield f"data: {uid}\n\n"
                except Empty:
                    yield ": ping\n\n"
        except GeneratorExit:
            if q in nfc_arayuz_dinleyicileri:
                nfc_arayuz_dinleyicileri.remove(q) 
            
    return Response(event_stream(), mimetype="text/event-stream")



@app.route('/api/kart_kontrol', methods=['POST'])
def kart_kontrol():
    data=request.json
    nfc_uid=data.get('uid').strip().upper()

    kullanici=db.kart_sorgula(nfc_uid)
    if not kullanici:
        db.log_kaydet(f"Yabancı Kart: {nfc_uid}", "YABANCI_KART")
        return jsonify({"durum": "HATA", "mesaj": "Sisteme kayıtlı olmayan yabancı bir kart okutuldu!"})

    if kullanici['aktif_mi']==0:
        db.log_kaydet(f"{kullanici['ad_soyad']} pasif kartla girmeye çalıştı!", "YETKİSİZ_GİRİŞ_DENEMESİ")
        return jsonify({"durum": "HATA", "mesaj": f"Geçiş Reddedildi! Sayın {kullanici['ad_soyad']}, yetkiniz dondurulmuş (İşten Ayrılan)."})
      
    if kullanici['iceride_mi'] == 1:
        db.log_kaydet(f"Zaten içeride olan kartla giriş denemesi: {kullanici['ad_soyad']}", "YETKİSİZ_GİRİŞ_DENEMESİ")
        return jsonify({"durum": "HATA", "mesaj": f"Geçiş Reddedildi! Sayın {kullanici['ad_soyad']}, sistemde zaten içeride görünüyorsunuz. Lütfen önce çıkış yapın."})

    elif kullanici['aktif_mi']==2:
        db.log_kaydet(f"Blokeli kartla giriş denemesi: {nfc_uid}", "YETKİSİZ_GİRİŞ_DENEMESİ")
        return jsonify({"durum": "HATA", "mesaj": "Bu kart şüpheli işlemler sebebiyle BLOKE edilmiştir! Yöneticinizle görüşün."})


    if kullanici.get('gecerlilik_tarihi'):
        from datetime import datetime
        gecerlilik = datetime.strptime(kullanici['gecerlilik_tarihi'], '%Y-%m-%d').date()
        bugun = datetime.now().date()
        if bugun > gecerlilik:
            db.log_kaydet(f"Süresi dolmuş kart denemesi: {kullanici['ad_soyad']}", "YETKİSİZ_GİRİŞ_DENEMESİ")
            return jsonify({"durum": "HATA", "mesaj": f"Geçiş Reddedildi! Kartınızın süresi {gecerlilik} tarihinde dolmuş."})


    return jsonify ({"durum": "BASARILI", "mesaj": f"Sayın {kullanici['ad_soyad']}, lütfen yüzünüzü kameraya hizalayıp taratın.", "rol":kullanici['rol']})

def arka_planda_yuz_tara(uid,fotograf_b64, foto_yolu):
    try:
        import numpy as np 
        if "," in fotograf_b64:
            fotograf_b64=fotograf_b64.split(",")[1]

        resim_verisi=base64.b64decode(fotograf_b64)
        nparr=np.frombuffer(resim_verisi,np.uint8)
        kare=cv2.imdecode(nparr,cv2.IMREAD_COLOR)

        dogrulandi_mi,mesaj,islenmis_kare=yz.yuz_dogrula(kare,foto_yolu)

        bekleyen_analizler[uid]={
            "durum":"TAMAMLANDI",
            "dogrulandi_mi": dogrulandi_mi,
            "mesaj":mesaj,
            "islenmis_kare":islenmis_kare
        }

    except Exception as e:
        bekleyen_analizler[uid]={"durum": "HATA", "mesaj":str(e)}

@app.route('/api/on_analiz_baslat', methods=['POST'])
def on_analiz_baslat():

  
    data=request.json
    uid=data.get('uid').strip().upper()
    fotograf_b64=data.get('image')
    
    kullanici=db.kart_sorgula(uid)
    if not kullanici or kullanici['aktif_mi']!=1:
        return jsonify({"durum": "HATA"})

    foto_yolu=kullanici['yuz_fotograf_yolu']

    bekleyen_analizler[uid]={"durum": "ISLENIYOR"}
    threading.Thread(target=arka_planda_yuz_tara, args=(uid,fotograf_b64, foto_yolu),daemon=True).start()

    return jsonify({"durum": "BASARILI"})





@app.route('/api/yuz_kontrol', methods=['POST'])
def yuz_kontrol():
    data=request.json
    nfc_uid=data.get('uid').strip().upper()
    
    kullanici=db.kart_sorgula(nfc_uid)
    if not kullanici or kullanici['aktif_mi'] != 1:
        return jsonify({"durum": "HATA", "mesaj": "Geçersiz veya yetkisiz kart."})
    bekleme_suresi=0
    while bekleme_suresi<30:
        sonuc=bekleyen_analizler.get(nfc_uid)

        if sonuc and sonuc.get("durum")=="TAMAMLANDI":
            dogrulandi_mi=sonuc["dogrulandi_mi"]
            mesaj=sonuc["mesaj"]
            islenmis_kare_veri=sonuc["islenmis_kare"]

            _,buffer=cv2.imencode('.jpg', islenmis_kare_veri)
            resim_b64_out=base64.b64encode(buffer).decode('utf-8')

            del bekleyen_analizler[nfc_uid]

            if dogrulandi_mi:
                if NODEMCU_IP:
                    try:
                        requests.get(f"http://{NODEMCU_IP}/motoru_ac", timeout=2)
                    except:
                        pass
                os.makedirs("log_resimleri", exist_ok=True)
                temiz_uid=nfc_uid.replace(":","")
                basarili_foto_yolu=f"log_resimleri/basarili_{temiz_uid}_{int(time.time())}.jpg"
                cv2.imwrite(basarili_foto_yolu, islenmis_kare_veri)

                baglanti = db.veritabani_baglantisi_al()
                imlec = baglanti.cursor()
                imlec.execute("UPDATE kullanicilar SET iceride_mi = 1 WHERE id = ?", (kullanici['id'],))
                baglanti.commit()
                baglanti.close()

            
                db.log_kaydet(f"{kullanici['ad_soyad']} giriş yaptı", "BAŞARILI_GİRİŞ", basarili_foto_yolu)
                global SON_CANLI_BILDIRIM
                SON_CANLI_BILDIRIM = {
                    "id": SON_CANLI_BILDIRIM["id"] + 1, 
                    "mesaj": f"🚪 {kullanici['ad_soyad']} Giriş Yaptı!"
                } 
                
                return jsonify({"durum": "BASARILI", "mesaj": f"Hoş Geldin, {kullanici['ad_soyad']}!", "foto": resim_b64_out})
            else:
                return jsonify({"durum": "HATA", "mesaj": f"Yüz Eşleşmedi: {mesaj}", "foto": resim_b64_out})
        
        elif sonuc and sonuc.get("durum")=="HATA":
            del bekleyen_analizler[nfc_uid]
            return jsonify({"durum": "HATA", "mesaj": f"Yüz Tespiti Hatası: {sonuc['mesaj']}"})
        
        time.sleep(0.1)
        bekleme_suresi+=0.1

    return jsonify({"durum": "HATA", "mesaj": "Belirlenen sürede yüz algılanamadı."})

    
@app.route('/api/kart_bloke_et', methods=['POST'])
def kart_bloke_et():
    data = request.json
    nfc_uid = data.get('uid').strip().upper()
    
    kullanici = db.kart_sorgula(nfc_uid)
    if kullanici:
        db.kullanici_yetki_guncelle(nfc_uid, 2)
        
        os.makedirs("log_resimleri", exist_ok=True)
        fotograf_b64 = data.get('image')
        ihlal_foto_yolu = ""
        if fotograf_b64:
            if "," in fotograf_b64:
                fotograf_b64 = fotograf_b64.split(",")[1]
            try:
                resim_verisi = base64.b64decode(fotograf_b64)
                temiz_uid = nfc_uid.replace(":", "")
                ihlal_foto_yolu = f"log_resimleri/bloke_{temiz_uid}.jpg"
                with open(ihlal_foto_yolu, "wb") as f:
                    f.write(resim_verisi)
            except:
                pass
                
        db.log_kaydet(f"{kullanici['ad_soyad']} kartı BLOKE edildi (3 Hata)!", "YETKİSİZ_GİRİŞ_DENEMESİ", ihlal_foto_yolu)
        return jsonify({"durum": "BASARILI", "mesaj": "Güvenlik İhlali: Kartınız bloke edildi!"})
    return jsonify({"durum": "HATA", "mesaj": "Kart bulunamadı."})
        


@app.route('/kapi_ac', methods=['POST'])
def kapi_ac():
    if not session.get('giris_basarili'):
        return jsonify({"durum": "HATA", "mesaj": "Yetkisiz Erişim!"}), 403
    if NODEMCU_IP:
        try:
            requests.get(f"http://{NODEMCU_IP}/motoru_ac", timeout=2)
        except:
            pass

    print("KAPI MANUEL OLARAK AÇILDI!")
    db.log_kaydet("Manuel butonla kapı açıldı", "BAŞARILI_GİRİŞ")
    return "OK"

@app.route('/api/admin_kart_kontrol', methods=['POST'])
def admin_kart_kontrol():
    data = request.json
    uid = data.get('uid')
    
    baglanti = db.veritabani_baglantisi_al()
    imlec = baglanti.cursor()
    
    
    imlec.execute("SELECT COUNT(*) FROM kullanicilar WHERE rol = 'YONETICI'")
    yonetici_sayisi = imlec.fetchone()[0]
    
    if yonetici_sayisi == 0:
        baglanti.close()
        return jsonify({"durum": "BASARILI", "mesaj": "Sistemde yönetici yok, şifrenizi giriniz."})
        
    
    imlec.execute("SELECT * FROM kullanicilar WHERE nfc_uid = ?", (uid,))
    kullanici_row = imlec.fetchone()
    baglanti.close()
    
    if not kullanici_row:
        return jsonify({"durum": "HATA", "mesaj": "Kart sistemde kayıtlı değil!"})
        
    kullanici = dict(kullanici_row)
    
    if kullanici.get('rol') == 'YONETICI':
        return jsonify({"durum": "BASARILI", "mesaj": "Yönetici kartı doğrulandı, lütfen şifrenizi girin."})
    else:
        return jsonify({"durum": "HATA", "mesaj": "Siz sadece personelsiniz, yönetim paneline giremezsiniz!"})

import pandas as pd
from io import BytesIO
from flask import send_file

@app.route('/api/rapor_indir')
def rapor_indir():
    if not session.get('giris_basarili'):
        return redirect(url_for('login'))
        
    baslangic = request.args.get('baslangic', '')
    bitis = request.args.get('bitis', '')
    
    baglanti = db.veritabani_baglantisi_al()
    sorgu = "SELECT olay_detayi as 'Personel / İşlem', durum as 'Giriş Durumu', olay_tarihi as 'Tarih ve Saat' FROM kayitlar"
    parametreler = []
    sorgu_kriterleri = []
    
    if baslangic != '':
        sorgu_kriterleri.append("date(olay_tarihi) >= ?")
        parametreler.append(baslangic)
    if bitis != '':
        sorgu_kriterleri.append("date(olay_tarihi) <= ?")
        parametreler.append(bitis)
        
    if len(sorgu_kriterleri) > 0:
        sorgu += " WHERE " + " AND ".join(sorgu_kriterleri)
        
    sorgu += " ORDER BY id DESC"
    
    df = pd.read_sql_query(sorgu, baglanti, params=parametreler)
    baglanti.close()
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Geçiş Kayıtları')
        
    output.seek(0)
    
    tarih_metni = "tum_kayitlar"
    if baslangic or bitis:
        tarih_metni = f"{baslangic}_{bitis}"
        
    return send_file(output, download_name=f"puantaj_raporu_{tarih_metni}.xlsx", as_attachment=True)

import random  
aktif_2fa_kodlari={}

import asyncio

@app.route('/api/uzaktan_giris_kod_gonder', methods=['POST'])
def uzaktan_giris_kod_gonder():
    data = request.json
    sifre = data.get('sifre')

    if sifre == SISTEM_SIFRESI:
        guvenlik_kodu = str(random.randint(100000, 999999))
        aktif_2fa_kodlari['yonetici'] = guvenlik_kodu

        mesaj = f"🚨 UZAKTAN GİRİŞ DENEMESİ 🚨\nSistem paneline uzaktan giriş yapılmaya çalışılıyor.\n\nOnay Kodunuz: {guvenlik_kodu}"
        
        asyncio.run(telegram_logger.mesaj_gonder(mesaj))
        
        return jsonify({"durum": "BASARILI", "mesaj": "Telegram'a onay kodu gönderildi."})
    else:
        db.log_kaydet("Uzaktan giriş: Hatalı sistem şifresi denemesi!", "YETKİSİZ_GİRİŞ_DENEMESİ")
        return jsonify({"durum": "HATA", "mesaj": "Hatalı Sistem Şifresi!"})


aktif_2fa_kodlari = {}
deneme_sayaci = 0 

@app.route('/api/uzaktan_giris_dogrula', methods=['POST'])
def uzaktan_giris_dogrula():
    global deneme_sayaci
    data = request.json
    girilen_kod = data.get('kod')
    
    beklenen_kod = aktif_2fa_kodlari.get('yonetici')
    
    if beklenen_kod and girilen_kod == beklenen_kod:
        session['giris_basarili'] = True
        del aktif_2fa_kodlari['yonetici'] 
        deneme_sayaci = 0 
        db.log_kaydet("Yönetici Uzaktan Giriş Yaptı (2FA Başarılı)", "SİSTEM_AYARI")
        return jsonify({"durum": "BASARILI", "url": url_for('dashboard')})
    else:
        deneme_sayaci += 1
        if deneme_sayaci >= 3:
            
            if 'yonetici' in aktif_2fa_kodlari:
                del aktif_2fa_kodlari['yonetici']
            db.log_kaydet("ŞÜPHELİ İŞLEM: Çok fazla hatalı 2FA! Kod imha edildi.", "YETKİSİZ_GİRİŞ_DENEMESİ")
            return jsonify({"durum": "HATA", "mesaj": "Çok fazla hata! Güvenlik kodu İMHA EDİLDİ."})
            
        return jsonify({"durum": "HATA", "mesaj": f"Hatalı Kod! Kalan deneme: {3 - deneme_sayaci}"})




@app.route('/api/sekme_kapandi', methods=['POST'])
def sekme_kapandi():
    """Tarayıcı sekmesi kapandığı an (Ping atmadan) tek seferlik sinyal gelir."""
    print("\n[BİLGİ] Yönetici sekmesi kapatıldı!")
    
    return "OK", 200

@app.route('/api/sunucu_durumu')
def sunucu_durumu():
    """Sunucudan tarayıcıya 'Ben Hayattayım' diyen açık hat (SSE)."""
    def generate():
        try:
            while True:
                yield "data: online\n\n"
                time.sleep(1) 
        except GeneratorExit:
           
            pass
            
    return Response(generate(), mimetype='text/event-stream')

@app.route('/kisi_loglari',methods=['GET'])
def kisi_loglari():
    if not session.get('giris_basarili'):
        return redirect(url_for('login'))

    baglanti=db.veritabani_baglantisi_al()
    imlec=baglanti.cursor()

    imlec.execute("SELECT id,ad_soyad FROM kullanicilar ORDER BY ad_soyad")
    kullanicilar=imlec.fetchall()

    secili_kisi_id=request.args.get('kisi_id')
    secili_tarih=request.args.get('tarih')

    import datetime
    if not secili_tarih:
        secili_tarih=datetime.date.today().strftime('%Y-%m-%d')
        
    secili_islem = request.args.get('islem_turu', 'tumu')
    
    # Durum filtresi için SQL koşulunu belirleyelim
    durum_kosulu = "durum In ('BAŞARILI_GİRİŞ', 'BAŞARILI_ÇIKIŞ')"
    if secili_islem == 'giris':
        durum_kosulu = "durum = 'BAŞARILI_GİRİŞ'"
    elif secili_islem == 'cikis':
        durum_kosulu = "durum = 'BAŞARILI_ÇIKIŞ'"

    loglar=[]
    secili_kisi_adi=""
    genel_loglar=[]

    if secili_kisi_id:
        imlec.execute("SELECT ad_soyad FROM kullanicilar WHERE id= ?",(secili_kisi_id,))
        kisi=imlec.fetchone()
        if kisi: 
            secili_kisi_adi=kisi['ad_soyad']
        
        sorgu=f"""
        SELECT olay_detayi, durum, olay_tarihi
        FROM kayitlar
        WHERE olay_detayi LIKE ?
        AND olay_tarihi LIKE ?
        AND {durum_kosulu}
        ORDER BY olay_tarihi ASC"""

        imlec.execute(sorgu,(f"{secili_kisi_adi}%", f"{secili_tarih}%"))
        ham_loglar=imlec.fetchall()

        for log in ham_loglar:
            tarih_obj = datetime.datetime.strptime(log['olay_tarihi'], '%Y-%m-%d %H:%M:%S')
            saat_dakika = tarih_obj.strftime('%H:%M')
            tip = "giris" if "GİRİŞ" in log['durum'] else "cikis"
            loglar.append({"saat": saat_dakika, "tip": tip})
            
    else:
        
        sorgu=f"""
        SELECT olay_detayi, durum, olay_tarihi
        FROM kayitlar
        WHERE olay_tarihi LIKE ?
        AND {durum_kosulu}
        ORDER BY olay_tarihi DESC"""
        imlec.execute(sorgu, (f"{secili_tarih}%",))
        ham_genel = imlec.fetchall()
        
        
        for log in ham_genel:
            saf_isim = log['olay_detayi']
            kisi_id_eslesme = None
            for k in kullanicilar:
                if k['ad_soyad'] in log['olay_detayi']:
                    kisi_id_eslesme = k['id']
                    saf_isim = k['ad_soyad']
                    break
            
            genel_loglar.append({
                "saat": log['olay_tarihi'].split(' ')[1][:5],
                "isim": saf_isim,
                "durum": log['durum'],
                "kisi_id": kisi_id_eslesme
            })

    baglanti.close()
    
    return render_template('kisi_loglari.html', 
                           kullanicilar=kullanicilar, 
                           secili_kisi_id=int(secili_kisi_id) if secili_kisi_id else None,
                           secili_kisi_adi=secili_kisi_adi,
                           secili_tarih=secili_tarih,
                           secili_islem=secili_islem,
                           loglar=loglar,
                           genel_loglar=genel_loglar)


from queue import Empty 

@app.route('/api/donanim_nfc_okundu', methods=['POST'])
def donanim_nfc_okundu():
    global NODEMCU_IP 
    NODEMCU_IP = request.remote_addr
    data = request.json

    if data.get("api_key") != API_SECRET_KEY:
        db.log_kaydet("Sahte donanım isteği engellendi!", "YETKİSİZ_GİRİŞ_DENEMESİ")
        return jsonify({"status": "RED", "mesaj": "Yetkisiz cihaz!"}), 403

    nfc_uid = data.get('uid').strip().upper()
    kapi_turu = data.get('kapi', 'giris') 
    
    kullanici = db.kart_sorgula(nfc_uid)
    if not kullanici or kullanici['aktif_mi'] != 1:
        return jsonify({"status": "RED", "mesaj": "Yetkisiz veya yabancı kart!"})
        
    if kapi_turu == "giris":
        for q in nfc_arayuz_dinleyicileri:
            q.put(nfc_uid)
        return jsonify({"status": "BEKLE", "mesaj": "Yüz taraması bekleniyor"})
        
    elif kapi_turu == "cikis":

        if kullanici['iceride_mi'] == 0:
            db.log_kaydet(f"Dışarıda görünen kartla çıkış denemesi: {kullanici['ad_soyad']}", "YETKİSİZ_GİRİŞ_DENEMESİ")
            return jsonify({"status": "RED"})
            
        baglanti = db.veritabani_baglantisi_al()
        imlec = baglanti.cursor()
        imlec.execute("UPDATE kullanicilar SET iceride_mi= 0 WHERE id= ?", (kullanici['id'],))
        baglanti.commit()
        baglanti.close()
        
        db.log_kaydet(f"{kullanici['ad_soyad']} kartı ile çıkış yapıldı", "BAŞARILI_ÇIKIŞ")
        global SON_CANLI_BILDIRIM
        SON_CANLI_BILDIRIM = {
            "id": SON_CANLI_BILDIRIM["id"] + 1, 
            "mesaj": f"🚪 {kullanici['ad_soyad']} Çıkış Yaptı!"
        }
        return jsonify({"status": "MOTOR_AC"})

@app.route('/api/canli_bildirim',methods=['GET'])
def canli_bildirim_getir():
    return jsonify(SON_CANLI_BILDIRIM)


if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:5000")
    threading.Thread(target=udp_dinleyici_baslat, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)




