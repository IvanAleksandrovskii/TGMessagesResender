# src/chat_manager.py

from .config import settings
from .config_manager import save_config


# Файл с конфигурацией пересылки бота
CONFIG_FILE = settings.bot_chats_config_file


async def validate_chats(app, SOURCE_CHAT_IDS, FORWARDING_CONFIG):
    """
    Проверяет и восстанавливает доступность всех чатов в конфигурации,
    предварительно загружая список диалогов для более надежного доступа.
    """
    print("Проверка доступа к чатам...")

    # Словарь для хранения информации о чатах
    chat_info = {}

    # Сначала загружаем все диалоги для кэширования
    print("Предварительная загрузка всех доступных диалогов...")
    cached_dialogs = {}
    async for dialog in app.get_dialogs():
        cached_dialogs[dialog.chat.id] = dialog.chat
        # Сохраняем информацию о чате
        if hasattr(dialog.chat, "username") and dialog.chat.username:
            chat_info[dialog.chat.id] = {
                "username": dialog.chat.username,
                "type": str(dialog.chat.type.name),
            }
        else:
            chat_info[dialog.chat.id] = {"type": str(dialog.chat.type.name)}

    print(f"Загружено {len(cached_dialogs)} диалогов")

    # Собираем все уникальные ID чатов, которые нужно проверить
    all_chat_ids = set(SOURCE_CHAT_IDS)
    for dest_ids in FORWARDING_CONFIG.values():
        all_chat_ids.update(dest_ids)

    # Отслеживаем проблемные чаты
    problematic_chats = set()

    # Проверяем все чаты за один проход
    for chat_id in all_chat_ids:
        if chat_id in cached_dialogs:
            print(f"Доступ к чату {chat_id} подтвержден (из кэша диалогов)")
        else:
            try:
                # Попытка получить информацию о чате напрямую, если его нет в диалогах
                chat = await app.get_chat(chat_id)
                print(f"Доступ к чату {chat_id} подтвержден (прямой запрос)")

                # Сохраняем информацию о чате
                if hasattr(chat, "username") and chat.username:
                    chat_info[chat_id] = {
                        "username": chat.username,
                        "type": str(chat.type.name),
                    }
                else:
                    chat_info[chat_id] = {"type": str(chat.type.name)}
            except Exception as e:
                print(f"Ошибка доступа к чату {chat_id}: {e}")
                problematic_chats.add(chat_id)

    if problematic_chats:
        print(f"Найдено недоступных чатов: {len(problematic_chats)}")

    # Теперь обновляем конфигурацию на основе результатов
    # Удаляем недоступные исходные чаты
    for source_id in list(SOURCE_CHAT_IDS):
        if source_id in problematic_chats:
            SOURCE_CHAT_IDS.remove(source_id)
            if source_id in FORWARDING_CONFIG:
                del FORWARDING_CONFIG[source_id]
                print(f"Чат {source_id} удален из конфигурации (недоступен)")

    # Удаляем недоступные чаты назначения
    for source_id in list(FORWARDING_CONFIG.keys()):
        dest_ids = FORWARDING_CONFIG[source_id]
        for dest_id in list(dest_ids):
            if dest_id in problematic_chats:
                FORWARDING_CONFIG[source_id].remove(dest_id)
                print(f"Чат назначения {dest_id} удален из конфигурации (недоступен)")

        # Если у источника больше нет чатов назначения, удаляем его полностью
        if not FORWARDING_CONFIG[source_id]:
            del FORWARDING_CONFIG[source_id]
            if source_id in SOURCE_CHAT_IDS:
                SOURCE_CHAT_IDS.remove(source_id)
            print(
                f"Исходный чат {source_id} удален из конфигурации (нет доступных чатов назначения)"
            )

    # Сохраняем обновленную конфигурацию с информацией о чатах
    save_config(SOURCE_CHAT_IDS, FORWARDING_CONFIG, chat_info)
    print("Конфигурация обновлена после проверки доступа к чатам")

    return SOURCE_CHAT_IDS, FORWARDING_CONFIG, chat_info


def print_current_config(FORWARDING_CONFIG, chat_info):
    """
    Выводит текущую конфигурацию пересылки с дополнительной информацией
    """
    for source_id, dest_ids in FORWARDING_CONFIG.items():
        source_info = ""
        if source_id in chat_info:
            if "username" in chat_info[source_id]:
                source_info = f" (@{chat_info[source_id]['username']})"
            source_info += f" [тип: {chat_info[source_id]['type']}]"

        dest_info = []
        for dest_id in dest_ids:
            info = str(dest_id)
            if dest_id in chat_info:
                if "username" in chat_info[dest_id]:
                    info += f" (@{chat_info[dest_id]['username']})"
                info += f" [тип: {chat_info[dest_id]['type']}]"
            dest_info.append(info)

        print(f"Из чата {source_id}{source_info} в чаты: {', '.join(dest_info)}")
