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
        with open(PROCESSED_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed(processed):
    with open(PROCESSED_FILE, "w") as f:
        f.write("\n".join(list(processed)[-500:]))

def clean_text(text):
    if not text:
        return ""
    # Убираем разметку
    text = re.sub(r'[\*\_\`\#\[\]\(\)]', '', text)
    
    # Схлопываем лишние пробелы и пустые строки, оставляя только чистый текст
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join([line for line in lines if line])
    return text.strip()

def has_links(text):
    if not text:
        return False
    # Проверяем наличие ссылок, доменов, упоминаний каналов или ботов
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

def upload_photos_to_wall(media_urls):
    attachments = []
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
    return attachments

def send_to_vk(text, media_urls):
    if not media_urls:
        return False
        
    try:
        attachments = upload_photos_to_wall(media_urls)
        if not attachments:
            return False

        vk.wall.post(
            owner_id=-GROUP_ID,
            message=text,
            attachments=",".join(attachments),
            from_group=1,
            signed=0
        )
        print("Пост успешно опубликован в VK!")
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
                text = txt_elem.get_text(separator='\n') if txt_elem else ""
                
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

def main():
    processed = load_processed()
    posts = fetch_telegram_posts()
    
    if not posts:
        print("Посты не найдены.")
        return

    if not processed:
        print("Инициализация базы: запоминаем текущие посты...")
        for post in posts:
            processed.add(post["id"])
        save_processed(processed)
        print("Готово. Теперь будут публиковаться только новые посты.")
        return

    published_count = 0
    posts.reverse()
    
    for post in posts:
        if post["id"] not in processed:
            processed.add(post["id"])
            
            # Проверка 1: Если нет картинок — пропускаем
            if not post["media"]:
                print(f"Пропуск (нет фото): {post['id']}")
                continue

            # Проверка 2: Если в оригинальном тексте есть ссылки/реклама — пропускаем
            if has_links(post["text"]):
                print(f"Пропуск (содержит ссылки/рекламу): {post['id']}")
                continue

            # Очищаем текст от лишних дыр и пробелов
            clean_msg = clean_text(post["text"])

            print(f"Публикуем чистый пост с фото...")
            success = send_to_vk(clean_msg, post["media"])
            if success:
                published_count += 1
                time.sleep(4)

    save_processed(processed)
    print(f"Готово. Опубликовано новых постов: {published_count}")

if __name__ == "__main__":
    main()
