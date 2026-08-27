import os
import re
import time
import threading
from datetime import datetime, timedelta
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
        print(f"Ошибка загрузки фото в VK: {e}", flush=True)
    return None

def post_to_vk_with_media(text, media_urls):
    try:
        attachments = []
        for img_url in media_urls[:10]:
            photo_attachment = upload_photo_to_vk(img_url)
            if photo_attachment:
                attachments.append(photo_attachment)
                time.sleep(1)

        vk.wall.post(
            owner_id=-int(VK_GROUP_ID),
            message=text,
            attachments=",".join(attachments) if attachments else None,
            from_group=1
        )
        print("SUCCESS: Пост с медиа успешно опубликован во ВКонтакте!", flush=True)
        time.sleep(3)
    except Exception as e:
        print(f"ERROR: Ошибка публикации в VK: {e}", flush=True)

def get_channel_posts_with_media():
    url = f"https://t.me/s/{CHANNEL_USERNAME}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    posts_data = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Статус ответа от Telegram web: {response.status_code}", flush=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            message_divs = soup.find_all('div', class_='tgme_widget_message')
            print(f"Найдено блоков сообщений на странице: {len(message_divs)}", flush=True)
            
            for msg in message_divs:
                link_tag = msg.find('a', class_='tgme_widget_message_date')
                if not link_tag:
                    continue
                
                post_id = link_tag['href']
                
                time_tag = msg.find('time', class_='datetime')
                post_date = datetime.now()
                if time_tag and time_tag.has_attr('datetime'):
                    try:
                        dt_str = time_tag['datetime'].split('+')[0].rstrip('Z')
                        post_date = datetime.fromisoformat(dt_str)
                    except:
                        pass
                
                text_elem = msg.find('div', class_='tgme_widget_message_text')
                raw_text = text_elem.get_text(separator='\n') if text_elem else ""
                text = clean_text(raw_text)

                media_urls = []
                photo_wraps = msg.find_all('a', class_='tgme_widget_message_photo_wrap')
                for wrap in photo_wraps:
                    style = wrap.get('style', '')
                    match = re.search(r"background-image:url\('(.*?)'\)", style)
                    if match:
                        media_urls.append(match.group(1))

                img_tags = msg.find_all('img', class_='tgme_widget_message_photo')
                for img in img_tags:
                    src = img.get('src')
                    if src and src not in media_urls:
                        media_urls.append(src)

                posts_data.append({
                    "id": post_id,
                    "date": post_date,
                    "text": text,
                    "media": media_urls
                })
    except Exception as e:
        print(f"ERROR при парсинге постов: {e}", flush=True)
        
    return posts_data

# Глобальный сет для обработанных постов
processed_ids = set()

def process_historical_posts():
    print("Запуск проверки постов за последние 2 недели...", flush=True)
    two_weeks_ago = datetime.now() - timedelta(days=14)

    all_posts = get_channel_posts_with_media()
    recent_posts = [p for p in all_posts if p["date"] >= two_weeks_ago]
    recent_posts.sort(key=lambda x: x["date"])

    if recent_posts:
        print(f"Найдено постов за 2 недели для публикации: {len(recent_posts)}", flush=True)
        for post in recent_posts:
            print(f"Публикуем архивный пост от {post['date']}...", flush=True)
            post_to_vk_with_media(post["text"], post["media"])
            processed_ids.add(post["id"])
    else:
        print("Постов за последние 2 недели не найдено на странице.", flush=True)
        for p in all_posts:
            processed_ids.add(p["id"])

    print(f"Архив обработан. Всего в базе исключений: {len(processed_ids)}", flush=True)

def monitor_new_posts():
    while True:
        try:
            current_posts = get_channel_posts_with_media()
            for post in current_posts:
                if post["id"] not in processed_ids:
                    print(f"Найден новый пост! Публикуем в VK...", flush=True)
                    post_to_vk_with_media(post["text"], post["media"])
                    processed_ids.add(post["id"])

            if len(processed_ids) > 300:
                global processed_ids
                processed_ids = set(list(processed_ids)[-150:])

        except Exception as e:
            print(f"ERROR в цикле мониторинга: {e}", flush=True)
            
        time.sleep(60)

# 1. Сначала прогоняем историю прямо при старте, чтобы логи сразу вывели результат
process_historical_posts()

# 2. Затем запускаем фоновый мониторинг новых постов
monitor_thread = threading.Thread(target=monitor_new_posts)
monitor_thread.daemon = True
monitor_thread.start()

# 3. Веб-сервер для Render (удерживает порт)
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

port = int(os.environ.get("PORT", 10000))
server = HTTPServer(("0.0.0.0", port), SimpleHandler)
server.serve_forever()
