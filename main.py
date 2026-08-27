import os
import json
import vk_api
import requests
from bs4 import BeautifulSoup

# Настройки (подставь свои переменные или оставь как у тебя через os.environ)
VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # ID группы со знаком минус, например -123456789
TG_CHANNEL = "https://t.me/s/topor"  # Твой канал-источник

STATE_FILE = "last_id.json"

def get_last_saved_id():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_id", 0)
        except Exception:
            return 0
    return 0

def save_last_id(post_id):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_id": post_id}, f)

def get_latest_telegram_post():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(TG_CHANNEL, headers=headers)
    if response.status_code != 200:
        print("Не удалось получить страницу Telegram")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    posts = soup.find_all('div', class_='tgme_widget_message')
    
    if not posts:
        return None

    # Берем самый последний (самый свежий) пост со страницы
    latest_post = posts[-1]
    
    # Достаем уникальный data-post (например, "topor/12345")
    post_data_id = latest_post.get('data-post')
    if not post_data_id:
        return None
    
    # Вытаскиваем числовой ID сообщения
    try:
        post_id = int(post_data_id.split('/')[-1])
    except ValueError:
        return None

    # Собираем текст
    text_elem = latest_post.find('div', class_='tgme_widget_message_text')
    text = text_elem.get_text(separator='\n', strip=True) if text_elem else ""

    # Собираем медиа (если есть картинка или видео)
    media_url = None
    photo_elem = latest_post.find('a', class_='tgme_widget_message_photo_wrap')
    if photo_elem:
        style = photo_elem.get('style', '')
        if 'url(' in style:
            try:
                media_url = style.split('url(\'')[1].split('\')[0]')
            except IndexError:
                pass

    # Проверяем видео
    video_elem = latest_post.find('video')
    if video_elem:
        media_url = video_elem.get('src')

    return {
        "id": post_id,
        "text": text,
        "media": media_url
    }

def main():
    print("Проверяем новые посты в Telegram...")
    
    # Проверяем, заданы ли обязательные переменные
    if not VK_TOKEN or not GROUP_ID:
        print("Ошибка: не заданы VK_TOKEN или GROUP_ID в переменных окружения!")
        return

    last_saved_id = get_last_saved_id()
    
    post = get_latest_telegram_post()
    if not post:
        print("Постов не найдено.")
        return

    current_post_id = post["id"]
    print(f"Последний пост в ТГ ID: {current_post_id}, в базе сохранен ID: {last_saved_id}")

    # Если ID совпадает с тем, что уже публиковали — ничего не делаем
    if current_post_id <= last_saved_id:
        print("Новых постов нет.")
        return

    # ЕСЛИ ЕСТЬ НОВЫЙ ПОСТ — ПУБЛИКУЕМ ЕГО
    print(f"Найден новый пост! Публикуем ID: {current_post_id}")
    
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()

    try:
        # Преобразуем GROUP_ID безопасно
        numeric_group_id = int(GROUP_ID)
        
        vk.wall.post(
            owner_id=numeric_group_id,
            message=post["text"] if post["text"] else " " # Защита от пустого текста
        )
        print("Пост успешно улетел в ВК!")
        
        # Сохраняем новый ID, чтобы больше никогда его не дублировать
        save_last_id(current_post_id)
        
    except Exception as e:
        print(f"Ошибка при публикации в ВК: {e}")

if __name__ == "__main__":
    main()
