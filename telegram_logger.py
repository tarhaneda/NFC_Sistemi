import telegram
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def mesaj_gonder(mesaj):
    """Telegram üzerinden uyarı bildirimi gönderir."""
    bot=telegram.Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=mesaj)
    print("Telegram'a mesaj başarıyla gönderildi!")

async def fotograf_gonder(fotograf_yolu, aciklama_mesaji):
    """Kamera resim çektiğinde, kapıdaki kişinin fotoğrafını yollar"""
    bot=telegram.Bot(token=BOT_TOKEN)
    with open(fotograf_yolu, "rb") as foto:
        await bot.send_photo(chat_id=CHAT_ID, photo=foto, caption=aciklama_mesaji)
        print("Telegram'a fotoğraf başarıyla gönderildi!")

if __name__=="__main__":
    asyncio.run(mesaj_gonder("Sistem test ediliyor... Kapı güvenliği aktif!"))