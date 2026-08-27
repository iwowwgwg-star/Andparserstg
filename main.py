import os
import re
import time
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
            
            # Берем САМЫЙ ПОСЛЕДНИЙ (свежий) пост из канала
            msg = messages[-1]
            link = msg.find('a', class_='tgme_widget_message_date')
            if not link:
                return None
            post_id = link['href']

            # Если в посте есть видео — сразу возвращаем флаг игнорирования
            has_video = bool(
                msg.find('video') or 
                msg.find('source') or 
                msg.find(class_=['tgme_widget_message_video_player', 'tgme_widget_message_video'])
            )
            
            if has_video:
                print(f"Самый свежий пост {post_id} содержит видео — игнорируем.")
                return {"id": post_id, "ignore": True}

            # Ищем картинки
            media = []
            for wrap in msg.find_all('a', class_='tgme_widget_message_photo_wrap'):
                style = wrap.get('style', '')
                match = re.search(r"background-image:url\('(.*?)'\)", style)
                if match:
                    media.append(match.group(1))

            if not media:
                print(f"Пост {post_id} без картинок — пропускаем.")
                return {"id": post_id, "ignore": True}

            txt_elem = msg.find('div', class_='tgme_widget_message_text')
            text = clean_text(txt_elem.get_text(separator='\n')) if txt_elem else ""

            return {"id": post_id, "text": text, "media": media, "ignore": False}
                
    except Exception as e:
        print(f"Ошибка парсинга Telegram: {e}")
    return None

def main():
    processed = load_processed()
    latest_post = fetch_latest_telegram_post()

    if not latest_post:
        print("Не удалось получить посты.")
        return

    post_id = latest_post["id"]

    # 1. Сначала проверяем, есть ли этот ID в базе
    if post_id in processed:
        print(f"Пост {post_id} уже есть в базе processed.txt. Пропускаем.")
        return

    # 2. Если пост с видео или без картинок — просто заносим его в базу, чтобы больше к нему не возвращаться
    if latest_post["ignore"]:
        processed.add(post_id)
        save_and_push_processed(processed)
        print(f"Пост {post_id} отсеян (видео/нет фото), добавлен в базу как обработанный.")
        return

    print(f"Обнаружен новый подходящий пост: {post_id}. Начинаем публикацию...")

    # Загружаем фотографии
    attachments = []
    for url in latest_post["media"][:10]:
        att = upload_photo(url)
        if att:
            attachments.append(att)
        time.sleep(0.3)

    if not attachments:
        print("Не удалось загрузить фотографии, отменяем публикацию.")
        return

    try:
        vk.wall.post(
            owner_id=-GROUP_ID,
            message=latest_post["text"],
            attachments=",".join(attachments),
            from_group=1,
            signed=0
        )
        print("Пост успешно опубликован в ВК!")
        
        # 3. После успешной публикации добавляем в базу и сохраняем на GitHub
        processed.add(post_id)
        save_and_push_processed(processed)
        
    except Exception as e:
        print(f"Ошибка публикации в VK: {e}")

if __name__ == "__main__":
    main()
