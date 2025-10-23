from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
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

# SocketIO для синхронізації
socketio = SocketIO(app, cors_allowed_origins="*")

# Простий кеш в пам'яті. Для продакшену краще використовувати Redis або Memcached.
# Ключ - URL, значення - словник з даними та часом збереження.
CACHE = {}
CACHE_TIMEOUT_SECONDS = 3600 # 1 година

# Watch Together система
WATCH_ROOMS = {}  # Кімнати для синхронізації
ROOM_TIMEOUT = 3600  # 1 година без активності

# SocketIO кімнати
SOCKET_ROOMS = {}  # Кімнати для SocketIO синхронізації

# HTML шаблон (вбудований в код)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HdRezka API Test</title>
    
    <!-- Discord Activities мета-теги -->
    <meta property="og:title" content="HdRezka - Спільний перегляд">
    <meta property="og:description" content="Дивіться фільми та серіали разом з друзями">
    <meta property="og:type" content="website">
    
    <!-- Discord перезапише цей CSP своїм -->
    <meta http-equiv="Content-Security-Policy" content="default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;">
    
    <!-- Crossorigin для відео -->
    <script>
        // Додаємо crossorigin="anonymous" до всіх відео елементів
        document.addEventListener('DOMContentLoaded', function() {
            const videos = document.querySelectorAll('video');
            videos.forEach(video => {
                video.setAttribute('crossorigin', 'anonymous');
                console.log('✅ Встановлено crossorigin для відео');
            });
        });
    </script>
    
    <script>
        // Перевіряємо Discord SDK
        function checkDiscordSDK() {
            return new Promise((resolve, reject) => {
                // Перевіряємо, чи доступний Discord SDK
                if (typeof DiscordSDK !== 'undefined') {
                    console.log('Discord SDK доступний');
                    resolve();
                    return;
                }
                
                // Перевіряємо, чи ми в Discord Activities
                if (window.location.hostname.includes('discordsays.com')) {
                    console.log('В Discord Activities - чекаємо SDK...');
                    // Чекаємо трохи для завантаження SDK
                    setTimeout(() => {
                        if (typeof DiscordSDK !== 'undefined') {
                            console.log('Discord SDK завантажено після очікування');
                            resolve();
                        } else {
                            console.log('Discord SDK не завантажено в Discord Activities - працюємо без SDK');
                            // В Discord Activities навіть без SDK
                            resolve();
                        }
                    }, 3000);
                } else {
                    console.log('Не в Discord Activities - працюємо локально');
                    reject(new Error('Не в Discord Activities'));
                }
            });
        }
    </script>
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
            border: none;
            outline: none;
            user-select: none;
            -webkit-user-select: none;
            -moz-user-select: none;
            -ms-user-select: none;
            touch-action: manipulation;
        }
        button:hover {
            background: #45a049;
        }
        button:active {
            background: #3d8b40;
            transform: translateY(1px);
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        button:focus {
            outline: 2px solid #4CAF50;
            outline-offset: 2px;
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
        
        /* Спеціальні стилі для Discord Activities */
        button:focus-visible {
            outline: 2px solid #4CAF50;
            outline-offset: 2px;
        }
        
        button:not(:disabled):hover {
            box-shadow: 0 2px 8px rgba(76, 175, 80, 0.3);
        }
        
        button:not(:disabled):active {
            box-shadow: 0 1px 4px rgba(76, 175, 80, 0.3);
        }
        
        /* Покращення для input полів */
        input:focus, select:focus {
            outline: 2px solid #4CAF50;
            outline-offset: 2px;
            border-color: #4CAF50;
        }
        
        /* Анімації для кращого UX */
        .result {
            transition: all 0.3s ease;
        }
        
        .container {
            transition: all 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>🎬 HdRezka API Tester</h2>
        <div id="modeIndicator" style="background: #e3f2fd; border: 1px solid #2196f3; padding: 10px; border-radius: 4px; margin-bottom: 20px; text-align: center;">
            <span id="modeText">🔄 Перевірка режиму роботи...</span>
        </div>
        
        <div class="form-group">
            <label for="url">URL сайту:</label>
            <input type="url" id="url" placeholder="https://hdrezka.ag/..." 
                   value="https://hdrezka.me/animation/adventures/31356-arifureta-silneyshiy-remeslennik-v-mire-tv-1-2019.html#t:111-s:1-e:3">
        </div>

        <button data-action="parse">📥 Парсити контент</button>
        <button data-action="test" style="background: #2196F3; margin-left: 10px;">🧪 Тест API</button>
        <button data-action="domains" style="background: #FF9800; margin-left: 10px;">🌐 Тест доменів</button>
        <button data-action="debug" style="background: #9C27B0; margin-left: 10px;">🔍 Debug</button>
        <button data-action="routes" style="background: #607D8B; margin-left: 10px;">🛣️ Маршрути</button>
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

        <button data-action="stream">🎬 Отримати стрім</button>
        <button data-action="stream-test" style="background: #E91E63; margin-left: 10px;">🧪 Тест стріму</button>
        <button data-action="test-video" style="background: #FF5722; margin-left: 10px;">🎥 Тест відео</button>
        <button data-action="test-hdrezka" style="background: #9C27B0; margin-left: 10px;">🔍 Тест HdRezka</button>
        <button data-action="test-direct" style="background: #4CAF50; margin-left: 10px;">🚀 Прямі відео</button>
        <button data-action="test-blob" style="background: #FF9800; margin-left: 10px;">💾 Тест Blob</button>
        
        <!-- Watch Together кнопки -->
        <div style="margin-top: 20px; padding: 15px; background: #2C2F33; border-radius: 8px; border: 2px solid #5865F2;">
            <h3 style="color: #5865F2; margin-top: 0;">👥 Watch Together</h3>
            <p style="color: #B9BBBE; font-size: 14px; margin-bottom: 15px;">
                Синхронізуйте перегляд з друзями! Відкрийте відео на своєму пристрої, а Discord буде синхронізувати паузи та час.
            </p>
            <button data-action="create-room" style="background: #5865F2; margin-right: 10px;">🏠 Створити кімнату</button>
            <button data-action="join-room" style="background: #57F287; margin-right: 10px;">🚪 Приєднатися</button>
            <button data-action="list-rooms" style="background: #FEE75C; color: #000; margin-right: 10px;">📋 Список кімнат</button>
            <a href="/controller" target="_blank" style="background: #FF6B6B; color: white; text-decoration: none; padding: 15px 30px; border-radius: 5px; display: inline-block; margin: 5px;">🎮 Контролер</a>
        </div>
        <div id="streamResult" class="result" style="display: none;"></div>
        
        <div id="videoContainer" style="display: none; margin-top: 20px;">
            <h3>📺 Відео плеєр</h3>
            <div class="form-group">
                <label for="qualitySelect">Якість відео:</label>
                <select id="qualitySelect" onchange="changeVideoQuality()"></select>
            </div>
            <video id="videoPlayer" 
                   controls 
                   crossorigin="anonymous"
                   preload="metadata"
                   style="width: 100%; max-width: 800px; height: auto;">
                Ваш браузер не підтримує відео
            </video>
            <div id="videoInfo" style="margin-top: 10px; font-size: 14px; color: #666;"></div>
        </div>
    </div>

    <script>
        // Discord Activities SDK ініціалізація
        let discordSDK;
        
        async function initializeDiscordSDK() {
            const modeIndicator = document.getElementById('modeIndicator');
            const modeText = document.getElementById('modeText');
            
            try {
                // Перевіряємо Discord SDK
                await checkDiscordSDK();
                
                // Перевіряємо, чи доступний DiscordSDK
                if (typeof DiscordSDK !== 'undefined') {
                    discordSDK = new DiscordSDK('1382172131051307038');
                    
                    const { code } = await discordSDK.commands.authorize({
                        client_id: '1382172131051307038',
                        response_type: 'code',
                        state: '',
                        prompt: 'none',
                        scope: ['identify', 'guilds']
                    });
                    
                    console.log('Discord SDK ініціалізовано успішно');
                    document.title = 'HdRezka - Discord Activity';
                    
                    modeIndicator.style.background = '#e8f5e8';
                    modeIndicator.style.borderColor = '#4caf50';
                    modeText.innerHTML = '🎮 Discord Activities режим - працюємо в Discord!';
                } else {
                    console.log('Discord SDK недоступний - працюємо в Discord Activities без SDK');
                    document.title = 'HdRezka - Discord Activity';
                    
                    modeIndicator.style.background = '#e8f5e8';
                    modeIndicator.style.borderColor = '#4caf50';
                    modeText.innerHTML = '🎮 Discord Activities режим - працюємо в Discord!';
                }
                
            } catch (error) {
                console.log('Discord SDK не доступний (запуск поза Discord):', error?.message || error);
                
                modeIndicator.style.background = '#fff3e0';
                modeIndicator.style.borderColor = '#ff9800';
                modeText.innerHTML = '🌐 Локальний режим - працюємо як звичайний сайт';
            }
        }
        
        // Ініціалізуємо Discord SDK при завантаженні сторінки
        window.addEventListener('load', initializeDiscordSDK);
        
        // Додаємо спеціальні обробники для Discord Activities
        document.addEventListener('DOMContentLoaded', function() {
            // Додаємо обробники для всіх кнопок
            const buttons = document.querySelectorAll('button');
            buttons.forEach(button => {
                // Додаємо обробники подій для Discord Activities
                button.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // Додаємо візуальний фідбек
                    this.style.transform = 'scale(0.95)';
                    setTimeout(() => {
                        this.style.transform = '';
                    }, 150);
                    
                    // Викликаємо функцію кнопки
                    const onclick = this.getAttribute('onclick');
                    const dataAction = this.getAttribute('data-action');
                    
                    if (onclick) {
                        try {
                            eval(onclick);
                        } catch (error) {
                            console.error('Помилка виконання onclick:', error);
                        }
                    } else if (dataAction) {
                        // Альтернативний спосіб через data-action
                        try {
                            switch(dataAction) {
                                case 'parse':
                                    parseContent();
                                    break;
                                case 'test':
                                    testAPI();
                                    break;
                                case 'domains':
                                    testDomains();
                                    break;
                                case 'stream':
                                    getStream();
                                    break;
                                case 'debug':
                                    debugInfo();
                                    break;
                                case 'routes':
                                    listRoutes();
                                    break;
                                case 'stream-test':
                                    testStream();
                                    break;
                                case 'test-video':
                                    testVideo();
                                    break;
                                case 'test-hdrezka':
                                    testHdRezka();
                                    break;
                                case 'test-direct':
                                    testDirect();
                                    break;
                                case 'test-blob':
                                    testBlob();
                                    break;
                                case 'create-room':
                                    createWatchRoom();
                                    break;
                                case 'join-room':
                                    joinWatchRoom();
                                    break;
                                case 'list-rooms':
                                    listWatchRooms();
                                    break;
                                default:
                                    console.log('Невідома дія:', dataAction);
                            }
                        } catch (error) {
                            console.error('Помилка виконання data-action:', error);
                        }
                    }
                });
                
                // Додаємо обробники для клавіатури
                button.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        this.click();
                    }
                });
            });
            
            // Додаємо обробники для input полів
            const inputs = document.querySelectorAll('input, select');
            inputs.forEach(input => {
                input.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        // Шукаємо кнопку після поля
                        const nextButton = this.parentElement.querySelector('button');
                        if (nextButton) {
                            nextButton.click();
                        }
                    }
                });
            });
        });
        
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
            console.log('=== showVideoPlayer викликано ===');
            console.log('Відео:', videos);
            
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
                
                console.log(`Встановлюємо відео якості ${bestQuality}`);
                console.log(`URL: ${videos[bestQuality]}`);
                
                // ВАЖЛИВО: Завантажуємо відео та створюємо Blob URL
                loadVideoAsBlob(videos[bestQuality], bestQuality);
            }
            
            videoContainerDiv.style.display = 'block';
            console.log('✅ Відео контейнер показано');
        }
        
        // НОВА функція для завантаження відео як Blob
        async function loadVideoAsBlob(videoUrl, quality) {
            try {
                console.log(`🔄 Завантаження відео як Blob: ${videoUrl}`);
                
                // Показуємо індикатор завантаження
                videoInfoDiv.innerHTML = '⏳ Завантаження відео...';
                
                // Завантажуємо відео
                const response = await fetch(videoUrl);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                console.log('✅ Відповідь отримано');
                console.log('Content-Type:', response.headers.get('content-type'));
                console.log('Content-Length:', response.headers.get('content-length'));
                
                // Отримуємо як blob з прогресом
                const contentLength = response.headers.get('content-length');
                const total = parseInt(contentLength, 10);
                let loaded = 0;
                
                const reader = response.body.getReader();
                const chunks = [];
                
                while (true) {
                    const { done, value } = await reader.read();
                    
                    if (done) break;
                    
                    chunks.push(value);
                    loaded += value.length;
                    
                    // Оновлюємо прогрес
                    if (total) {
                        const percent = ((loaded / total) * 100).toFixed(1);
                        videoInfoDiv.innerHTML = `⏳ Завантажено: ${percent}% (${(loaded / 1024 / 1024).toFixed(1)} MB / ${(total / 1024 / 1024).toFixed(1)} MB)`;
                    } else {
                        videoInfoDiv.innerHTML = `⏳ Завантажено: ${(loaded / 1024 / 1024).toFixed(1)} MB`;
                    }
                }
                
                console.log('✅ Відео повністю завантажено');
                
                // Створюємо Blob
                const blob = new Blob(chunks, { type: 'video/mp4' });
                const blobUrl = URL.createObjectURL(blob);
                
                console.log('✅ Blob URL створено:', blobUrl);
                
                // Встановлюємо Blob URL для відео
                videoPlayer.src = blobUrl;
                
                // Зберігаємо Blob URL для очищення пізніше
                if (window.currentBlobUrl) {
                    URL.revokeObjectURL(window.currentBlobUrl);
                }
                window.currentBlobUrl = blobUrl;
                
                // Обробники подій
                videoPlayer.onerror = function(e) {
                    console.error('❌ ПОМИЛКА ВІДЕО:', e);
                    console.error('Error code:', videoPlayer.error?.code);
                    console.error('Error message:', videoPlayer.error?.message);
                    
                    videoInfoDiv.innerHTML = `
                        <span style="color: red; font-weight: bold;">
                            ❌ Помилка відтворення відео
                            <br>Код: ${videoPlayer.error?.code}
                        </span>
                    `;
                };
                
                videoPlayer.onloadedmetadata = function() {
                    console.log('✅ Метадані завантажено');
                    console.log('Duration:', videoPlayer.duration);
                    updateVideoInfo(quality, videoUrl);
                };
                
                videoPlayer.oncanplay = function() {
                    console.log('✅ Відео готове до відтворення');
                };
                
                videoPlayer.load();
                
            } catch (error) {
                console.error('❌ Помилка завантаження Blob:', error);
                videoInfoDiv.innerHTML = `
                    <span style="color: red; font-weight: bold;">
                        ❌ Помилка завантаження: ${error.message}
                    </span>
                `;
            }
        }

        function changeVideoQuality() {
            const selectedQuality = qualitySelect.value;
            
            if (currentStreamData && currentStreamData.videos[selectedQuality]) {
                const currentTime = videoPlayer.currentTime;
                
                // Завантажуємо нову якість як Blob
                loadVideoAsBlob(currentStreamData.videos[selectedQuality], selectedQuality)
                    .then(() => {
                        // Відновлюємо позицію
                videoPlayer.currentTime = currentTime;
                videoPlayer.play();
                    });
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
                    let activity = {
                        details: details,
                        state: state,
                        assets: {
                            large_image: 'hdrezka_logo',
                            large_text: 'HdRezka - Спільний перегляд'
                        },
                        timestamps: {
                            start: Math.floor(Date.now() / 1000)
                        }
                    };
                    
                    // Додаємо інформацію про Watch Together
                    if (currentRoomId) {
                        if (isHost) {
                            activity.details = `👑 Хост кімнати: ${details}`;
                            activity.state = `Кімната: ${currentRoomId} | ${state}`;
                            activity.assets.small_image = 'crown';
                            activity.assets.small_text = 'Хост кімнати';
                        } else {
                            activity.details = `👥 Гість кімнати: ${details}`;
                            activity.state = `Кімната: ${currentRoomId} | Синхронізація з хостом`;
                            activity.assets.small_image = 'users';
                            activity.assets.small_text = 'Гість кімнати';
                        }
                    }
                    
                    await discordSDK.commands.setActivity({
                        activity: activity
                    });
                    
                    console.log('✅ Discord Activity оновлено');
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
        
        // Функція для debug інформації
        async function debugInfo() {
            const parseResultDiv = document.getElementById('parseResult');
            showLoading(parseResultDiv, 'Отримання debug інформації...');
            
            try {
                const response = await fetch(`${API_BASE}/debug`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                console.log('Debug - статус:', response.status);
                
                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Debug повернув не JSON:', text);
                    showResult(parseResultDiv, `Debug повернув не JSON дані:\n${text}`, true);
                    return;
                }
                
                const data = await response.json();
                showResult(parseResultDiv, data);
                
                console.log('Debug успішний:', data);
                
            } catch (error) {
                console.error('Помилка debug:', error);
                showResult(parseResultDiv, `Помилка debug: ${error.message}`, true);
            }
        }
        
        // Функція для перевірки маршрутів
        async function listRoutes() {
            const parseResultDiv = document.getElementById('parseResult');
            showLoading(parseResultDiv, 'Отримання списку маршрутів...');
            
            try {
                const response = await fetch(`${API_BASE}/routes`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                console.log('Routes - статус:', response.status);
                
                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Routes повернув не JSON:', text);
                    showResult(parseResultDiv, `Routes повернув не JSON дані:\n${text}`, true);
                    return;
                }
                
                const data = await response.json();
                showResult(parseResultDiv, data);
                
                console.log('Routes успішний:', data);
                
            } catch (error) {
                console.error('Помилка routes:', error);
                showResult(parseResultDiv, `Помилка routes: ${error.message}`, true);
            }
        }
        
        // Функція для тестування стріму
        async function testStream() {
            const streamResultDiv = document.getElementById('streamResult');
            showLoading(streamResultDiv, 'Тестування стріму...');
            
            try {
                const testData = {
                    url: 'https://example.com/test',
                    translation: '1',
                    season: '1',
                    episode: '1'
                };
                
                const response = await fetch(`${API_BASE}/stream-test`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(testData)
                });
                
                console.log('Stream test - статус:', response.status);
                
                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Stream test повернув не JSON:', text);
                    showResult(streamResultDiv, `Stream test повернув не JSON дані:\n${text}`, true);
                    return;
                }
                
                const data = await response.json();
                showResult(streamResultDiv, data);
                
                console.log('Stream test успішний:', data);
                
            } catch (error) {
                console.error('Помилка stream test:', error);
                showResult(streamResultDiv, `Помилка stream test: ${error.message}`, true);
            }
        }
        
        // Функція для тестування відео
        async function testVideo() {
            const streamResultDiv = document.getElementById('streamResult');
            showLoading(streamResultDiv, 'Тестування відео...');
            
            try {
                const response = await fetch(`${API_BASE}/test-video`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                console.log('Video test - статус:', response.status);
                
                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Video test повернув не JSON:', text);
                    showResult(streamResultDiv, `Video test повернув не JSON дані:\n${text}`, true);
                    return;
                }
                
                const data = await response.json();
                showResult(streamResultDiv, data);
                
                console.log('Video test успішний:', data);
                
            } catch (error) {
                console.error('Помилка video test:', error);
                showResult(streamResultDiv, `Помилка video test: ${error.message}`, true);
            }
        }
        
        // Функція для тестування HdRezka
        async function testHdRezka() {
            const streamResultDiv = document.getElementById('streamResult');
            showLoading(streamResultDiv, 'Тестування HdRezka...');
            
            try {
                const response = await fetch(`${API_BASE}/test-hdrezka`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                console.log('HdRezka test - статус:', response.status);
                
                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('HdRezka test повернув не JSON:', text);
                    showResult(streamResultDiv, `HdRezka test повернув не JSON дані:\n${text}`, true);
                    return;
                }
                
                const data = await response.json();
                showResult(streamResultDiv, data);
                
                console.log('HdRezka test успішний:', data);
                
            } catch (error) {
                console.error('Помилка HdRezka test:', error);
                showResult(streamResultDiv, `Помилка HdRezka test: ${error.message}`, true);
            }
        }
        
        // Функція для тестування прямих відео
        async function testDirect() {
            const streamResultDiv = document.getElementById('streamResult');
            showLoading(streamResultDiv, 'Тестування прямих відео...');
            
            try {
                const response = await fetch(`${API_BASE}/test-direct`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                console.log('Direct test - статус:', response.status);
                
                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Direct test повернув не JSON:', text);
                    showResult(streamResultDiv, `Direct test повернув не JSON дані:\n${text}`, true);
                    return;
                }
                
                const data = await response.json();
                showResult(streamResultDiv, data);
                
                console.log('Direct test успішний:', data);
                
            } catch (error) {
                console.error('Помилка Direct test:', error);
                showResult(streamResultDiv, `Помилка Direct test: ${error.message}`, true);
            }
        }
        
        // Функція для тестування Blob
        async function testBlob() {
            const streamResultDiv = document.getElementById('streamResult');
            showLoading(streamResultDiv, 'Тестування Blob...');
            
            try {
                const response = await fetch(`${API_BASE}/test-blob`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                console.log('Blob test - статус:', response.status);
                
                // Перевіряємо, чи відповідь є JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Blob test повернув не JSON:', text);
                    showResult(streamResultDiv, `Blob test повернув не JSON дані:\n${text}`, true);
                    return;
                }
                
                const data = await response.json();
                showResult(streamResultDiv, data);
                
                console.log('Blob test успішний:', data);
                
            } catch (error) {
                console.error('Помилка Blob test:', error);
                showResult(streamResultDiv, `Помилка Blob test: ${error.message}`, true);
            }
        }
        
        // ===== WATCH TOGETHER СИСТЕМА =====
        
        let currentRoomId = null;
        let isHost = false;
        let syncInterval = null;
        
        // Створення кімнати
        async function createWatchRoom() {
            const streamResultDiv = document.getElementById('streamResult');
            showLoading(streamResultDiv, 'Створення кімнати...');
            
            try {
                if (!currentStreamData || !currentStreamData.videos) {
                    showResult(streamResultDiv, 'Спочатку отримайте стрім!', true);
                    return;
                }
                
                const videoUrl = Object.values(currentStreamData.videos)[0];
                const videoTitle = document.getElementById('url').value || 'Невідоме відео';
                
                const response = await fetch(`${API_BASE}/watch/create-room`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        host_id: 'user_' + Math.random().toString(36).substr(2, 9),
                        video_url: videoUrl,
                        video_title: videoTitle
                    })
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    currentRoomId = data.room_id;
                    isHost = true;
                    
                    showResult(streamResultDiv, {
                        message: '✅ Кімната створена!',
                        room_id: data.room_id,
                        video_title: data.video_title,
                        instructions: [
                            '1. Поділіться кодом кімнати з друзями',
                            '2. Відкрийте відео на своєму пристрої',
                            '3. Discord буде синхронізувати перегляд',
                            '4. Ви - хост, ви контролюєте відтворення'
                        ]
                    });
                    
                    // Запускаємо синхронізацію
                    startSync();
                    
                    console.log('🏠 Кімната створена:', data.room_id);
                } else {
                    showResult(streamResultDiv, `Помилка: ${data.error}`, true);
                }
                
            } catch (error) {
                console.error('Помилка створення кімнати:', error);
                showResult(streamResultDiv, `Помилка: ${error.message}`, true);
            }
        }
        
        // Приєднання до кімнати
        async function joinWatchRoom() {
            const roomId = prompt('Введіть код кімнати:');
            if (!roomId) return;
            
            const streamResultDiv = document.getElementById('streamResult');
            showLoading(streamResultDiv, 'Приєднання до кімнати...');
            
            try {
                const response = await fetch(`${API_BASE}/watch/join-room/${roomId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: 'user_' + Math.random().toString(36).substr(2, 9)
                    })
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    currentRoomId = roomId;
                    isHost = false;
                    
                    showResult(streamResultDiv, {
                        message: '✅ Приєднано до кімнати!',
                        room_id: data.room_id,
                        video_title: data.video_title,
                        video_url: data.video_url,
                        viewers_count: data.viewers_count,
                        instructions: [
                            '1. Відкрийте відео за посиланням вище',
                            '2. Discord буде синхронізувати з хостом',
                            '3. Ви - гість, слідкуйте за хостом'
                        ]
                    });
                    
                    // Запускаємо синхронізацію
                    startSync();
                    
                    console.log('🚪 Приєднано до кімнати:', roomId);
                } else {
                    showResult(streamResultDiv, `Помилка: ${data.error}`, true);
                }
                
            } catch (error) {
                console.error('Помилка приєднання:', error);
                showResult(streamResultDiv, `Помилка: ${error.message}`, true);
            }
        }
        
        // Список кімнат
        async function listWatchRooms() {
            const streamResultDiv = document.getElementById('streamResult');
            showLoading(streamResultDiv, 'Завантаження кімнат...');
            
            try {
                const response = await fetch(`${API_BASE}/watch/rooms`);
                const data = await response.json();
                
                if (data.status === 'success') {
                    showResult(streamResultDiv, {
                        message: `Знайдено ${data.total} активних кімнат`,
                        rooms: data.rooms,
                        instructions: [
                            'Натисніть "🚪 Приєднатися" та введіть код кімнати',
                            'Або створіть нову кімнату кнопкою "🏠 Створити кімнату"'
                        ]
                    });
                } else {
                    showResult(streamResultDiv, `Помилка: ${data.error}`, true);
                }
                
            } catch (error) {
                console.error('Помилка списку кімнат:', error);
                showResult(streamResultDiv, `Помилка: ${error.message}`, true);
            }
        }
        
        // Запуск синхронізації
        function startSync() {
            if (syncInterval) {
                clearInterval(syncInterval);
            }
            
            syncInterval = setInterval(async () => {
                if (!currentRoomId) return;
                
                try {
                    if (isHost) {
                        // Хост відправляє стан
                        if (videoPlayer && !videoPlayer.paused) {
                            await syncRoomState(videoPlayer.paused, videoPlayer.currentTime);
                        }
                    } else {
                        // Гість отримує стан
                        const response = await fetch(`${API_BASE}/watch/room/${currentRoomId}`);
                        const data = await response.json();
                        
                        if (data.status === 'success' && videoPlayer) {
                            // Синхронізуємо з хостом
                            const timeDiff = Math.abs(videoPlayer.currentTime - data.current_time);
                            
                            if (timeDiff > 2) { // Якщо різниця більше 2 секунд
                                videoPlayer.currentTime = data.current_time;
                                console.log(`🔄 Синхронізація: ${data.current_time.toFixed(1)}s`);
                            }
                            
                            if (videoPlayer.paused !== !data.is_playing) {
                                if (data.is_playing) {
                                    videoPlayer.play().catch(e => console.log('Автозапуск заблоковано'));
                                } else {
                                    videoPlayer.pause();
                                }
                                console.log(`🔄 Синхронізація: ${data.is_playing ? 'play' : 'pause'}`);
                            }
                        }
                    }
                } catch (error) {
                    console.error('Помилка синхронізації:', error);
                }
            }, 1000); // Синхронізація кожну секунду
            
            console.log('🔄 Синхронізація запущена');
        }
        
        // Відправка стану кімнати
        async function syncRoomState(isPlaying, currentTime) {
            if (!currentRoomId || !isHost) return;
            
            try {
                await fetch(`${API_BASE}/watch/sync/${currentRoomId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: 'host',
                        is_playing: !isPlaying,
                        current_time: currentTime
                    })
                });
            } catch (error) {
                console.error('Помилка відправки стану:', error);
            }
        }
        
        // Очищення Blob URLs при закритті
        window.addEventListener('beforeunload', function() {
            if (window.currentBlobUrl) {
                URL.revokeObjectURL(window.currentBlobUrl);
                console.log('🧹 Blob URL очищено');
            }
            
            if (syncInterval) {
                clearInterval(syncInterval);
                console.log('🛑 Синхронізація зупинена');
            }
        });
    </script>
