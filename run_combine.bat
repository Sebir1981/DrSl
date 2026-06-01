@echo off
chcp 65001 >nul
echo ========================================
echo  📦 Сборка проекта DrSl
echo ========================================
echo.

REM Переходим в папку, где лежит этот файл
cd /d "%~dp0"

REM Проверяем наличие Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Ошибка: Python не найден в системе!
    pause
    exit /b 1
)

REM Активируем виртуальное окружение (если существует)
if exist ".venv\Scripts\activate.bat" (
    echo 🔧 Активация .venv...
    call .venv\Scripts\activate.bat
)

REM Проверяем наличие скрипта
if not exist "combine_py.py" (
    echo ❌ Ошибка: combine_py.py не найден!
    pause
    exit /b 1
)

echo 🚀 Запуск объединения файлов...
echo.

REM === НАСТРОЙКИ (меняйте только эти строки) ===
set PROJECT_DIR=.
set OUTPUT_FILE=full_project.txt
set FLAGS=-r --html --static
REM ==============================================

python combine_py.py %PROJECT_DIR% %FLAGS% -r --html --static -o %OUTPUT_FILE%

echo.
echo ========================================
if %errorlevel% equ 0 (
    echo ✅ Успешно! Файл сохранён: %OUTPUT_FILE%
) else (
    echo ❌ Произошла ошибка. Проверьте консоль выше.
)
echo ========================================
pause