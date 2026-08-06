import face_recognition
import cv2
import os

# YAPAY ZEKA HAFIZASI (Önbellek)
Hafiza_Cache = {}

def yuz_dogrula(kamera_karesi, beklenen_kisi_foto_yolu):
    if not os.path.exists(beklenen_kisi_foto_yolu):
        return False, "Sistemde referans fotoğraf bulunamadı", kamera_karesi

    # HIZ İÇİN %75 KÜÇÜLTME EKLENDİ (Performansı 4-5 kat artırır!)
    kucuk_kare = cv2.resize(kamera_karesi, (0, 0), fx=0.25, fy=0.25)
    rgb_kare = cv2.cvtColor(kucuk_kare, cv2.COLOR_BGR2RGB)
    
    anlik_yuz_konumlari_kucuk = face_recognition.face_locations(rgb_kare)
    anlik_yuz_kodlari = face_recognition.face_encodings(rgb_kare, anlik_yuz_konumlari_kucuk)
        
    if len(anlik_yuz_kodlari) == 0:
        return False, "Kamerada net bir yüz bulunamadı", kamera_karesi
    
    # KAYITLI FOTOĞRAFI HAFIZADAN GETİR (Sistemi uçuran kısım)
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
        eslesme = face_recognition.compare_faces([beklenen_kodlama], anlik_kod, tolerance=0.6)[0]
        if eslesme:
            eslesme_basarili = True
            hedef_konum = (ust, sag, alt, sol)
            break 
            
    if eslesme_basarili:
        ust, sag, alt, sol = hedef_konum
        ust, sag, alt, sol = ust * 4, sag * 4, alt * 4, sol * 4
        
        cv2.rectangle(kamera_karesi, (sol, ust), (sag, alt), (0, 255, 0), 3) # Sadece çerçeve
        cv2.putText(kamera_karesi, "", (20, 40), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 255, 0), 2) # Yazı köşede
        return True, "Doğrulama başarılı.", kamera_karesi

    else:
        ust, sag, alt, sol = anlik_yuz_konumlari_kucuk[0]
        ust, sag, alt, sol = ust * 4, sag * 4, alt * 4, sol * 4
        cv2.rectangle(kamera_karesi, (sol, ust), (sag, alt), (0, 0, 255), 3) # Kırmızı çerçeve
        cv2.putText(kamera_karesi, "", (20, 40), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 0, 255), 2) # Yazı köşede

        return False, "Yüz eşleşmedi (Yabancı)", kamera_karesi
