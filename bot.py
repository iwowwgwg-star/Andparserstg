import os
import re
import time
import vk_api
import requests
from bs4 import BeautifulSoup
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

VK_TOKEN = os.getenv("VK_TOKEN", "ТВОЙ_ТОКЕН_ЕСЛИ_НЕ_ЧЕРЕЗ_ENV")
GROUP_ID = int(os.getenv("GROUP_ID", "231926003"))
TG_CHANNEL = "topor"

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
upload = vk_api.upload.VkUpload(vk_session)

# Переменная для хранения ID последнего обработанного поста в памяти
last_processed_id = ""

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'http\S+|www.\S+', '', text)
    text = re.sub(r'\b[a-zA-Z0-9][-a-zA-Z0-9]*\.(com|ru|org|net|me|io|info|biz|cc|co)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[*_`#\[\]()]', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def upload_photo(img_url):
    try:
        response = requests.get(img_url, stream=True, timeout=15)
        if response.status_code == 200:
            photo = upload.photo_wall(photos=response.raw, group_id=GROUP_ID)
            return f"photo{photo[0]['owner_id']}_{photo[0]['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
    return None

def fetch_latest_telegram_post():
    url = f"https://t.me/s/{TG_CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            messages = soup.find_all('div', class_='tgme_widget_message')
            if not messages:
                return None
            
            msg = messages[-1]
            link = msg.find('a', class_='tgme_widget_message_date')
            if not link:
                return None
            post_id = link['href']

            has_video = bool(
                msg.find('video') or 
                msg.find('source') or 
                msg.find(class_=['tgme_widget_message_video_player', 'tgme_widget_message_video'])
            )
            if has_video:
                return {"id": post_id, "ignore": True}

            media = []
            # Собираем обычные одиночные фото
            for wrap in msg.find_all('a', class_='tgme_widget_message_photo_wrap'):
                style = wrap.get('style', '')
                match = re.search(r"background-image:url\('(.*?)'\)", style)
                if match:
                    media.append(match.group(1))
            
            # Собираем фото из альбомов (галерей с несколькими картинками)
            for photo in msg.find_all('div', class_='tgme_widget_message_grouped_photo'):
                style = photo.get('style', '')
                match = re.search(r"background-image:url\('(.*?)'\)", style)
                if match:
                    media.append(match.group(1))

            if not media:
                return {"id": post_id, "ignore": True}

            txt_elem = msg.find('div', class_='tgme_widget_message_text')
            text = clean_text(txt_elem.get_text(separator='\n')) if txt_elem else ""

            return {"id": post_id, "text": text, "media": media, "ignore": False}
                
    except Exception as e:
        print(f"Ошибка парсинга Telegram: {e}")
    return None

def bot_loop():
    global last_processed_id
    print("Бот запущен в фоновом режиме...")
    while True:
        try:
            print("Проверка ленты Telegram...")
            latest_post = fetch_latest_telegram_post()
            
            if latest_post:
                post_id = latest_post["id"]
                if post_id != last_processed_id:
                    if latest_post["ignore"]:
                        print(f"Пост {post_id} пропущен (видео или без фото).")
                        last_processed_id = post_id
                    else:
                        print(f"Публикуем новый пост: {post_id}")
                        attachments = []
                        # Берем до 10 картинок из галереи
                        for url in latest_post["media"][:10]:
                            att = upload_photo(url)
                            if att:
                                attachments.append(att)
                            time.sleep(0.5)

                        if attachments:
                            try:
                                vk.wall.post(
                                    owner_id=-GROUP_ID,
                                    message=latest_post["text"],
                                    attachments=",".join(attachments),
                                    from_group=1,
                                    signed=0
                                )
                                print("Пост успешно опубликован в ВК!")
                                last_processed_id = post_id
                            except Exception as e:
                                print(f"Ошибка публикации в VK: {e}")
                else:
                    print("Новых постов нет.")
        except Exception as e:
            print(f"Ошибка в цикле бота: {e}")
            
        # Пауза 15 минут перед следующей проверкой
        time.sleep(900)

# Простейший HTTP-сервер для Render, чтобы сервис не засыпал
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

if __name__ == "__main__":
    t = threading.Thread(target=bot_loop)
    t.daemon = True
    t.start()

    run_server()
