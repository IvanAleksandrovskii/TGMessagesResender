# src/message_handler.py

import asyncio

from pyrogram import Client
from pyrogram.errors import FloodWait, MessageIdInvalid
from pyrogram.types import Message


# Глобальный буфер для медиагрупп {media_group_id: {"messages": [...], "task": Task}}
media_groups_buffer = {}


async def fallback_copy(client: Client, message: Message, dest_chat_id, prefix: str):
    """
    Резервный метод копирования сообщения, если пересылка (forward) не удалась.
    Поддерживает одиночные сообщения и медиагруппы (copy_media_group).
    """
    try:
        # Если у сообщения есть media_group_id, пробуем копировать как альбом
        if message.media_group_id is not None:
            try:
                await client.copy_media_group(
                    chat_id=dest_chat_id,
                    from_chat_id=message.chat.id,
                    message_id=message.id,
                )
                print(f"[fallback_copy] Медиагруппа скопирована в {dest_chat_id}")
                return
            except Exception as e:
                print(f"[fallback_copy] Ошибка при copy_media_group: {e}")
                # Если copy_media_group не сработал, пробуем копировать по одному

        # Если это одиночное сообщение (или copy_media_group не получилось)
        if message.text:
            await message.copy(dest_chat_id, text=prefix + message.text)
        elif message.caption:
            await message.copy(dest_chat_id, caption=prefix + message.caption)
        else:
            await message.copy(dest_chat_id, caption=prefix if message.media else None)

        print(
            f"[fallback_copy] Сообщение(я) скопировано в {dest_chat_id} (резервный метод)."
        )

    except Exception as e:
        print(f"[fallback_copy] Не удалось скопировать сообщение в {dest_chat_id}: {e}")


async def process_media_group_with_delay(
    client: Client,
    mg_id: str,
    source_chat_id: int,
    chat_info: dict,
    prefix: str,
    delay: float = 1.0,
):
    """
    Отложенная пересылка медиагруппы: ждём небольшую паузу, затем отправляем
    весь альбом «одним блоком» (forward_messages) во все чаты из FORWARDING_CONFIG.
    """
    from .app import FORWARDING_CONFIG  # ваш глобальный конфиг

    await asyncio.sleep(delay)

    # Забираем накопленные сообщения из буфера
    group_data = media_groups_buffer.pop(mg_id, None)
    if not group_data:
        return  # Кто-то уже забрал или очистил

    messages = group_data["messages"]
    if not messages:
        return

    # Сортируем по ID, чтобы сохранить исходный порядок
    messages.sort(key=lambda m: m.id)

    # Все ID сообщений в группе
    message_ids = [m.id for m in messages]

    # Определяем, в какие чаты нужно пересылать
    if source_chat_id not in FORWARDING_CONFIG:
        # Не настроена пересылка
        return
    dest_chat_ids = set(FORWARDING_CONFIG[source_chat_id])

    # Пересылаем альбом в каждый чат-получатель
    for dest_chat_id in dest_chat_ids:
        try:
            await client.forward_messages(
                chat_id=dest_chat_id,
                from_chat_id=source_chat_id,
                message_ids=message_ids,
            )
            print(f"Медиагруппа {mg_id} переслана одним блоком в {dest_chat_id}.")
        except FloodWait as fw:
            print(
                f"FloodWait при отправке медиагруппы {mg_id} -> {dest_chat_id}: ждём {fw.value} секунд."
            )
            await asyncio.sleep(fw.value)
            try:
                await client.forward_messages(
                    chat_id=dest_chat_id,
                    from_chat_id=source_chat_id,
                    message_ids=message_ids,
                )
                print(
                    f"Медиагруппа {mg_id} переслана в {dest_chat_id} (после FloodWait)."
                )
            except Exception as e:
                print(
                    f"Ошибка после FloodWait (медиагруппа {mg_id} -> {dest_chat_id}): {e}, резервный метод."
                )
                # Берём «якорное» сообщение, чтобы fallback_copy понимать что копировать
                anchor_message = messages[0]
                await fallback_copy(client, anchor_message, dest_chat_id, prefix)
        except MessageIdInvalid:
            print(
                f"[MediaGroup] MESSAGE_ID_INVALID для {mg_id}, сообщение удалено или недоступно."
            )
        except Exception as e:
            print(
                f"Ошибка при пересылке медиагруппы {mg_id} -> {dest_chat_id}: {e}, резервный метод."
            )
            anchor_message = messages[0]
            await fallback_copy(client, anchor_message, dest_chat_id, prefix)


