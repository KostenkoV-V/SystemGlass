"""
Модуль работы с системными метриками
"""

import psutil
import time
from typing import Tuple

# Типы для аннотаций
NetworkStats = psutil._common.snetio
Timestamp = float

def init_counters() -> Tuple[NetworkStats, Timestamp]:
    """
    Инициализирует начальные значения для отслеживания сетевой активности
    
    Returns:
        Кортеж из:
        - Текущих сетевых счетчиков
        - Текущего времени в секундах
    """
    return psutil.net_io_counters(), time.time()

def update_metrics(last_net: NetworkStats, last_time: Timestamp) -> Tuple[float, float, float, float, Timestamp]:
    """
    Обновляет системные метрики и рассчитывает сетевую активность
    
    Args:
        last_net: Предыдущие значения сетевых счетчиков
        last_time: Время последнего измерения (в секундах)
        
    Returns:
        Кортеж из:
        - CPU загрузка в процентах
        - Использование RAM в процентах
        - Скорость отправки данных (KB/s)
        - Скорость получения данных (KB/s)
        - Текущее время измерения (в секундах)
        
    Note:
        Все значения скорости автоматически нормализуются по времени измерения
    """
    # Получаем текущие значения метрик
    cpu_usage = psutil.cpu_percent(interval=None)
    ram_usage = psutil.virtual_memory().percent
    current_net = psutil.net_io_counters()
    
    # Рассчитываем временной интервал
    current_time = time.time()
    time_diff = max(current_time - last_time, 1e-6)  # Защита от нулевого делителя
    
    # Вычисляем скорости передачи данных
    sent_speed = (current_net.bytes_sent - last_net.bytes_sent) / time_diff / 1024
    recv_speed = (current_net.bytes_recv - last_net.bytes_recv) / time_diff / 1024
    
    return cpu_usage, ram_usage, sent_speed, recv_speed, current_time