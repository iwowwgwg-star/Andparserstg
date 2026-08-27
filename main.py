import os
import re
import time
import vk_api
import requests
from bs4 import BeautifulSoup

# Твой пользовательский токен для загрузки картинок
VK_TOKEN = "vk1.a.KFziyAOmDYFo-38aGxsFBMG3oety-HKr5m3YOX27_UGvJTaIwJLtZPeCd2OUZS5UO2432U8L7ZphRIjHEl0_Nz3nnSBqij6DBSU3MqHCzSEhRGCGVEDKxSqT258qxZzpxn4Mz9jGcbkCrAeLqZlFpLFDYqP-T38GUVibieb3JssaXlxPD1IvOeCWN1i3DFt4HNWCkB5_wKMEMbhwU2EdRQ"
GROUP_ID = 231926003
TG_CHANNEL = "topor"

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
upload = vk_api.upload.VkUpload(vk_session)

# Файл для сохранения уже отправленных постов, чтобы не было дублей
PROCESSED_FILE = "processed.txt"

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed(processed):
    with open(PROCESSED_FILE, "w") as f:
        f.write("\n".join(list(processed)[-300:]))

def clean_text(text):
    if not text:
        return ""
    # Вырезаем любые ссылки и домены из текста
    text = re.sub(r'http\S+|www\.\S+', '', text)
    text = re.sub(r'\b[a-zA-Z0-9][-a-zA-Z0-9]*\.(com|ru|org|net|me|io|info|biz|cc|co)\b', '', text, flags=re.IGNORECASE)
    # Убираем лишние спецсимволы
    text = re.sub(r'[\*\_\`\#\[\]\(\)]', '', text)
    # Убираем образовавшиеся двойные пробелы и пустые строки
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

def send_to_vk(text, media_urls):
    try:
        attachments = []
        for url in media_urls[:10]:
            att = upload_photo(url)
            if att:
                attachments.append(att)
                time.sleep(0.4)

        vk.wall.post(
            owner_id=-GROUP_ID,
            message=text,
            attachments=",".join(attachments) if attachments else None,
            from_group=1, # Публикация строго от имени сообщества
            signed=0
        )
        print("Пост с картинками успешно опубликован в группе от имени сообщества!")
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
                
                # Собираем все картинки из поста (если они есть)
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

    # Если база пустая (первый запуск) — проверяем последние 50 постов (примерно за месяц)
    if not processed:
        print("Первый запуск: проверяем ленту за последний месяц...")
        posts.reverse()
        for post in posts[-50:]: 
            # Пропускаем пост, если в нем нет картинок
            if not post["media"]:
                print(f"Пропускаем пост (нет картинок): {post['id']}")
                processed.add(post["id"]) 
                continue

            print("Публикуем пост с картинками...")
            success = send_to_vk(post["text"], post["media"])
            if success:
                processed.add(post["id"])
                time.sleep(3)
        
        # Добавляем все остальные просмотренные в базу
        for p in posts:
            processed.add(p["id"])
        save_processed(processed)
        print("Инициализация завершена. Теперь бот будет ждать новые посты.")
        return

    # Обычный режим (проверка новых)
    published_count = 0
    for post in posts:
        if post["id"] not in processed:
            # Если у нового поста нет картинок — пропускаем
            if not post["media"]:
                print(f"Пропускаем новый пост без картинок: {post['id']}")
                processed.add(post["id"])
                continue

            print("Обнаружен новый пост с картинками, публикуем...")
            success = send_to_vk(post["text"], post["media"])
            if success:
                processed.add(post["id"])
                published_count += 1
                time.sleep(3)

    save_processed(processed)
    print(f"Готово. Опубликовано новых постов с картинками: {published_count}")

if __name__ == "__main__":
    main()
