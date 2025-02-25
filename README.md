# Бот-ретранслятор сообщений в Telegram

Бот-ретранслятор предназначен для пересылки сообщений между чатами/каналами/группами в Telegram. Он работает в режиме userbot, то есть использует учётную запись Telegram (не бота) для автоматизации задач.

## Установка

Добавить переменные в окружение:
    API_ID, API_HASH - получить тут -> <https://my.telegram.org/apps>

! Важно, не использовать основной аккаунт Telegram, а создать новый просто для этого бота или тот, который не жалко потерять, userbot'ов иногда блокируют.

Создайте папку чатов с названием `Forward Bot` и добавьте в неё чаты, которые вы хотите отслеживать и те, в которые хотите пересылать данные.

```bash
docker compose run --rm telegram-forwarder
```

Далее для отсоединения от контейнера выполните поочередно (после этого контейнер будет работать в фоне):

- Ctrl + P
- Ctrl + Q

## Повторная настройка

Для повторной настройки удалите файл `forward_config.json` и запустите бота снова. Вам будет предложено настроить пересылку заново.
