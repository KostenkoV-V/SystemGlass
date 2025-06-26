"""
Модуль геокодирования и перевода
"""

import re
import requests
import logging
from typing import Tuple, List, Optional

# Импорты из проекта
from config import TRANSLATE_API, GEOCODE_URL

def translate_ru_to_en(text: str) -> str:
    """
    Переводит русский текст на английский через Google Translate API
    
    Args:
        text: Текст на русском языке
        
    Returns:
        Переведенный текст или оригинальный при ошибке
    """
    params = {
        'client': 'gtx', 
        'sl': 'ru', 
        'tl': 'en', 
        'dt': 't', 
        'q': text
    }
    
    try:
        response = requests.get(TRANSLATE_API, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        return ''.join([chunk[0] for chunk in data[0]])
        
    except Exception as e:
        logging.warning(f"Не удалось перевести '{text}': {e}")
        return text

def geocode_city(city: str) -> Tuple[float, float]:
    """
    Получает координаты для указанного города
    
    Args:
        city: Название города (на русском или английском)
        
    Returns:
        Широта и долгота
        
    Raises:
        ValueError: Если город не найден
    """
    # Автоматический перевод при необходимости
    if re.search('[\u0400-\u04FF]', city):
        city_en = translate_ru_to_en(city)
        logging.info(f"Перевод города с русского: '{city}' -> '{city_en}'")
        city = city_en

    # Запрос к геокодирующему API
    response = requests.get(
        GEOCODE_URL, 
        params={"name": city, "count": 5}, 
        timeout=5
    )
    response.raise_for_status()
    
    results: List[dict] = response.json().get("results", [])
    
    if not results:
        raise ValueError(f"Город '{city}' не найден")

    city_lower = city.strip().lower()
    
    # 1. Точное совпадение
    for location in results:
        if location.get("name", "").strip().lower() == city_lower:
            return location["latitude"], location["longitude"]
            
    # 2. Частичное совпадение
    for location in results:
        if location.get("name", "").strip().lower().startswith(city_lower):
            return location["latitude"], location["longitude"]
            
    # 3. Первый результат как fallback
    return results[0]["latitude"], results[0]["longitude"]

def detect_city_by_ip() -> Optional[str]:
    """
    Определяет город по IP-адресу
    
    Returns:
        Название города или None при ошибке
        
    Note:
        Используется ipapi.co, который может быть недоступен
        Альтернатива: https://ipapi.com/json/ 
    """
    try:
        response = requests.get("https://ipapi.co/json/",  timeout=5)
        response.raise_for_status()
        return response.json().get("city")
        
    except requests.RequestException as e:
        logging.error(f"Ошибка определения по IP: {e}")
        return None