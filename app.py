from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import json
import traceback
import os
import sys
from time import time
from HdRezkaApi import HdRezkaApi

# Логування для діагностики
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=[
    "https://discord.com",
    "https://*.discord.com",
    "https://discordapp.com",
    "https://*.discordapp.com"
])

# Простий кеш в пам'яті. Для продакшену краще використовувати Redis або Memcached.
# Ключ - URL, значення - словник з даними та часом збереження.
CACHE = {}
CACHE_TIMEOUT_SECONDS = 3600 # 1 година

# HTML шаблон (вбудований в код)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HdRezka API Test</title>
    <script src="https://discord.com/api/activities/sdk.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        h2 {
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }
        input, select, button {
            width: 100%;
            padding: 10px;
            margin: 5px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background: #4CAF50;
            color: white;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background: #45a049;
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .result {
            background: #f9f9f9;
            border: 1px solid #ddd;
            padding: 15px;
            border-radius: 4px;
            margin-top: 10px;
            white-space: pre-wrap;
            font-family: monospace;
            max-height: 400px;
            overflow-y: auto;
        }
        .error {
            background: #ffebee;
            border-color: #f44336;
            color: #d32f2f;
        }
        .success {
            background: #e8f5e8;
            border-color: #4CAF50;
            color: #2e7d32;
        }
        .loading {
            color: #ff9800;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        #seasonEpisodeControls {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>🎬 HdRezka API Tester</h2>
        
        <div class="form-group">
            <label for="url">URL сайту:</label>
            <input type="url" id="url" placeholder="https://hdrezka.ag/..." 
                   value="https://hdrezka.me/animation/adventures/31356-arifureta-silneyshiy-remeslennik-v-mire-tv-1-2019.html#t:111-s:1-e:3">
        </div>

        <button onclick="parseContent()">📥 Парсити контент</button>
        <button onclick="testAPI()" style="background: #2196F3; margin-left: 10px;">🧪 Тест API</button>
        <button onclick="testDomains()" style="background: #FF9800; margin-left: 10px;">🌐 Тест доменів</button>
        <div id="parseResult" class="result" style="display: none;"></div>
    </div>

    <div class="container" id="streamContainer" style="display: none;">
        <h2>🎥 Отримати стрім</h2>
        
        <div class="form-group">
            <label for="translation">Переклад:</label>
            <select id="translation"></select>
        </div>

        <div id="seasonEpisodeControls">
            <div class="form-group">
                <label for="season">Сезон:</label>
                <select id="season"></select>
            </div>

            <div class="form-group">
                <label for="episode">Серія:</label>
                <select id="episode"></select>
            </div>
        </div>

        <button onclick="getStream()">🎬 Отримати стрім</button>
        <div id="streamResult" class="result" style="display: none;"></div>
        
        <div id="videoContainer" style="display: none; margin-top: 20px;">
            <h3>📺 Відео плеєр</h3>
            <div class="form-group">
                <label for="qualitySelect">Якість відео:</label>
                <select id="qualitySelect" onchange="changeVideoQuality()"></select>
            </div>
            <video id="videoPlayer" controls style="width: 100%; max-width: 800px; height: auto;">
                Ваш браузер не підтримує відео
            </video>
            <div id="videoInfo" style="margin-top: 10px; font-size: 14px; color: #666;"></div>
        </div>
    </div>

    <script>
        // Discord Activities SDK ініціалізація
        let discordSDK;
        
        async function initializeDiscordSDK() {
            try {
                discordSDK = new DiscordSDK('848279368462499851'); // Замініть на ваш Client ID
                
                const { code } = await discordSDK.commands.authorize({
                    client_id: '848279368462499851', // Замініть на ваш Client ID
                    response_type: 'code',
                    state: '',
                    prompt: 'none',
                    scope: ['identify', 'guilds']
                });
                
                console.log('Discord SDK ініціалізовано успішно');
                
                // Оновлюємо заголовок сторінки для Discord Activities
                document.title = 'HdRezka - Discord Activity';
                
            } catch (error) {
                console.log('Discord SDK не доступний (запуск поза Discord):', error);
                // Якщо не в Discord, працюємо як звичайний сайт
            }
        }
        
        // Ініціалізуємо Discord SDK при завантаженні сторінки
        window.addEventListener('load', initializeDiscordSDK);
        
        const API_BASE = '/api';
        let currentData = null;
        let currentStreamData = null;

        const urlInput = document.getElementById('url');
        const parseResultDiv = document.getElementById('parseResult');
        const streamContainerDiv = document.getElementById('streamContainer');
        const translationSelect = document.getElementById('translation');
        const seasonSelect = document.getElementById('season');
        const episodeSelect = document.getElementById('episode');
        const streamResultDiv = document.getElementById('streamResult');
        const videoContainerDiv = document.getElementById('videoContainer');
        const qualitySelect = document.getElementById('qualitySelect');
        const videoPlayer = document.getElementById('videoPlayer');
        const videoInfoDiv = document.getElementById('videoInfo');
        const seasonEpisodeControls = document.getElementById('seasonEpisodeControls');

        function showResult(element, data, isError = false) {
            element.style.display = 'block';
            element.className = `result ${isError ? 'error' : 'success'}`;
            element.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
        }

        function showLoading(element, message = 'Завантаження...') {
            element.style.display = 'block';
            element.className = 'result loading';
            element.textContent = message;
        }

        async function parseContent() {
            const url = urlInput.value;
            if (!url) {
                alert('Введіть URL!');
                return;
            }

            showLoading(parseResultDiv, 'Парсинг контенту...');
            streamContainerDiv.style.display = 'none';
            videoContainerDiv.style.display = 'none';
            
            try {
                const response = await fetch(`${API_BASE}/parse`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });

                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Не JSON відповідь:', text);
                    throw new Error(`Сервер повернув не JSON дані. Статус: ${response.status}`);
                }

                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Помилка сервера при парсингу');
                }

                currentData = data;
                showResult(parseResultDiv, data);
                
                // Оновлюємо Discord активність
                updateDiscordActivity(data.name || 'Невідомий контент', 'Переглядає контент');
                
                fillTranslations(data.translations);

                if (data.type === 'video.tv_series') {
                    seasonEpisodeControls.style.display = 'block';
                    fillSeasonsAndEpisodes(data);
                } else {
                    seasonEpisodeControls.style.display = 'none';
                }
                
                streamContainerDiv.style.display = 'block';
                
            } catch (error) {
                showResult(parseResultDiv, `Помилка: ${error.message}`, true);
            }
        }

        function fillTranslations(translations) {
            translationSelect.innerHTML = '';
            for (const [name, id] of Object.entries(translations)) {
                const option = document.createElement('option');
                option.value = id;
                option.textContent = name;
                translationSelect.appendChild(option);
            }
        }

        function fillSeasonsAndEpisodes(data) {
            seasonSelect.innerHTML = '';
            episodeSelect.innerHTML = '';

            const selectedTranslatorId = translationSelect.value;
            const translatorName = Object.keys(data.translations).find(key => data.translations[key] === selectedTranslatorId);
            
            if (translatorName && data.seasons && data.seasons[translatorName]) {
                const seasonsInfoForTranslator = data.seasons[translatorName];
                
                for (const [id, name] of Object.entries(seasonsInfoForTranslator.seasons)) {
                    const option = document.createElement('option');
                    option.value = id;
                    option.textContent = name;
                    seasonSelect.appendChild(option);
                }
                
                if (Object.keys(seasonsInfoForTranslator.seasons).length > 0) {
                    const firstSeasonId = Object.keys(seasonsInfoForTranslator.seasons)[0];
                    fillEpisodes(firstSeasonId);
                }
            }
        }

        function fillEpisodes(seasonId) {
            episodeSelect.innerHTML = '';
            
            if (!currentData || !currentData.seasons) return;
            
            const selectedTranslatorId = translationSelect.value;
            const translatorName = Object.keys(currentData.translations).find(key => currentData.translations[key] === selectedTranslatorId);

            if (translatorName && currentData.seasons[translatorName] && 
                currentData.seasons[translatorName].episodes && 
                currentData.seasons[translatorName].episodes[seasonId]) {
                
                const episodes = currentData.seasons[translatorName].episodes[seasonId];
                for (const [id, name] of Object.entries(episodes)) {
                    const option = document.createElement('option');
                    option.value = id;
                    option.textContent = name;
                    episodeSelect.appendChild(option);
                }
            }
        }

        translationSelect.addEventListener('change', function() {
            if (currentData && currentData.type === 'video.tv_series') {
                fillSeasonsAndEpisodes(currentData);
            }
        });

        seasonSelect.addEventListener('change', function() {
            fillEpisodes(this.value);
        });

        async function getStream() {
            const url = urlInput.value;
            const translation = translationSelect.value;
            let season = null;
            let episode = null;

            if (!url || !translation) {
                alert('Спочатку парсіть контент та виберіть переклад!');
                return;
            }

            if (currentData && currentData.type === 'video.tv_series') {
                season = seasonSelect.value;
                episode = episodeSelect.value;
                if (!season || !episode) {
                    alert('Для серіалу виберіть сезон і серію!');
                    return;
                }
            }

            showLoading(streamResultDiv, 'Отримання стріму...');
            videoContainerDiv.style.display = 'none';
            
            try {
                const requestData = { url, translation };
                if (season) requestData.season = season;
                if (episode) requestData.episode = episode;

                const response = await fetch(`${API_BASE}/stream`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestData)
                });

                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Не JSON відповідь для stream:', text);
                    throw new Error(`Сервер повернув не JSON дані. Статус: ${response.status}`);
                }

                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Помилка сервера при отриманні стріму');
                }

                currentStreamData = data;
                showResult(streamResultDiv, data);
                
                if (data.videos && Object.keys(data.videos).length > 0) {
                    showVideoPlayer(data.videos);
                } else {
                    showResult(streamResultDiv, 'Не знайдено доступних відеопотоків.', true);
                }
                
            } catch (error) {
                showResult(streamResultDiv, `Помилка: ${error.message}`, true);
            }
        }

        function showVideoPlayer(videos) {
            const qualities = Object.keys(videos).sort((a, b) => {
                const aNum = parseInt(a);
                const bNum = parseInt(b);
                return bNum - aNum;
            });
            
            qualitySelect.innerHTML = '';
            qualities.forEach(quality => {
                const option = document.createElement('option');
                option.value = quality;
                option.textContent = quality;
                qualitySelect.appendChild(option);
            });
            
            if (qualities.length > 0) {
                const bestQuality = qualities[0];
                qualitySelect.value = bestQuality;
                videoPlayer.src = videos[bestQuality];
                videoPlayer.load();
                updateVideoInfo(bestQuality, videos[bestQuality]);
            }
            
            videoContainerDiv.style.display = 'block';
        }

        function changeVideoQuality() {
            const selectedQuality = qualitySelect.value;
            
            if (currentStreamData && currentStreamData.videos[selectedQuality]) {
                const currentTime = videoPlayer.currentTime;
                videoPlayer.src = currentStreamData.videos[selectedQuality];
                videoPlayer.load();
                videoPlayer.currentTime = currentTime;
                videoPlayer.play();
                updateVideoInfo(selectedQuality, currentStreamData.videos[selectedQuality]);
            }
        }

        function updateVideoInfo(quality, url) {
            const urlShort = url.length > 100 ? url.substring(0, 100) + '...' : url;
            
            let seasonEpisode = '';
            if (currentStreamData.season && currentStreamData.episode) {
                seasonEpisode = `Сезон ${currentStreamData.season}, Серія ${currentStreamData.episode} | `;
            }
            
            videoInfoDiv.innerHTML = `
                <strong>Якість:</strong> ${quality} | 
                ${seasonEpisode}
                <strong>URL:</strong> <a href="${url}" target="_blank" style="color: #4CAF50;">${urlShort}</a>
            `;
            
            // Оновлюємо статус Discord Activities
            updateDiscordActivity(currentData?.name || 'Невідомий контент', 'Дивиться відео');
        }
        
        // Функція для оновлення статусу Discord Activities
        async function updateDiscordActivity(details, state) {
            if (discordSDK) {
                try {
                    await discordSDK.commands.setActivity({
                        activity: {
                            details: details,
                            state: state,
                            assets: {
                                large_image: 'hdrezka_logo',
                                large_text: 'HdRezka API'
                            },
                            timestamps: {
                                start: Math.floor(Date.now() / 1000)
                            }
                        }
                    });
                } catch (error) {
                    console.log('Помилка оновлення Discord активності:', error);
                }
            }
        }
        
        // Функція для очищення Discord активності
        async function clearDiscordActivity() {
            if (discordSDK) {
                try {
                    await discordSDK.commands.setActivity({
                        activity: null
                    });
                } catch (error) {
                    console.log('Помилка очищення Discord активності:', error);
                }
            }
        }
        
        // Функція для тестування API
        async function testAPI() {
            const parseResultDiv = document.getElementById('parseResult');
            showLoading(parseResultDiv, 'Тестування API...');
            
            try {
                const response = await fetch(`${API_BASE}/test`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ test: 'data' })
                });
                
                console.log('Тест API - статус:', response.status);
                console.log('Тест API - заголовки:', response.headers);
                
                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('API повернув не JSON:', text);
                    showResult(parseResultDiv, `API повернув не JSON дані:\n${text}`, true);
                    return;
                }
                
                const data = await response.json();
                showResult(parseResultDiv, data);
                
                console.log('API тест успішний:', data);
                
            } catch (error) {
                console.error('Помилка тесту API:', error);
                showResult(parseResultDiv, `Помилка тесту API: ${error.message}`, true);
            }
        }
        
        // Функція для тестування доменів HdRezka
        async function testDomains() {
            const parseResultDiv = document.getElementById('parseResult');
            showLoading(parseResultDiv, 'Тестування доменів HdRezka...');
            
            const domains = [
                'https://rezka.ag',
                'https://hdrezka.ag', 
                'https://hdrezka.me',
                'https://hdrezka.ua'
            ];
            
            const results = [];
            
            for (const domain of domains) {
                try {
                    console.log(`Тестуємо домен: ${domain}`);
                    const response = await fetch(domain, {
                        method: 'HEAD',
                        mode: 'no-cors',
                        timeout: 5000
                    });
                    
                    results.push({
                        domain: domain,
                        status: 'success',
                        message: 'Доступний'
                    });
                    
                } catch (error) {
                    console.log(`Домен ${domain} недоступний:`, error);
                    results.push({
                        domain: domain,
                        status: 'error',
                        message: error.message
                    });
                }
            }
            
            showResult(parseResultDiv, {
                message: 'Результати тестування доменів',
                results: results,
                timestamp: new Date().toISOString()
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "HdRezka API",
        "description": "Перегляд фільмів та серіалів з HdRezka через Discord Activities",
        "version": "1.0.0",
        "author": "Your Name",
        "repository": "https://github.com/yourusername/hdrezka-python-app",
        "entrypoint": "/",
        "supported_platforms": ["desktop"],
        "tags": ["entertainment", "video", "streaming"],
        "permissions": {
            "identify": {
                "description": "Отримати базову інформацію про користувача"
            }
        },
        "ui": {
            "width": 1200,
            "height": 800,
            "resizable": True
        },
        "assets": {
            "large_image": "https://your-domain.com/logo-large.png",
            "small_image": "https://your-domain.com/logo-small.png"
        }
    })

@app.route('/api/test', methods=['GET', 'POST'])
def test_api():
    """Тестовий endpoint для перевірки роботи API"""
    return jsonify({
        'status': 'success',
        'message': 'API працює',
        'timestamp': time(),
        'method': request.method,
        'headers': dict(request.headers),
        'data': request.get_json() if request.is_json else None
    })

@app.route('/api/parse', methods=['POST'])
def parse_content():
    try:
        # Перевіряємо, чи запит містить JSON
        if not request.is_json:
            return jsonify({'error': 'Запит повинен містити JSON дані'}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Порожній JSON запит'}), 400
            
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL є обов\'язковим'}), 400
        
        # Перевіряємо кеш
        cached_item = CACHE.get(url)
        if cached_item and (time() - cached_item['timestamp'] < CACHE_TIMEOUT_SECONDS):
            print(f"Повернення результату з кешу для URL: {url}")
            return jsonify(cached_item['data'])

        print(f"Кеш не знайдено або застарів. Виконую парсинг для URL: {url}")
        # Створюємо екземпляр API
        rezka = HdRezkaApi(url)
        
        # Отримуємо базову інформацію
        # Використовуємо rezka.id, rezka.name, rezka.type, щоб спрацювали @property
        result = {
            'name': rezka.name,
            'type': rezka.type,
            'id': rezka.id,
            'translations': rezka.getTranslations()
        }
        
        # Якщо це серіал, отримуємо сезони та епізоди
        if rezka.type == 'video.tv_series':
            result['seasons'] = rezka.getSeasons()
        
        # Зберігаємо результат в кеш
        CACHE[url] = {
            'data': result,
            'timestamp': time()
        }

        return jsonify(result)
        
    except Exception as e:
        print(f"Помилка при парсингу: {str(e)}")
        print(traceback.format_exc())
        
        # Додаткова інформація про помилку для користувача
        error_message = str(e)
        if "403" in error_message:
            error_message = "Сайт тимчасово заблокував доступ. Спробуйте пізніше або використайте інший URL."
        elif "404" in error_message:
            error_message = "URL не знайдено. Перевірте правильність посилання."
        elif "timeout" in error_message.lower():
            error_message = "Час очікування вичерпано. Спробуйте ще раз."
        
        return jsonify({'error': error_message}), 500

