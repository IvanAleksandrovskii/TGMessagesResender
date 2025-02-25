# src/config.py

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(".env")


API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "0123456789abcdef0123456789abcdef")
CHATS_FLODER_NAME = "Forward Bot"
BOT_CHATS_CONFIG_FILE = "forward_config.json"


@dataclass
class Config:
    # Telegram API sensitive data
    api_id: int = API_ID
    api_hash: str = API_HASH
    # Имя файла для хранения конфигурации пересылки
    bot_chats_config_file: str = BOT_CHATS_CONFIG_FILE
    # Имя папки для хранения чатов для пересылки
    chats_folder_name: str = CHATS_FLODER_NAME
    # Использовать интерактивный режим выбора чатов из папки
    interactive_folder_setup: bool = True


# Глобальное объявление настроек
settings = Config()
