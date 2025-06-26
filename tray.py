"""
Модуль системного трея для управления приложением
"""

# Сторонние библиотеки
from PIL import Image, ImageDraw
import pystray
import tkinter as tk

# Стандартные библиотеки
import threading

# Константы для построения иконки
ICON_SIZE = 64
RECT_OFFSET = 16
RECT_COLOR = "#ffffff"
ICON_NAME = "weather"
ICON_TITLE = "WeatherWidget"

def create_tray_icon(app: tk.Tk) -> pystray.Icon:
    """
    Создает и запускает иконку системного трея с меню
    
    Args:
        app: Основное окно приложения Tkinter
        
    Returns:
        Объект иконки системного трея
    """
    # Создание изображения иконки (прозрачный фон с белым квадратом)
    icon_image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon_image)
    
    # Рисуем центральный квадрат
    rect_coords = (
        RECT_OFFSET, RECT_OFFSET, 
        ICON_SIZE - RECT_OFFSET, ICON_SIZE - RECT_OFFSET
    )
    draw.rectangle(rect_coords, fill=RECT_COLOR)

    # Создание контекстного меню системного трея
    menu = (
        pystray.MenuItem("Настройки", lambda _: _open_settings_safe(app)),
        pystray.MenuItem("Выход", lambda _: _quit_app_safe(app)),
    )

    # Создание и запуск иконки в отдельном потоке
    tray_icon = pystray.Icon(ICON_NAME, icon_image, ICON_TITLE, menu)
    threading.Thread(target=tray_icon.run, daemon=True).start()
    
    return tray_icon

def _open_settings_safe(app: tk.Tk) -> None:
    """Безопасный вызов окна настроек в основном потоке"""
    app.after(0, app._open_settings)

def _quit_app_safe(app: tk.Tk) -> None:
    """Безопасное завершение приложения в основном потоке"""
    app.after(0, app._quit)