# src/message_handler.py

import asyncio

from pyrogram import Client
from pyrogram.errors import FloodWait, MessageIdInvalid
from pyrogram.types import Message


# Глобальный буфер для медиагрупп {media_group_id: {"messages": [...], "task": Task}}
media_groups_buffer = {}


async def copy_message_handler(client: Client, message: Message, chat_info=None):
    """
    Обработчик входящих сообщений с поддержкой:
    - медиагрупп (отправка альбомом),
    - FloodWait,
    - множественных чатов назначения из FORWARDING_CONFIG.
    Использует метод copy_message, чтобы отправлять сообщения от имени бота.
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

    # Формируем префикс для сообщения
    source_chat_info = ""
    if chat_info and source_chat_id in chat_info:
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
                process_media_group_with_copy(
                    client=client,
                    mg_id=mg_id,
                    source_chat_id=source_chat_id,
                    chat_info=chat_info,
                    prefix=prefix,
                )
            )

        # Возвращаемся сразу, т.к. отправка будет через задачу
        return

    # Иначе — одиночное сообщение (без media_group_id). Копируем сразу в каждый чат
    dest_chat_ids = set(FORWARDING_CONFIG[source_chat_id])

    for dest_chat_id in dest_chat_ids:
        try:
            # Определяем, есть ли текст или подпись, и добавляем к ним префикс
            if message.text:
                # Для текстовых сообщений все равно используем caption
                await client.copy_message(
                    chat_id=dest_chat_id,
                    from_chat_id=source_chat_id,
                    message_id=message.id,
                    caption=prefix + message.text,
                )
            elif message.caption:
                await client.copy_message(
                    chat_id=dest_chat_id,
                    from_chat_id=source_chat_id,
                    message_id=message.id,
                    caption=prefix + message.caption,
                )
            else:
                # Если нет ни текста, ни подписи, просто копируем с префиксом в подписи
                await client.copy_message(
                    chat_id=dest_chat_id,
                    from_chat_id=source_chat_id,
                    message_id=message.id,
                    caption=prefix if message.media else None,
                )
            print(f"Сообщение из {source_chat_id} скопировано в {dest_chat_id}")
        except FloodWait as fw:
            print(f"FloodWait: ожидание {fw.value} секунд (одиночное сообщение)")
            await asyncio.sleep(fw.value)
            try:
                if message.text:
                    await client.copy_message(
                        chat_id=dest_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=message.id,
                        caption=prefix + message.text,
                    )
                elif message.caption:
                    await client.copy_message(
                        chat_id=dest_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=message.id,
                        caption=prefix + message.caption,
                    )
                else:
                    await client.copy_message(
                        chat_id=dest_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=message.id,
                        caption=prefix if message.media else None,
                    )
                print(
                    f"Сообщение из {source_chat_id} скопировано в {dest_chat_id} (после FloodWait)"
                )

            except MessageIdInvalid:
                print(
                    f"[Single] MESSAGE_ID_INVALID для сообщения {message.id}, удалено?"
                )
            except Exception as e:
                print(f"Ошибка после FloodWait (одиночное сообщение): {e}")


async def process_media_group_with_copy(
    client: Client,
    mg_id: str,
    source_chat_id: int,
    chat_info: dict,
    prefix: str,
    delay: float = 1.0,
):
    """
    Отложенная копия медиагруппы: ждём небольшую паузу, затем копируем
    каждое сообщение альбома во все чаты из FORWARDING_CONFIG.
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

    # Определяем, в какие чаты нужно пересылать
    if source_chat_id not in FORWARDING_CONFIG:
        # Не настроена пересылка
        return
    dest_chat_ids = set(FORWARDING_CONFIG[source_chat_id])

    # Пытаемся копировать как media_group, если это возможно
    for dest_chat_id in dest_chat_ids:
        try:
            # Используем первое сообщение из группы, Pyrogram найдет остальные автоматически
            # метод copy_media_group принимает только один message_id
            await client.copy_media_group(
                chat_id=dest_chat_id,
                from_chat_id=source_chat_id,
                message_id=messages[0].id,
            )
            print(f"Медиагруппа {mg_id} скопирована одним блоком в {dest_chat_id}.")
        except FloodWait as fw:
            print(
                f"FloodWait при копировании медиагруппы {mg_id} -> {dest_chat_id}: ждём {fw.value} секунд."
            )
            await asyncio.sleep(fw.value)
            try:
                await client.copy_media_group(
                    chat_id=dest_chat_id,
                    from_chat_id=source_chat_id,
                    message_id=messages[0].id,
                )
                print(
                    f"Медиагруппа {mg_id} скопирована в {dest_chat_id} (после FloodWait)."
                )
            except Exception as e:
                print(
                    f"Ошибка после FloodWait для медиагруппы {mg_id}: {e}, копируем по одному"
                )
                # Если copy_media_group не работает, копируем по одному
                await copy_messages_one_by_one(client, messages, dest_chat_id, prefix)
        except AttributeError:
            # Если метод copy_media_group отсутствует, копируем по одному
            print(f"Метод copy_media_group не найден, копируем по одному")
            await copy_messages_one_by_one(client, messages, dest_chat_id, prefix)
        except Exception as e:
            print(
                f"Ошибка при копировании медиагруппы {mg_id} -> {dest_chat_id}: {e}, копируем по одному"
            )
            await copy_messages_one_by_one(client, messages, dest_chat_id, prefix)


async def copy_messages_one_by_one(client, messages, dest_chat_id, prefix):
    """
    Копирует сообщения из медиагруппы по одному, если copy_media_group не сработал
    """
    for i, message in enumerate(messages):
        try:
            # Для первого сообщения в группе добавляем префикс
            current_prefix = prefix if i == 0 else ""

            if message.caption:
                await client.copy_message(
                    chat_id=dest_chat_id,
                    from_chat_id=message.chat.id,
                    message_id=message.id,
                    caption=current_prefix + (message.caption or ""),
                )
            else:
                await client.copy_message(
                    chat_id=dest_chat_id,
                    from_chat_id=message.chat.id,
                    message_id=message.id,
                    caption=current_prefix if message.media else None,
                )

            # Небольшая пауза между сообщениями
            await asyncio.sleep(0.5)
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            try:
                if message.caption:
                    await client.copy_message(
                        chat_id=dest_chat_id,
                        from_chat_id=message.chat.id,
                        message_id=message.id,
                        caption=current_prefix + (message.caption or ""),
                    )
                else:
                    await client.copy_message(
                        chat_id=dest_chat_id,
                        from_chat_id=message.chat.id,
                        message_id=message.id,
                        caption=current_prefix if message.media else None,
                    )
            except Exception as e:
                print(
                    f"Ошибка при копировании сообщения {message.id} из медиагруппы: {e}"
                )
        except Exception as e:
            print(f"Ошибка при копировании сообщения {message.id} из медиагруппы: {e}")

    print(f"Медиагруппа скопирована по одному сообщению в {dest_chat_id}")


def create_copy_handler(chat_info_data):
    """
    Создает функцию-обработчик сообщений с доступом к информации о чатах
    """

    async def handler(client, message):
        await copy_message_handler(client, message, chat_info_data)

    return handler
