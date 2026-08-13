from cv2 import cvtColor
import face_recognition
import cv2
import os
import numpy as np

# YAPAY ZEKA HAFIZASI (Önbellek)
Hafiza_Cache = {}

yuz_dedektoru=cv2.CascadeClassifier(cv2.data.haarcascades+ 'haarcascade_frontalface_default.xml')

# ===================================================================
# [YENİ] MATEMATİKSEL CANLILIK (LIVENESS) TESPİTİ
# Hiçbir şey indirmez! Ekran piksel yapısını ve ışık yansımasını ölçer.
# ===================================================================
def canli_insan_mi(kamera_karesi, ust, sag, alt, sol):
    try:
        # Yüzü resimden kesiyoruz
        ust, alt = max(0, int(ust)), min(kamera_karesi.shape[0], int(alt))
        sol, sag = max(0, int(sol)), min(kamera_karesi.shape[1], int(sag))
        
        yuz_kirpilmis = kamera_karesi[ust:alt, sol:sag]
        if yuz_kirpilmis.shape[0] < 20 or yuz_kirpilmis.shape[1] < 20:
            return False
            
        # 1. TEST: Piksel / Moiré (Laplacian Varyansı) Analizi
        # Telefon ekranları kameraya tutulduğunda mikro titreşimler ve pikseller bulanıklık yaratır
        gri_yuz = cv2.cvtColor(yuz_kirpilmis, cv2.COLOR_BGR2GRAY)
        netlik = cv2.Laplacian(gri_yuz, cv2.CV_64F).var()
        
        # 2. TEST: Işık Yansıması (HSV Renk Uzayı)
        # Telefon ekranı kendi ışığını yayar, insan derisi ise ortam ışığını yansıtır.
        hsv_yuz = cv2.cvtColor(yuz_kirpilmis, cv2.COLOR_BGR2HSV)
        parlaklik_ortalamasi = np.mean(hsv_yuz[:, :, 2])
        
        # Karar Mekanizması:
        # Kağıt fotoğraf ise çok düşük netlik (blur) olur.
        # Ekran/Tablet ise hem aşırı parlaklık hem de Laplacian gürültüsü olur.
        if netlik < 60:
            print(f"[LIVENESS] Reddedildi! Bulanık / Fotoğraf (Netlik: {netlik:.1f})")
            return False
            
        if parlaklik_ortalamasi > 160:
             print(f"[LIVENESS] Reddedildi! Aşırı Parlama / Ekran Yüzeyi (Parlaklık: {parlaklik_ortalamasi:.1f})")
             return False
             
        # Eğer bu testleri geçerse gerçek insandır.
        print(f"[LIVENESS] BAŞARILI! (Netlik: {netlik:.1f}, Parlaklık: {parlaklik_ortalamasi:.1f})")
        return True
        
    except Exception as e:
        print("[HATA] Canlılık Tespiti Başarısız:", e)
        return False
# ===================================================================


def yuz_dogrula(kamera_karesi, beklenen_kisi_foto_yolu):
    if not os.path.exists(beklenen_kisi_foto_yolu):
        return False, "Sistemde referans fotoğraf bulunamadı", kamera_karesi

    # HIZ İÇİN %75 KÜÇÜLTME
    kucuk_kare = cv2.resize(kamera_karesi, (0, 0), fx=0.25, fy=0.25)
    rgb_kare = cv2.cvtColor(kucuk_kare, cv2.COLOR_BGR2RGB)
    gri_kare = cvtColor(kucuk_kare,cv2.COLOR_BGR2GRAY)

    bulunan_yuzler=yuz_dedektoru.detectMultiScale(gri_kare,scaleFactor=1.1,minNeighbors=5,minSize=(20,20))

    anlik_yuz_konumlari_kucuk=[]
    for(x,y,w,h) in bulunan_yuzler:
        anlik_yuz_konumlari_kucuk.append((y,x+w,y+h,x))

    anlik_yuz_kodlari=face_recognition.face_encodings(rgb_kare,anlik_yuz_konumlari_kucuk)
    
    if len(anlik_yuz_kodlari) == 0:
        return False, "Kamerada net bir yüz bulunamadı", kamera_karesi
    
    if beklenen_kisi_foto_yolu not in Hafiza_Cache:
        kayitli_resim = face_recognition.load_image_file(beklenen_kisi_foto_yolu)
        kayitli_yuz_kodlari = face_recognition.face_encodings(kayitli_resim)
        
        if len(kayitli_yuz_kodlari) == 0:
            return False, "Kayıtlı yüz tespit edilemedi", kamera_karesi
            
        Hafiza_Cache[beklenen_kisi_foto_yolu] = kayitli_yuz_kodlari[0]

    beklenen_kodlama = Hafiza_Cache[beklenen_kisi_foto_yolu]
    
    eslesme_basarili = False
    hedef_konum = None

    for (ust, sag, alt, sol), anlik_kod in zip(anlik_yuz_konumlari_kucuk, anlik_yuz_kodlari):
        eslesme = face_recognition.compare_faces([beklenen_kodlama], anlik_kod, tolerance=0.65)[0]
        if eslesme:
            eslesme_basarili = True
            hedef_konum = (ust, sag, alt, sol)
            break 
            
    if eslesme_basarili:
        ust, sag, alt, sol = hedef_konum
        ust, sag, alt, sol = ust * 4, sag * 4, alt * 4, sol * 4
        
        # ===========================================================
        # [YENİ] KİMLİK EŞLEŞTİKTEN SONRA CANLILIK KONTROLÜ
        # ===========================================================
        canli_mi = canli_insan_mi(kamera_karesi, ust, sag, alt, sol)
        
        if canli_mi:
            cv2.rectangle(kamera_karesi, (sol, ust), (sag, alt), (0, 255, 0), 3) # Yeşil (Kabul)
            cv2.putText(kamera_karesi, "GERCEK", (sol, ust - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 0), 2)
            return True, "Doğrulama başarılı.", kamera_karesi
        else:
            cv2.rectangle(kamera_karesi, (sol, ust), (sag, alt), (0, 165, 255), 3) # Turuncu (Sahte Uyarısı)
            cv2.putText(kamera_karesi, "SAHTE (VIDEO) REDDEDILDI", (sol, ust - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 165, 255), 2)
            return False, "Yüz eşleşti ama Canlılık Testi Başarısız (Ekran Tespit Edildi)", kamera_karesi
        # ===========================================================

    else:
        ust, sag, alt, sol = anlik_yuz_konumlari_kucuk[0]
        ust, sag, alt, sol = ust * 4, sag * 4, alt * 4, sol * 4
        cv2.rectangle(kamera_karesi, (sol, ust), (sag, alt), (0, 0, 255), 3) # Kırmızı çerçeve
        return False, "Yüz eşleşmedi (Yabancı)", kamera_karesi

