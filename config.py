"""
Модуль конфигурации и констант
"""

import json
import logging
import sys
from pathlib import Path

# ==== API URLs ====
API_URL = "https://api.open-meteo.com/v1/forecast" 
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search" 
TRANSLATE_API = "https://translate.googleapis.com/translate_a/single" 

# ==== Пути к файлам ====
CONFIG_DIR = Path.home() / ".config" / "MyWeatherWidget"
CONFIG_FILE = CONFIG_DIR / "config.json"

# ==== Интервалы обновления ====
WEATHER_INTERVAL_SEC = 10   # Обновление погоды каждые 10 секунд
METRICS_INTERVAL_MS = 500   # Обновление метрик каждые 0.5 секунды

# ==== Настройки по умолчанию ====
ALPHA_DEFAULT = 0.9
CITY_DEFAULT = None

WEATHER_ICONS = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 
    45: "🌫️", 48: "🌫️", 
    51: "🌦️", 52: "🌧️", 53: "🌧️", 54: "🌧️", 
    55: "🌧️", 56: "🌨️", 57: "🌨️", 61: "🌧️",
    62: "🌧️", 63: "🌧️", 66: "🌨️", 67: "🌨️",
    80: "🌧️", 81: "🌧️", 82: "🌧️",
    71: "❄️", 72: "❄️", 73: "❄️", 
    77: "🌨️", 85: "❄️", 86: "❄️",
    95: "⛈️", 96: "⛈️", 99: "⛈️"
}

def setup_logging() -> None:
    """Настройка логирования в консоль"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def load_config() -> dict:
    """Загрузка конфигурации из файла"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    if not CONFIG_FILE.exists():
        default_config = {
            "city": CITY_DEFAULT,
            "lat": None,
            "lon": None,
            "alpha": ALPHA_DEFAULT
        }
        with CONFIG_FILE.open('w') as f:
            json.dump(default_config, f, indent=2)
        return default_config
        
    with CONFIG_FILE.open('r') as f:
        return json.load(f)

def save_config(cfg: dict) -> None:
    """Сохранение конфигурации в файл"""
    with CONFIG_FILE.open('w') as f:
        json.dump(cfg, f, indent=2)