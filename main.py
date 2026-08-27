import os
import json
import vk_api
import feedparser  # встроенный или стандартный парсер RSS

VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
# Используем RSS-поток публичного канала вместо тупящего HTML
TG_RSS_URL = "https://t.me/s/topor"  # Или RSS-зеркало, если понадобится

STATE_FILE = "last_id.json"

def get_last_saved_id():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_id", "")
        except Exception:
            return ""
    return ""

def save_last_id(post_id):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_id": post_id}, f)

def get_latest_telegram_post():
    # Парсим через публичный RSS/Atom поток Telegram-канала
    rss_url = "https://tg.i-c-a.su/rss/topor" # Публичный стабильный RSS-мост для Telegram
    
    try:
        feed = feedparser.parse(rss_url)
        if not feed.entries:
            return None
            
        # Берем самый первый (самый свежий) элемент из ленты
        latest = feed.entries[0]
        post_id = latest.get("id") or latest.get("link")
        text = latest.get("summary", "")
        
        return {
            "id": post_id,
            "text": text
        }
    except Exception as e:
        print(f"Ошибка при чтении RSS: {e}")
        return None

def main():
    print("Проверяем новые посты через быстрый RSS...")
    
    if not VK_TOKEN or not GROUP_ID:
        print("Ошибка: не заданы VK_TOKEN или GROUP_ID!")
        return

    last_saved_id = get_last_saved_id()
    
    post = get_latest_telegram_post()
    if not post:
        print("Не удалось получить посты из ленты.")
        return

    current_post_id = post["id"]
    print(f"Последний ID в ленте: {current_post_id}, в базе сохранен: {last_saved_id}")

    # Сравниваем строковые ID (ссылки или уникальные хэши)
    if current_post_id == last_saved_id:
        print("Новых постов нет.")
        return

    print(f"Найден новый пост! Публикуем...")
    
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()

    try:
        numeric_group_id = int(GROUP_ID)
        vk.wall.post(
            owner_id=numeric_group_id,
            message=post["text"] if post["text"] else " "
        )
        print("Пост успешно улетел в ВК!")
        save_last_id(current_post_id)
        
    except Exception as e:
        print(f"Ошибка при публикации в ВК: {e}")

if __name__ == "__main__":
    main()
