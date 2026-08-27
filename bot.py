import os
import re
import time
import requests
from telegram import Bot
import vk_api

# --- НАСТРОЙКИ ---
TELEGRAM_BOT_TOKEN = "8802950683:AAHwTov5xaDfQQjiMv8JGwbCNjzb-QEpK6k"
VK_ACCESS_TOKEN = "vk1.a.DBQcaf6sVpZAogJRlukkc_Z04_qgWxmCr9uZZgE_E2-ZJQIAmpGKQh1iI2ezVQNz7JsuW7iWnQnVUlvncavyUHzF7qJDp8zvb38TUBR7s2b24MYsAmkXgMLu8fClyVRTycGB1Wyk8MG3vJceWf0kJYngu77ka8EZzRn2fJRsL85sSLsl0OK_KUCMw3wHQXpJI_R4FhM6G7S9jP2vPW5ITA"
VK_GROUP_ID = "229040854"
CHANNEL_USERNAME = "@topor"

bot = Bot(token=TELEGRAM_BOT_TOKEN)
vk_session = vk_api.VkApi(token=VK_ACCESS_TOKEN)
vk = vk_session.get_api()

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'[\*\_\`\#\[\]\(\)]', '', text)
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text).strip()
    return text

def post_to_vk(text):
    try:
        vk.wall.post(
            owner_id=-int(VK_GROUP_ID),
            message=text,
            from_group=1
        )
        print("Пост успешно опубликован во ВКонтакте!")
    except Exception as e:
        print(f"Ошибка публикации в VK: {e}")

print(f"Бот запущен и следит за каналом {CHANNEL_USERNAME}...")

last_processed_text = ""

while True:
    try:
        updates = bot.get_updates(offset=-1, limit=1)
        
        if updates:
            message = updates[0].channel_post or updates[0].message
            if message and message.text:
                post_text = clean_text(message.text)
                
                if post_text and post_text != last_processed_text:
                    print("Найден новый пост, отправляем в VK...")
                    post_to_vk(post_text)
                    last_processed_text = post_text
                    
        time.sleep(30)
    except Exception as e:
        print(f"Ошибка в цикле проверки: {e}")
        time.sleep(30)
