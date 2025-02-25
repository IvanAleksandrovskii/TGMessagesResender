# src/config.py

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(".env")


API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "0123456789abcdef0123456789abcdef")

CHATS_FLODER_NAME = "Forward Bot"


@dataclass
class Config:
    api_id: int = API_ID
    api_hash: str = API_HASH

    bot_chats_config_file: str = "forward_config.json"

    chats_folder_name: str = CHATS_FLODER_NAME

    # Новая настройка: использовать интерактивный режим выбора чатов из папки
    interactive_folder_setup: bool = True


settings = Config()
