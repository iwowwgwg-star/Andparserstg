import os
import re
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import vk_api
import requests
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ ---
VK_ACCESS_TOKEN = "vk1.a.DBQcaf6sVpZAogJRlukkc_Z04_qgWxmCr9uZZgE_E2-ZJQIAmpGKQh1iI2ezVQNz7JsuW7iWnQnVUlvncavyUHzF7qJDp8zvb38TUBR7s2b24MYsAmkXgMLu8fClyVRTycGB1Wyk8MG3vJceWf0kJYngu77ka8EZzRn2fJRsL85sSLsl0OK_KUCMw3wHQXpJI_R4FhM6G7S9jP2vPW5ITA"
VK_GROUP_ID = "229040854"
CHANNEL_USERNAME = "topor"

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

def upload_photo_to_vk(img_url):
    try:
        response = requests.get(img_url, stream=True, timeout=10)
        if response.status_code == 200:
            photo = upload.photo_wall(
                photos=response.raw,
                group_id=int(VK_GROUP_ID)
            )
            return f"photo{photo[0]['owner_id']}_{photo[0]['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото в VK: {e}")
    return None

def post_to_vk_with_media(text, media_urls):
    try:
        attachments = []
        
        # Загружаем каждую картинку во ВКонтакте и добавляем во вложения
        for img_url in media_urls[:10]: # VK разрешает до 10 вложений
            photo_attachment = upload_photo_to_vk(img_url)
            if photo_attachment:
                attachments.append(photo_attachment)

        vk.wall.post(
            owner_id=-int(VK_GROUP_ID),
            message=text,
            attachments=",".join(attachments) if attachments else None,
            from_group=1
        )
        print("SUCCESS: Пост с медиа успешно опубликован во ВКонтакте!")
        time.sleep(3)
    except Exception as e:
        print(f"ERROR: Ошибка публикации в VK: {e}")

def get_channel_posts_with_media():
    url = f"https://t.me/s/{CHANNEL_USERNAME}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    posts_data = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            message_divs = soup.find_all('div', class_='tgme_widget_message')
            
            for msg in message_divs:
                # Уникальный ID поста по ссылке или структуре
                link_tag = msg.find('a', class_='tgme_widget_message_date')
                post_id = link_tag['href'] if link_tag else str(id(msg))
                
                # Текст поста
                text_elem = msg.find('div', class_='tgme_widget_message_text')
                raw_text = text_elem.get_text(separator='\n') if text_elem else ""
                text = clean_text(raw_text)

                # Поиск картинок (включая галереи, если их несколько в посте)
                media_urls = []
                photo_wraps = msg.find_all('a', class_='tgme_widget_message_photo_wrap')
                for wrap in photo_wraps:
                    style = wrap.get('style', '')
                    # Telegram прячет ссылки на фото в стиле background-image
                    match = re.search(r"background-image:url\('(.*?)'\)", style)
                    if match:
                        media_urls.append(match.group(1))

                # Также проверим прямые теги img на случай одиночных фото
                img_tags = msg.find_all('img', class_='tgme_widget_message_photo')
                for img in img_tags:
                    src = img.get('src')
                    if src and src not in media_urls:
                        media_urls.append(src)

                if text or media_urls:
                    posts_data.append({
                        "id": post_id,
                        "text": text,
                        "media": media_urls
                    })
    except Exception as e:
        print(f"ERROR при парсинге постов: {e}")
        
    return posts_data

def run_bot():
    print(f"Бот запущен и следит за каналом @{CHANNEL_USERNAME} (текст + медиа)...")
    processed_ids = set()

    # Первичная инициализация (чтобы не спамить старыми постами при старте)
    initial_posts = get_channel_posts_with_media()
    for p in initial_posts:
        processed_ids.add(p["id"])
    print(f"Загружено постов в историю: {len(processed_ids)}. Ожидание новых...")

    while True:
        try:
            current_posts = get_channel_posts_with_media()
            for post in current_posts:
                if post["id"] not in processed_ids:
                    print(f"Найден новый пост! Текст: {post['text'][:30]}... Кар картинок: {len(post['media'])}")
                    post_to_vk_with_media(post["text"], post["media"])
                    processed_ids.add(post["id"])

            if len(processed_ids) > 200:
                processed_ids = set(list(processed_ids)[-100:])

        except Exception as e:
            print(f"ERROR в цикле проверки: {e}")
            
        time.sleep(60)

# Запуск в фоновом потоке
bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

# Веб-сервер для Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

port = int(os.environ.get("PORT", 10000))
server = HTTPServer(("0.0.0.0", port), SimpleHandler)
server.serve_forever()