@app.route('/api/stream', methods=['POST'])
def get_stream():
    try:
        # Перевіряємо, чи запит містить JSON
        if not request.is_json:
            return jsonify({'error': 'Запит повинен містити JSON дані'}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Порожній JSON запит'}), 400
            
        url = data.get('url')
        translation = data.get('translation')
        season = data.get('season')
        episode = data.get('episode')
        
        if not url or not translation:
            return jsonify({'error': 'URL та переклад є обов\'язковими'}), 400
        
        # Створюємо екземпляр API
        rezka = HdRezkaApi(url)
        
        # Отримуємо стрім
        stream = rezka.getStream(season, episode, translation)
        
        # Перевіряємо, чи отримали ми дані
        if not stream or not hasattr(stream, 'videos'):
            return jsonify({'error': 'Не вдалося отримати стрім'}), 404
        
        result = {
            'videos': stream.videos,
            'season': stream.season,
            'episode': stream.episode
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Помилка при отриманні стріму: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import os
    
    # Діагностика середовища
    logger.info(f"Python версія: {sys.version}")
    logger.info(f"Поточний робочий каталог: {os.getcwd()}")
    logger.info(f"Доступні змінні середовища: {list(os.environ.keys())}")
    
    port = int(os.environ.get('PORT', 5001))
    logger.info(f"Запуск на порту: {port}")
    
    # Перевірка залежностей
    try:
        import flask
        import requests
        import bs4
        logger.info("Всі залежності успішно імпортовані")
    except ImportError as e:
        logger.error(f"Помилка імпорту: {e}")
        sys.exit(1)
    
    app.run(debug=False, host='0.0.0.0', port=port)