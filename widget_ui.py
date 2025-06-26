"""
Основной виджет приложения: плавающий оверлей с погодой и системными метриками
"""

import tkinter as tk
import requests
import logging
from typing import Optional, Tuple
import psutil
import sys

from config import (
    setup_logging, 
    load_config, 
    save_config, 
    WEATHER_ICONS, 
    WEATHER_INTERVAL_SEC, 
    METRICS_INTERVAL_MS, 
    ALPHA_DEFAULT,
    API_URL
)

from geocode import geocode_city, detect_city_by_ip
from tray import create_tray_icon
from metrics import init_counters, update_metrics

class WeatherWidget(tk.Tk):
    """Главное приложение с погодой и системными метриками"""
    
    def __init__(self) -> None:
        super().__init__()
        setup_logging()
        self.cfg = load_config()
        self.drag_locked = False
        
        # Определение и установка города
        city = self.cfg.get("city") or detect_city_by_ip()
        self._set_city(city)
        
        # Инициализация параметров
        self.alpha = self.cfg.get("alpha", ALPHA_DEFAULT)
        self._init_ui()
        self._init_tray()
        self._init_counters()
        
        # Запуск обновлений
        self.after(0, self._update_weather)
        self.after(0, self._update_metrics)

    def _set_city(self, city: str) -> None:
        """Установка текущего города и сохранение координат в конфиг"""

        try:
            lat, lon = geocode_city(city)
            self.cfg.update({"city": city, "lat": lat, "lon": lon})

        except ValueError:
            logging.warning("Не удалось определить координаты для '%s'", city)

        save_config(self.cfg)

    def _init_ui(self) -> None:

        """Инициализация пользовательского интерфейса"""

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", self.alpha)
        self.geometry("650x30+100+100")
        self.configure(bg="#1a1a1a")
        
        # Сохраните фрейм как атрибут класса
        self.frame = tk.Frame(self, bg="#1a1a1a")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Создание меток для погоды и метрик
        self.weather_label = self._create_label()
        self.cpu_label = self._create_label()
        self.ram_label = self._create_label()
        self.net_label = self._create_label()
        
        # Кнопка блокировки
        self.lock_button = self._create_lock_button(self.frame)
        
        # Привязка событий перетаскивания
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag)

    def _create_label(self) -> tk.Label:
        """Создание унифицированной метки интерфейса"""
        label = tk.Label(
            master=self.frame,  # Теперь self.frame существует
            bg="#1a1a1a",
            fg="#ffffff",
            font=("Segoe UI", 12, "bold")
        )
        label.pack(side=tk.LEFT, padx=8)
        return label

    def _create_lock_button(self, parent: tk.Frame) -> tk.Label:
        """Создание кнопки блокировки окна"""
        lock_btn = tk.Label(
            parent,
            text="📌",
            bg="#1a1a1a",
            fg="#ffffff",
            font=("Segoe UI", 12)
        )
        lock_btn.pack(side=tk.LEFT, padx=8)
        lock_btn.bind("<Button-1>", self._toggle_lock)
        return lock_btn

    def _init_tray(self) -> None:
        """Инициализация иконки в системном трее"""
        self.tray_icon = create_tray_icon(self)

    def _init_counters(self) -> None:
        """Инициализация счетчиков сетевой активности"""
        self.last_network_io, self.last_time = init_counters()

    def _update_weather(self) -> None:
        """Запрос и отображение данных о погоде"""
        lat, lon = self.cfg.get("lat"), self.cfg.get("lon")
        logging.info("Запрос погоды с координатами: lat=%s, lon=%s", lat, lon)
        
        if lat is not None and lon is not None:
            try:
                response = requests.get(
                    API_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current_weather": True,
                        "timezone": "Europe/Helsinki"
                    },
                    timeout=5
                )
                data = response.json().get("current_weather", {})
                
                icon = WEATHER_ICONS.get(data.get("weathercode", 0), "🌐")
                temp = data.get("temperature", "?")
                wind = data.get("windspeed", "?")
                self.weather_label.config(text=f"{icon} {temp}°C  {wind} m/s")
                logging.info("Обновлена погода: %s", self.weather_label.cget("text"))
                
            except requests.RequestException as e:
                logging.error("Ошибка погоды: %s", e)
                
        # Планирование следующего обновления
        self.after(WEATHER_INTERVAL_SEC * 1000, self._update_weather)

    def _update_metrics(self) -> None:
        """Обновление системных метрик (CPU, RAM, сеть)"""

        cpu, ram, sent, recv, now = update_metrics(self.last_network_io, self.last_time)
        self.last_network_io, self.last_time = psutil.net_io_counters(), now
        
        self.cpu_label.config(text=f"CPU: {cpu:.1f}%")
        self.ram_label.config(text=f"RAM: {ram:.1f}%")
        self.net_label.config(text=f"Net: ↑{sent:.1f} ↓{recv:.1f} KB/s")
        
        self.after(METRICS_INTERVAL_MS, self._update_metrics)

    def _open_settings(self) -> None:
        """Открытие окна настроек приложения"""
        dlg = tk.Toplevel(self)
        dlg.title("Настройки")
        dlg.geometry("300x200")
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)
        
        # Поле ввода города
        tk.Label(dlg, text="Город:", bg="#2a2a2a", fg="#ffffff").pack(pady=(10, 0))
        city_var = tk.StringVar(value=self.cfg.get("city", ""))
        tk.Entry(dlg, textvariable=city_var).pack(fill=tk.X, padx=20)
        
        # Ползунок прозрачности
        tk.Label(dlg, text="Прозрачность:", bg="#2a2a2a", fg="#ffffff").pack(pady=(10, 0))
        alpha_var = tk.DoubleVar(value=self.alpha)
        tk.Scale(
            dlg,
            from_=0.1,
            to=1.0,
            variable=alpha_var,
            orient=tk.HORIZONTAL,
            resolution=0.01,
            bg="#2a2a2a"
        ).pack(fill=tk.X, padx=20)
        
        # Кнопка сохранения
        def save_and_close() -> None:
            self._set_city(city_var.get().strip())
            self.alpha = alpha_var.get()
            self.attributes("-alpha", self.alpha)
            self.cfg["alpha"] = self.alpha
            save_config(self.cfg)
            dlg.destroy()
            
        tk.Button(
            dlg,
            text="Сохранить",
            command=save_and_close,
            bg="#4a4a4a",
            fg="#ffffff"
        ).pack(pady=20)

    def _on_drag_start(self, event: tk.Event) -> None:
        """Начало перетаскивания окна"""
        if self.drag_locked:
            return
        self._drag_x, self._drag_y = event.x, event.y

    def _on_drag(self, event: tk.Event) -> None:
        """Перемещение окна при зажатой левой кнопке мыши"""
        if self.drag_locked:
            return
        x = self.winfo_pointerx() - self._drag_x
        y = self.winfo_pointery() - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _quit(self) -> None:
        """Завершение работы приложения"""
        self.tray_icon.stop()
        self.destroy()
        sys.exit(0)

    def _toggle_lock(self, event=None) -> None:
        """Переключение состояния блокировки окна"""
        self.drag_locked = not self.drag_locked
        self.lock_button.config(fg="#ff4444" if self.drag_locked else "#ffffff")
        
        if self.drag_locked:
            # Отвязка событий перетаскивания
            self.unbind("<ButtonPress-1>")
            self.unbind("<B1-Motion>")
        else:
            # Восстановление привязок
            self.bind("<ButtonPress-1>", self._on_drag_start)
            self.bind("<B1-Motion>", self._on_drag)


WeatherWidget().mainloop()