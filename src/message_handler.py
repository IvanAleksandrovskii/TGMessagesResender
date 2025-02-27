# src/message_handler.py

import asyncio
import random

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait,
    MessageIdInvalid,
    ChatWriteForbidden,
    UserDeactivated,
    PeerIdInvalid,
)

# from pyrogram.enums import ChatType


# Храним тут ID уже "отклонённых" медиагрупп, чтобы не отвечать несколько раз
responded_media_groups = set()


async def copy_message_handler(client: Client, message: Message, chat_info=None):
    """
    Обработчик входящих сообщений с поддержкой:
      - только одиночного медиа (или без медиа).
      - FloodWait
      - множественных чатов назначения из FORWARDING_CONFIG.

    Если пользователь пытается отправить альбом (media_group_id),
    бот отвечает «Можно прикрепить не более одного файла!» и НЕ пересылает
    (причём только 1 раз на всю группу).

    Если сообщение из группы/канала одиночное — пересылаем без предупреждений.
    """
    from .app import FORWARDING_CONFIG

    source_chat_id = message.chat.id
    chat_type = message.chat.type
    print(f"Сообщение в {source_chat_id} (тип: {chat_type}) получено")

    # Игнорируем собственные сообщения бота (если бот работает от аккаунта, а не Bot API)
    if message.from_user and message.from_user.id == client.me.id:
        print(f"Сообщение в {source_chat_id} игнорируется (собственное сообщение).")
        return

    # Проверяем, настроена ли пересылка из этого чата
    if source_chat_id not in FORWARDING_CONFIG:
        return

    # Проверяем, есть ли в сообщении media_group_id
    if message.media_group_id:
        if message.media_group_id not in responded_media_groups:
            responded_media_groups.add(message.media_group_id)
            # Отправляем предупреждение
            try:
                await client.send_message(
                    chat_id=source_chat_id,
                    text="Можно прикрепить не более одного файла!",
                    reply_to_message_id=message.id,
                )
                print(
                    f"Медиагруппа {message.media_group_id} "
                    f"из чата {source_chat_id} отклонена."
                )
            except Exception as e:
                print(f"Ошибка при отправке сообщения отклонения: {e}")
        else:
            print(
                f"Повторная медиагруппа {message.media_group_id} "
                f"из чата {source_chat_id} — игнорируется."
            )
        return

    # Если сообщение не содержит media_group_id (одиночное сообщение)
    dest_chat_ids = FORWARDING_CONFIG[source_chat_id]

    # Отправляем предварительное уведомление о получении сообщения
    max_estimated_time = (
        (len(dest_chat_ids) - 1) * 3 if len(dest_chat_ids) > 1 else 0
    )  # 3 минуты максимум на каждый чат после первого

    try:
        await client.send_message(
            chat_id=source_chat_id,
            text=f"✅ Сообщение получено и будет переслано в чатах: {len(dest_chat_ids)} шт.\n\n"
            f"⏱️ Максимальное расчетное время отправки: {max_estimated_time} минут.\n\n"
            f"ℹ️ С большой вероятностью пересылка будет выполнена значительно быстрее. "
            f"Задержки между отправками добавлены в целях безопасности аккаунта, "
            f"чтобы избежать подозрений в спам-активность.",
            reply_to_message_id=message.id,
        )
    except Exception as e:
        print(f"Ошибка при отправке предварительного уведомления: {e}")

    # Пересылаем сообщение
    result = await forward_single_message(client, message, dest_chat_ids)

    # Отправляем уведомление о статусе пересылки
    await send_forwarding_status(client, message, result)


async def forward_single_message(client: Client, message: Message, dest_chat_ids):
    """Пересылка (copy_message) одного сообщения в указанные чаты с обработкой FloodWait."""
    source_chat_id = message.chat.id

    # Следим за успешными и неудачными пересылками
    results = {"success": [], "errors": {}}

    for dest_chat_id in dest_chat_ids:
        try:
            # Добавляем случайный отсрочку от 1 до 3 минут перед отправкой
            if len(results["success"]) > 0:  # Не отсрочивать до первого сообщения
                delay_seconds = random.randint(60, 180)
                print(
                    f"Ожидание {delay_seconds} секунд перед пересылкой в {dest_chat_id}..."
                )
                await asyncio.sleep(delay_seconds)

            # Пытаемся переслать сообщение
            await client.copy_message(
                chat_id=dest_chat_id,
                from_chat_id=source_chat_id,
                message_id=message.id,
            )
            print(
                f"Сообщение {message.id} из {source_chat_id} переслано в {dest_chat_id}"
            )
            results["success"].append(dest_chat_id)

        except FloodWait as fw:
            print(
                f"FloodWait: ожидание {fw.value}s при пересылке одного сообщения {message.id}"
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
                    f"переслано в {dest_chat_id} (после FloodWait)"
                )
                results["success"].append(dest_chat_id)
            except Exception as e:
                print(f"Ошибка после FloodWait (одиночное сообщение): {e}")
                results["errors"][dest_chat_id] = str(e)
        except (ChatWriteForbidden, UserDeactivated, PeerIdInvalid) as e:
            # Не можем отправить сообщение в этот чат
            print(f"Ошибка доступа к чату {dest_chat_id}: {e}")
            results["errors"][dest_chat_id] = f"Ошибка доступа: {str(e)}"
        except MessageIdInvalid:
            # Сообщение удалено или недоступно
            print(
                f"[Single] MESSAGE_ID_INVALID для сообщения {message.id}, возможно удалено?"
            )
            results["errors"][dest_chat_id] = "Message became invalid"
        except Exception as e:
            print(f"Ошибка пересылки в {dest_chat_id}: {e}")
            results["errors"][dest_chat_id] = str(e)

    return results


async def send_forwarding_status(client: Client, original_message: Message, result):
    """Отправляет уведомление о статусе пересылки сообщения отправителю."""
    source_chat_id = original_message.chat.id

    if not result["errors"]:
        # Все сообщения пересланы успешно
        status_message = (
            f"✅ Сообщение успешно переслано в {len(result['success'])} чатов."
        )
    else:
        # Некоторые или все пересылки не удалось
        status_message = (
            f"⚠️ Статус пересылки сообщений:\n"
            f"✅ Сообщение успешно переслано в {len(result['success'])} чатов.\n"
            f"❌ Не удалось переслать сообщение в {len(result['errors'])} чатов:\n"
        )

        for chat_id, error in result["errors"].items():
            status_message += f"- Chat {chat_id}: {error}\n"

        if result["errors"]:
            status_message += "\nПрочитайте ошибку выше. Если их ошибки не ясна конкретная проблема, эти чаты могут быть заблокированы или удалены, бот не может получить доступ."

    try:
        await client.send_message(
            chat_id=source_chat_id,
            text=status_message,
            reply_to_message_id=original_message.id,
        )
    except Exception as e:
        print(f"Ошибка при отправке уведомления о статусе пересылки: {e}")


def create_copy_handler(chat_info_data):
    """
    Создает функцию-обработчик сообщений с доступом к информации о чатах
    """

    async def handler(client, message):
        await copy_message_handler(client, message, chat_info_data)

    return handler
