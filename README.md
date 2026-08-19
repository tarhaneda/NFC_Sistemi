# NFC ve Yüz Doğrulama Tabanlı Kapı Geçiş Sistemi

RC522 NFC/RFID okuyucu, NodeMCU ve Python kullanılarak geliştirilen, kart ve yüz doğrulamasını birlikte kullanan çift aşamalı kapı geçiş sistemi.

## Proje Hakkında

Bu proje, fiziksel erişim kontrolünün sağlanması amacıyla geliştirilmiş bir kapı geçiş sistemidir.

Sistemde kullanıcıların giriş işlemleri yalnızca kart doğrulamasına bağlı bırakılmamış, güvenliği artırmak amacıyla **NFC/RFID kart doğrulaması ve yüz doğrulaması olmak üzere iki aşamalı bir doğrulama mekanizması** kullanılmıştır.

Sistem; donanım bileşenleri, Python tabanlı yönetim arayüzü, SQLite veritabanı ve Telegram bildirim entegrasyonunun birlikte çalıştığı bir yapıdan oluşmaktadır.

## Kullanılan Teknolojiler

### Donanım

* NodeMCU
* RC522 NFC/RFID Reader
* Motor
* L298N Motor Sürücü

### Yazılım

* Python
* SQLite
* Telegram Bot API

### Haberleşme

* SPI
* Wi-Fi

## Sistem Özellikleri

### Kart Yönetimi

* Yeni kart ekleme
* Kartların kullanıcılarla ilişkilendirilmesi
* Kartları pasif hale getirme
* Kart doğrulama

### Çift Aşamalı Doğrulama

Sistemde giriş işlemi iki aşamalı olarak gerçekleştirilir:

1. NFC/RFID kart doğrulaması
2. Yüz doğrulaması

Her iki doğrulama aşamasının başarılı olması durumunda giriş işlemi gerçekleştirilir.

### Kullanıcı Yönetimi

Python arayüzü üzerinden kullanıcıların ve kart bilgilerinin yönetilmesi sağlanmaktadır.

Kullanıcıların sistemden tamamen silinmesi yerine kart veya erişim yetkilerinin pasif hale getirilebilmesi sağlanarak geçmiş kayıtların korunması amaçlanmıştır.

### Geçiş Kayıtları

Sistemde gerçekleşen giriş ve çıkış işlemleri SQLite veritabanında kayıt altına alınmaktadır.

Arayüz üzerinden:

* Genel geçiş kayıtları
* Kişi bazlı geçiş kayıtları
* Tarih aralığına göre kayıtlar

görüntülenebilmektedir.

### Telegram Bildirimleri

Gerçekleşen geçiş işlemleri Telegram botu aracılığıyla bildirilerek sistemdeki hareketlerin anlık olarak takip edilebilmesi sağlanmıştır.

## Sistem Çalışma Akışı

```text id="x6s9ju"
Kullanıcı
    │
    ▼
NFC/RFID Kart Okutma
    │
    ▼
RC522
    │
    ▼
NodeMCU
    │
    ▼
Kart Bilgilerinin İşlenmesi
    │
    ▼
Kart Doğrulama
    │
    ├── Başarısız → Erişim Reddedilir
    │
    ▼
Yüz Doğrulama
    │
    ├── Başarısız → Erişim Reddedilir
    │
    ▼
Erişim Onaylanır
    │
    ├──► Kapı Mekanizması
    │
    ├──► SQLite Log Kaydı
    │
    └──► Telegram Bildirimi
```

## Python Yönetim Arayüzü

Python ile geliştirilen yönetim arayüzü üzerinden sistemin kullanıcı ve kart yönetimi gerçekleştirilmektedir.

Arayüz üzerinden:

* Kullanıcı ekleme
* Kart tanımlama
* Kartı pasif hale getirme
* Geçiş kayıtlarını görüntüleme
* Kişi bazlı kayıtları görüntüleme
* Tarih aralığına göre kayıtları filtreleme

işlemleri gerçekleştirilebilmektedir.

## Veritabanı

Sistemde yerel veri depolama amacıyla **SQLite** kullanılmıştır.

Veritabanında temel olarak kullanıcı ve geçiş kayıtlarına ilişkin bilgiler tutulmaktadır.

Sistemde gerçekleştirilen işlemlerin kayıt altına alınması sayesinde geçmiş geçişlerin incelenebilmesi ve raporlanabilmesi sağlanmıştır.

## Donanım Bileşenleri

| Bileşen | Görevi                                 |
| ------- | -------------------------------------- |
| NodeMCU | Sistem kontrolü ve haberleşme          |
| RC522   | NFC/RFID kart okuma                    |
| L298N   | Motor kontrolü                         |
| Motor   | Kapı mekanizmasının hareketini sağlama |




## Proje Görselleri

### Donanım Kurulumu
<img width="1536" height="2048" alt="WhatsApp Image 2026-08-14 at 16 35 49" src="https://github.com/user-attachments/assets/53c480cf-e4c3-4c70-8cdd-fa023ec6567b" />

### Python Yönetim Arayüzü

<img width="1902" height="890" alt="image" src="https://github.com/user-attachments/assets/8342fcda-9b32-498c-a877-076e0444792d" />


### Geçiş Kayıtları

<img width="1887" height="891" alt="image" src="https://github.com/user-attachments/assets/edf5ac23-e690-4f8d-a0df-53eb1720ba2b" />


## Geliştirici

**Eda Nur Tarhan**

Bilgisayar Mühendisliği Öğrencisi

GitHub:
https://github.com/tarhaneda
