# src/app.py

import asyncio
import json
import traceback

from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, MessageIdInvalid

from .client import app
from .config import settings
from .check_folder import check_folder_existence


# Файл с конфигурацией пересылки бота
CONFIG_FILE = settings.bot_chats_config_file

# Глобальные переменные для хранения настроек пересылки
SOURCE_CHAT_IDS = []
FORWARDING_CONFIG = {}


# Функция для интерактивного выбора чатов
async def interactive_setup():
    """
    Интерактивно настраивает чаты для пересылки
    """
    global SOURCE_CHAT_IDS, FORWARDING_CONFIG

    print("\n=== Настройка пересылки сообщений ===")
    print("Загрузка доступных диалогов...")

    # Загружаем все доступные диалоги
    dialogs = []
    dialog_dict = {}

    # Для каждого диалога создаем пары [номер]: информация о чате
    async for dialog in app.get_dialogs():
        # Работаем только с группами, супергруппами и личными чатами
        if dialog.chat.type in [
            ChatType.GROUP,
            ChatType.SUPERGROUP,
            ChatType.PRIVATE,
            ChatType.CHANNEL,
        ]:
            # Собираем информацию о чате
            chat_id = dialog.chat.id
            if dialog.chat.type == ChatType.PRIVATE:
                chat_name = f"{dialog.chat.first_name} {dialog.chat.last_name or ''}"
            else:
                chat_name = dialog.chat.title

            # Добавляем в список и словарь для быстрого доступа
            dialogs.append(dialog)
            dialog_dict[len(dialogs)] = {
                "id": chat_id,
                "name": chat_name,
                "type": dialog.chat.type,
            }

    # Выводим список диалогов
    print("\nДоступные диалоги:")
    for i, info in dialog_dict.items():
        chat_type = (
            "Группа"
            if info["type"] in [ChatType.GROUP, ChatType.SUPERGROUP]
            else "Личный чат" if info["type"] == ChatType.PRIVATE else "Канал"
        )
        print(f"[{i}] {info['name']} ({chat_type}) - ID: {info['id']}")

    # Выбор исходных чатов для пересылки
    print(
        "\nВыберите номера чатов, ИЗ которых нужно пересылать сообщения (введите номера через запятую):"
    )
    source_input = input("> ")
    source_indexes = [
        int(i.strip()) for i in source_input.split(",") if i.strip().isdigit()
    ]

    selected_source_chats = (
        {}
    )  # Словарь для хранения информации о выбранных исходных чатах

    for idx in source_indexes:
        if idx in dialog_dict:
            chat_id = dialog_dict[idx]["id"]
            chat_name = dialog_dict[idx]["name"]
            SOURCE_CHAT_IDS.append(chat_id)
            selected_source_chats[chat_id] = {
                "index": idx,
                "name": chat_name,
            }

            # Для каждого исходного чата выбираем чаты назначения
            print(
                f"\nВыберите номера чатов, В которые нужно пересылать сообщения из {chat_name} (введите номера через запятую):"
            )
            dest_input = input("> ")
            dest_indexes = [
                int(i.strip()) for i in dest_input.split(",") if i.strip().isdigit()
            ]

            dest_chat_ids = []
            for dest_idx in dest_indexes:
                if dest_idx in dialog_dict:
                    dest_chat_id = dialog_dict[dest_idx]["id"]
                    # Check that we're not forwarding to the same chat by comparing actual chat IDs
                    if dest_chat_id != chat_id:
                        dest_chat_ids.append(dest_chat_id)

            if dest_chat_ids:
                FORWARDING_CONFIG[chat_id] = dest_chat_ids
                print(
                    f"Пересылка из {chat_name} настроена в {len(dest_chat_ids)} чат(ов)"
                )

    # Выводим итоговую конфигурацию
    print("\n=== Итоговая конфигурация пересылки ===")
    for source_id in FORWARDING_CONFIG:
        source_name = next(
            (
                info["name"]
                for i, info in dialog_dict.items()
                if info["id"] == source_id
            ),
            f"Чат {source_id}",
        )
        dest_names = [
            next(
                (
                    info["name"]
                    for i, info in dialog_dict.items()
                    if info["id"] == dest_id
                ),
                f"Чат {dest_id}",
            )
            for dest_id in FORWARDING_CONFIG[source_id]
        ]

        print(f"Из: {source_name} -> В: {', '.join(dest_names)}")

    # Сохраняем конфигурацию в файл для последующего использования
    save_config = (
        input("\nСохранить конфигурацию для будущих запусков? (да/нет): ")
        .lower()
        .strip()
    )
    if save_config in ["да", "д", "yes", "y"]:
        config = {
            "SOURCE_CHAT_IDS": SOURCE_CHAT_IDS,
            "FORWARDING_CONFIG": FORWARDING_CONFIG,
        }

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print(f"Конфигурация сохранена в файл {CONFIG_FILE}")


