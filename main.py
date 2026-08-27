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

def clean_text(text):
    """Полное избавление от пробельного мусора, лишних переносов и кривых отступов"""
    if not text:
        return ""
    # Убираем markdown-символы
    text = re.sub(r'[\*\_\`\#\[\]\(\)]', '', text)
    # Схлопываем повторяющиеся пробелы и табуляции в один пробел
    text = re.sub(r'[ \t]+', ' ', text)
    # Убираем пустые строки и нормализуем переносы
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join([line for line in lines if line])
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def has_links(text):
    if not text:
        return False
    link_patterns = [
        r'http\S+',
        r'www\.\S+',
        r't\.me\/\S+',
        r'@\w+',
        r'\b[a-zA-Z0-9][-a-zA-Z0-9]*\.(com|ru|org|net|me|io|info|biz|cc|co|xyz)\b'
    ]
    for pattern in link_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False

def get_vk_existing_texts():
    texts = set()
    try:
        wall = vk.wall.get(owner_id=-GROUP_ID, count=100)
        for item in wall.get('items', []):
            if 'text' in item:
                texts.add(item['text'].strip())
    except Exception as e:
        print(f"Ошибка получения постов из ВК: {e}")
    return texts

def upload_media_to_wall(media_urls, video_urls):
    attachments = []
    
    # Загружаем карусель / все фото из поста (до 10 штук)
    for url in media_urls[:10]:
        try:
            response = requests.get(url, stream=True, timeout=15)
            if response.status_code == 200:
                photo = upload.photo_wall(photos=response.raw, group_id=GROUP_ID)
                if photo:
                    attachments.append(f"photo{photo[0]['owner_id']}_{photo[0]['id']}")
            time.sleep(0.3)
        except Exception as e:
            print(f"Ошибка загрузки фото: {e}")

    # Загружаем видео, если оно есть
    for v_url in video_urls[:2]:
        try:
            v_resp = requests.get(v_url, stream=True, timeout=30)
            if v_resp.status_code == 200:
                video_file = "temp_video.mp4"
                with open(video_file, 'wb') as f:
                    for chunk in v_resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                video_data = upload.video(video_file=video_file, name="Видео из Telegram", group_id=GROUP_ID)
                if video_data:
                    attachments.append(f"video{video_data['owner_id']}_{video_data['id']}")
                
                if os.path.exists(video_file):
                    os.remove(video_file)
        except Exception as e:
            print(f"Ошибка загрузки видео в ВК: {e}")

    return attachments

def send_to_vk(text, media_urls, video_urls):
    if not media_urls and not video_urls:
        return False
    try:
        attachments = upload_media_to_wall(media_urls, video_urls)
        if not attachments:
            return False

        vk.wall.post(
            owner_id=-GROUP_ID,
            message=text,
            attachments=",".join(attachments),
            from_group=1,
            signed=0
        )
        print("Пост с медиа/каруселью успешно опубликован в VK!")
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
            # Парсим все доступные блоки сообщений (веб-версия выдает расширенную ленту)
            for msg in soup.find_all('div', class_='tgme_widget_message'):
                link = msg.find('a', class_='tgme_widget_message_date')
                if not link:
                    continue
                
                txt_elem = msg.find('div', class_='tgme_widget_message_text')
                text = txt_elem.get_text(separator='\n') if txt_elem else ""
                
                # Собираем ВСЕ фотографии (поддерживает одиночные и альбомы/карусели)
                media = []
                photo_wraps = msg.find_all('a', class_='tgme_widget_message_photo_wrap')
                for wrap in photo_wraps:
                    style = wrap.get('style', '')
                    match = re.search(r"background-image:url\('(.*?)'\)", style)
                    if match:
                        media.append(match.group(1))
                
                # Собираем видео
                videos = []
                vid_elem = msg.find('video')
                if vid_elem and vid_elem.get('src'):
                    videos.append(vid_elem.get('src'))
                
                posts.append({"text": text, "media": media, "videos": videos})
    except Exception as e:
        print(f"Ошибка парсинга Telegram: {e}")
    return posts

def main():
    posts = fetch_telegram_posts()
    if not posts:
        print("Посты не найдены.")
        return

    vk_texts = get_vk_existing_texts()
    published_count = 0
    # Идем от старых к новым, чтобы выстраивать хронологию
    posts.reverse()
    
    for post in posts:
        if not post["media"] and not post["videos"]:
            continue

        if has_links(post["text"]):
            continue

        clean_msg = clean_text(post["text"])
        
        if clean_msg and clean_msg not in vk_texts:
            print("Найден качественный пост, отправляем в VK...")
            success = send_to_vk(clean_msg, post["media"], post["videos"])
            if success:
                vk_texts.add(clean_msg)
                published_count += 1
                # Пауза между постами, чтобы ВК не банил за быстрый постинг каруселей
                time.sleep(6)
        else:
            print("Пост пропущен (уже есть на стене, пустой или рекламный со ссылками).")

    print(f"Готово. Опубликовано новых постов за этот запуск: {published_count}")

if __name__ == "__main__":
    main()