</body>
</html>
"""

# ===== HTML ДЛЯ DISCORD ACTIVITY (КОНТРОЛЕР) =====
CONTROLLER_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Watch Together - Controller</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            margin: 0;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            font-size: 2em;
            margin-bottom: 30px;
        }
        .status {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .controls {
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 15px 30px;
            margin: 5px;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
        }
        button:hover {
            background: #45a049;
            transform: translateY(-2px);
        }
        button:active {
            transform: translateY(0);
        }
        button.pause {
            background: #ff9800;
        }
        button.pause:hover {
            background: #e68900;
        }
        .video-input {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            border: none;
            font-size: 14px;
        }
        .player-link {
            background: rgba(76, 175, 80, 0.2);
            border: 2px solid #4CAF50;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            margin: 20px 0;
        }
        .player-link a {
            color: #4CAF50;
            font-size: 1.2em;
            font-weight: bold;
            text-decoration: none;
        }
        .users {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
        }
        .user {
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 5px 10px;
            margin: 5px;
            border-radius: 15px;
        }
        .seek-controls {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
        .seek-input {
            flex: 1;
            padding: 10px;
            border-radius: 5px;
            border: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Watch Together</h1>
        
        <div class="status">
            <h3>📊 Статус</h3>
            <div id="roomInfo">Підключення...</div>
            <div id="videoInfo">Відео не вибрано</div>
        </div>

        <div class="player-link">
            <h3>🎥 Відкрийте плеєр</h3>
            <a href="#" id="playerLink" target="_blank">
                Відкрити відео плеєр в новому вікні →
            </a>
            <p style="color: rgba(255,255,255,0.7); margin-top: 10px;">
                Відео буде відтворюватись в окремому вікні, а тут ви зможете керувати ним
            </p>
        </div>

        <div class="controls">
            <h3>🎮 Керування</h3>
            
            <div>
                <input type="text" 
                       id="videoUrl" 
                       class="video-input" 
                       placeholder="Вставте URL з HdRezka...">
                <button onclick="parseVideo()">📥 Парсити відео</button>
            </div>

            <div id="translationControls" style="display: none; margin-top: 15px;">
                <select id="translationSelect" class="video-input"></select>
                <div id="seasonEpisode" style="display: none;">
                    <select id="seasonSelect" class="video-input"></select>
                    <select id="episodeSelect" class="video-input"></select>
                </div>
                <button onclick="loadVideo()">▶️ Завантажити відео</button>
            </div>

            <div id="playbackControls" style="display: none; margin-top: 15px;">
                <button onclick="sendPlay()">▶️ Play</button>
                <button class="pause" onclick="sendPause()">⏸️ Pause</button>
                
                <div class="seek-controls">
                    <input type="number" 
                           id="seekTime" 
                           class="seek-input" 
                           placeholder="Час (секунди)" 
                           min="0">
                    <button onclick="sendSeek()">⏩ Перемотати</button>
                </div>
            </div>
        </div>

        <div class="users">
            <h3>👥 Користувачі в кімнаті (<span id="userCount">0</span>)</h3>
            <div id="userList"></div>
        </div>
    </div>

    <script>
        const socket = io();
        const roomId = 'room_' + Math.random().toString(36).substr(2, 9);
        let currentVideoData = null;
        let parsedContent = null;

        // Підключення до кімнати
        socket.on('connect', () => {
            console.log('✅ Підключено до сервера');
            socket.emit('join_room', { room: roomId });
            
            // Оновлюємо посилання на плеєр
            const playerUrl = window.location.origin + '/player.html?room=' + roomId;
            document.getElementById('playerLink').href = playerUrl;
        });

        socket.on('room_joined', (data) => {
            console.log('✅ Приєднано до кімнати:', data);
            document.getElementById('roomInfo').innerHTML = 
                '🏠 Кімната: <strong>' + roomId + '</strong><br>' +
                '👥 Учасників: <strong>' + data.user_count + '</strong>';
        });

        socket.on('user_joined', (data) => {
            console.log('👤 Користувач приєднався:', data);
            updateUsers(data.users);
        });

        socket.on('user_left', (data) => {
            console.log('👋 Користувач вийшов:', data);
            updateUsers(data.users);
        });

        function updateUsers(users) {
            const count = users.length;
            document.getElementById('userCount').textContent = count;
            
            const userList = document.getElementById('userList');
            userList.innerHTML = users.map(user => 
                '<span class="user">👤 Користувач #' + user.substr(-4) + '</span>'
            ).join('');
        }

        // Парсинг відео
        async function parseVideo() {
            const url = document.getElementById('videoUrl').value;
            if (!url) {
                alert('Введіть URL!');
                return;
            }

            try {
                const response = await fetch('/api/parse', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });

                const data = await response.json();
                console.log('Парсинг результат:', data);
                
                parsedContent = data;
                
                // Показуємо вибір перекладу
                const translationSelect = document.getElementById('translationSelect');
                translationSelect.innerHTML = '';
                
                for (const [name, id] of Object.entries(data.translations)) {
                    const option = document.createElement('option');
                    option.value = id;
                    option.textContent = name;
                    translationSelect.appendChild(option);
                }
                
                // Показуємо сезони якщо серіал
                if (data.type === 'video.tv_series' && data.seasons) {
                    document.getElementById('seasonEpisode').style.display = 'block';
                    fillSeasons(data);
                }
                
                document.getElementById('translationControls').style.display = 'block';
                
            } catch (error) {
                alert('Помилка парсингу: ' + error.message);
            }
        }

        function fillSeasons(data) {
            const translationId = document.getElementById('translationSelect').value;
            const translatorName = Object.keys(data.translations)
                .find(key => data.translations[key] === translationId);
            
            if (!translatorName || !data.seasons || !data.seasons[translatorName]) return;
            
            const seasons = data.seasons[translatorName].seasons;
            const seasonSelect = document.getElementById('seasonSelect');
            
            seasonSelect.innerHTML = '';
            for (const [id, name] of Object.entries(seasons)) {
                const option = document.createElement('option');
                option.value = id;
                option.textContent = name;
                seasonSelect.appendChild(option);
            }
            
            fillEpisodes(data);
        }

        function fillEpisodes(data) {
            const translationId = document.getElementById('translationSelect').value;
            const seasonId = document.getElementById('seasonSelect').value;
            
            const translatorName = Object.keys(data.translations)
                .find(key => data.translations[key] === translationId);
            
            if (!translatorName || !data.seasons || !data.seasons[translatorName]) return;
            
            const episodes = data.seasons[translatorName].episodes[seasonId];
            const episodeSelect = document.getElementById('episodeSelect');
            
            episodeSelect.innerHTML = '';
            for (const [id, name] of Object.entries(episodes)) {
                const option = document.createElement('option');
                option.value = id;
                option.textContent = name;
                episodeSelect.appendChild(option);
            }
        }

        // Завантаження відео
        async function loadVideo() {
            const url = document.getElementById('videoUrl').value;
            const translation = document.getElementById('translationSelect').value;
            
            let season = null;
            let episode = null;
            
            if (parsedContent && parsedContent.type === 'video.tv_series') {
                season = document.getElementById('seasonSelect').value;
                episode = document.getElementById('episodeSelect').value;
            }

            try {
                const response = await fetch('/api/stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, translation, season, episode })
                });

                const data = await response.json();
                console.log('Stream результат:', data);
                
                currentVideoData = data;
                
                // Надсилаємо всім в кімнаті
                socket.emit('load_video', {
                    room: roomId,
                    videoData: data
                });
                
                document.getElementById('videoInfo').innerHTML = 
                    '🎬 Відео завантажено<br>' +
                    'Якостей: <strong>' + Object.keys(data.videos).length + '</strong>';
                
                document.getElementById('playbackControls').style.display = 'block';
                
            } catch (error) {
                alert('Помилка завантаження: ' + error.message);
            }
        }

        // Керування відтворенням
        function sendPlay() {
            socket.emit('control', {
                room: roomId,
                action: 'play'
            });
        }

        function sendPause() {
            socket.emit('control', {
                room: roomId,
                action: 'pause'
            });
        }

        function sendSeek() {
            const time = parseFloat(document.getElementById('seekTime').value);
            if (isNaN(time)) {
                alert('Введіть коректний час!');
                return;
            }
            
            socket.emit('control', {
                room: roomId,
                action: 'seek',
                time: time
            });
        }
    </script>
</body>
</html>
"""

