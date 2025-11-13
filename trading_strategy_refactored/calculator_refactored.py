"""
calculator.py
----------------
封裝所有「純計算邏輯」，不碰 GUI、不碰網路、不碰下單。
"""

from typing import Tuple, Optional


def parse_time_string(time_str: str) -> Tuple[int, int, int, int]:
    """將 "HHMMSSmmm" 解析成 (時, 分, 秒, 毫秒)。"""
    hours = int(time_str[:2])
    minutes = int(time_str[2:4])
    seconds = int(time_str[4:6])
    milliseconds = int(time_str[6:9])
    return hours, minutes, seconds, milliseconds


def to_ms(hours: int, minutes: int, seconds: int, milliseconds: int) -> int:
    """將時間轉成總毫秒數。"""
    return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds


def parse_profit_triplet(s: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """解析 "p1:p2:p3" 為三個整數，失敗回傳 (None, None, None)。"""
    try:
        parts = [int(x.strip()) for x in s.split(":") if x.strip().isdigit()]
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
    except Exception:
        pass
    return None, None, None


def calc_profit_targets(entry: int, stop: int, direction: str):
    """
    計算三段停利價，多空共用：
    unit = |stop-entry| + 2
    多: entry + n*unit
    空: entry - n*unit
    """
    unit = abs(stop - entry) + 2
    if direction == "多":
        return entry + unit, entry + 2 * unit, entry + 3 * unit
    else:
        return entry - unit, entry - 2 * unit, entry - 3 * unit


def calc_fibonacci_levels(high_price: int, low_price: int, key_price: int):
    """
    根據高點/低點/關鍵價計算上下五個費波那契價位。
    回傳 dict: {"sell": [...], "buy": [...]}
    """
    pressure_diff = high_price - key_price
    support_diff = key_price - low_price

    r236 = round(key_price + pressure_diff * 0.236)
    r382 = round(key_price + pressure_diff * 0.382)
    r50 = round(key_price + pressure_diff * 0.5)
    r618 = round(key_price + pressure_diff * 0.618)
    r786 = round(key_price + pressure_diff * 0.786)

    s236 = round(key_price - support_diff * 0.236)
    s382 = round(key_price - support_diff * 0.382)
    s50 = round(key_price - support_diff * 0.5)
    s618 = round(key_price - support_diff * 0.618)
    s786 = round(key_price - support_diff * 0.786)

    return {
        "sell": [r236, r382, r50, r618, r786],
        "buy": [s236, s382, s50, s618, s786],
    }
