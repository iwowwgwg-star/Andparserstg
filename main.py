import os
import sys
import json
import re
import requests
from bs4 import BeautifulSoup

VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
TG_CHANNEL = os.getenv("TG_CHANNEL", "topor")

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

def get_vk_wall_texts():
    # Приводим GROUP_ID к правильному виду с минусом для API
    group_owner_id = GROUP_ID if str(GROUP_ID).startswith("-") else f"-{GROUP_ID}"
    url = "https://api.vk.com/method/wall.get"
    params = {
        "owner_id": group_owner_id,
        "count": 20,
        "access_token": VK_TOKEN,
        "v": "5.131"
    }
    try:
        res = requests.get(url, params=params).json()
        if "response" in res and "items" in res["response"]:
            return [item.get("text", "").strip().lower() for item in res["response"]["items"]]
    except Exception as e:
        print(f"Ошибка при получении стены ВК: {e}")
    return []

def get_all_tg_posts():
    url = f"https://t.me/s/{TG_CHANNEL}"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    }
    posts_list = []
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Ошибка доступа к Telegram: код {response.status_code}")
            return posts_list
            
        soup = BeautifulSoup(response.text, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message')
        
        for latest in messages:
            post_id_elem = latest.get('data-post')
            if not post_id_elem:
                continue
                
            text_elem = latest.find('div', class_='tgme_widget_message_text')
            text = text_elem.get_text(separator="\n") if text_elem else ""
            
            images = []
            for p in latest.find_all('a', class_='tgme_widget_message_photo_wrap'):
                style = p.get('style', '')
                if 'background-image:url(\'' in style:
                    img_url = style.split('background-image:url(\'')[1].split('\')')[0]
                    images.append(img_url)
                    
            videos = []
            for v in latest.find_all('video'):
                src = v.get('src')
                if src: videos.append(src)
            for s in latest.find_all('source'):
                src = s.get('src')
                if src: videos.append(src)
                    
            posts_list.append({
                "tg_id": post_id_elem,
                "text": clean_text(text),
                "images": images,
                "videos": videos
            })
    except Exception as e:
        print(f"Ошибка при парсинге Telegram: {e}")
        
    return posts_list

def upload_photo_to_vk(img_url):
    try:
        group_owner_id = GROUP_ID if str(GROUP_ID).startswith("-") else f"-{GROUP_ID}"
        server_url = "https://api.vk.com/method/photos.getWallUploadServer"
        params = {"owner_id": group_owner_id, "access_token": VK_TOKEN, "v": "5.131"}
        res = requests.get(server_url, params=params).json()
        if "response" not in res: return None
        upload_url = res["response"]["upload_url"]
        
        img_data = requests.get(img_url).content
        files = {"photo": ("image.jpg", img_data, "image/jpeg")}
        upload_res = requests.post(upload_url, files=files).json()
        
        save_params = {
            "owner_id": group_owner_id,
            "server": upload_res["server"],
            "photo": upload_res["photo"],
            "hash": upload_res["hash"],
            "access_token": VK_TOKEN,
            "v": "5.131"
        }
        saved_res = requests.get("https://api.vk.com/method/photos.saveWallPhoto", params=save_params).json()
        if "response" in saved_res:
            p = saved_res["response"][0]
            return f"photo{p['owner_id']}_{p['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
    return None

def upload_video_to_vk(video_url):
    try:
        server_url = "https://api.vk.com/method/docs.getWallUploadServer"
        params = {"group_id": abs(int(GROUP_ID)), "access_token": VK_TOKEN, "v": "5.131"}
        res = requests.get(server_url, params=params).json()
        if "response" not in res: return None
        upload_url = res["response"]["upload_url"]
        
        video_data = requests.get(video_url).content
        files = {"file": ("video.mp4", video_data, "video/mp4")}
        upload_res = requests.post(upload_url, files=files).json()
        if "file" not in upload_res: return None

        save_params = {"file": upload_res["file"], "access_token": VK_TOKEN, "v": "5.131"}
        saved_res = requests.get("https://api.vk.com/method/docs.save", params=save_params).json()
        if "response" in saved_res:
            d = saved_res["response"]["doc"]
            return f"doc{d['owner_id']}_{d['id']}"
    except Exception as e:
        print(f"Ошибка загрузки видео: {e}")
    return None

def post_to_vk(text, attachments):
    url = "https://api.vk.com/method/wall.post"
    group_owner_id = GROUP_ID if str(GROUP_ID).startswith("-") else f"-{GROUP_ID}"
    
    params = {
        "owner_id": group_owner_id,
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
    print(f"Пост успешно опубликован! ID: {response.get('response', {}).get('post_id')}")
    return True

if __name__ == "__main__":
    if not VK_TOKEN or not GROUP_ID:
        print("Ошибка: Не заданы VK_TOKEN или GROUP_ID!")
        sys.exit(1)
        
    history = load_history()
    vk_texts = get_vk_wall_texts()
    posts = get_all_tg_posts()
    
    if not posts:
        print("Посты на странице канала не найдены.")
        sys.exit(0)
        
    new_posts_found = False
    
    for post in posts:
        tg_id = post["tg_id"]
        post_text_clean = post["text"].lower()
        
        if tg_id in history:
            continue
            
        is_duplicate = False
        if post_text_clean:
            for vk_t in vk_texts:
                if post_text_clean in vk_t or vk_t in post_text_clean:
                    is_duplicate = True
                    break
        
        if is_duplicate:
            print(f"Пост {tg_id} уже есть в VK, пропускаем.")
            history.append(tg_id)
            new_posts_found = True
            continue
            
        print(f"Публикуем новый пост: {tg_id}")
        
        attachments = []
        for img_url in post["images"]:
            vk_photo = upload_photo_to_vk(img_url)
            if vk_photo: attachments.append(vk_photo)
            
        for vid_url in post["videos"]:
            vk_video = upload_video_to_vk(vid_url)
            if vk_video: attachments.append(vk_video)
            
        success = post_to_vk(post["text"], attachments)
        
        if success:
            history.append(tg_id)
            new_posts_found = True
            
    if new_posts_found:
        if len(history) > 100:
            history = history[-100:]
        save_history(history)
    else:
        print("Новых постов для публикации нет.")
