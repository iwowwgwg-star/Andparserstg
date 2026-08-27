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

def get_latest_vk_post_text():
    """Получает текст самого последнего поста на стене ВК"""
    try:
        posts = vk.wall.get(owner_id=-GROUP_ID, count=1, v="5.131")
        if posts['items']:
            return posts['items'][0].get('text', '').strip()
    except Exception as e:
        print(f"Ошибка получения постов из ВК: {e}")
    return ""

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
            
            # Берем самый последний пост в ТГ
            msg = messages[-1]
            link = msg.find('a', class_='tgme_widget_message_date')
            if not link:
                return None
            post_id = link['href']

            # Пропускаем, если есть видео
            has_video = bool(
                msg.find('video') or 
                msg.find('source') or 
                msg.find(class_=['tgme_widget_message_video_player', 'tgme_widget_message_video'])
            )
            if has_video:
                print(f"Пост {post_id} содержит видео. Пропускаем.")
                return None

            # Ищем картинки
            media = []
            for wrap in msg.find_all('a', class_='tgme_widget_message_photo_wrap'):
                style = wrap.get('style', '')
                match = re.search(r"background-image:url\('(.*?)'\)", style)
                if match:
                    media.append(match.group(1))

            if not media:
                print(f"Пост {post_id} без картинок. Пропускаем.")
                return None

            txt_elem = msg.find('div', class_='tgme_widget_message_text')
            text = clean_text(txt_elem.get_text(separator='\n')) if txt_elem else ""

            return {"id": post_id, "text": text, "media": media}
                
    except Exception as e:
        print(f"Ошибка парсинга Telegram: {e}")
    return None

def main():
    print("Проверка ленты Telegram...")
    tg_post = fetch_latest_telegram_post()

    if not tg_post:
        print("Подходящий пост в Telegram не найден.")
        return

    print(f"Свежий пост в ТГ найден: {tg_post['id']}")

    # Получаем текст последнего поста из ВК для сравнения
    last_vk_text = get_latest_vk_post_text()

    # Сравниваем тексты (по первыми 100 символам)
    if last_vk_text and tg_post["text"] and last_vk_text[:100] == tg_post["text"][:100]:
        print("Этот пост уже есть на стене ВК. Ничего не публикуем.")
        return

    print(f"Публикуем новый пост: {tg_post['id']}")
    time.sleep(1)

    # Загружаем картинки
    attachments = []
    for url in tg_post["media"][:10]:
        att = upload_photo(url)
        if att:
            attachments.append(att)
        time.sleep(0.5)

    if not attachments:
        print("Не удалось загрузить фотографии, отмена.")
        return

    try:
        vk.wall.post(
            owner_id=-GROUP_ID,
            message=tg_post["text"],
            attachments=",".join(attachments),
            from_group=1,
            signed=0
        )
        print("Пост успешно опубликован в ВК!")
        
    except Exception as e:
        print(f"Ошибка публикации в VK: {e}")

if __name__ == "__main__":
    main()
