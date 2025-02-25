# src/check_folder.py

import json
import os

from pyrogram.raw import functions
from pyrogram.errors import FloodWait

from .client import app
from .config import settings

DIR_NAME = settings.chats_folder_name
CONFIG_FILE = settings.bot_chats_config_file


async def check_folder_existence():
    """
    Проверяет существование папки с названием DIR_NAME в Telegram
    и извлекает из неё информацию о чатах для пересылки.
    Если конфигурационный файл существует, использует его без запроса ввода.

    Returns:
        tuple: (существует_ли_папка, конфигурация_чатов, информация_о_чатах)
    """
    # Проверяем наличие файла конфигурации
    if os.path.exists(CONFIG_FILE):
        try:
            print(f"\n=== Найден файл конфигурации {CONFIG_FILE} ===")
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)

            source_chat_ids = config.get("SOURCE_CHAT_IDS", [])
            forwarding_config = config.get("FORWARDING_CONFIG", {})
            chat_info = config.get("CHAT_INFO", {})

            # Выводим загруженную конфигурацию
            print("Загруженная конфигурация пересылки:")
            for source_id, dest_ids in forwarding_config.items():
                print(
                    f"Из: Чат {source_id} -> В: {', '.join([f'Чат {dest_id}' for dest_id in dest_ids])}"
                )

            print(f"✅ Конфигурация загружена из файла {CONFIG_FILE}")
            print(
                f"Для изменения конфигурации удалите файл {settings.bot_chats_config_file} и запустите бота снова."
            )

            return True, forwarding_config, chat_info
        except Exception as e:
            print(f"⚠️ Ошибка при чтении файла конфигурации: {str(e)}")
            print("Продолжаем с настройкой через папку...")
    else:
        print(f"\n=== Файл конфигурации {CONFIG_FILE} не найден ===")
        print("Продолжаем с настройкой через папку...")

    try:
        print("\n=== Проверка папки для пересылки сообщений ===")
        response = await app.invoke(functions.messages.GetDialogFilters())
        target_folder = next(
            (f for f in response if getattr(f, "title", "") == DIR_NAME), None
        )

        if not target_folder:
            print(
                f"❌ Папка '{DIR_NAME}' не найдена. Создайте папку с именем '{DIR_NAME}' "
                "и добавьте в неё чаты, которые вы хотите отслеживать и те, "
                "в которые хотите пересылать данные."
            )
            return False, {}, {}

        print(f"✅ Папка '{DIR_NAME}' найдена! ID: {target_folder.id}")

        # Получаем список чатов из папки
        chat_info = {}
        folder_chats = []

        # Словарь для хранения информации о чатах по номеру в списке
        dialog_dict = {}

        # Сначала собираем все диалоги для быстрого поиска
        all_dialogs = {}
        print("Загрузка всех доступных диалогов...")
        async for dialog in app.get_dialogs():
            all_dialogs[dialog.chat.id] = dialog.chat

        # Собираем все чаты из папки
        print(f"Получение чатов из папки '{DIR_NAME}'...")
        for peer in target_folder.include_peers:
            chat_id = None
            chat_type = None

            if hasattr(peer, "channel_id"):
                chat_id = -1000000000000 - peer.channel_id  # Формат супергруппы/канала
                chat_type = "CHANNEL/SUPERGROUP"
            elif hasattr(peer, "chat_id"):
                chat_id = -peer.chat_id  # Формат группы
                chat_type = "GROUP"
            elif hasattr(peer, "user_id"):
                chat_id = peer.user_id  # Личный чат
                chat_type = "PRIVATE"

            if chat_id:
                folder_chats.append(chat_id)
                chat_info[chat_id] = {"type": chat_type}

        print(f"Найдено {len(folder_chats)} чатов в папке '{DIR_NAME}'")

        # Получаем дополнительную информацию о чатах для отображения в интерактивном меню
        chat_index = 1  # Начинаем нумерацию с 1

        for chat_id in folder_chats:
            # Проверяем, есть ли чат в уже загруженных диалогах
            if chat_id in all_dialogs:
                chat = all_dialogs[chat_id]

                # Определяем имя чата
                if hasattr(chat, "title") and chat.title:
                    chat_name = chat.title
                elif hasattr(chat, "first_name"):
                    chat_name = f"{chat.first_name} {chat.last_name or ''}".strip()
                else:
                    chat_name = f"Чат {chat_id}"

                # Сохраняем username, если есть
                if hasattr(chat, "username") and chat.username:
                    chat_info[chat_id]["username"] = chat.username

                dialog_dict[chat_index] = {
                    "id": chat_id,
                    "name": chat_name,
                    "type": chat_info[chat_id]["type"],
                }

                print(f"- [{chat_index}] {chat_name} (ID: {chat_id})")
                chat_index += 1
            else:
                # Если чата нет в диалогах, мы всё равно добавляем его, но с пометкой
                chat_name = f"Чат {chat_id}"
                dialog_dict[chat_index] = {
                    "id": chat_id,
                    "name": chat_name,
                    "type": chat_info[chat_id]["type"],
                }
                print(
                    f"- [{chat_index}] {chat_name} (ID: {chat_id}) - ограниченный доступ"
                )
                chat_index += 1

        if len(dialog_dict) == 0:
            print(f"⚠️ Папка '{DIR_NAME}' не содержит доступных чатов.")
            return False, {}, {}

        # Начинаем интерактивный выбор чатов
        source_chat_ids = []
        forwarding_config = {}

        print("\n=== Настройка пересылки сообщений из папки ===")
        print(f"Доступные диалоги из папки '{DIR_NAME}':")

        # Выводим список диалогов с более понятными типами чатов
        for i, info in dialog_dict.items():
            chat_type_name = (
                "Группа"
                if "GROUP" in info["type"]
                else (
                    "Супергруппа/Канал"
                    if "CHANNEL" in info["type"] or "SUPERGROUP" in info["type"]
                    else "Личный чат"
                )
            )
            print(f"[{i}] {info['name']} ({chat_type_name}) - ID: {info['id']}")

        # Выбор исходных чатов для пересылки
        print(
            "\nВыберите номера чатов, ИЗ которых нужно пересылать сообщения (введите номера через запятую):"
        )
        source_input = input("> ")
        source_indexes = [
            int(i.strip()) for i in source_input.split(",") if i.strip().isdigit()
        ]

        selected_source_chats = (
            {}
        )  # Словарь для хранения информации о выбранных исходных чатах

        for idx in source_indexes:
            if idx in dialog_dict:
                chat_id = dialog_dict[idx]["id"]
                chat_name = dialog_dict[idx]["name"]
                source_chat_ids.append(chat_id)
                selected_source_chats[chat_id] = {
                    "index": idx,
                    "name": chat_name,
                }

                # Для каждого исходного чата выбираем чаты назначения
                print(
                    f"\nВыберите номера чатов, В которые нужно пересылать сообщения из {chat_name} (введите номера через запятую):"
                )
                dest_input = input("> ")
                dest_indexes = [
                    int(i.strip()) for i in dest_input.split(",") if i.strip().isdigit()
                ]

                dest_chat_ids = []
                for dest_idx in dest_indexes:
                    if dest_idx in dialog_dict:
                        dest_chat_id = dialog_dict[dest_idx]["id"]
                        # Проверяем, что не пересылаем в тот же самый чат
                        if dest_chat_id != chat_id:
                            dest_chat_ids.append(dest_chat_id)

                if dest_chat_ids:
                    forwarding_config[chat_id] = dest_chat_ids
                    print(
                        f"Пересылка из {chat_name} настроена в {len(dest_chat_ids)} чат(ов)"
                    )

        # Выводим итоговую конфигурацию
        print("\n=== Итоговая конфигурация пересылки ===")
        for source_id in forwarding_config:
            source_name = next(
                (
                    info["name"]
                    for i, info in dialog_dict.items()
                    if info["id"] == source_id
                ),
                f"Чат {source_id}",
            )
            dest_names = [
                next(
                    (
                        info["name"]
                        for i, info in dialog_dict.items()
                        if info["id"] == dest_id
                    ),
                    f"Чат {dest_id}",
                )
                for dest_id in forwarding_config[source_id]
            ]

            print(f"Из: {source_name} -> В: {', '.join(dest_names)}")

        # Сохраняем конфигурацию в файл
        config = {
            "SOURCE_CHAT_IDS": source_chat_ids,
            "FORWARDING_CONFIG": forwarding_config,
            "CHAT_INFO": chat_info,
        }

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        print(f"✅ Конфигурация сохранена в файл {CONFIG_FILE}")

        return True, forwarding_config, chat_info

    except Exception as e:
        print(f"⚠️ Ошибка при проверке папки: {str(e)}")
        return False, {}, {}
