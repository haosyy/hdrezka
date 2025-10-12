# 🚀 Завантаження на GitHub + Розгортання на Render.com

## Крок 1: Підготовка проекту для GitHub

1. **Створіть файл `.gitignore`:**
   ```
   __pycache__/
   *.pyc
   *.pyo
   *.pyd
   .env
   .venv/
   venv/
   .DS_Store
   *.log
   ```

2. **Оновіть README.md** (створіть якщо немає):
   ```markdown
   # HdRezka API для Discord Activities
   
   Сайт для перегляду фільмів та серіалів з інтеграцією Discord Activities.
   
   ## Розгортання на Render.com
   
   1. Fork цей репозиторій
   2. Підключіть до Render.com
   3. Налаштуйте Discord Client ID
   4. Насолоджуйтесь!
   ```

## Крок 2: Завантаження на GitHub

### Варіант A: Через GitHub Desktop (Найпростіший)

1. **Завантажте GitHub Desktop** з [desktop.github.com](https://desktop.github.com)

2. **Створіть репозиторій:**
   - Відкрийте GitHub Desktop
   - File → New Repository
   - Назва: `hdrezka-discord-app`
   - Local Path: `C:\Users\roost\OneDrive\Pulpit\best\`
   - ✅ Initialize with README
   - Create Repository

3. **Скопіюйте файли:**
   - Скопіюйте всі файли з вашої папки в нову папку репозиторію
   - В GitHub Desktop ви побачите всі файли
   - Напишіть коміт: "Initial commit - HdRezka API with Discord Activities"
   - Натисніть "Commit to main"

4. **Завантажте на GitHub:**
   - Натисніть "Publish repository"
   - Виберіть "Keep this code private" або зробіть публічним
   - Натисніть "Publish Repository"

### Варіант B: Через командний рядок

1. **Відкрийте PowerShell в папці проекту:**
   ```powershell
   cd "C:\Users\roost\OneDrive\Pulpit\best\hdrezka-python-app-main"
   ```

2. **Ініціалізуйте Git:**
   ```powershell
   git init
   git add .
   git commit -m "Initial commit - HdRezka API with Discord Activities"
   ```

3. **Створіть репозиторій на GitHub:**
   - Перейдіть на [github.com](https://github.com)
   - Натисніть "New repository"
   - Назва: `hdrezka-discord-app`
   - Створіть репозиторій

4. **Підключіть до GitHub:**
   ```powershell
   git remote add origin https://github.com/YOUR_USERNAME/hdrezka-discord-app.git
   git branch -M main
   git push -u origin main
   ```

## Крок 3: Розгортання на Render.com

1. **Зареєструйтеся на [render.com](https://render.com)**
   - Можете через GitHub акаунт

2. **Створіть новий Web Service:**
   - Натисніть "New +" → "Web Service"
   - Підключіть ваш GitHub репозиторій
   - Виберіть `hdrezka-discord-app`

3. **Налаштування:**
   ```
   Name: hdrezka-discord-app
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn --worker-tmp-dir /dev/shm --bind 0.0.0.0:$PORT --timeout 120 app:app
   ```

4. **Натисніть "Create Web Service"**

5. **Отримайте URL:**
   - Render дасть вам URL типу: `https://hdrezka-discord-app.onrender.com`

## Крок 4: Налаштування Discord

1. **Перейдіть в Discord Developer Portal**
2. **В OAuth2 → Redirects додайте:**
   `https://hdrezka-discord-app.onrender.com/`

3. **Оновіть код:**
   - В GitHub репозиторії відкрийте `app.py`
   - Замініть `YOUR_CLIENT_ID` на ваш Client ID
   - Зробіть коміт змін

4. **Render автоматично перезапустить сайт**

## ✅ Готово!

Тепер ваш сайт доступний за адресою:
`https://hdrezka-discord-app.onrender.com`

Ви можете використовувати його в Discord Activities!

## 🔄 Оновлення коду

Коли хочете оновити код:
1. Внесіть зміни в файли
2. Зробіть коміт в GitHub
3. Render автоматично перезапустить сайт