# ===== HTML ДЛЯ ВІДЕО ПЛЕЄРА (ОКРЕМЕ ВІКНО) =====
PLAYER_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Watch Together - Player</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #000;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            overflow: hidden;
        }
        #videoContainer {
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        video {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        #status {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            font-family: Arial, sans-serif;
        }
        #quality {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px;
            border-radius: 5px;
            font-family: Arial, sans-serif;
        }
        select {
            background: rgba(255,255,255,0.1);
            color: white;
            border: none;
            padding: 5px;
            border-radius: 3px;
        }
        #message {
            color: white;
            font-size: 1.5em;
            text-align: center;
            padding: 40px;
        }
    </style>
</head>
<body>
    <div id="status">Підключення...</div>
    <div id="quality" style="display: none;">
        Якість: 
        <select id="qualitySelect" onchange="changeQuality()"></select>
    </div>
    
    <div id="videoContainer">
        <div id="message">Очікування відео від ведучого...</div>
        <video id="videoPlayer" controls style="display: none;"></video>
    </div>

    <script>
        const socket = io();
        const urlParams = new URLSearchParams(window.location.search);
        const roomId = urlParams.get('room');
        
        const videoPlayer = document.getElementById('videoPlayer');
        const message = document.getElementById('message');
        const qualitySelect = document.getElementById('qualitySelect');
        
        let currentVideoData = null;
        let isControlledSeek = false;

        if (!roomId) {
            message.textContent = '❌ Не вказано кімнату!';
        } else {
            socket.on('connect', () => {
                console.log('✅ Підключено');
                socket.emit('join_room', { room: roomId });
                document.getElementById('status').textContent = '✅ Підключено';
            });

            socket.on('load_video', (data) => {
                console.log('📥 Отримано відео:', data);
                currentVideoData = data.videoData;
                
                // Заповнюємо якості
                qualitySelect.innerHTML = '';
                const qualities = Object.keys(data.videoData.videos).sort((a, b) => {
                    return parseInt(b) - parseInt(a);
                });
                
                qualities.forEach(q => {
                    const option = document.createElement('option');
                    option.value = q;
                    option.textContent = q;
                    qualitySelect.appendChild(option);
                });
                
                // Завантажуємо кращу якість
                const bestQuality = qualities[0];
                loadQuality(bestQuality);
                
                document.getElementById('quality').style.display = 'block';
                message.style.display = 'none';
                videoPlayer.style.display = 'block';
            });

            socket.on('control', (data) => {
                console.log('🎮 Команда:', data);
                
                if (data.action === 'play') {
                    videoPlayer.play();
                } else if (data.action === 'pause') {
                    videoPlayer.pause();
                } else if (data.action === 'seek') {
                    isControlledSeek = true;
                    videoPlayer.currentTime = data.time;
                    setTimeout(() => { isControlledSeek = false; }, 100);
                }
            });
        }

        function loadQuality(quality) {
            if (!currentVideoData) return;
            
            const videoUrl = currentVideoData.videos[quality];
            const currentTime = videoPlayer.currentTime;
            const wasPaused = videoPlayer.paused;
            
            videoPlayer.src = videoUrl;
            videoPlayer.load();
            
            videoPlayer.onloadedmetadata = () => {
                videoPlayer.currentTime = currentTime;
                if (!wasPaused) {
                    videoPlayer.play();
                }
            };
            
            qualitySelect.value = quality;
        }

        function changeQuality() {
            const quality = qualitySelect.value;
            loadQuality(quality);
        }

        // Відключаємо локальне керування
        videoPlayer.onplay = (e) => {
            if (!isControlledSeek) {
                videoPlayer.pause();
            }
        };

        videoPlayer.onpause = (e) => {
            if (!isControlledSeek) {
                // Дозволяємо паузу
            }
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/controller')
def controller():
    """Discord Activity контролер"""
    return render_template_string(CONTROLLER_TEMPLATE)

@app.route('/player.html')
def player():
    """Окремий відео плеєр"""
    return render_template_string(PLAYER_TEMPLATE)

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

@app.route('/api/debug', methods=['GET'])
def debug_info():
    """Діагностичний endpoint для перевірки налаштувань"""
    return jsonify({
        'status': 'success',
        'message': 'Debug інформація',
        'timestamp': time(),
        'environment': {
            'PORT': os.environ.get('PORT', 'не встановлено'),
            'PYTHON_VERSION': os.environ.get('PYTHON_VERSION', 'не встановлено'),
            'RAILWAY_ENVIRONMENT': os.environ.get('RAILWAY_ENVIRONMENT', 'не встановлено'),
            'RAILWAY_PROJECT_ID': os.environ.get('RAILWAY_PROJECT_ID', 'не встановлено')
        },
        'request_info': {
            'method': request.method,
            'url': request.url,
            'headers': dict(request.headers),
            'remote_addr': request.remote_addr
        }
    })

@app.route('/api/routes', methods=['GET'])
def list_routes():
    """Показує всі доступні маршрути"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'rule': str(rule)
        })
    
    return jsonify({
        'status': 'success',
        'message': 'Доступні маршрути',
        'routes': routes,
        'total': len(routes)
    })

@app.route('/api/stream-test', methods=['POST'])
def stream_test():
    """Тестовий endpoint для стріму"""
    print("=== STREAM TEST ENDPOINT ВИКЛИКАНО ===")
    try:
        data = request.get_json()
        print(f"Отримані дані: {data}")
        
        # ТЕСТОВІ ВІДЕО ЧЕРЕЗ ПРОКСІ (Discord вимагає)
        base_url = request.url_root.rstrip('/')
        if base_url.startswith('http://'):
            base_url = base_url.replace('http://', 'https://')
        
        import urllib.parse
        test_videos = {
            '360p': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
            '720p': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4',
            '1080p': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4'
        }
        
        proxied_videos = {}
        for quality, video_url in test_videos.items():
            encoded_url = urllib.parse.quote(video_url, safe='')
            proxied_videos[quality] = f'{base_url}/api/video-proxy/{encoded_url}'
        
        return jsonify({
            'status': 'success',
            'message': 'Stream test працює! (через проксі)',
            'received_data': data,
            'test_videos': proxied_videos,
            'timestamp': time()
        })
    except Exception as e:
        print(f"Помилка в stream_test: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-video')
def test_video():
    """Тестовий endpoint для перевірки відео"""
    try:
        import requests
        
        # Тестове відео
        video_url = 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4'
        
        print(f"=== ТЕСТ ВІДЕО ===")
        print(f"URL: {video_url}")
        
        # Перевіряємо доступність
        response = requests.head(video_url, timeout=10)
        print(f"Статус: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print(f"Content-Length: {response.headers.get('content-length')}")
        
        return jsonify({
            'status': 'success',
            'video_url': video_url,
            'response_status': response.status_code,
            'content_type': response.headers.get('content-type'),
            'content_length': response.headers.get('content-length'),
            'headers': dict(response.headers)
        })
        
    except Exception as e:
        print(f"Помилка тесту відео: {e}")
        return jsonify({'error': f'Помилка тесту відео: {str(e)}'}), 500

@app.route('/api/test-hdrezka')
def test_hdrezka():
    """Тестовий endpoint для перевірки HdRezka парсингу"""
    try:
        from HdRezkaApi import HdRezkaApi
        
        # Тестовий URL
        test_url = 'https://rezka.ag/films/comedy/79188-chumovaya-pyatnica-2-2025-latest.html'
        
        print(f"=== ТЕСТ HDREZKA ===")
        print(f"URL: {test_url}")
        
        # Створюємо об'єкт HdRezkaApi
        rezka = HdRezkaApi(test_url)
        
        # Отримуємо переклади
        print("Отримуємо переклади...")
        translations = rezka.getTranslations()
        print(f"Переклади: {translations}")
        
        # Отримуємо сезони
        print("Отримуємо сезони...")
        seasons = rezka.getSeasons()
        print(f"Сезони: {seasons}")
        
        # Спробуємо отримати стрім
        print("Спробуємо отримати стрім...")
        stream = rezka.getStream(season='1', episode='1', translation='1')
        
        result = {
            'status': 'success',
            'url': test_url,
            'translations': translations,
            'seasons': seasons,
            'stream_success': stream is not None,
            'stream_videos': stream.videos if stream else None,
            'message': 'HdRezka тест завершено'
        }
        
        print(f"Результат: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Помилка тесту HdRezka: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f'Помилка тесту HdRezka: {str(e)}'}), 500

@app.route('/api/test-direct')
def test_direct():
    """Тестовий endpoint для прямих відео без проксі"""
    try:
        print("=== ТЕСТ ПРЯМИХ ВІДЕО ===")
        
        # Прямі посилання на Google відео
        direct_videos = {
            '360p': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
            '720p': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4',
            '1080p': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4'
        }
        
        # Тестуємо доступність кожного відео
        import requests
        results = {}
        
        for quality, url in direct_videos.items():
            try:
                print(f"Тестуємо {quality}: {url}")
                response = requests.head(url, timeout=10)
                results[quality] = {
                    'url': url,
                    'status': response.status_code,
                    'content_type': response.headers.get('content-type'),
                    'content_length': response.headers.get('content-length'),
                    'accessible': response.status_code == 200
                }
                print(f"✅ {quality}: {response.status_code}")
            except Exception as e:
                results[quality] = {
                    'url': url,
                    'error': str(e),
                    'accessible': False
                }
                print(f"❌ {quality}: {e}")
        
        result = {
            'status': 'success',
            'message': 'Тест прямих відео завершено',
            'videos': results,
            'total_accessible': sum(1 for v in results.values() if v.get('accessible', False)),
            'total_videos': len(results)
        }
        
        print(f"Результат: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Помилка тесту прямих відео: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f'Помилка тесту прямих відео: {str(e)}'}), 500

@app.route('/api/test-blob')
def test_blob():
    """Тестовий endpoint для Blob завантаження"""
    try:
        print("=== ТЕСТ BLOB ЗАВАНТАЖЕННЯ ===")
        
        # Отримуємо базовий URL
        base_url = request.url_root.rstrip('/')
        if base_url.startswith('http://'):
            base_url = base_url.replace('http://', 'https://')
        
        # Тестове відео через проксі
        test_video_url = f'{base_url}/api/video-proxy/https%3A//commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4'
        
        result = {
            'status': 'success',
            'message': 'Blob тест готовий - натисніть "🎬 Отримати стрім" для тестування',
            'test_video_url': test_video_url,
            'instructions': [
                '1. Натисніть "🎬 Отримати стрім"',
                '2. Відео завантажиться як Blob',
                '3. Перевірте консоль для логів',
                '4. Відео має працювати в Discord Activities!'
            ],
            'blob_benefits': [
                '✅ Обходить Discord CSP обмеження',
                '✅ Відео завантажується на клієнті',
                '✅ Створює blob: URL для відтворення',
                '✅ Працює з будь-якими зовнішніми джерелами'
            ]
        }
        
        print(f"Результат: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Помилка тесту Blob: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f'Помилка тесту Blob: {str(e)}'}), 500

# ===== WATCH TOGETHER СИСТЕМА =====

@app.route('/api/watch/create-room', methods=['POST'])
def create_watch_room():
    """Створює кімнату для синхронізації перегляду"""
    try:
        import uuid
        import time
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Потрібні дані'}), 400
        
        # Створюємо унікальну кімнату
        room_id = str(uuid.uuid4())[:8]
        host_id = data.get('host_id', 'unknown')
        video_url = data.get('video_url')
        video_title = data.get('video_title', 'Невідоме відео')
        
        # Зберігаємо кімнату
        WATCH_ROOMS[room_id] = {
            'host_id': host_id,
            'video_url': video_url,
            'video_title': video_title,
            'is_playing': False,
            'current_time': 0,
            'last_update': time.time(),
            'viewers': [host_id],
            'created_at': time.time()
        }
        
        print(f"🏠 Створено кімнату {room_id} для {video_title}")
        
        return jsonify({
            'status': 'success',
            'room_id': room_id,
            'message': 'Кімната створена',
            'video_url': video_url,
            'video_title': video_title
        })
        
    except Exception as e:
        print(f"Помилка створення кімнати: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watch/join-room/<room_id>', methods=['POST'])
def join_watch_room(room_id):
    """Приєднується до кімнати"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Потрібні дані'}), 400
        
        user_id = data.get('user_id', 'unknown')
        
        if room_id not in WATCH_ROOMS:
            return jsonify({'error': 'Кімната не знайдена'}), 404
        
        room = WATCH_ROOMS[room_id]
        
        # Додаємо користувача
        if user_id not in room['viewers']:
            room['viewers'].append(user_id)
        
        room['last_update'] = time.time()
        
        print(f"👥 {user_id} приєднався до кімнати {room_id}")
        
        return jsonify({
            'status': 'success',
            'room_id': room_id,
            'video_url': room['video_url'],
            'video_title': room['video_title'],
            'is_playing': room['is_playing'],
            'current_time': room['current_time'],
            'viewers_count': len(room['viewers'])
        })
        
    except Exception as e:
        print(f"Помилка приєднання: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watch/sync/<room_id>', methods=['POST'])
def sync_watch_room(room_id):
    """Синхронізує стан перегляду"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Потрібні дані'}), 400
        
        if room_id not in WATCH_ROOMS:
            return jsonify({'error': 'Кімната не знайдена'}), 404
        
        room = WATCH_ROOMS[room_id]
        user_id = data.get('user_id')
        
        # Оновлюємо стан кімнати
        room['is_playing'] = data.get('is_playing', False)
        room['current_time'] = data.get('current_time', 0)
        room['last_update'] = time.time()
        
        print(f"🔄 Синхронізація кімнати {room_id}: {room['is_playing']} @ {room['current_time']:.1f}s")
        
        return jsonify({
            'status': 'success',
            'is_playing': room['is_playing'],
            'current_time': room['current_time'],
            'viewers_count': len(room['viewers'])
        })
        
    except Exception as e:
        print(f"Помилка синхронізації: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watch/room/<room_id>')
def get_watch_room(room_id):
    """Отримує стан кімнати"""
    try:
        if room_id not in WATCH_ROOMS:
            return jsonify({'error': 'Кімната не знайдена'}), 404
        
        room = WATCH_ROOMS[room_id]
        
        # Очищуємо застарілі кімнати
        if time.time() - room['last_update'] > ROOM_TIMEOUT:
            del WATCH_ROOMS[room_id]
            return jsonify({'error': 'Кімната застаріла'}), 410
        
        return jsonify({
            'status': 'success',
            'room_id': room_id,
            'video_url': room['video_url'],
            'video_title': room['video_title'],
            'is_playing': room['is_playing'],
            'current_time': room['current_time'],
            'viewers_count': len(room['viewers']),
            'created_at': room['created_at']
        })
        
    except Exception as e:
        print(f"Помилка отримання кімнати: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watch/rooms')
def list_watch_rooms():
    """Список активних кімнат"""
    try:
        # Очищуємо застарілі кімнати
        current_time = time.time()
        expired_rooms = []
        
        for room_id, room in WATCH_ROOMS.items():
            if current_time - room['last_update'] > ROOM_TIMEOUT:
                expired_rooms.append(room_id)
        
        for room_id in expired_rooms:
            del WATCH_ROOMS[room_id]
            print(f"🗑️ Видалено застарілу кімнату {room_id}")
        
        # Повертаємо активні кімнати
        active_rooms = []
        for room_id, room in WATCH_ROOMS.items():
            active_rooms.append({
                'room_id': room_id,
                'video_title': room['video_title'],
                'viewers_count': len(room['viewers']),
                'is_playing': room['is_playing'],
                'created_at': room['created_at']
            })
        
        return jsonify({
            'status': 'success',
            'rooms': active_rooms,
            'total': len(active_rooms)
        })
        
    except Exception as e:
        print(f"Помилка списку кімнат: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/video-proxy/<path:video_url>')
def video_proxy(video_url):
    """Проксі для відео з повною підтримкою Range requests"""
    try:
        import requests
        from flask import Response, stream_with_context
        import urllib.parse
        
        # Декодуємо URL
        video_url = urllib.parse.unquote(video_url)
        
        print(f"\n=== ВІДЕО ПРОКСІ ===")
        print(f"URL: {video_url}")
        print(f"Client headers: {dict(request.headers)}")
        
        # Підготовка заголовків
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # КРИТИЧНО: Передаємо Range заголовок
        range_header = request.headers.get('Range')
        if range_header:
            headers['Range'] = range_header
            print(f"📊 Range request: {range_header}")
        
        # Запит до оригінального відео
        print(f"🌐 Запит до: {video_url}")
        response = requests.get(
            video_url, 
            headers=headers,
            stream=True,
            timeout=30
        )
        
        print(f"✅ Статус: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print(f"Content-Length: {response.headers.get('content-length')}")
        
        if range_header:
            print(f"Content-Range: {response.headers.get('content-range', 'Not provided')}")
        
        # Підготовка заголовків відповіді
        response_headers = {
            'Content-Type': response.headers.get('content-type', 'video/mp4'),
            'Accept-Ranges': 'bytes',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Content-Type, Accept',
            'Access-Control-Expose-Headers': 'Content-Length, Content-Range, Accept-Ranges',
            'Cache-Control': 'public, max-age=3600',
        }
        
        # Додаємо Content-Length
        if response.headers.get('content-length'):
            response_headers['Content-Length'] = response.headers.get('content-length')
        
        # КРИТИЧНО: Додаємо Content-Range для Range requests
        if response.headers.get('content-range'):
            response_headers['Content-Range'] = response.headers.get('content-range')
            print(f"📤 Відправляємо Content-Range: {response_headers['Content-Range']}")
        
        # Streaming генератор
        def generate():
            try:
                bytes_sent = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        bytes_sent += len(chunk)
                        yield chunk
                print(f"✅ Надіслано {bytes_sent} байт")
            except Exception as e:
                print(f"❌ Помилка в generate: {e}")
                raise
        
        # Повертаємо відповідь
        # 206 Partial Content для Range requests, 200 для повного файлу
        status_code = response.status_code
        print(f"📤 Повертаємо статус: {status_code}")
        
        return Response(
            stream_with_context(generate()),
            status=status_code,
            headers=response_headers,
            direct_passthrough=True
        )
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Помилка запиту: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 502
        
    except Exception as e:
        print(f"❌ Загальна помилка: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/video-proxy/<path:video_url>', methods=['OPTIONS'])
def video_proxy_options(video_url):
    """CORS preflight"""
    return '', 204, {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
        'Access-Control-Allow-Headers': 'Range, Content-Type, Accept',
        'Access-Control-Max-Age': '3600'
    }

@app.route('/api/video-proxy/<path:video_url>', methods=['HEAD'])
def video_proxy_head(video_url):
    """HEAD запит для отримання інформації про відео"""
    try:
        import requests
        import urllib.parse
        
        video_url = urllib.parse.unquote(video_url)
        
        print(f"HEAD запит: {video_url}")
        
        response = requests.head(video_url, timeout=10)
        
        return '', response.status_code, {
            'Content-Type': response.headers.get('content-type', 'video/mp4'),
            'Content-Length': response.headers.get('content-length', '0'),
            'Accept-Ranges': 'bytes',
            'Access-Control-Allow-Origin': '*'
        }
        
    except Exception as e:
        print(f"HEAD помилка: {e}")
        return '', 500

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
        if "403" in error_message or "Forbidden" in error_message:
            error_message = "🚫 HdRezka заблокував доступ з серверів Render.com. Спробуйте:\n• Інший URL з HdRezka\n• Простіший фільм\n• Пізніше (менше навантаження)\n• Використати VPN"
        elif "404" in error_message:
            error_message = "❌ URL не знайдено. Перевірте правильність посилання."
        elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
            error_message = "⏰ Час очікування вичерпано. HdRezka занадто повільно відповідає."
        elif "Не вдалося отримати доступ до жодного домену" in error_message:
            error_message = "🌐 Всі домени HdRezka заблоковані для серверів Render.com. Спробуйте інший URL або пізніше."
        
        return jsonify({'error': error_message}), 500

@app.route('/api/stream', methods=['POST'])
def get_stream():
    print("=== STREAM ENDPOINT ВИКЛИКАНО ===")
    print(f"Method: {request.method}")
    print(f"URL: {request.url}")
    print(f"Headers: {dict(request.headers)}")
    
    try:
        # Перевіряємо, чи запит містить JSON
        if not request.is_json:
            print("Помилка: не JSON запит")
            return jsonify({'error': 'Запит повинен містити JSON дані'}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Порожній JSON запит'}), 400
            
        url = data.get('url')
        translation = data.get('translation')
        season = data.get('season')
        episode = data.get('episode')
        
        print(f"Отримані дані: url={url}, translation={translation}, season={season}, episode={episode}")
        
        if not url or not translation:
            return jsonify({'error': 'URL та переклад є обов\'язковими'}), 400
        
        # ===== ТЕСТОВІ ВІДЕО ЧЕРЕЗ ПРОКСІ =====
        print("⚠️ Використовуємо тестові відео через проксі")
        
        # Отримуємо базовий URL
        base_url = request.url_root.rstrip('/')
        if base_url.startswith('http://'):
            base_url = base_url.replace('http://', 'https://')
        
        print(f"Base URL: {base_url}")
        
        # Тестові відео
        test_videos = {
            '360p': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
            '720p': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4',
            '1080p': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4'
        }
        
        # Проксіруємо через наш домен
        import urllib.parse
        proxied_videos = {}
        for quality, video_url in test_videos.items():
            encoded_url = urllib.parse.quote(video_url, safe='')
            proxied_url = f'{base_url}/api/video-proxy/{encoded_url}'
            proxied_videos[quality] = proxied_url
            print(f"  {quality}: {proxied_url}")
        
        result = {
            'videos': proxied_videos,
            'season': season,
            'episode': episode,
            'test_mode': True,
            'message': '⚠️ Тестові відео через проксі (Discord вимагає)'
        }
        
        print(f"✅ Повертаємо {len(proxied_videos)} якостей через проксі")
        return jsonify(result)
        
    except Exception as e:
        print(f"Помилка при отриманні стріму: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# ===== SOCKETIO EVENTS =====

@socketio.on('join_room')
def handle_join(data):
    room = data['room']
    join_room(room)
    
    if room not in SOCKET_ROOMS:
        SOCKET_ROOMS[room] = {
            'users': [],
            'video': None
        }
    
    SOCKET_ROOMS[room]['users'].append(request.sid)
    
    emit('room_joined', {
        'room': room,
        'user_count': len(SOCKET_ROOMS[room]['users'])
    }, room=request.sid)
    
    emit('user_joined', {
        'user': request.sid,
        'users': SOCKET_ROOMS[room]['users']
    }, room=room)

@socketio.on('disconnect')
def handle_disconnect():
    for room, data in SOCKET_ROOMS.items():
        if request.sid in data['users']:
            data['users'].remove(request.sid)
            
            emit('user_left', {
                'user': request.sid,
                'users': data['users']
            }, room=room)
            
            break

@socketio.on('load_video')
def handle_load_video(data):
    room = data['room']
    
    if room in SOCKET_ROOMS:
        SOCKET_ROOMS[room]['video'] = data['videoData']
    
    emit('load_video', data, room=room, include_self=False)

@socketio.on('control')
def handle_control(data):
    room = data['room']
    emit('control', data, room=room, include_self=False)

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
    
    socketio.run(app, debug=False, host='0.0.0.0', port=port)