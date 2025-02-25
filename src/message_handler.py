# src/message_handler.py

import asyncio

from pyrogram.errors import FloodWait, MessageIdInvalid


async def forward_message(client, message, chat_info=None):
    """
    Обрабатывает входящие сообщения и пересылает их в указанные чаты.
    Приоритетно использует forward вместо copy для обычных сообщений.
    Сохраняет медиагруппы и прикрепленные файлы в исходном виде.
    Также обрабатывает FloodWait, чтобы не отправлять сообщения слишком быстро.
    """
    # Получаем глобальные переменные для конфигурации
    from .app import FORWARDING_CONFIG

    # Получаем ID чата, из которого пришло сообщение
    source_chat_id = message.chat.id

    print(f"Получено сообщение из чата {source_chat_id}: {message.text}")

    # Игнорируем собственные сообщения (если бот запущен под тем же аккаунтом)
    if message.from_user and message.from_user.id == client.me.id:
        print(f"Сообщение в {source_chat_id} проигнорировано (собственное сообщение).")
        return

    # Проверяем, настроена ли пересылка из этого чата
    if source_chat_id not in FORWARDING_CONFIG:
        return

    # Получаем информацию об исходном чате для префикса
    source_chat_info = ""
    source_chat_link = ""

    if chat_info and source_chat_id in chat_info:
        if "username" in chat_info[source_chat_id]:
            source_chat_link = f"https://t.me/{chat_info[source_chat_id]['username']}"
            source_chat_info = f"@{chat_info[source_chat_id]['username']}"
        if "type" in chat_info[source_chat_id]:
            chat_type = chat_info[source_chat_id]["type"]
            # Дополняем информацию типом чата
            if not source_chat_info:
                source_chat_info = f"{chat_type} {source_chat_id}"
            else:
                source_chat_info += f" ({chat_type})"

    if not source_chat_info:
        # Если нет информации в chat_info, используем простой идентификатор
        source_chat_info = f"Чат {source_chat_id}"

    # Префикс для случаев, когда нужно скопировать сообщение
    prefix = f"📨 Переслано из: {source_chat_info}"
    if source_chat_link:
        prefix += f" [{source_chat_link}]"
    prefix += "\n\n"

    # Проверяем, является ли сообщение частью медиагруппы
    if message.media_group_id is not None:
        # Инициализируем отслеживание медиагрупп, если это не было сделано
        if not hasattr(client, "_processed_media_groups"):
            client._processed_media_groups = {}

        # Если этой медиагруппы нет в словаре - добавляем с временной меткой
        if message.media_group_id not in client._processed_media_groups:
            # Добавляем ID сообщения, которое будет использоваться как якорь
            client._processed_media_groups[message.media_group_id] = {
                "timestamp": asyncio.get_event_loop().time(),
                "anchor_message_id": message.id,
                "processed_chats": set(),  # Множество чатов, в которые уже отправили
            }

            # Очистка старых медиагрупп (старше 10 минут)
            current_time = asyncio.get_event_loop().time()
            for mg_id in list(client._processed_media_groups.keys()):
                if (
                    current_time - client._processed_media_groups[mg_id]["timestamp"]
                    > 600
                ):  # 10 минут
                    del client._processed_media_groups[mg_id]

            print(f"Новая медиагруппа {message.media_group_id}, якорь: {message.id}")
        else:
            # Если эта медиагруппа уже обрабатывается, просто возвращаемся
            print(
                f"Пропуск повторного сообщения из медиагруппы {message.media_group_id}"
            )
            return

    destination_chat_ids = FORWARDING_CONFIG[source_chat_id]
    # Используем сет для уникальности чатов назначения
    unique_dest_ids = set(destination_chat_ids)

    # Обрабатываем пересылку для каждого чата назначения
    for dest_chat_id in unique_dest_ids:
        # Если это медиагруппа и мы уже отправили её в этот чат - пропускаем
        if (
            message.media_group_id is not None
            and dest_chat_id
            in client._processed_media_groups[message.media_group_id]["processed_chats"]
        ):
            print(
                f"Медиагруппа {message.media_group_id} уже отправлена в чат {dest_chat_id}, пропускаем"
            )
            continue

        # Создаем список возможных вариантов доступа к чату - сначала предпочтительный
        access_methods = []

        # Определяем лучший способ доступа к чату (username или ID)
        if (
            chat_info
            and dest_chat_id in chat_info
            and "username" in chat_info[dest_chat_id]
        ):
            username = "@" + chat_info[dest_chat_id]["username"]
            access_methods = [
                username,
                dest_chat_id,
            ]  # Сначала пробуем username, потом ID
            print(f"Используем username {username} для доступа к чату {dest_chat_id}")
        else:
            access_methods = [dest_chat_id]  # Только ID

        # Пробуем разные методы доступа, до первого успешного
        success = False
        for target_chat in access_methods:
            try:
                # Обработка медиагруппы
                if message.media_group_id is not None:
                    anchor_id = client._processed_media_groups[message.media_group_id][
                        "anchor_message_id"
                    ]

                    # Для медиагрупп всегда используем copy_media_group
                    await client.copy_media_group(
                        chat_id=target_chat,
                        from_chat_id=source_chat_id,
                        message_id=anchor_id,
                    )

                    # Отмечаем, что в этот чат медиагруппа уже отправлена
                    client._processed_media_groups[message.media_group_id][
                        "processed_chats"
                    ].add(dest_chat_id)

                    print(
                        f"Медиагруппа из {source_chat_id} скопирована в {dest_chat_id}"
                    )
                else:
                    # Для обычных сообщений сначала пробуем forward (пересылку)
                    try:
                        await message.forward(target_chat)
                        print(
                            f"Сообщение из {source_chat_id} переслано в {dest_chat_id}"
                        )
                        success = True
                        break
                    except Exception as fwd_err:
                        print(
                            f"Ошибка при пересылке в {dest_chat_id}: {fwd_err}, пробуем копирование"
                        )

                        # Если пересылка не сработала - копируем с префиксом
                        if message.text:
                            # Для текстовых сообщений добавляем префикс
                            await message.copy(
                                target_chat,
                                caption=prefix + (message.text or ""),
                                text=prefix + (message.text or ""),
                            )
                        elif message.caption:
                            # Для медиафайлов с подписью добавляем префикс к подписи
                            await message.copy(
                                target_chat, caption=prefix + message.caption
                            )
                        else:
                            # Для остальных просто копируем
                            await message.copy(
                                target_chat, caption=prefix if message.media else None
                            )

                        print(
                            f"Сообщение из {source_chat_id} скопировано в {dest_chat_id} с префиксом"
                        )

                success = True
                break  # Прерываем цикл после успешной пересылки
            except MessageIdInvalid:
                print(
                    f"Ошибка MESSAGE_ID_INVALID: сообщение удалено, пропускаем {source_chat_id}"
                )
                success = True  # Считаем это успехом, т.к. дальнейшие попытки не нужны
                break
            except FloodWait as fw:
                print(f"FloodWait: нужно подождать {fw.value} секунд")
                await asyncio.sleep(fw.value)
                # После ожидания повторная попытка с тем же методом
                try:
                    if message.media_group_id is not None:
                        anchor_id = client._processed_media_groups[
                            message.media_group_id
                        ]["anchor_message_id"]
                        await client.copy_media_group(
                            chat_id=target_chat,
                            from_chat_id=source_chat_id,
                            message_id=anchor_id,
                        )
                        client._processed_media_groups[message.media_group_id][
                            "processed_chats"
                        ].add(dest_chat_id)
                        print(
                            f"Медиагруппа из {source_chat_id} скопирована в {dest_chat_id} (после FloodWait)"
                        )
                    else:
                        # После FloodWait сначала пробуем пересылку
                        try:
                            await message.forward(target_chat)
                            print(
                                f"Сообщение из {source_chat_id} переслано в {dest_chat_id} (после FloodWait)"
                            )
                        except Exception as fwd_err:
                            print(
                                f"Ошибка при пересылке после FloodWait: {fwd_err}, пробуем копирование"
                            )

                            # Если пересылка не сработала - копируем с префиксом
                            if message.text:
                                await message.copy(
                                    target_chat, text=prefix + message.text
                                )
                            elif message.caption:
                                await message.copy(
                                    target_chat, caption=prefix + message.caption
                                )
                            else:
                                await message.copy(
                                    target_chat,
                                    caption=prefix if message.media else None,
                                )

                            print(
                                f"Сообщение из {source_chat_id} скопировано в {dest_chat_id} с префиксом (после FloodWait)"
                            )

                    success = True
                    break
                except MessageIdInvalid:
                    print(
                        f"Ошибка MESSAGE_ID_INVALID после FloodWait: сообщение удалено"
                    )
                    success = True  # Считаем это успехом
                    break
                except Exception as e:
                    print(
                        f"Ошибка при копировании в {dest_chat_id} через {target_chat}: {e}"
                    )
                    # Продолжаем со следующим методом
            except Exception as e:
                print(
                    f"Ошибка при копировании в {dest_chat_id} через {target_chat}: {e}"
                )
                # Продолжаем со следующим методом

        # Если все методы не сработали, пробуем найти чат через диалоги (только если не удалось переслать)
        if not success:
            print(f"Пробуем найти чат {dest_chat_id} в списке диалогов")
            try:
                found = False
                async for dialog in client.get_dialogs():
                    if dialog.chat.id == dest_chat_id:
                        print(f"Чат {dest_chat_id} найден в диалогах")
                        found = True
                        try:
                            if message.media_group_id is not None:
                                anchor_id = client._processed_media_groups[
                                    message.media_group_id
                                ]["anchor_message_id"]
                                await client.copy_media_group(
                                    chat_id=dialog.chat.id,
                                    from_chat_id=source_chat_id,
                                    message_id=anchor_id,
                                )
                                client._processed_media_groups[message.media_group_id][
                                    "processed_chats"
                                ].add(dest_chat_id)
                                print(
                                    f"Медиагруппа из {source_chat_id} скопирована в {dest_chat_id} (через диалоги)"
                                )
                            else:
                                # Через диалоги также сначала пробуем пересылку
                                try:
                                    await message.forward(dialog.chat.id)
                                    print(
                                        f"Сообщение из {source_chat_id} переслано в {dest_chat_id} (через диалоги)"
                                    )
                                except Exception as fwd_err:
                                    print(
                                        f"Ошибка при пересылке через диалоги: {fwd_err}, пробуем копирование"
                                    )

                                    # Если пересылка не сработала - копируем с префиксом
                                    if message.text:
                                        await message.copy(
                                            dialog.chat.id, text=prefix + message.text
                                        )
                                    elif message.caption:
                                        await message.copy(
                                            dialog.chat.id,
                                            caption=prefix + message.caption,
                                        )
                                    else:
                                        await message.copy(
                                            dialog.chat.id,
                                            caption=prefix if message.media else None,
                                        )
                                    print(
                                        f"Сообщение из {source_chat_id} скопировано в {dest_chat_id} с префиксом (через диалоги)"
                                    )

                            break
                        except MessageIdInvalid:
                            print(
                                f"Ошибка MESSAGE_ID_INVALID: сообщение удалено (при попытке через диалоги)"
                            )
                            break
                        except Exception as e:
                            print(f"Ошибка при копировании через диалоги: {e}")

                if not found:
                    print(f"Чат {dest_chat_id} не найден в диалогах")
            except Exception as e:
                print(f"Ошибка при поиске в диалогах: {e}")


def create_handler(chat_info_data):
    """
    Создает функцию-обработчик сообщений с доступом к информации о чатах
    """

    async def handler(client, message):
        await forward_message(client, message, chat_info_data)

    return handler
