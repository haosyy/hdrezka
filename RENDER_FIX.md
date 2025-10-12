# 🔧 Виправлення проблем з Render.com

## ❌ Типові проблеми:

### 1. **Неправильна конфігурація**
- Неправильний start command
- Відсутність runtime.txt
- Неправильні залежності

### 2. **Проблеми з портом**
- Render використовує змінну $PORT
- Локально використовується 5001

### 3. **Проблеми з залежностями**
- Відсутні версії пакетів
- Конфлікти версій

## ✅ Що виправлено:

### 1. **Оновлено app.py:**
```python
# Автоматичне визначення порту
port = int(os.environ.get('PORT', 5001))
app.run(debug=False, host='0.0.0.0', port=port)
```

### 2. **Додано runtime.txt:**
```
python-3.11.7
```

### 3. **Оновлено requirements.txt:**
```
Flask==2.3.3
Flask-Cors==4.0.0
requests==2.31.0
beautifulsoup4==4.12.2
gunicorn==21.2.0
```

### 4. **Створено render.yaml:**
```yaml
services:
  - type: web
    name: hdrezka-discord-app
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --worker-tmp-dir /dev/shm --bind 0.0.0.0:$PORT --timeout 120 --workers 2 app:app
```

## 🚀 Кроки для розгортання:

### 1. **Завантажте оновлений код на GitHub:**
```bash
git add .
git commit -m "Fix Render deployment issues"
git push origin main
```

### 2. **Налаштування Render.com:**

**Якщо створюєте новий сервіс:**
- **Name:** `hdrezka-discord-app`
- **Environment:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn --worker-tmp-dir /dev/shm --bind 0.0.0.0:$PORT --timeout 120 --workers 2 app:app`

**Якщо оновлюєте існуючий:**
- Перейдіть в налаштування сервісу
- Оновіть Start Command
- Натисніть "Save Changes"
- Натисніть "Manual Deploy" → "Deploy latest commit"

### 3. **Перевірте логи:**
- Перейдіть в "Logs" в Render Dashboard
- Шукайте помилки імпорту або запуску

## 🔍 Діагностика:

### Логи мають показувати:
```
INFO:Python версія: 3.11.7
INFO:Поточний робочий каталог: /opt/render/project/src
INFO:Запуск на порту: 10000
INFO:Всі залежності успішно імпортовані
```

### Якщо є помилки:
1. **Import Error** - перевірте requirements.txt
2. **Port Error** - перевірте start command
3. **Build Error** - перевірте runtime.txt

## 🛠️ Альтернативні налаштування:

### Якщо render.yaml не працює:
Використовуйте ручні налаштування:

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn --worker-tmp-dir /dev/shm --bind 0.0.0.0:$PORT --timeout 120 --workers 2 app:app
```

**Environment Variables:**
```
PYTHON_VERSION=3.11.7
FLASK_ENV=production
```

## 🎯 Очікуваний результат:

Після успішного розгортання:
- Сайт доступний за URL типу: `https://your-app.onrender.com`
- Логи показують успішний запуск
- Discord Activities працюють

## 📞 Якщо все ще не працює:

1. **Перевірте логи Render** - скопіюйте помилки
2. **Спробуйте інший start command:**
   ```bash
   python app.py
   ```
3. **Перевірте Discord Client ID** - він має бути правильний
4. **Спробуйте інший хостинг** - Railway, Heroku, або Vercel

**Найчастіше проблема в неправильному start command або відсутності версій пакетів!**
