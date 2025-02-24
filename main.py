# main.py

import asyncio
import os
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
# from pyrogram.types import Dialog
from pyrogram.enums import ChatType

from dotenv import load_dotenv

load_dotenv(".env")


API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "0123456789abcdef0123456789abcdef")


# Создаем экземпляр клиента Pyrogram
app = Client(
    "message_forwarder_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=None,  # Не используем токен бота для логина по номеру телефона
)

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

    for idx in source_indexes:
        if idx in dialog_dict:
            chat_id = dialog_dict[idx]["id"]
            SOURCE_CHAT_IDS.append(chat_id)

            # Для каждого исходного чата выбираем чаты назначения
            print(
                f"\nВыберите номера чатов, В которые нужно пересылать сообщения из {dialog_dict[idx]['name']} (введите номера через запятую):"
            )
            dest_input = input("> ")
            dest_indexes = [
                int(i.strip()) for i in dest_input.split(",") if i.strip().isdigit()
            ]

            dest_chat_ids = []
            for dest_idx in dest_indexes:
                if (
                    dest_idx in dialog_dict and dest_idx != idx
                ):  # Проверяем, что не пересылаем в тот же чат
                    dest_chat_id = dialog_dict[dest_idx]["id"]
                    dest_chat_ids.append(dest_chat_id)

            if dest_chat_ids:
                FORWARDING_CONFIG[chat_id] = dest_chat_ids
                print(
                    f"Пересылка из {dialog_dict[idx]['name']} настроена в {len(dest_chat_ids)} чат(ов)"
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
    save_config = input(
        "\nСохранить конфигурацию для будущих запусков? (да/нет): "
    ).lower()
    if save_config in ["да", "д", "yes", "y"]:
        config = {
            "SOURCE_CHAT_IDS": SOURCE_CHAT_IDS,
            "FORWARDING_CONFIG": FORWARDING_CONFIG,
        }
        import json

        with open("forward_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print("Конфигурация сохранена в файл forward_config.json")


# Функция для загрузки сохраненной конфигурации
def load_saved_config():
    """
    Загружает сохраненную конфигурацию из файла
    """
    global SOURCE_CHAT_IDS, FORWARDING_CONFIG
    try:
        import json

        with open("forward_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            SOURCE_CHAT_IDS = config.get("SOURCE_CHAT_IDS", [])
            FORWARDING_CONFIG = config.get("FORWARDING_CONFIG", {})

            # Конвертируем строковые ключи обратно в int, так как JSON сохраняет все ключи как строки
            FORWARDING_CONFIG = {int(k): v for k, v in FORWARDING_CONFIG.items()}

        print("Загружена сохраненная конфигурация:")
        for source_id in FORWARDING_CONFIG:
            print(f"Из чата {source_id} в чаты: {FORWARDING_CONFIG[source_id]}")
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        print("Сохраненная конфигурация не найдена или повреждена")
        return False


# Функция для обработки входящих сообщений
async def forward_message(client, message):
    """
    Обрабатывает входящие сообщения и пересылает их в указанные чаты.

    :param client: Экземпляр клиента Pyrogram
    :param message: Объект сообщения
    """
    # Получаем ID чата, из которого пришло сообщение
    source_chat_id = message.chat.id

    # Проверяем, настроена ли пересылка из этого чата
    if source_chat_id in FORWARDING_CONFIG:
        # Получаем список чатов для пересылки
        destination_chat_ids = FORWARDING_CONFIG[source_chat_id]

        # Пересылаем сообщение в каждый чат из списка
        for dest_chat_id in destination_chat_ids:
            try:
                # Пересылаем сообщение
                await message.forward(dest_chat_id)
                print(f"Сообщение из {source_chat_id} переслано в {dest_chat_id}")
            except Exception as e:
                # Обрабатываем возможные ошибки
                print(f"Ошибка при пересылке сообщения в {dest_chat_id}: {e}")


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
    has_config = load_saved_config()

    # Если конфигурация не найдена или пользователь хочет изменить её
    if not has_config or input(
        "Хотите настроить пересылку заново? (да/нет): "
    ).lower() in ["да", "д", "yes", "y"]:
        await interactive_setup()

    # Если нет настроенных чатов, завершаем работу
    if not SOURCE_CHAT_IDS or not FORWARDING_CONFIG:
        print("Не настроено ни одной пересылки. Завершение работы.")
        await app.stop()
        return

    # Создаем фильтр для отслеживания сообщений только из указанных чатов
    source_chats_filter = filters.chat(SOURCE_CHAT_IDS)

    # Регистрируем обработчик для всех входящих сообщений из указанных чатов
    app.add_handler(MessageHandler(forward_message, filters=source_chats_filter))

    print("Бот запущен и готов к работе!")
    print(f"Отслеживаются сообщения из {len(SOURCE_CHAT_IDS)} чатов")

    # Держим бота запущенным до нажатия Ctrl+C
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


# Запускаем основную функцию
if __name__ == "__main__":
    # Устанавливаем обработчик событий цикла для корректного завершения
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