# Функция для загрузки сохраненной конфигурации
def load_saved_config():
    """
    Загружает сохраненную конфигурацию из файла, включая информацию о чатах
    """
    global SOURCE_CHAT_IDS, FORWARDING_CONFIG
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
        return True, chat_info
    except (FileNotFoundError, json.JSONDecodeError):
        print("Сохраненная конфигурация не найдена или повреждена")
        return False, {}


# Функция для пересылки сообщений c антифлудом
async def forward_message(client, message, chat_info=None):
    """
    Обрабатывает входящие сообщения и пересылает их в указанные чаты.
    Использует информацию о чате (USERNAME и пр.), если есть.
    Также обрабатывает FloodWait, чтобы не отправлять сообщения слишком быстро.
    """
    # Получаем ID чата, из которого пришло сообщение
    source_chat_id = message.chat.id

    # Игнорируем собственные сообщения (если бот запущен под тем же аккаунтом)
    if message.from_user and message.from_user.id == client.me.id:
        print(f"Сообщение в {source_chat_id} проигнорировано (собственное сообщение).")
        return

    # Проверяем, настроена ли пересылка из этого чата
    if source_chat_id in FORWARDING_CONFIG:
        destination_chat_ids = FORWARDING_CONFIG[source_chat_id]

        for dest_chat_id in destination_chat_ids:
            # Попробуем узнать «целевой» чат (используем username, если есть в chat_info)
            target_chat = dest_chat_id
            if (
                chat_info
                and dest_chat_id in chat_info
                and "username" in chat_info[dest_chat_id]
            ):
                target_chat = chat_info[dest_chat_id]["username"]
                print(
                    f"Используем username @{target_chat} для доступа к чату {dest_chat_id}"
                )

            try:
                # Первая попытка пересылки
                await message.forward(target_chat)
                print(f"Сообщение из {source_chat_id} переслано в {dest_chat_id}")

            except MessageIdInvalid:
                print(
                    f"Ошибка MESSAGE_ID_INVALID: сообщение удалено, пропускаем {source_chat_id}"
                )
                continue

            except FloodWait as fw:
                # Обработка «флуда»: Telegram просит подождать fw.value секунд
                print(
                    f"FloodWait: нужно подождать {fw.value} секунд, чтобы продолжить."
                )
                await asyncio.sleep(fw.value)

                # После ожидания повторная попытка пересылки
                try:
                    await message.forward(target_chat)
                    print(
                        f"Сообщение из {source_chat_id} переслано в {dest_chat_id} (после FloodWait)."
                    )
                except MessageIdInvalid:
                    print(
                        f"Ошибка MESSAGE_ID_INVALID: сообщение удалено, пропускаем {source_chat_id}"
                    )
                    continue
                except Exception as e2:
                    print(f"Ошибка при повторной пересылке в {dest_chat_id}: {e2}")

            except Exception as e:
                # Прочие ошибки (включая недоступность чата, неправильный username, и т.д.)
                print(f"Ошибка при пересылке сообщения в {dest_chat_id}: {e}")
                print(traceback.format_exc())

                # ---- Попытка fallback-доступа к чату ----
                try:
                    # Если это групповая/супергруппа с отрицательным ID — пробуем искать в get_dialogs
                    if dest_chat_id < 0:
                        print(
                            f"Пробуем найти группу {dest_chat_id} в списке диалогов..."
                        )
                        found = False
                        async for dialog in client.get_dialogs():
                            if dialog.chat.id == dest_chat_id:
                                print(
                                    f"Чат {dest_chat_id} найден в диалогах! Снова пересылаем..."
                                )
                                found = True
                                await message.forward(dialog.chat.id)
                                print(
                                    f"Успешно переслали из {source_chat_id} в {dest_chat_id} (через диалоги)"
                                )
                                break
                        if not found:
                            print(f"Чат {dest_chat_id} так и не найден в диалогах.")
                    else:
                        # Для остальных (положительные ID) пробуем resolve_peer
                        print(
                            f"Пробуем resolve_peer для {dest_chat_id} и снова переслать..."
                        )
                        await client.resolve_peer(dest_chat_id)
                        await message.forward(dest_chat_id)
                        print(
                            f"Сообщение из {source_chat_id} переслано в {dest_chat_id} (после resolve_peer)."
                        )

                except FloodWait as fw2:
                    # Если при fallback'е тоже словили FloodWait — ждём и снова пробуем
                    print(f"FloodWait (fallback): ждём {fw2.value} сек.")
                    await asyncio.sleep(fw2.value)
                    try:
                        # Последняя попытка
                        await message.forward(dest_chat_id)
                        print(
                            f"Сообщение успешно переслано после дополнительного FloodWait (fallback)."
                        )
                    except Exception as e3:
                        print(f"Снова ошибка при повторной пересылке (fallback): {e3}")

                except Exception as e2:
                    print(f"Не удалось восстановить доступ к чату {dest_chat_id}: {e2}")
                    print(traceback.format_exc())


