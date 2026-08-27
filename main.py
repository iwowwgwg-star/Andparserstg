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
    if not text:
        return ""
    text = re.sub(r'[\*\_\`\#\[\]\(\)]', '', text)
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join([line for line in lines if line])
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
    """Получает тексты последних постов со стены группы VK, чтобы исключить дубли"""
    texts = set()
    try:
        wall = vk.wall.get(owner_id=-GROUP_ID, count=50)
        for item in wall.get('items', []):
            if 'text' in item:
                texts.add(item['text'].strip())
    except Exception as e:
        print(f"Ошибка получения постов из ВК: {e}")
    return texts

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
                
                txt_elem = msg.find('div', class_='tgme_widget_message_text')
                text = txt_elem.get_text(separator='\n') if txt_elem else ""
                
                media = []
                for wrap in msg.find_all('a', class_='tgme_widget_message_photo_wrap'):
                    style = wrap.get('style', '')
                    match = re.search(r"background-image:url\('(.*?)'\)", style)
                    if match:
                        media.append(match.group(1))
                
                posts.append({"text": text, "media": media})
    except Exception as e:
        print(f"Ошибка парсинга Telegram: {e}")
    return posts

def main():
    posts = fetch_telegram_posts()
    if not posts:
        print("Посты не найдены.")
        return

    # Загружаем уже имеющиеся тексты со стены VK
    vk_texts = get_vk_existing_texts()
    
    published_count = 0
    # Идем от старых к новым
    posts.reverse()
    
    for post in posts:
        if not post["media"]:
            continue

        if has_links(post["text"]):
            continue

        clean_msg = clean_text(post["text"])
        
        # Если такого текста еще нет на стене группы — публикуем
        if clean_msg and clean_msg not in vk_texts:
            print("Найден новый уникальный пост, публикуем...")
            success = send_to_vk(clean_msg, post["media"])
            if success:
                vk_texts.add(clean_msg) # добавляем в локальную базу чтобы не дублировать в рамках одного запуска
                published_count += 1
                time.sleep(4)
        else:
            print("Пост уже есть в VK или пустой, пропускаем.")

    print(f"Готово. Опубликовано новых постов: {published_count}")

if __name__ == "__main__":
    main()
