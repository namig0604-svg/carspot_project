@echo off
REM CarSpot Setup Script для Windows
REM Этот скрипт создаст всю структуру проекта

echo ==========================================
echo  CarSpot Setup для Windows
echo ==========================================
echo.

REM Создание основных папок
echo [1/5] Создание структуры папок...
mkdir app
mkdir app\models
mkdir app\schemas
mkdir app\api
mkdir app\utils
mkdir CarSpot-iOS\Views
mkdir CarSpot-iOS\Models
mkdir CarSpot-iOS\Services
mkdir uploads

echo [2/5] Папки созданы!
echo.

REM Установка зависимостей Python
echo [3/5] Установка зависимостей Python...
echo Это может занять 2-3 минуты...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [4/5] Зависимости установлены!
echo.

REM Информация для пользователя
echo [5/5] Готово!
echo.
echo ==========================================
echo  ✓ Проект готов к запуску!
echo ==========================================
echo.
echo Следующие шаги:
echo.
echo 1. Запусти Docker Desktop (если еще не запущен)
echo 2. Открой Command Prompt в папке проекта
echo 3. Введи: docker-compose up
echo.
echo Больше инструкций смотри в INSTALLATION.md
echo.
pause
