import os
import re
import time
import threading
from datetime import datetime, timedelta
from telegram import Bot
import vk_api
from http.server import HTTPServer, BaseHTTPRequestHandler

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
        time.sleep(3)
    except Exception as e:
        print(f"Ошибка публикации в VK: {e}")

# Функция для работы бота в фоне
def run_bot():
    print(f"Бот запущен и проверяет историю канала {CHANNEL_USERNAME} за последние 14 дней...")
    processed_message_ids = set()
    two_weeks_ago = datetime.now() - timedelta(days=14)

    try:
        updates = bot.get_updates(offset=-100, limit=100)
        historical_posts = []
        for update in updates:
            message = update.channel_post or update.message
            if message and message.text:
                msg_date = message.date
                if msg_date.replace(tzinfo=None) >= two_weeks_ago:
                    post_text = clean_text(message.text)
                    if post_text:
                        historical_posts.append((message.message_id, post_text, msg_date))

        historical_posts.sort(key=lambda x: x[2])

        if historical_posts:
            print(f"Найдено постов за 2 недели для публикации: {len(historical_posts)}")
            for msg_id, text, date in historical_posts:
                print(f"Публикуем старый пост от {date}...")
                post_to_vk(text)
                processed_message_ids.add(msg_id)
        else:
            print("Новых постов за последние 2 недели не найдено.")
    except Exception as e:
        print(f"Ошибка при обработке истории: {e}")

    print("Переходим в режим реального времени (мониторинг новых постов)...")

    while True:
        try:
            updates = bot.get_updates(offset=-1, limit=1)
            if updates:
                message = updates[0].channel_post or updates[0].message
                if message and message.text:
                    if message.message_id not in processed_message_ids:
                        post_text = clean_text(message.text)
                        if post_text:
                            print("Найден свежий пост, отправляем в VK...")
                            post_to_vk(post_text)
                            processed_message_ids.add(message.message_id)
            time.sleep(30)
        except Exception as e:
            print(f"Ошибка в цикле проверки: {e}")
            time.sleep(30)

# Запускаем бота в отдельном фоновом потоке
bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

# Простейший веб-сервер для Render, чтобы он видел открытый порт и не выдавал тайм-аут
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

port = int(os.environ.get("PORT", 10000))
server = HTTPServer(("0.0.0.0", port), SimpleHandler)
print(f"Веб-сервер запущен на порту {port}, чтобы удовлетворить требования Render.")
server.serve_forever()
