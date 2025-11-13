"""
calculator.py
----------------
封裝所有「純計算邏輯」：

- 僅處理數值與字串運算。
- 不碰 GUI、不碰網路、不碰下單 API。

這樣可以讓計算邏輯更容易測試與重複利用。
"""

from typing import Tuple, Optional


def parse_time_string(time_str: str) -> Tuple[int, int, int, int]:
    """
    將 "HHMMSSmmm" 時間字串解析成 (時, 分, 秒, 毫秒)。

    參數
    -----
    time_str : str
        形如 "091530123" 的字串，依序代表「時分秒毫秒」。

    回傳
    -----
    (h, m, s, ms) : tuple[int, int, int, int]
        對應的時 / 分 / 秒 / 毫秒整數。
    """
    hours = int(time_str[:2])
    minutes = int(time_str[2:4])
    seconds = int(time_str[4:6])
    milliseconds = int(time_str[6:9])
    return hours, minutes, seconds, milliseconds


def to_ms(hours: int, minutes: int, seconds: int, milliseconds: int) -> int:
    """
    將時間組合轉成「自午夜起算的總毫秒數」。

    用於 tick 時間差的計算。

    參數
    -----
    hours, minutes, seconds, milliseconds : int
        時、分、秒、毫秒。

    回傳
    -----
    total_ms : int
        對應的總毫秒數。
    """
    return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds


def parse_profit_triplet(s: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    解析 "p1:p2:p3" 形式的停利價字串，轉為三個整數。

    參數
    -----
    s : str
        形如 "17700:17650:17600" 的字串。

    回傳
    -----
    (p1, p2, p3) : tuple[int | None, int | None, int | None]
        若成功解析且數量 >= 3，回傳前三個停利價；
        否則回傳 (None, None, None)。
    """
    try:
        parts = [int(x.strip()) for x in s.split(":") if x.strip().isdigit()]
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
    except Exception:
        pass
    return None, None, None


def calc_profit_targets(entry: int, stop: int, direction: str):
    """
    計算三段停利價，多空共用。

    規則
    -----
    - 單位距離 unit = |stop - entry| + 2
    - 多單：
        p1 = entry + 1 * unit
        p2 = entry + 2 * unit
        p3 = entry + 3 * unit
    - 空單：
        p1 = entry - 1 * unit
        p2 = entry - 2 * unit
        p3 = entry - 3 * unit

    參數
    -----
    entry : int
        進場參考價。
    stop : int
        初始止損價。
    direction : str
        "多" 或 "空"。

    回傳
    -----
    (p1, p2, p3) : tuple[int, int, int]
        三段停利目標價位。
    """
    unit = abs(stop - entry) + 2
    if direction == "多":
        return entry + unit, entry + 2 * unit, entry + 3 * unit
    else:
        return entry - unit, entry - 2 * unit, entry - 3 * unit


def calc_fibonacci_levels(high_price: int, low_price: int, key_price: int):
    """
    根據「日高 / 日低 / 關鍵價」計算上下兩組費波那契價位。

    費波係數：0.236, 0.382, 0.5, 0.618, 0.786

    參數
    -----
    high_price : int
        日內最高價。
    low_price : int
        日內最低價。
    key_price : int
        關鍵價（通常是合併均價或真實均價）。

    回傳
    -----
    levels : dict
        {
            "sell": [r236, r382, r50, r618, r786],  # 壓力價位
            "buy":  [s236, s382, s50, s618, s786],  # 支撐價位
        }
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
