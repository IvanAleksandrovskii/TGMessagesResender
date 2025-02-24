# main.py

import asyncio

from src import main as app


# Запускаем основную функцию
if __name__ == "__main__":
    # Устанавливаем обработчик событий цикла для корректного завершения
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(app())
    except KeyboardInterrupt:
        print("Бот остановлен.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
