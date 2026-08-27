import os
import re
import time
import vk_api
import requests

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
        f.write("\n".join(list(processed)[-1000:]))

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

def upload_video(video_url):
    try:
        response = requests.get(video_url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            return None
            
        server_info = vk.docs.getWallUploadServer(group_id=GROUP_ID, v="5.131")
        upload_url = server_info['upload_url']
        
        files = {'file': ('video.mp4', response.content, 'video/mp4')}
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
        
        for url in media_urls[:10]:
            att = upload_photo(url)
            if att:
                attachments.append(att)
            time.sleep(0.4)

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
        print("Пост успешно опубликован в VK!")
        return True
    except Exception as e:
        print(f"Ошибка публикации стены ВК: {e}")
        return False

def fetch_telegram_posts_json():
    """Используем публичный AJAX/JSON эндпоинт виджета Telegram без токенов и авторизации"""
    url = f"https://t.me/s/{TG_CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    posts = []
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            for msg in soup.find_all('div', class_='tgme_widget_message'):
                link = msg.find('a', class_='tgme_widget_message_date')
                if not link:
                    continue
                post_id = link['href'] # Уникальная ссылка (гарантия от дублей)

                txt_elem = msg.find('div', class_='tgme_widget_message_text')
                text = clean_text(txt_elem.get_text(separator='\n')) if txt_elem else ""

                # Картинки
                media = []
                for wrap in msg.find_all('a', class_='tgme_widget_message_photo_wrap'):
                    style = wrap.get('style', '')
                    match = re.search(r"background-image:url\('(.*?)'\)", style)
                    if match:
                        media.append(match.group(1))

                # Видео (включая альтернативные теги)
                videos = []
                for v in msg.find_all('video'):
                    src = v.get('src')
                    if src:
                        videos.append(src)
                for s in msg.find_all('source'):
                    src = s.get('src')
                    if src:
                        videos.append(src)
                # Проверяем также встроенные стили/дата-атрибуты плеера
                for pv in msg.find_all('i', class_='tgme_widget_message_video_player'):
                    # Иногда прямая ссылка зашита вбекграунд видео-превью или дата атрибуты
                    pass

                posts.append({"id": post_id, "text": text, "media": media, "videos": videos})
    except Exception as e:
        print(f"Ошибка парсинга Telegram: {e}")
    return posts

def main():
    processed = load_processed()
    posts = fetch_telegram_posts_json()

    if not posts:
        print("Посты не найдены.")
        return

    published_count = 0
    posts.reverse()

    for post in posts:
        if post["id"] in processed:
            continue

        processed.add(post["id"])

        if not post["media"] and not post["videos"]:
            continue

        print(f"Публикуем новый пост {post['id']} (фото: {len(post['media'])}, видео: {len(post['videos'])})")
        success = send_to_vk(post["text"], post["media"], post["videos"])
        if success:
            published_count += 1
            time.sleep(3)

    save_processed(processed)
    print(f"Готово. Опубликовано новых постов: {published_count}")

if __name__ == "__main__":
    main()