async def forward_message(client: Client, message: Message, chat_info=None):
    """
    Обработчик входящих сообщений с поддержкой:
    - медиагрупп (отправка альбомом),
    - FloodWait,
    - fallback-копирования (если forward не доступен),
    - множественных чатов назначения из FORWARDING_CONFIG.
    """
    from .app import FORWARDING_CONFIG  # Ваш глобальный конфиг с пересылками

    source_chat_id = message.chat.id
    print(f"Получено сообщение из чата {source_chat_id}")

    # Игнорируем собственные сообщения бота (если бот работает от аккаунта, а не Bot API)
    if message.from_user and message.from_user.id == client.me.id:
        print(f"Сообщение в {source_chat_id} проигнорировано (собственное сообщение).")
        return

    # Проверяем, настроена ли пересылка из этого чата
    if source_chat_id not in FORWARDING_CONFIG:
        return

    # Для fallback-копирования формируем префикс
    source_chat_info = ""
    if chat_info and source_chat_id in chat_info:
        # например, chat_info[123123] = {"username": "some_channel", "type": "channel"}
        if "username" in chat_info[source_chat_id]:
            source_chat_info = f"@{chat_info[source_chat_id]['username']}"
        elif "type" in chat_info[source_chat_id]:
            source_chat_info = f"{chat_info[source_chat_id]['type']} {source_chat_id}"

    if not source_chat_info:
        source_chat_info = f"Чат {source_chat_id}"

    prefix = f"📨 Переслано из: {source_chat_info}\n\n"

    # Если у сообщения есть media_group_id — обрабатываем как часть альбома
    if message.media_group_id:
        mg_id = message.media_group_id

        # Если в буфере ещё нет этой группы - создаём
        if mg_id not in media_groups_buffer:
            media_groups_buffer[mg_id] = {"messages": [], "task": None}

        media_groups_buffer[mg_id]["messages"].append(message)

        # Если нет запущенной задачи на отправку альбома, создаём её
        if media_groups_buffer[mg_id]["task"] is None:
            media_groups_buffer[mg_id]["task"] = asyncio.create_task(
                process_media_group_with_delay(
                    client=client,
                    mg_id=mg_id,
                    source_chat_id=source_chat_id,
                    chat_info=chat_info,
                    prefix=prefix,
                )
            )

        # Возвращаемся сразу, т.к. отправка будет через задачу
        return

    # Иначе — одиночное сообщение (без media_group_id). Пересылаем сразу в каждый чат
    dest_chat_ids = set(FORWARDING_CONFIG[source_chat_id])
    for dest_chat_id in dest_chat_ids:
        try:
            await message.forward(dest_chat_id)
            print(f"Сообщение из {source_chat_id} переслано в {dest_chat_id}")
        except FloodWait as fw:
            print(f"FloodWait: ожидание {fw.value} секунд (одиночное сообщение)")
            await asyncio.sleep(fw.value)
            try:
                await message.forward(dest_chat_id)
                print(
                    f"Сообщение из {source_chat_id} переслано в {dest_chat_id} (после FloodWait)"
                )
            except Exception as e:
                print(
                    f"Ошибка после FloodWait (одиночное сообщение): {e}, резервный метод"
                )
                await fallback_copy(client, message, dest_chat_id, prefix)
        except MessageIdInvalid:
            print(f"[Single] MESSAGE_ID_INVALID для сообщения {message.id}, удалено?")
        except Exception as e:
            print(
                f"Ошибка при пересылке одиночного сообщения в {dest_chat_id}: {e}, резервный метод"
            )
            await fallback_copy(client, message, dest_chat_id, prefix)


def create_handler(chat_info_data):
    """
    Создает функцию-обработчик сообщений с доступом к информации о чатах
    """

    async def handler(client, message):
        await forward_message(client, message, chat_info_data)

    return handler
