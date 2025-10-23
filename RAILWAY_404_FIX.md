# 🚂 Виправлення проблем з Railway.app

## ❌ Проблема:
404 помилка при запиті до `/api/stream` на Railway.app

## 🔍 Діагностика:

### 1. **Натисніть кнопку "🔍 Debug":**
Це покаже інформацію про налаштування Railway:
- PORT змінну
- Railway environment
- Request headers
- URL інформацію

### 2. **Перевірте логи Railway:**
```bash
# В Railway Dashboard
# Перейдіть в Logs
# Шукайте помилки запуску
```

## ✅ Можливі причини та рішення:

### 1. **Неправильний порт:**
Railway може використовувати інший порт.

**Рішення:**
```python
# В app.py перевірте:
port = int(os.environ.get('PORT', 5001))
print(f"Запуск на порту: {port}")
```

### 2. **Проблеми з gunicorn:**
Railway може не запускати gunicorn правильно.

**Рішення:**
Створіть `Procfile`:
```
web: gunicorn --bind 0.0.0.0:$PORT --timeout 120 app:app
```

### 3. **Проблеми з залежностями:**
Не всі пакети встановлені.

**Рішення:**
Перевірте `requirements.txt`:
```
Flask==2.3.3
Flask-Cors==4.0.0
requests==2.31.0
beautifulsoup4==4.12.2
gunicorn==21.2.0
```

### 4. **Проблеми з CORS:**
Railway може блокувати запити.

**Рішення:**
```python
CORS(app, origins=[
    "https://discord.com",
    "https://*.discord.com",
    "https://discordapp.com",
    "https://*.discordapp.com",
    "https://web-production-*.up.railway.app"
])
```

## 🛠️ Кроки виправлення:

### 1. **Оновіть код на Railway:**
```bash
git add .
git commit -m "Fix Railway deployment"
git push origin main
```

### 2. **Перевірте налаштування Railway:**
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --timeout 120 app:app`
- **Port:** Автоматично з `$PORT`

### 3. **Додайте змінні середовища:**
```bash
# В Railway Dashboard
PORT=8080
PYTHON_VERSION=3.11.7
FLASK_ENV=production
```

### 4. **Перевірте домен:**
Railway дає домен типу:
`https://web-production-xxxxx.up.railway.app`

## 🔧 Альтернативні рішення:

### 1. **Використовуйте Heroku:**
```bash
# Heroku має кращу підтримку Flask
heroku create your-app-name
git push heroku main
```

### 2. **Використовуйте Render:**
```bash
# Render також підтримує Flask
# Але може блокувати HdRezka
```

### 3. **Використовуйте Vercel:**
```bash
# Vercel для статичних сайтів
# Може потребувати адаптації
```

## 📊 Порівняння хостингів:

| Хостинг | Flask | Discord | HdRezka | Складність |
|---------|-------|---------|---------|------------|
| Railway | ✅ | ✅ | ✅ | Середня |
| Heroku | ✅ | ✅ | ✅ | Низька |
| Render | ✅ | ✅ | ❌ | Низька |
| Vercel | ⚠️ | ✅ | ⚠️ | Висока |

## 🎯 Рекомендовані кроки:

### 1. **Спочатку Debug:**
- Натисніть "🔍 Debug"
- Подивіться на інформацію
- Перевірте PORT та environment

### 2. **Перевірте логи:**
- Railway Dashboard → Logs
- Шукайте помилки запуску
- Перевірте чи запускається gunicorn

### 3. **Оновіть налаштування:**
- Перевірте Build/Start команди
- Додайте змінні середовища
- Перевірте домен

### 4. **Якщо не допомагає:**
- Спробуйте Heroku
- Або локальний запуск з ngrok

## 🚨 Критичні перевірки:

### 1. **Чи запускається сервер:**
```bash
# В логах Railway має бути:
Starting gunicorn...
Listening on: http://0.0.0.0:8080
```

### 2. **Чи доступний API:**
```bash
# Перевірте в браузері:
https://your-app.up.railway.app/api/test
```

### 3. **Чи працює парсинг:**
```bash
# Натисніть "🧪 Тест API"
# Має показати успішну відповідь
```

## 💡 Поради:

1. **Завжди перевіряйте логи** - там найбільше інформації
2. **Використовуйте Debug кнопку** - для діагностики
3. **Тестуйте API endpoints** - перед тестуванням функцій
4. **Перевіряйте домен** - правильний URL в Discord

## 🎯 Очікувані результати:

### ✅ Працюючий Railway:
```
Debug показує:
- PORT: 8080
- RAILWAY_ENVIRONMENT: production
- Request URL: https://your-app.up.railway.app/api/debug
```

### ❌ Проблемний Railway:
```
Debug показує:
- PORT: не встановлено
- RAILWAY_ENVIRONMENT: не встановлено
- 404 помилки в логах
```

**Спочатку натисніть "🔍 Debug" та подивіться на інформацію!**
