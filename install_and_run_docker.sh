#!/bin/bash

# Путь к Docker Desktop
DOCKER_APP="/Applications/Docker.app"
DOCKER_DOWNLOAD_URL="https://desktop.docker.com/mac/main/amd64/Docker.dmg"
DOCKER_DMG_PATH="/tmp/Docker.dmg"

# Проверяем, установлен ли Docker
if [ -d "$DOCKER_APP" ]; then
    echo "Docker Desktop уже установлен."
else
    echo "Docker Desktop не найден. Начинаю установку..."

    # Скачиваем Docker
    curl -L -o "$DOCKER_DMG_PATH" "$DOCKER_DOWNLOAD_URL"

    # Монтируем DMG
    hdiutil attach "$DOCKER_DMG_PATH"

    # Запускаем установку
    sudo /Volumes/Docker/Docker.app/Contents/MacOS/install --accept-license --user=$USER

    # Отмонтируем DMG
    hdiutil detach /Volumes/Docker
fi

# Запускаем Docker
echo "Запускаю Docker Desktop..."
open -a Docker

# Ожидаем, пока Docker не будет готов
echo "Ожидание запуска Docker..."
until docker info >/dev/null 2>&1; do
    sleep 3
done

echo "Docker запущен."

# Определяем директорию скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Запускаем `docker compose`
echo "Запускаем docker compose из каталога: $SCRIPT_DIR"
cd "$SCRIPT_DIR" && docker compose run --rm telegram-forwarder

echo "Скрипт завершён."