# Функция для проверки и обновления доступа к чатам
async def validate_chats():
    """
    Проверяет и восстанавливает доступность всех чатов в конфигурации,
    с особым подходом к групповым чатам с отрицательными ID.
    """
    print("Проверка доступа к чатам...")

    # Сначала проверим доступность всех чатов, не удаляя их сразу
    problematic_source_ids = []
    problematic_dest_pairs = []

    # Словарь для хранения информации о чатах
    chat_info = {}

    # Проверяем исходные чаты
    for source_id in SOURCE_CHAT_IDS:
        try:
            # Попытка получить информацию о чате (самый надежный, но медленный метод)
            chat = await app.get_chat(source_id)
            print(f"Доступ к исходному чату {source_id} подтвержден")

            # Сохраняем дополнительную информацию о чате
            # Преобразуем ChatType в строку для сериализации в JSON
            if hasattr(chat, "username") and chat.username:
                chat_info[source_id] = {
                    "username": chat.username,
                    "type": str(chat.type.name),
                }
            else:
                chat_info[source_id] = {"type": str(chat.type.name)}

        except Exception as e:
            print(f"Ошибка доступа к исходному чату {source_id}: {e}")
            problematic_source_ids.append(source_id)

    # Проверяем чаты назначения
    for source_id, dest_ids in FORWARDING_CONFIG.items():
        for dest_id in dest_ids:
            if dest_id not in chat_info:  # Проверяем только если еще не проверяли

                if int(dest_id) < 0:  # Это групповой чат с отрицательным ID
                    problematic_dest_pairs.append((source_id, dest_id))

                else:
                    try:
                        chat = await app.get_chat(dest_id)
                        print(f"Доступ к чату назначения {dest_id} подтвержден")

                        # Сохраняем дополнительную информацию о чате
                        # Преобразуем ChatType в строку для сериализации в JSON
                        if hasattr(chat, "username") and chat.username:
                            chat_info[dest_id] = {
                                "username": chat.username,
                                "type": str(chat.type.name),
                            }
                        else:
                            chat_info[dest_id] = {"type": str(chat.type.name)}

                    except Exception as e:
                        print(f"Ошибка доступа к чату назначения {dest_id}: {e}")
                        problematic_dest_pairs.append((source_id, dest_id))

    # Для проблемных групповых чатов с отрицательным ID используем специальный подход
    for source_id in problematic_source_ids[:]:
        if source_id < 0:  # Отрицательный ID - возможно, это группа
            try:
                # Попытка загрузить диалоги для поиска чата
                print(f"Попытка найти группу с ID {source_id} через список диалогов...")
                found = False

                async for dialog in app.get_dialogs():
                    if dialog.chat.id == source_id:
                        print(f"Группа {source_id} найдена в диалогах!")
                        found = True
                        # Сохраняем информацию о чате (преобразуем тип в строку)
                        if hasattr(dialog.chat, "username") and dialog.chat.username:
                            chat_info[source_id] = {
                                "username": dialog.chat.username,
                                "type": str(dialog.chat.type.name),
                            }
                        else:
                            chat_info[source_id] = {"type": str(dialog.chat.type.name)}
                        break

                if found:
                    problematic_source_ids.remove(source_id)
                else:
                    print(f"Группа {source_id} не найдена в диалогах")
            except Exception as e:
                print(f"Ошибка при поиске группы {source_id} в диалогах: {e}")

    # Проверяем и обрабатываем проблемные чаты назначения
    for source_id, dest_id in problematic_dest_pairs[:]:
        if dest_id < 0:  # Отрицательный ID - возможно, это группа
            try:
                print(
                    f"Попытка найти группу назначения {dest_id} через список диалогов..."
                )
                found = False

                async for dialog in app.get_dialogs():
                    if dialog.chat.id == dest_id:
                        print(f"Группа назначения {dest_id} найдена в диалогах!")
                        found = True
                        # Сохраняем информацию о чате (преобразуем тип в строку)
                        if hasattr(dialog.chat, "username") and dialog.chat.username:
                            chat_info[dest_id] = {
                                "username": dialog.chat.username,
                                "type": str(dialog.chat.type.name),
                            }
                        else:
                            chat_info[dest_id] = {"type": str(dialog.chat.type.name)}

                        problematic_dest_pairs.remove((source_id, dest_id))
                        break

                if not found:
                    print(f"Группа назначения {dest_id} не найдена в диалогах")
            except Exception as e:
                print(f"Ошибка при поиске группы назначения {dest_id} в диалогах: {e}")

    # Теперь обновляем конфигурацию на основе результатов
    # Удаляем недоступные исходные чаты
    for source_id in problematic_source_ids:
        if source_id in SOURCE_CHAT_IDS:
            SOURCE_CHAT_IDS.remove(source_id)
        if source_id in FORWARDING_CONFIG:
            del FORWARDING_CONFIG[source_id]
            print(f"Чат {source_id} удален из конфигурации (недоступен)")

    # Удаляем недоступные чаты назначения
    for source_id, dest_id in problematic_dest_pairs:
        if source_id in FORWARDING_CONFIG and dest_id in FORWARDING_CONFIG[source_id]:
            FORWARDING_CONFIG[source_id].remove(dest_id)
            print(f"Чат назначения {dest_id} удален из конфигурации (недоступен)")

            # Если у источника больше нет чатов назначения, удаляем его полностью
            if not FORWARDING_CONFIG[source_id]:
                del FORWARDING_CONFIG[source_id]
                if source_id in SOURCE_CHAT_IDS:
                    SOURCE_CHAT_IDS.remove(source_id)
                print(
                    f"Исходный чат {source_id} удален из конфигурации (нет доступных чатов назначения)"
                )

    # Сохраняем информацию о чатах для будущего использования
    config = {
        "SOURCE_CHAT_IDS": SOURCE_CHAT_IDS,
        "FORWARDING_CONFIG": FORWARDING_CONFIG,
        "CHAT_INFO": chat_info,  # Новое поле с информацией о чатах
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    print("Конфигурация обновлена после проверки доступа к чатам")

    return chat_info


'''
# Основная функция для запуска бота
async def main():
    """
    Основная функция для запуска бота.
    Настраивает обработчики и запускает клиент.
    """
    global SOURCE_CHAT_IDS, FORWARDING_CONFIG

    print("Запуск бота для пересылки сообщений...")

    # Запускаем клиент для настройки
    await app.start()

    # Проверяем, есть ли сохраненная конфигурация
    has_config, chat_info = load_saved_config()

    # Если конфигурация не найдена или пользователь хочет изменить её
    if (
        not has_config
    ):  # or input("Хотите настроить пересылку заново? (да/нет): ").lower() in ["да", "д", "yes", "y"]
        await interactive_setup()
        # После настройки обновляем информацию о чатах
        chat_info = await validate_chats()
    else:
        # Проверяем и обновляем доступ к чатам перед запуском
        chat_info = await validate_chats()

    # Если нет настроенных чатов, завершаем работу
    if not SOURCE_CHAT_IDS or not FORWARDING_CONFIG:
        print("Не настроено ни одной пересылки. Завершение работы.")
        await app.stop()
        return

    # Создаем фильтр для отслеживания сообщений только из указанных чатов
    source_chats_filter = filters.chat(SOURCE_CHAT_IDS)

    # Define a closure to include chat_info
    def create_handler(chat_info_data):
        async def handler(client, message):
            await forward_message(client, message, chat_info_data)

        return handler

    # Регистрируем обработчик для всех входящих сообщений из указанных чатов
    app.add_handler(
        MessageHandler(
            create_handler(chat_info),
            filters=source_chats_filter,
        )
    )

    print("Бот запущен и готов к работе!")
    print(f"Отслеживаются сообщения из {len(SOURCE_CHAT_IDS)} чатов")
    print("Нажмите Ctrl+C для завершения работы")

    # Выводим текущую конфигурацию пересылки с дополнительной информацией
    for source_id, dest_ids in FORWARDING_CONFIG.items():
        source_info = ""
        if source_id in chat_info:
            if "username" in chat_info[source_id]:
                source_info = f" (@{chat_info[source_id]['username']})"
            source_info += f" [тип: {chat_info[source_id]['type']}]"

        dest_info = []
        for dest_id in dest_ids:
            info = str(dest_id)
            if dest_id in chat_info:
                if "username" in chat_info[dest_id]:
                    info += f" (@{chat_info[dest_id]['username']})"
                info += f" [тип: {chat_info[dest_id]['type']}]"
            dest_info.append(info)

        print(f"Из чата {source_id}{source_info} в чаты: {', '.join(dest_info)}")

    # Держим бота запущенным до нажатия Ctrl+C
    await idle()

    # Корректно останавливаем клиент при завершении работы
    await app.stop()
'''


async def main():
    """
    Основная функция для запуска бота.
    Настраивает обработчики и запускает клиент.
    """
    global SOURCE_CHAT_IDS, FORWARDING_CONFIG

    print("Запуск бота для пересылки сообщений...")

    # Запускаем клиент для настройки
    await app.start()

    # Проверяем наличие папки и настраиваем пересылку на её основе
    use_folder = (
        settings.chats_folder_name if hasattr(settings, "chats_folder_name") else False
    )

    if use_folder and settings.interactive_folder_setup:
        # Проверяем папку и настраиваем пересылку
        folder_exists, folder_config, chat_info = await check_folder_existence()

        if not folder_exists:
            print(
                f"Для работы бота необходимо создать папку '{settings.chats_folder_name}' в Telegram"
            )
            print(
                "и добавить в неё чаты, из которых нужно пересылать сообщения, и чаты для пересылки."
            )
            await app.stop()
            return

        SOURCE_CHAT_IDS = list(folder_config.keys())
        FORWARDING_CONFIG = folder_config
    else:
        # Стандартный режим без использования папки
        # Проверяем, есть ли сохраненная конфигурация
        has_config, chat_info = load_saved_config()

        # Если конфигурация не найдена или пользователь хочет изменить её
        if not has_config:
            await interactive_setup()
            # После настройки обновляем информацию о чатах
            chat_info = await validate_chats()
        else:
            # Проверяем и обновляем доступ к чатам перед запуском
            chat_info = await validate_chats()

    # Если нет настроенных чатов, завершаем работу
    if not SOURCE_CHAT_IDS or not FORWARDING_CONFIG:
        print("Не настроено ни одной пересылки. Завершение работы.")
        await app.stop()
        return

    # Создаем фильтр для отслеживания сообщений только из указанных чатов
    source_chats_filter = filters.chat(SOURCE_CHAT_IDS)

    # Define a closure to include chat_info
    def create_handler(chat_info_data):
        async def handler(client, message):
            await forward_message(client, message, chat_info_data)

        return handler

    # Регистрируем обработчик для всех входящих сообщений из указанных чатов
    app.add_handler(
        MessageHandler(
            create_handler(chat_info),
            filters=source_chats_filter,
        )
    )

    print("Бот запущен и готов к работе!")
    print(f"Отслеживаются сообщения из {len(SOURCE_CHAT_IDS)} чатов")
    print("Нажмите Ctrl+C для завершения работы")

    # Выводим текущую конфигурацию пересылки с дополнительной информацией
    for source_id, dest_ids in FORWARDING_CONFIG.items():
        source_info = ""
        if source_id in chat_info:
            if "username" in chat_info[source_id]:
                source_info = f" (@{chat_info[source_id]['username']})"
            source_info += f" [тип: {chat_info[source_id]['type']}]"

        dest_info = []
        for dest_id in dest_ids:
            info = str(dest_id)
            if dest_id in chat_info:
                if "username" in chat_info[dest_id]:
                    info += f" (@{chat_info[dest_id]['username']})"
                info += f" [тип: {chat_info[dest_id]['type']}]"
            dest_info.append(info)

        print(f"Из чата {source_id}{source_info} в чаты: {', '.join(dest_info)}")

    # Держим бота запущенным до принудительного завершения
    await idle()

    # Корректно останавливаем клиент при завершении работы
    await app.stop()


# Функция для поддержания работы бота
async def idle():
    """
    Функция для поддержания работы бота до принудительного завершения.
    """
    try:
        # Ждем до бесконечности или до прерывания
        while True:
            await asyncio.sleep(3600)  # Проверка каждый час
    except KeyboardInterrupt:
        # Обработка нажатия Ctrl+C
        print("Завершение работы бота...")
