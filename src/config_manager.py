# src/config_manager.py

import json

from .config import settings


# Файл с конфигурацией пересылки бота
CONFIG_FILE = settings.bot_chats_config_file


def load_saved_config():
    """
    Загружает сохраненную конфигурацию из файла, включая информацию о чатах
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            SOURCE_CHAT_IDS = config.get("SOURCE_CHAT_IDS", [])
            FORWARDING_CONFIG = config.get("FORWARDING_CONFIG", {})

            # Конвертируем строковые ключи обратно в int, так как JSON сохраняет все ключи как строки
            FORWARDING_CONFIG = {int(k): v for k, v in FORWARDING_CONFIG.items()}

            # Загружаем информацию о чатах, если она есть
            chat_info = config.get("CHAT_INFO", {})
            # Конвертируем строковые ключи обратно в int
            chat_info = {int(k): v for k, v in chat_info.items()} if chat_info else {}

        print("Загружена сохраненная конфигурация:")
        for source_id in FORWARDING_CONFIG:
            print(f"Из чата {source_id} в чаты: {FORWARDING_CONFIG[source_id]}")
        return True, SOURCE_CHAT_IDS, FORWARDING_CONFIG, chat_info
    except (FileNotFoundError, json.JSONDecodeError):
        print("Сохраненная конфигурация не найдена или повреждена")
        return False, [], {}, {}


def save_config(SOURCE_CHAT_IDS, FORWARDING_CONFIG, chat_info=None):
    """
    Сохраняет конфигурацию в файл
    """
    config = {
        "SOURCE_CHAT_IDS": SOURCE_CHAT_IDS,
        "FORWARDING_CONFIG": FORWARDING_CONFIG,
    }

    if chat_info:
        config["CHAT_INFO"] = chat_info

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    print(f"Конфигурация сохранена в файл {CONFIG_FILE}")
