import os
import re
import time
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

def save_processed(processed):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(list(processed)[-500:]))

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'http\S+|www.\S+', '', text)
    text = re.sub(r'\b[a-zA-Z0-9][-a-zA-Z0-9]*\.(com|ru|org|net|me|io|info|biz|cc|co)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[*_`#\[\]()]', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def get_vk_wall_texts():
    """Получает тексты последних постов со стены ВК для проверки на дубликаты"""
    try:
        url = "https://api.vk.com/method/wall.get"
        params = {
            "owner_id": -GROUP_ID,
            "count": 20,
            "access_token": VK_TOKEN,
            "v": "5.131"
        }
        response = requests.get(url, params=params, timeout=15).json()
        if "response" in response and "items" in response["response"]:
            return [item.get("text", "").strip().lower() for item in response["response"]["items"]]
    except Exception as e:
        print(f"Ошибка получения стены ВК: {e}")
    return []

def upload_photo(img_url):
    try:
        response = requests.get(img_url, stream=True, timeout=15)
        if response.status_code == 200:
            photo = upload.photo_wall(photos=response.raw, group_id=GROUP_ID)
            return f"photo{photo[0]['owner_id']}_{photo[0]['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
    return None

def upload_video(video_url):
    """Загружает видео через документы VK для стены"""
    try:
        server_info = vk.docs.getWallUploadServer(group_id=GROUP_ID, v="5.131")
        upload_url = server_info['upload_url']
        
        video_data = requests.get(video_url, stream=True, timeout=30).content
        files = {'file': ('video.mp4', video_data, 'video/mp4')}
        upload_res = requests.post(upload_url, files=files).json()
        
        if 'file' in upload_res:
            saved = vk.docs.save(file=upload_res['file'], title="video", v="5.131")
            if 'doc' in saved:
                d = saved['doc']
                return f"doc{d['owner_id']}_{d['id']}"
    except Exception as e:
        print(f"Ошибка загрузки видео: {e}")
    return None

def send_to_vk(text, media_urls, video_urls):
    try:
        attachments = []
        
        # Загружаем картинки
        for url in media_urls[:10]:
            att = upload_photo(url)
            if att:
                attachments.append(att)
            time.sleep(0.4)

        # Загружаем видео
        for url in video_urls[:3]:
            att = upload_video(url)
            if att:
                attachments.append(att)
            time.sleep(0.5)

        vk.wall.post(
            owner_id=-GROUP_ID,
            message=text,
            attachments=",".join(attachments) if attachments else None,
            from_group=1,
            signed=0
        )
        print("Пост с медиа успешно опубликован в группе от имени сообщества!")
        return True
    except Exception as e:
        print(f"Ошибка публикации в VK: {e}")
        return False

def fetch_telegram_posts():
    url = f"https://t.me/s/{TG_CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    posts = []
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for msg in soup.find_all('div', class_='tgme_widget_message'):
                link = msg.find('a', class_='tgme_widget_message_date')
                if not link:
                    continue
                post_id = link['href']

                txt_elem = msg.find('div', class_='tgme_widget_message_text')
                text = clean_text(txt_elem.get_text(separator='\n')) if txt_elem else ""

                # Собираем картинки
                media = []
                for wrap in msg.find_all('a', class_='tgme_widget_message_photo_wrap'):
                    style = wrap.get('style', '')
                    match = re.search(r"background-image:url\('(.*?)'\)", style)
                    if match:
                        media.append(match.group(1))

                # Собираем видео
                videos = []
                for v in msg.find_all('video'):
                    src = v.get('src')
                    if src:
                        videos.append(src)
                for s in msg.find_all('source'):
                    src = s.get('src')
                    if src:
                        videos.append(src)

                posts.append({"id": post_id, "text": text, "media": media, "videos": videos})
    except Exception as e:
        print(f"Ошибка парсинга Telegram: {e}")
    return posts

def main():
    processed = load_processed()
    vk_texts = get_vk_wall_texts()
    posts = fetch_telegram_posts()

    if not posts:
        print("Посты не найдены.")
        return

    # Если база пустая (самый первый запуск)
    if not processed:
        print("Инициализация: запоминаем текущие посты без спама в ВК...")
        for post in posts:
            processed.add(post["id"])
        save_processed(processed)
        print("База инициализирована. Теперь бот будет публиковать ТОЛЬКО новые выходящие посты.")
        return

    # Обычный режим работы: проверяем, появились ли новые посты
    published_count = 0
    posts.reverse()

    for post in posts:
        if post["id"] not in processed:
            processed.add(post["id"])

            # Если у поста нет ни картинок, ни видео — пропускаем
            if not post["media"] and not post["videos"]:
                print(f"Пропускаем новый пост без медиа: {post['id']}")
                continue

            # Проверяем на дубликаты по тексту в ВК
            post_text_lower = post["text"].lower()
            is_duplicate = any(post_text_lower in vk_t or vk_t in post_text_lower for vk_t in vk_texts if vk_t)
            if is_duplicate:
                print(f"Пост {post['id']} уже есть на стене ВК, пропускаем.")
                continue

            print("Обнаружен новый пост с медиа (фото/видео), публикуем...")
            success = send_to_vk(post["text"], post["media"], post["videos"])
            if success:
                published_count += 1
                time.sleep(3)

    save_processed(processed)
    print(f"Готово. Опубликовано новых постов: {published_count}")

if __name__ == "__main__":
    main()
