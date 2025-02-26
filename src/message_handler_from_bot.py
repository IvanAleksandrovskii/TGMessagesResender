# src/message_handler_from_bot.py

import asyncio

from pyrogram import Client
from pyrogram.errors import FloodWait, MessageIdInvalid
from pyrogram.types import Message
from pyrogram.enums import ChatType


# Храним тут ID уже "отклонённых" медиагрупп, чтобы не отвечать несколько раз
responded_media_groups = set()


async def copy_message_handler(client: Client, message: Message, chat_info=None):
    """
    Обработчик входящих сообщений с поддержкой:
      - только одиночного медиа (или без медиа).
      - FloodWait
      - множественных чатов назначения из FORWARDING_CONFIG.

    Если пользователь (в личном чате) пытается отправить альбом (media_group_id),
    бот отвечает «Можно прикрепить не более одного файла!» и НЕ пересылает
    (причём только 1 раз на всю группу).

    Если сообщение из группы/канала содержит несколько медиа, бот просто игнорирует.
    Если сообщение из группы/канала одиночное — пересылаем без предупреждений.
    """
    from .app import FORWARDING_CONFIG

    source_chat_id = message.chat.id
    chat_type = message.chat.type  # Будет ChatType.PRIVATE, ChatType.GROUP и т.п.
    print(f"Получено сообщение из чата {source_chat_id} (тип: {chat_type})")

    # Игнорируем собственные сообщения бота (если бот работает от аккаунта, а не Bot API)
    if message.from_user and message.from_user.id == client.me.id:
        print(f"Сообщение в {source_chat_id} проигнорировано (собственное).")
        return

    # Проверяем, настроена ли пересылка из этого чата
    if source_chat_id not in FORWARDING_CONFIG:
        return

    # Проверяем на медиагруппу - обрабатываем в зависимости от типа чата
    if message.media_group_id:
        # Если это личный чат:
        if chat_type == ChatType.PRIVATE:
            if message.media_group_id not in responded_media_groups:
                responded_media_groups.add(message.media_group_id)
                # Отправляем предупреждение
                await client.send_message(
                    chat_id=source_chat_id,
                    text="Можно прикрепить не более одного файла!",
                    reply_to_message_id=message.id,
                )
                print(
                    f"Отклонена медиагруппа {message.media_group_id} "
                    f"из личного чата {source_chat_id}."
                )
            else:
                print(
                    f"Повторный альбом {message.media_group_id} "
                    f"из личного чата {source_chat_id} — игнорируем."
                )
        else:
            # Для групп/каналов просто игнорируем медиагруппы
            print(
                f"Медиагруппа {message.media_group_id} из {chat_type} "
                f"(id={source_chat_id}) — игнорируем."
            )
        return

    # Если у сообщения НЕТ media_group_id (одиночное сообщение) — пересылаем
    dest_chat_ids = FORWARDING_CONFIG[source_chat_id]
    await forward_single_message(client, message, dest_chat_ids)


async def forward_single_message(client: Client, message: Message, dest_chat_ids):
    """Пересылка (copy_message) одного сообщения в указанные чаты с обработкой FloodWait."""
    source_chat_id = message.chat.id
    for dest_chat_id in dest_chat_ids:
        try:
            await client.copy_message(
                chat_id=dest_chat_id,
                from_chat_id=source_chat_id,
                message_id=message.id,
            )
            print(
                f"Сообщение {message.id} из {source_chat_id} скопировано в {dest_chat_id}"
            )
        except FloodWait as fw:
            print(
                f"FloodWait: ожидание {fw.value}с при копировании одиночного сообщения {message.id}"
            )
            await asyncio.sleep(fw.value)
            try:
                await client.copy_message(
                    chat_id=dest_chat_id,
                    from_chat_id=source_chat_id,
                    message_id=message.id,
                )
                print(
                    f"Сообщение {message.id} из {source_chat_id} "
                    f"скопировано в {dest_chat_id} (после FloodWait)"
                )
            except MessageIdInvalid:
                print(
                    f"[Single] MESSAGE_ID_INVALID для сообщения {message.id}, возможно удалено?"
                )
            except Exception as e:
                print(f"Ошибка после FloodWait (одиночное сообщение): {e}")


def create_copy_handler(chat_info_data):
    """
    Создает функцию-обработчик сообщений с доступом к информации о чатах
    """

    async def handler(client, message):
        await copy_message_handler(client, message, chat_info_data)

    return handler
