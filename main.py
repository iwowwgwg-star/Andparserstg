import os
import re
import time
import threading
from datetime import datetime
import vk_api
import requests
from bs4 import BeautifulSoup
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- КОНФИГУРАЦИЯ ---
VK_TOKEN = "vk1.a.DBQcaf6sVpZAogJRlukkc_Z04_qgWxmCr9uZZgE_E2-ZJQIAmpGKQh1iI2ezVQNz7JsuW7iWnQnVUlvncavyUHzF7qJDp8zvb38TUBR7s2b24MYsAmkXgMLu8fClyVRTycGB1Wyk8MG3vJceWf0kJYngu77ka8EZzRn2fJRsL85sSLsl0OK_KUCMw3wHQXpJI_R4FhM6G7S9jP2vPW5ITA"
GROUP_ID = 229040854
TG_CHANNEL = "topor"
CHECK_INTERVAL = 60  # проверка каждую минуту

# Инициализация VK API
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
upload = vk_api.upload.VkUpload(vk_session)

processed_posts = set()

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'[\*\_\`\#\[\]\(\)]', '', text)
    text = re.sub(r'http\S+', '', text)
    return text.strip()

def upload_photo(img_url):
    try:
        response = requests.get(img_url, stream=True, timeout=10)
        if response.status_code == 200:
            photo = upload.photo_wall(photos=response.raw, group_id=GROUP_ID)
            return f"photo{photo[0]['owner_id']}_{photo[0]['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
    return None

def send_to_vk(text, media_urls):
    try:
        attachments = []
        for url in media_urls[:10]:
            att = upload_photo(url)
            if att:
                attachments.append(att)
                time.sleep(0.4)

        if not attachments:
            print("Пост пропущен: нет фотографий.")
            return False

        vk.wall.post(
            owner_id=-GROUP_ID,
            message=text,
            attachments=",".join(attachments),
            signed=0
        )
        print("Пост успешно опубликован в группе!")
        return True
    except Exception as e:
        print(f"Ошибка публикации в VK: {e}")
        return False

def fetch_telegram_posts():
    url = f"https://t.me/s/{TG_CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    posts = []
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for msg in soup.find_all('div', class_='tgme_widget_message'):
                link = msg.find('a', class_='tgme_widget_message_date')
                if not link:
                    continue
                post_id = link['href']
                
                txt_elem = msg.find('div', class_='tgme_widget_message_text')
                text = clean_text(txt_elem.get_text(separator='\n')) if txt_elem else ""
                
                media = []
                for wrap in msg.find_all('a', class_='tgme_widget_message_photo_wrap'):
                    style = wrap.get('style', '')
                    match = re.search(r"background-image:url\('(.*?)'\)", style)
                    if match:
                        media.append(match.group(1))
                
                posts.append({"id": post_id, "text": text, "media": media})
    except Exception as e:
        print(f"Ошибка парсинга Telegram: {e}")
        
    return posts

def bot_loop():
    global processed_posts
    print("Бот запущен в фоне и следит за каналом...")
    initial_posts = fetch_telegram_posts()
    for p in initial_posts:
        processed_posts.add(p["id"])
    print(f"Инициализация завершена. Базовых постов в памяти: {len(processed_posts)}")

    while True:
        try:
            current_posts = fetch_telegram_posts()
            for post in current_posts:
                if post["id"] not in processed_posts:
                    print("Обнаружен новый пост, публикуем...")
                    send_to_vk(post["text"], post["media"])
                    processed_posts.add(post["id"])
            
            if len(processed_posts) > 200:
                processed_posts = set(list(processed_posts)[-100:])
                
        except Exception as e:
            print(f"Ошибка в цикле: {e}")
            
        time.sleep(CHECK_INTERVAL)

# Запускаем бота в отдельном фоновом потоке
threading.Thread(target=bot_loop, daemon=True).start()

# Простейший веб-сервер для занятия порта, чтобы Render не ругался
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Bot is running!".encode("utf-8"))
        
    def log_message(self, format, *args):
        return

port = int(os.environ.get("PORT", 10000))
server = HTTPServer(("0.0.0.0", port), SimpleHandler)
print(f"Веб-сервер занял порт {port}", flush=True)
server.serve_forever()
