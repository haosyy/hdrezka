# 🚀 Швидке розгортання на Heroku

## Крок 1: Підготовка

1. **Встановіть Heroku CLI:**
   - Завантажте з [devcenter.heroku.com](https://devcenter.heroku.com/articles/heroku-cli)
   - Або через winget: `winget install Heroku.HerokuCLI`

2. **Створіть акаунт на [heroku.com](https://heroku.com)**

## Крок 2: Розгортання

1. **Відкрийте PowerShell в папці з проектом:**
   ```powershell
   cd "C:\Users\roost\OneDrive\Pulpit\best\hdrezka-python-app-main"
   ```

2. **Увійдіть в Heroku:**
   ```powershell
   heroku login
   ```

3. **Створіть додаток:**
   ```powershell
   heroku create your-hdrezka-app
   ```
   (замініть `your-hdrezka-app` на унікальну назву)

4. **Завантажте код:**
   ```powershell
   git init
   git add .
   git commit -m "Initial commit"
   git push heroku main
   ```

5. **Запустіть додаток:**
   ```powershell
   heroku ps:scale web=1
   ```

## Крок 3: Отримання URL

Після успішного розгортання ви отримаєте URL типу:
`https://your-hdrezka-app.herokuapp.com`

## Крок 4: Налаштування Discord

1. Перейдіть в Discord Developer Portal
2. В OAuth2 → Redirects додайте: `https://your-hdrezka-app.herokuapp.com/`
3. Використовуйте цей URL в коді

## ⚡ Альтернатива (без Git):

Якщо не хочете використовувати Git, можете:

1. Створити ZIP архів з файлами проекту
2. Використовувати Heroku Dashboard для завантаження
3. Або використати інший хостинг як Railway/Render
