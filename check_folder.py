# check_folder.py

import os
from pyrogram import Client
from pyrogram.raw import functions
from dotenv import load_dotenv

load_dotenv(".env")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")


async def check_folder_existence():
    app = Client("my_account", api_id=API_ID, api_hash=API_HASH)

    async with app:
        try:
            response = await app.invoke(functions.messages.GetDialogFilters())

            target_folder = next(
                (f for f in response if getattr(f, "title", "") == "Forward Bot"), None
            )

            if target_folder:
                print(f"✅ Папка найдена! ID: {target_folder.id}")
                print("Включенные чаты:")
                for peer in target_folder.include_peers:
                    if hasattr(peer, "channel_id"):
                        print(f"- Канал: {peer.channel_id}")
                    elif hasattr(peer, "chat_id"):
                        print(f"- Чат: {peer.chat_id}")
                    elif hasattr(peer, "user_id"):
                        print(f"- Пользователь: {peer.user_id}")
                    else:
                        print(f"- Неизвестный тип: {peer}")
            else:
                print(
                    "❌ Папка не найдена. Создайте папку с именем 'Forward Bot' "
                    "и добавьте в неё чаты, которые вы хотите отслеживать или те, в которые хотите пересылать данные."
                )

        except Exception as e:
            print(f"⚠️ Ошибка: {str(e)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(check_folder_existence())
