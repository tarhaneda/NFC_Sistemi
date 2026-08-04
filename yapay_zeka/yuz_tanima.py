import face_recognition
import cv2
import os

# YAPAY ZEKA HAFIZASI (Önbellek)
Hafiza_Cache = {}

def yuz_dogrula(kamera_karesi, beklenen_kisi_foto_yolu):
    if not os.path.exists(beklenen_kisi_foto_yolu):
        return False, "Sistemde referans fotoğraf bulunamadı", kamera_karesi

    # KÜÇÜLTME YOK! Tam HD çözünürlükte maksimum doğrulukla arıyoruz.
    rgb_kare = cv2.cvtColor(kamera_karesi, cv2.COLOR_BGR2RGB)
    anlik_yuz_konumlari = face_recognition.face_locations(rgb_kare)
    anlik_yuz_kodlari = face_recognition.face_encodings(rgb_kare, anlik_yuz_konumlari)
        
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

    for (ust, sag, alt, sol), anlik_kod in zip(anlik_yuz_konumlari, anlik_yuz_kodlari):
        eslesme = face_recognition.compare_faces([beklenen_kodlama], anlik_kod, tolerance=0.6)[0]
        if eslesme:
            eslesme_basarili = True
            hedef_konum = (ust, sag, alt, sol)
            break 
            
    if eslesme_basarili:
        ust, sag, alt, sol = hedef_konum
        cv2.rectangle(kamera_karesi, (sol, ust), (sag, alt), (0, 255, 0), 3)
        cv2.rectangle(kamera_karesi, (sol, alt - 35), (sag, alt), (0, 255, 0), cv2.FILLED)
        cv2.putText(kamera_karesi, "ONAYLANDI", (sol + 6, alt - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)
        return True, "Doğrulama başarılı.", kamera_karesi
    else:
        ust, sag, alt, sol = anlik_yuz_konumlari[0]
        cv2.rectangle(kamera_karesi, (sol, ust), (sag, alt), (0, 0, 255), 3)
        cv2.rectangle(kamera_karesi, (sol, alt - 35), (sag, alt), (0, 0, 255), cv2.FILLED)
        cv2.putText(kamera_karesi, "YABANCI", (sol + 6, alt - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)
        return False, "Yüz eşleşmedi (Yabancı)", kamera_karesi
