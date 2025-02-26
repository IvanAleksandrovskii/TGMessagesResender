(*
  AppleScript: InstallAndRunDocker.applescript
  Назначение:
    1. Проверить, установлен ли Docker Desktop
    2. При необходимости установить и запустить
    3. Выполнить docker compose run --rm telegram-forwarder
    4. Вернуть управление пользователю (завершить скрипт)

  Запуск:
    osascript InstallAndRunDocker.applescript
*)

-- Путь к Docker Desktop
set dockerAppPath to "/Applications/Docker.app"

-- Команда для скачивания Docker Desktop (ссылка может меняться)
set dockerDownloadURL to "https://desktop.docker.com/mac/main/amd64/Docker.dmg"
set dockerDMGPath to "/tmp/Docker.dmg"

-- Проверяем, установлен ли Docker Desktop:
tell application "System Events"
    if exists folder dockerAppPath then
        set dockerInstalled to true
    else
        set dockerInstalled to false
    end if
end tell

-- Если не установлен, качаем и устанавливаем
if dockerInstalled is false then
    display dialog "Docker Desktop не найден. Начинаю установку..." buttons {"OK"} default button "OK"
    
    -- Скачиваем Docker.dmg
    do shell script "curl -L -o " & quoted form of dockerDMGPath & " " & dockerDownloadURL with administrator privileges
    
    -- Монтируем DMG
    do shell script "hdiutil attach " & quoted form of dockerDMGPath with administrator privileges
    
    -- Запускаем установку
    -- --accept-license  - автоматически принимаем лицензионное соглашение
    -- --user=$USER      - выполним операции, требующие root, от имени текущего пользователя
    do shell script "/Volumes/Docker/Docker.app/Contents/MacOS/install --accept-license --user=$USER" with administrator privileges
    
    -- Отмонтируем DMG
    do shell script "hdiutil detach /Volumes/Docker" with administrator privileges
end if

-- Запускаем Docker Desktop
display dialog "Запускаю Docker Desktop..." buttons {"OK"} default button "OK"
try
    tell application "Docker" to activate
on error
    -- Если вдруг через tell application не получается, пробуем открыть напрямую
    do shell script "open " & quoted form of dockerAppPath
end try

-- Ожидаем, пока Docker не будет готов
set dockerReady to false
repeat until dockerReady
    delay 3
    try
        -- Если docker info отработает без ошибки, значит Docker готов
        do shell script "docker info >/dev/null 2>&1"
        set dockerReady to true
    on error
        -- Docker еще не успел подняться
        set dockerReady to false
    end try
end repeat

-- Находим директорию, в которой лежит сам скрипт
-- 1) Получаем POSIX-путь к скрипту
-- 2) С помощью 'dirname' получаем родительскую директорию
set scriptPosixPath to POSIX path of (path to me)
set scriptDir to do shell script "dirname " & quoted form of scriptPosixPath

display dialog "Docker запущен. Запускаем docker compose из каталога:\n" & scriptDir buttons {"OK"} default button "OK"

try
    -- Переходим в директорию скрипта и выполняем docker compose
    do shell script "cd " & quoted form of scriptDir & " && docker compose run --rm telegram-forwarder"
on error errMsg
    display dialog "Ошибка при запуске docker compose: " & errMsg
end try

display dialog "Скрипт завершён." buttons {"OK"} default button "OK"
