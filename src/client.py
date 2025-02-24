from pyrogram import Client
from .config import settings


# Создаем экземпляр клиента Pyrogram
app = Client(
    "message_forwarder_bot",
    api_id=settings.api_id,
    api_hash=settings.api_hash,
    bot_token=None,  # Не используем токен бота для логина по номеру телефона
)
