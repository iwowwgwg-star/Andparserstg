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
upload = vk_api.upload.VkUpload(vk_session)

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'[\*\_\`\#\[\]\(\)]', '', text)
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text).strip()
    return text

print(f"Бот запущен и готов к работе...")
while True:
    try:
        time.sleep(30)
    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(30)
