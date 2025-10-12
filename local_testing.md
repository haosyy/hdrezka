# 🧪 Локальне тестування Discord Activities

## Варіант 1: Ngrok (Рекомендую для тестування)

1. **Встановіть ngrok:**
   ```bash
   # Windows (через Chocolatey)
   choco install ngrok
   
   # Або завантажте з https://ngrok.com/
   ```

2. **Запустіть ваш сайт локально:**
   ```bash
   python app.py
   ```

3. **В іншому терміналі запустіть ngrok:**
   ```bash
   ngrok http 5001
   ```

4. **Скопіюйте HTTPS URL** (виглядає як `https://abc123.ngrok.io`)

5. **Використовуйте цей URL в Discord Developer Portal**

## Варіант 2: Cloudflare Tunnel

1. **Встановіть cloudflared:**
   ```bash
   # Windows
   winget install Cloudflare.cloudflared
   ```

2. **Запустіть туннель:**
   ```bash
   cloudflared tunnel --url http://localhost:5001
   ```

## Варіант 3: Serveo

1. **Запустіть ваш сайт:**
   ```bash
   python app.py
   ```

2. **В іншому терміналі:**
   ```bash
   ssh -R 80:localhost:5001 serveo.net
   ```

## ⚠️ Важливо:

- **Тільки для тестування!** Локальні туннелі нестабільні
- URL змінюється при кожному перезапуску
- Для продакшену використовуйте справжній хостинг

## 🚀 Для постійного використання:

Рекомендую використовувати **Heroku** - це найпростіший спосіб:

1. Створіть акаунт на heroku.com
2. Завантажте код через Git
3. Отримайте постійний домен
4. Налаштуйте в Discord Developer Portal
