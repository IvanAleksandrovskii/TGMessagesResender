# src/app.py

import asyncio

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from .client import app
from .config import settings
from .check_folder import check_folder_existence
from .config_manager import load_saved_config
from .chat_manager import validate_chats, print_current_config
from .setup_manager import interactive_setup
from .message_handler import create_handler


# Файл с конфигурацией пересылки бота
CONFIG_FILE = settings.bot_chats_config_file

# Глобальные переменные для хранения настроек пересылки
SOURCE_CHAT_IDS = []
FORWARDING_CONFIG = {}


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

    chat_info = {}  # Инициализируем chat_info

    # Проверяем, есть ли сохраненная конфигурация
    has_config, saved_source_ids, saved_forwarding_config, saved_chat_info = (
        load_saved_config()
    )

    if has_config:
        SOURCE_CHAT_IDS = saved_source_ids
        FORWARDING_CONFIG = saved_forwarding_config
        chat_info = saved_chat_info
    elif use_folder and settings.interactive_folder_setup:
        # Проверяем папку и настраиваем пересылку только если нет сохранённой конфигурации
        folder_exists, folder_config, folder_chat_info = await check_folder_existence()
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
        chat_info = folder_chat_info
    else:
        # Если конфигурация не найдена и не используем папку - проводим интерактивную настройку
        SOURCE_CHAT_IDS, FORWARDING_CONFIG = await interactive_setup(app)

    # Проверяем и обновляем доступ к чатам перед запуском
    # Это обновит SOURCE_CHAT_IDS и FORWARDING_CONFIG на основе доступности чатов
    SOURCE_CHAT_IDS, FORWARDING_CONFIG, chat_info = await validate_chats(
        app, SOURCE_CHAT_IDS, FORWARDING_CONFIG
    )

    # Если нет настроенных чатов, завершаем работу
    if not SOURCE_CHAT_IDS or not FORWARDING_CONFIG:
        print("Не настроено ни одной пересылки. Завершение работы.")
        await app.stop()
        return

    # Создаем фильтр для отслеживания сообщений только из указанных чатов
    source_chats_filter = filters.chat(SOURCE_CHAT_IDS)
    print("Фильтр для отслеживания сообщений:", SOURCE_CHAT_IDS)

    # Регистрируем обработчик для всех входящих сообщений из указанных чатов
    print("Регистрируем обработчик для всех входящих сообщений из указанных чатов")
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
    print_current_config(FORWARDING_CONFIG, chat_info)

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
