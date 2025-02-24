# src/config.py

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(".env")


API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "0123456789abcdef0123456789abcdef")


@dataclass
class Config:
    api_id: int = API_ID
    api_hash: str = API_HASH

    bot_chats_config_file: str = "forward_config.json"


settings = Config()
