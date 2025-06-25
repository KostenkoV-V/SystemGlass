"""
WeatherWidget: Плавающий оверлей-виджет для Linux и Windows,
отображающий актуальную погоду и системные метрики.
"""
import json
import logging
import re
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, List

import psutil
import requests
import tkinter as tk
from PIL import Image, ImageDraw
import pystray

# ----------------------------------
# Конфигурация и константы
# ----------------------------------
API_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
TRANSLATE_API = "https://translate.googleapis.com/translate_a/single"
CONFIG_DIR = Path.home() / ".config" / "MyWeatherWidget"
CONFIG_FILE = CONFIG_DIR / "config.json"
WEATHER_INTERVAL_SEC = 10  # обновление погоды каждые 10 сек
METRICS_INTERVAL_MS = 500   # обновление метрик каждые 0.5 сек
ALPHA_DEFAULT = 0.9
CITY_DEFAULT = None

WEATHER_ICONS = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️",
    48: "🌫️", 51: "🌦️", 52: "🌧️", 53: "🌧️", 54: "🌧️",
    55: "🌧️", 56: "🌨️", 57: "🌨️", 61: "🌧️", 62: "🌧️",
    63: "🌧️", 66: "🌨️", 67: "🌨️", 71: "❄️", 72: "❄️",
    73: "❄️", 77: "🌨️", 80: "🌧️", 81: "🌧️", 82: "🌧️",
    85: "❄️", 86: "❄️", 95: "⛈️", 96: "⛈️", 99: "⛈️"
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        default = {"city": CITY_DEFAULT, "lat": None, "lon": None, "alpha": ALPHA_DEFAULT}
        CONFIG_FILE.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return default
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def translate_ru_to_en(text: str) -> str:
    """Простая трансляция русского текста на английский через Google Translate API."""
    params = {
        'client': 'gtx', 'sl': 'ru', 'tl': 'en', 'dt': 't', 'q': text
    }
    try:
        resp = requests.get(TRANSLATE_API, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return ''.join([chunk[0] for chunk in data[0]])
    except Exception as e:
        logging.warning("Не удалось перевести '%s': %s", text, e)
        return text


def geocode_city(city: str) -> Tuple[float, float]:
    # если введён русский текст, переводим
    if re.search('[\u0400-\u04FF]', city):
        city_en = translate_ru_to_en(city)
        logging.info("Перевод города с русского: '%s' -> '%s'", city, city_en)
        city = city_en
    resp = requests.get(GEOCODE_URL, params={"name": city, "count": 5}, timeout=5)
    resp.raise_for_status()
    results: List[dict] = resp.json().get("results") or []
    if not results:
        raise ValueError(f"City '{city}' not found")
    city_lower = city.strip().lower()
    for loc in results:
        if loc.get("name", "").strip().lower() == city_lower:
            return loc["latitude"], loc["longitude"]
    for loc in results:
        if loc.get("name", "").strip().lower().startswith(city_lower):
            return loc["latitude"], loc["longitude"]
    return results[0]["latitude"], results[0]["longitude"]


def detect_city_by_ip() -> Optional[str]:
    try:
        resp = requests.get("https://ipapi.co/json/", timeout=5)
        resp.raise_for_status()
        return resp.json().get("city")
    except requests.RequestException:
        return CITY_DEFAULT


class WeatherWidget(tk.Tk):
    """Tkinter-приложение: плавающий оверлей виджет погоды и метрик."""

    def __init__(self) -> None:
        super().__init__()
        setup_logging()
        self.cfg = load_config()
        city = self.cfg.get("city") or detect_city_by_ip()
        self._set_city(city)
        self.alpha = self.cfg.get("alpha", ALPHA_DEFAULT)

        self._init_ui()
        self._init_tray()
        self._init_counters()

        self.after(0, self._update_weather)
        self.after(0, self._update_metrics)

    def _set_city(self, city: str) -> None:
        try:
            lat, lon = geocode_city(city)
            self.cfg.update({"city": city, "lat": lat, "lon": lon})
        except ValueError:
            logging.warning("Не удалось определить координаты для '%s'", city)
        save_config(self.cfg)

    def _init_ui(self) -> None:
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", self.alpha)
        self.geometry("600x30+100+100")
        self.configure(bg="#1a1a1a")

        frame = tk.Frame(self, bg="#1a1a1a")
        frame.pack(fill=tk.BOTH, expand=True)

        self.weather_label = tk.Label(frame, bg="#1a1a1a", fg="#ffffff", font=("Segoe UI", 12, "bold"))
        self.cpu_label = tk.Label(frame, bg="#1a1a1a", fg="#ffffff", font=("Segoe UI", 12, "bold"))
        self.ram_label = tk.Label(frame, bg="#1a1a1a", fg="#ffffff", font=("Segoe UI", 12, "bold"))
        self.net_label = tk.Label(frame, bg="#1a1a1a", fg="#ffffff", font=("Segoe UI", 12, "bold"))

        for lbl in (self.weather_label, self.cpu_label, self.ram_label, self.net_label):
            lbl.pack(side=tk.LEFT, padx=8)

        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag)

    def _init_tray(self) -> None:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle((16, 16, 48, 48), fill="#ffffff")
        menu = (
            pystray.MenuItem("Настройки", lambda _: self.after(0, self._open_settings)),
            pystray.MenuItem("Выход", lambda _: self.after(0, self._quit)),
        )
        self.tray_icon = pystray.Icon("weather", img, "WeatherWidget", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _init_counters(self) -> None:
        self.last_net = psutil.net_io_counters()
        self.last_time = time.time()

    def _update_weather(self) -> None:
        lat, lon = self.cfg.get("lat"), self.cfg.get("lon")
        logging.info("Запрос погоды с координатами: lat=%s, lon=%s", lat, lon)
        if lat is not None and lon is not None:
            try:
                data = requests.get(
                    API_URL,
                    params={"latitude": lat, "longitude": lon, "current_weather": True, "timezone": "Europe/Helsinki"},
                    timeout=5
                ).json().get("current_weather", {})
                icon = WEATHER_ICONS.get(data.get("weathercode", 0), "🌐")
                temp = data.get("temperature", "?")
                wind = data.get("windspeed", "?")
                text = f"{icon} {temp}°C  {wind} m/s"
                self.weather_label.config(text=text)
                logging.info("Обновлена погода: %s", text)
            except requests.RequestException as e:
                logging.error("Ошибка погоды: %s", e)
        self.after(WEATHER_INTERVAL_SEC * 1000, self._update_weather)

    def _update_metrics(self) -> None:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        net = psutil.net_io_counters()
        now = time.time()
        dt = max(now - self.last_time, 1e-6)
        sent = (net.bytes_sent - self.last_net.bytes_sent) / dt / 1024
        recv = (net.bytes_recv - self.last_net.bytes_recv) / dt / 1024
        self.last_net, self.last_time = net, now

        self.cpu_label.config(text=f"CPU: {cpu:.1f}%")
        self.ram_label.config(text=f"RAM: {ram:.1f}%")
        self.net_label.config(text=f"Net: ↑{sent:.1f} ↓{recv:.1f} KB/s")
        self.after(METRICS_INTERVAL_MS, self._update_metrics)

    def _open_settings(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Настройки")
        dlg.geometry("300x200")
        dlg.configure(bg="#2a2a2a")
        dlg.resizable(False, False)

        tk.Label(dlg, text="Город:", bg="#2a2a2a", fg="#ffffff").pack(pady=(10, 0))
        city_var = tk.StringVar(value=self.cfg.get("city", ""))
        tk.Entry(dlg, textvariable=city_var).pack(fill=tk.X, padx=20)

        tk.Label(dlg, text="Прозрачность:", bg="#2a2a2a", fg="#ffffff").pack(pady=(10, 0))
        alpha_var = tk.DoubleVar(value=self.alpha)
        tk.Scale(dlg, from_=0.1, to=1.0, variable=alpha_var, orient=tk.HORIZONTAL, resolution=0.01, bg="#2a2a2a").pack(fill=tk.X, padx=20)

        def save_and_close() -> None:
            self._set_city(city_var.get().strip())
            self.alpha = alpha_var.get()
            self.attributes("-alpha", self.alpha)
            self.cfg["alpha"] = self.alpha
            save_config(self.cfg)
            dlg.destroy()

        tk.Button(dlg, text="Сохранить", command=save_and_close, bg="#4a4a4a", fg="#ffffff").pack(pady=20)

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_x, self._drag_y = event.x, event.y

    def _on_drag(self, event: tk.Event) -> None:
        x = self.winfo_pointerx() - self._drag_x
        y = self.winfo_pointery() - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _quit(self) -> None:
        self.tray_icon.stop()
        self.destroy()
        sys.exit(0)



WeatherWidget().mainloop()
