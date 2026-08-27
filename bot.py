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
VK_ACCESS_TOKEN = "vk1.a.FTxUindxEHS4SckFmLrcLI6bjGTYg18aqdb8tHGLmX37H3gShp4x0p9CAZDuApEYPxprUE2yCAHhUADfvz-0PWGGh_1y-8T7j_Bk7HWA2NX9txVfHXVRMgG8NYKJuxScAdaqHk-HDUp3ox6s8KMdhtIrpYz4QRJwAOYmRw9Ol8JrsSbZNhvrB0MayT7j6ln_ClBkyaztbzm9cvuSsUXcyA"
VK_GROUP_ID = "229040854"
CHANNEL_USERNAME = "topor"

vk_session = vk_api.VkApi(token=VK_ACCESS_TOKEN)
vk = vk_session.get_api()
upload = vk_api.upload.VkUpload(vk_session)

processed_ids = set()
is_initialized = False

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'[\*\_\`\#\[\]\(\)]', '', text)
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text).strip()
    return text

def upload_photo_to_vk(img_url):
    try:
        if not img_url:
            return None
        response = requests.get(img_url, stream=True, timeout=10)
        if response.status_code == 200:
            photo = upload.photo_wall(
                photos=response.raw,
                group_id=int(VK_GROUP_ID)
            )
            return f"photo{photo[0]['owner_id']}_{photo[0]['id']}"
    except Exception as e:
        print(f"Пропуск битого фото: {e}", flush=True)
    return None

def post_to_vk_with_media(text, media_urls):
    try:
        attachments = []
        for img_url in media_urls[:10]:
            photo_attachment = upload_photo_to_vk(img_url)
            if photo_attachment:
                attachments.append(photo_attachment)
                time.sleep(0.5)

        if not attachments:
            print("ПРОПУСК: В посте нет фотографий, публикация отменена.", flush=True)
            return False

        response = vk.wall.post(
            owner_id=-int(VK_GROUP_ID),
            message=text,
            attachments=",".join(attachments),
            from_group=1,
            signed=0
        )
        
        post_id = response.get('post_id')
        print(f"SUCCESS: Ссылка на пост -> https://vk.com/wall-{VK_GROUP_ID}_{post_id}", flush=True)
        time.sleep(3)
        return True
    except Exception as e:
        print(f"ERROR: Ошибка публикации в VK: {e}", flush=True)
        return False

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

def check_and_publish():
    global is_initialized, processed_ids
    try:
        print("Проверка канала на наличие постов...", flush=True)
        current_posts = get_channel_posts_with_media()
        
        if not is_initialized:
            print("Первый запуск: выгрузка постов за 2 недели...", flush=True)
            two_weeks_ago = datetime.now() - timedelta(days=14)
            recent_posts = [p for p in current_posts if p["date"] >= two_weeks_ago]
            recent_posts.sort(key=lambda x: x["date"])

            if recent_posts:
                print(f"Найдено постов за 2 недели: {len(recent_posts)}", flush=True)
                for post in recent_posts:
                    print(f"Проверяем пост от {post['date']}...", flush=True)
                    published = post_to_vk_with_media(post["text"], post["media"])
                    if published:
                        processed_ids.add(post["id"])
                    else:
                        processed_ids.add(post["id"])
            else:
                for p in current_posts:
                    processed_ids.add(p["id"])
            
            is_initialized = True
            print("Инициализация завершена!", flush=True)
            return

        for post in current_posts:
            if post["id"] not in processed_ids:
                print(f"Найден новый пост, проверяем наличие фото...", flush=True)
                published = post_to_vk_with_media(post["text"], post["media"])
                processed_ids.add(post["id"])

        if len(processed_ids) > 300:
            processed_ids = set(list(processed_ids)[-150:])

    except Exception as e:
        print(f"ERROR в цикле проверки: {e}", flush=True)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        check_and_publish()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running and checked posts!")
        
    def log_message(self, format, *args):
        return

def self_ping():
    time.sleep(10)
    hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
    if hostname:
        url = f"https://{hostname}"
        while True:
            try:
                requests.get(url, timeout=10)
            except:
                pass
            time.sleep(60)

ping_thread = threading.Thread(target=self_ping)
ping_thread.daemon = True
ping_thread.start()

port = int(os.environ.get("PORT", 10000))
server = HTTPServer(("0.0.0.0", port), SimpleHandler)
print(f"Веб-сервер успешно запущен на порту {port}", flush=True)
server.serve_forever()
