import os
import time
import requests
import vk_api
from datetime import datetime

# Настройки из переменных окружения
VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")  # Например, 229040854 (без минуса)

# Инициализация сессии VK API
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()

def upload_photo_to_vk(image_url):
    try:
        # 1. Получаем сервер для загрузки фото в группу
        upload_server = vk.photos.getWallUploadServer(group_id=int(VK_GROUP_ID))
        
        # 2. Скачиваем картинку по ссылке
        img_response = requests.get(image_url, timeout=15)
        if img_response.status_code != 200:
            print(f"ERROR: Не удалось скачать картинку по ссылке {image_url}", flush=True)
            return None
        
        # 3. Отправляем фото на сервер ВК
        files = {'photo': ('image.jpg', img_response.content, 'image/jpeg')}
        upload_response = requests.post(upload_server['upload_url'], files=files).json()
        
        if 'photo' in upload_response and upload_response['photo'] != '[]':
            # 4. Сохраняем фото на стене группы
            saved_photo = vk.photos.saveWallPhoto(
                group_id=int(VK_GROUP_ID),
                server=upload_response['server'],
                photo=upload_response['photo'],
                hash=upload_response['hash']
            )
            if saved_photo:
                photo_id = saved_photo[0]['id']
                owner_id = saved_photo[0]['owner_id']
                return f"photo{owner_id}_{photo_id}"
        return None
    except Exception as e:
        print(f"ERROR: Ошибка при загрузке фото в VK: {e}", flush=True)
        return None

def post_to_vk_with_media(text, media_urls):
    try:
        attachments = []
        for img_url in media_urls[:10]:
            photo_attachment = upload_photo_to_vk(img_url)
            if photo_attachment:
                attachments.append(photo_attachment)
                time.sleep(0.5)

        if not attachments:
            print("ПРОПУСК: В посте нет фотографий, публикация отменена.", flush=True)
            return False

        # Публикация записи на стену сообщества с выводом ID
        response = vk.wall.post(
            owner_id=-int(VK_GROUP_ID),
            message=text,
            attachments=",".join(attachments),
            from_group=1,
            signed=0
        )
        
        post_id = response.get('post_id')
        print(f"SUCCESS: Пост успешно опубликован в VK! ID записи: {post_id}", flush=True)
        time.sleep(3)
        return True
    except Exception as e:
        print(f"ERROR: Ошибка публикации в VK: {e}", flush=True)
        return False

def main():
    print("Бот запущен и готов к работе...", flush=True)
    while True:
        try:
            # Здесь вызывается ваша логика выгрузки постов (например, из базы данных или внешнего источника)
            # Пример:
            # posts = fetch_new_posts()
            # for post in posts:
            #     post_to_vk_with_media(post['text'], post['images'])
            
            # Цикл опроса (раз в час или по вашему таймеру)
            time.sleep(3600)
        except Exception as e:
            print(f"ERROR в главном цикле: {e}", flush=True)
            time.sleep(60)

if __name__ == "__main__":
    main()
