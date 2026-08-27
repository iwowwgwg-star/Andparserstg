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
        f.write("\n".join(list(processed)[-200:]))

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

def upload_video_as_doc(video_url):
    try:
        print(f"Скачиваем видео для загрузки: {video_url}")
        resp = requests.get(video_url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
            
        server_info = vk.docs.getWallUploadServer(group_id=GROUP_ID, v="5.131")
        upload_url = server_info['upload_url']
        
        files = {'file': ('video.mp4', resp.content, 'video/mp4')}
        upload_res = requests.post(upload_url, files=files, timeout=60).json()
        
        if 'file' in upload_res:
            saved = vk.docs.save(file=upload_res['file'], title="video", v="5.131")
            if 'doc' in saved:
                d = saved['doc']
                return f"doc{d['owner_id']}_{d['id']}"
    except Exception as e:
        print(f"Ошибка загрузки видео-документа в VK: {e}")
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

    post_id = latest_post["id"]

    if post_id in processed:
        print(f"Последний пост ({post_id}) уже обработан. Новых постов нет.")
        return

    if not latest_post["media"] and not latest_post["videos"] and not latest_post["text"]:
        print("Пост пустой, пропускаем.")
        return

    print(f"Обнаружен новый последний пост, публикуем: {post_id}")

    attachments = []
    
    for url in latest_post["media"][:10]:
        att = upload_photo(url)
        if att:
            attachments.append(att)
        time.sleep(0.3)

    for url in latest_post["videos"][:1]:
        att = upload_video_as_doc(url)
        if att:
            attachments.append(att)
        time.sleep(0.3)

    try:
        vk.wall.post(
            owner_id=-GROUP_ID,
            message=latest_post["text"],
            attachments=",".join(attachments) if attachments else None,
            from_group=1,
            signed=0
        )
        print("Пост успешно опубликован!")
        
        processed.add(post_id)
        save_processed(processed)
        
    except Exception as e:
        print(f"Ошибка публикации в VK: {e}")

if __name__ == "__main__":
    main()
