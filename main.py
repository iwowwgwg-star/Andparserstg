import os
import sys
import json
import re
import requests
from bs4 import BeautifulSoup

VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
TG_CHANNEL = os.getenv("TG_CHANNEL", "andparserstg")

HISTORY_FILE = "sent_posts.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def get_latest_tg_post():
    url = f"https://t.me/s/{TG_CHANNEL}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Ошибка доступа к Telegram: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message')
        
        if not messages:
            return None
            
        latest = messages[-1]
        post_id_elem = latest.get('data-post')
        if not post_id_elem:
            return None
            
        text_elem = latest.find('div', class_='tgme_widget_message_text')
        text = text_elem.get_text(separator="\n") if text_elem else ""
        
        # Сбор картинок
        images = []
        photos = latest.find_all('a', class_='tgme_widget_message_photo_wrap')
        for p in photos:
            style = p.get('style', '')
            if 'background-image:url(\'' in style:
                img_url = style.split('background-image:url(\'')[1].split('\')')[0]
                images.append(img_url)
                
        # Сбор видео
        videos = []
        video_tags = latest.find_all('video')
        for v in video_tags:
            src = v.get('src')
            if src:
                videos.append(src)
                
        if not videos:
            source_tags = latest.find_all('source')
            for s in source_tags:
                src = s.get('src')
                if src:
                    videos.append(src)
                
        return {
            "tg_id": post_id_elem,
            "text": clean_text(text),
            "images": images,
            "videos": videos
        }
    except Exception as e:
        print(f"Ошибка при парсинге Telegram: {e}")
        return None

def upload_photo_to_vk(img_url):
    try:
        server_url = "https://api.vk.com/method/photos.getWallUploadServer"
        params = {"owner_id": GROUP_ID, "access_token": VK_TOKEN, "v": "5.131"}
        res = requests.get(server_url, params=params).json()
        
        if "response" not in res:
            return None
        upload_url = res["response"]["upload_url"]
        
        img_data = requests.get(img_url).content
        files = {"photo": ("image.jpg", img_data, "image/jpeg")}
        upload_res = requests.post(upload_url, files=files).json()
        
        save_params = {
            "owner_id": GROUP_ID,
            "server": upload_res["server"],
            "photo": upload_res["photo"],
            "hash": upload_res["hash"],
            "access_token": VK_TOKEN,
            "v": "5.131"
        }
        saved_res = requests.get("https://api.vk.com/method/photos.saveWallPhoto", params=save_params).json()
        
        if "response" in saved_res:
            photo_info = saved_res["response"][0]
            return f"photo{photo_info['owner_id']}_{photo_info['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото в ВК: {e}")
    return None

def upload_video_to_vk(video_url):
    try:
        # Загружаем видео как документ для стены, чтобы оно было прямо в посте
        server_url = "https://api.vk.com/method/docs.getWallUploadServer"
        params = {"group_id": abs(int(GROUP_ID)), "access_token": VK_TOKEN, "v": "5.131"}
        res = requests.get(server_url, params=params).json()
        
        if "response" not in res:
            return None
        upload_url = res["response"]["upload_url"]
        
        video_data = requests.get(video_url).content
        files = {"file": ("video.mp4", video_data, "video/mp4")}
        upload_res = requests.post(upload_url, files=files).json()
        
        if "file" not in upload_res:
            return None

        save_params = {
            "file": upload_res["file"],
            "access_token": VK_TOKEN,
            "v": "5.131"
        }
        saved_res = requests.get("https://api.vk.com/method/docs.save", params=save_params).json()
        
        if "response" in saved_res:
            doc_info = saved_res["response"]["doc"]
            return f"doc{doc_info['owner_id']}_{doc_info['id']}"
    except Exception as e:
        print(f"Ошибка загрузки видео в ВК: {e}")
    return None

def post_to_vk(text, attachments):
    url = "https://api.vk.com/method/wall.post"
    params = {
        "owner_id": GROUP_ID,
        "from_group": 1,
        "message": text,
        "attachments": ",".join(attachments) if attachments else "",
        "access_token": VK_TOKEN,
        "v": "5.131"
    }
    response = requests.post(url, data=params).json()
    if "error" in response:
        print(f"Ошибка публикации в ВК: {response['error']}")
        return False
    else:
        print(f"Пост с медиа успешно опубликован! ID: {response.get('response', {}).get('post_id')}")
        return True

if __name__ == "__main__":
    if not VK_TOKEN or not GROUP_ID:
        print("Ошибка: Не заданы VK_TOKEN или GROUP_ID!")
        sys.exit(1)
        
    history = load_history()
    post = get_latest_tg_post()
    
    if not post:
        print("Новых постов не найдено.")
        sys.exit(0)
        
    tg_id = post["tg_id"]
    
    if tg_id in history:
        print(f"Пост {tg_id} уже публиковался ранее. Пропускаем.")
        sys.exit(0)
        
    print(f"Найден новый пост: {tg_id}")
    
    attachments = []
    
    # Загружаем все картинки
    for img_url in post["images"]:
        vk_photo = upload_photo_to_vk(img_url)
        if vk_photo:
            attachments.append(vk_photo)
            
    # Загружаем все видео в тело поста
    for vid_url in post["videos"]:
        vk_video = upload_video_to_vk(vid_url)
        if vk_video:
            attachments.append(vk_video)
            
    success = post_to_vk(post["text"], attachments)
    
    if success:
        history.append(tg_id)
        if len(history) > 100:
            history = history[-100:]
        save_history(history)
