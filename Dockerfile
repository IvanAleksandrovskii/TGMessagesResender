# Используем официальный образ Python
FROM python:3.10-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы в рабочую директорию
COPY . .

# Устанавливаем переменную окружения для хранения файлов в томе
# ENV PYTHONUNBUFFERED=1

# Копируем скрипт запуска приложения
COPY start.sh .

# Даем права на запуск скрипта
RUN chmod +x start.sh

# Устанавливаем скрипт запуска приложения
ENTRYPOINT ["/app/start.sh"]