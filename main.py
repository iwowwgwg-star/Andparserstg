import os
import re
import time
import hashlib
import subprocess
import vk_api
import requests
from bs4 import BeautifulSoup

VK_TOKEN = "vk1.a.KFziyAOmDYFo-38aGxsFBMG3oety-HKr5m3YOX27_UGvJTaIwJLtZPeCd2OUZS5UO2432U8L7ZphRIjHEl0_Nz3nnSBqij6DBSU3MqHCzSEhRGCGVEDKxSqT258qxZzpxn4Mz9jGcbkCrAeLqZlFpLFDYqP-T38GUVibieb3JssaXlxPD1IvOeCWN1i3DFt4HNWCkB5_wKMEMbhwU2EdRQ"
GROUP_ID = 231926003
TG_CHANNEL = "topor"

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
upload = vk_api.upload.VkUpload(vk_session)

PROCESSED_FILE = "processed.txt"

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_and_push_processed(processed):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(list(processed)[-200:]))
    
    try:
        subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", PROCESSED_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Auto-update processed posts database"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("База processed.txt успешно синхронизирована с GitHub.")
    except Exception as e:
        print(f"Ошибка Git при отправке в репозиторий: {e}")

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'http\S+|www.\S+', '', text)
    text = re.sub(r'\b[a-zA-Z0-9][-a-zA-Z0-9]*\.(com|ru|org|net|me|io|info|biz|cc|co)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[*_`#\[\]()]', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def get_post_identifier(post_id, text):
    """Создает уникальный хэш на основе ссылки и текста, чтобы точно исключить дубли и пропуски"""
    base_str = f"{post_id}_{text[:50]}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def upload_photo(img_url):
    try:
        response = requests.get(img_url, stream=True, timeout=15)
        if response.status_code == 200:
            photo = upload.photo_wall(photos=response.raw, group_id=GROUP_ID)
            return f"photo{photo[0]['owner_id']}_{photo[0]['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
    return None

def upload_video_as_doc(video_url):
    try:
        print(f"Принудительно качаем видео: {video_url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "video/webm,video/ogg,video/mp4,q=0.3,*/*;q=0.5",
            "Range": "bytes=0-"
        }
        resp = requests.get(video_url, stream=True, timeout=60, headers=headers)
        if resp.status_code not in [200, 206]:
            print(f"Ошибка скачивания видео, HTTP код: {resp.status_code}")
            return None
            
        video_bytes = resp.content
        print(f"Размер скачанного видео: {len(video_bytes)} байт")

        # Если файл меньше 100 КБ, значит Телеграм отдал битую заглушку
        if len(video_bytes) < 100000:
            print("Ошибка: файл слишком мал, это не полноценное видео.")
            return None

        server_info = vk.docs.getWallUploadServer(group_id=GROUP_ID, v="5.131")
        upload_url = server_info['upload_url']
        
        files = {'file': ('video.mp4', video_bytes, 'video/mp4')}
        upload_res = requests.post(upload_url, files=files, timeout=90).json()
        
        if 'file' in upload_res:
            saved = vk.docs.save(file=upload_res['file'], title="Telegram Video", v="5.131")
            if 'doc' in saved:
                d = saved['doc']
                print("Видео успешно загружено как документ в ВК!")
                return f"doc{d['owner_id']}_{d['id']}"
    except Exception as e:
        print(f"Критическая ошибка загрузки видео в VK: {e}")
    return None

def fetch_latest_telegram_post():
    url = f"https://t.me/s/{TG_CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
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

            txt_elem = msg.find('div', class_='tgme_widget_message_text')
            text = clean_text(txt_elem.get_text(separator='\n')) if txt_elem else ""

            media = []
            for wrap in msg.find_all('a', class_='tgme_widget_message_photo_wrap'):
                style = wrap.get('style', '')
                match = re.search(r"background-image:url\('(.*?)'\)", style)
                if match:
                    media.append(match.group(1))

            videos = []
            for v in msg.find_all('video'):
                src = v.get('src')
                if src:
                    videos.append(src)
            for s in msg.find_all('source'):
                src = s.get('src')
                if src:
                    videos.append(src)

            return {"id": post_id, "text": text, "media": media, "videos": videos}
    except Exception as e:
        print(f"Ошибка парсинга Telegram: {e}")
    return None

def main():
    processed = load_processed()
    latest_post = fetch_latest_telegram_post()

    if not latest_post:
        print("Посты не найдены.")
        return

    unique_key = get_post_identifier(latest_post["id"], latest_post["text"])

    if unique_key in processed:
        print(f"Этот пост уже обработан (ключ: {unique_key}). Новых записей нет.")
        return

    if not latest_post["media"] and not latest_post["videos"] and not latest_post["text"]:
        print("Пост пустой, пропускаем.")
        return

    print(f"Обнаружен новый пост: {latest_post['id']}. Начинаем сбор медиа...")

    attachments = []
    
    # Загружаем фотографии
    for url in latest_post["media"][:10]:
        att = upload_photo(url)
        if att:
            attachments.append(att)
        time.sleep(0.3)

    # Загружаем видео
    for url in latest_post["videos"][:1]:
        att = upload_video_as_doc(url)
        if att:
            attachments.append(att)
        time.sleep(0.3)

    try:
        # Публикуем всё единым постом в ВК
        vk.wall.post(
            owner_id=-GROUP_ID,
            message=latest_post["text"],
            attachments=",".join(attachments) if attachments else None,
            from_group=1,
            signed=0
        )
        print("Пост со всеми медиафайлами успешно опубликован в ВК!")
        
        # Сохраняем уникальный ключ в базу
        processed.add(unique_key)
        save_and_push_processed(processed)
        
    except Exception as e:
        print(f"Ошибка публикации в VK: {e}")

if __name__ == "__main__":
    main()
