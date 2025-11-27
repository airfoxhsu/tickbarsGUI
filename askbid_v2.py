import os
import glob
import re
import tkinter as tk
from tkinter import filedialog
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import pandas as pd
import matplotlib.pyplot as plt


# ===============================================================
# 資料結構 (Data Structures)
# ===============================================================
@dataclass
class QuoteSnapshot:
    """
    報價快照，儲存單一時間點的報價資訊
    """
    symbol: str      # 商品代碼 "TXF" (大台) 或 "MXF" (小台)
    time_str: str    # 時間字串 "HH:MM:SS.mmm"
    matpri: int      # 成交價
    total_vol: int   # 總成交量 (tmatqty)
    bestbq: List[int] # 最佳買進量列表
    bestbp: List[int] # 最佳買進價列表
    bestsq: List[int] # 最佳賣出量列表
    bestsp: List[int] # 最佳賣出價列表


@dataclass
class Trade:
    """
    交易紀錄，儲存進出場資訊
    """
    date: str        # 日期 (YYYYMMDD)
    file: str        # 來源檔案名稱
    session: str     # 盤別 "DAY" (日盤) / "NIGHT" (夜盤)
    direction: int   # 方向：-1 = 空單, 1 = 多單
    entry_time: str  # 進場時間
    exit_time: Optional[str] # 出場時間
    entry_price: int # 進場價格
    exit_price: Optional[int] # 出場價格
    pnl: Optional[float] # 損益
    exit_reason: Optional[str] # 出場原因


@dataclass
class BlockStats:
    """
    區塊統計，用於追蹤每 1000 筆 Tick 的狀態
    """
    count: int = 0      # 目前累積的 Tick 數
    txf_diff: int = 0   # TXF 成交內外盤差 (主動買 - 主動賣)
    mxf_diff: int = 0   # MXF 成交內外盤差
    prices: List[int] = field(default_factory=list) # 紀錄區塊內的成交價 (用於判斷趨勢)
    times: List[str] = field(default_factory=list)  # 紀錄區塊內的時間

    def reset(self):
        """重置區塊統計數據"""
        self.count = 0
        self.txf_diff = 0
        self.mxf_diff = 0
        self.prices.clear()
        self.times.clear()


# ===============================================================
# 解析 REGEX (Regular Expressions)
# ===============================================================
QUOTE_REGEX = re.compile(
    r"Symbol=(?P<symbol>\w+),"
    r"ref=(?P<ref>\d+),"
    r"open=(?P<open>\d+),"
    r"high=(?P<high>\d+),"
    r"low=(?P<low>\d+),"
    r"up=(?P<up>\d+),"
    r"dn=(?P<dn>\d+),"
    r"mattime=(?P<mattime>\d+),"
    r"matpri=(?P<matpri>-?\d+),"
    r"matqty=(?P<matqty>-?\d+),"
    r"tmatqty=(?P<tmatqty>-?\d+),"
    r"bestbq=(?P<bestbq>[0-9,]+),"
    r"bestbp=(?P<bestbp>[0-9,]+),"
    r"bestsq=(?P<bestsq>[0-9,]+),"
    r"bestsp=(?P<bestsp>[0-9,]+)"
)


def parse_levels(s: str) -> List[int]:
    """解析逗號分隔的數值字串為整數列表"""
    return [int(x) for x in s.split(",") if x.strip().isdigit()]


def format_mattime(s: str) -> str:
    """
    將 mattime 字串 (如 84500, 130000) 格式化為 HH:MM:SS.mmm
    """
    # 補滿 6 位 (HHMMSS)
    s = s.zfill(6)
    # 取出 HH, MM, SS
    h = s[:2]
    m = s[2:4]
    sec = s[4:6]
    # 處理毫秒 (如果有，通常 mattime 可能是 HHMMSSmmm)
    ms = "000"
    if len(s) > 6:
        ms = s[6:].ljust(3, '0')[:3] # 取前3位或補0
    
    return f"{h}:{m}:{sec}.{ms}"


# ===============================================================
# 解析 TXF / MXF 報價
# ===============================================================
def parse_quote(line: str) -> Optional[QuoteSnapshot]:
    """
    解析單行 Log 文字為 QuoteSnapshot 物件
    """

    if "Symbol=TXF" not in line and "Symbol=MXF" not in line:
        return None

    m = QUOTE_REGEX.search(line)
    if not m:
        return None

    # 剔除盤前試搓資料 (tmatqty 為 -1)
    tmatqty = int(m.group("tmatqty"))
    if tmatqty == -1:
        return None

    raw = m.group("symbol")
    if raw.startswith("TXF"):
        symbol = "TXF"
    elif raw.startswith("MXF"):
        symbol = "MXF"
    else:
        return None

    # 改用 mattime 欄位
    mattime_raw = m.group("mattime")
    time_str = format_mattime(mattime_raw)

    return QuoteSnapshot(
        symbol=symbol,
        time_str=time_str,
        matpri=int(m.group("matpri")),
        total_vol=tmatqty,
        bestbq=parse_levels(m.group("bestbq")),
        bestbp=parse_levels(m.group("bestbp")),
        bestsq=parse_levels(m.group("bestsq")),
        bestsp=parse_levels(m.group("bestsp")),
    )



# ===============================================================
# 選擇 Logs 根目錄 + 輸入日期區間
# ===============================================================
def choose_log_root() -> Optional[str]:
    """彈出視窗選擇 Logs 資料夾"""
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askdirectory(
        title="選擇 Logs 根目錄 (例如 H:\\Coding\\python\\TickBarsGUI\\Logs)"
    )
    root.destroy()
    return path if path else None

def input_date_ranges() -> (List[tuple], str):
    """
    讓使用者在 Console 輸入日期區間
    回傳: (區間列表, 原始輸入字串)
    """
    text = input("請輸入日期區間 (格式: yyyymmdd-yyyymmdd，多個用逗號分隔；單一天可寫 yyyymmdd)：\n> ").strip()
    ranges: List[tuple] = []

    if not text:
        return ranges, text

    parts = text.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            s, e = part.split("-", 1)
        else:
            s = e = part

        s = s.strip()
        e = e.strip()
        if len(s) == 8 and len(e) == 8 and s.isdigit() and e.isdigit():
            if s > e:
                s, e = e, s
            ranges.append((s, e))

    return ranges, text


def collect_log_files(root_dir: str, date_ranges: List[tuple]) -> List[str]:
    """
    蒐集指定日期區間內的 event.log 檔案
    """
    if not date_ranges:
        return []

    log_files: List[str] = []
    date_set = set()

    for entry in os.listdir(root_dir):
        full_path = os.path.join(root_dir, entry)
        if not os.path.isdir(full_path):
            continue
        if len(entry) == 8 and entry.isdigit():
            in_range = False
            for (start, end) in date_ranges:
                if start <= entry <= end:
                    in_range = True
                    break
            if not in_range:
                continue

            date_set.add(entry)
            for f in glob.glob(os.path.join(full_path, "event.log")):
                log_files.append(f)


    log_files.sort()
    print(f"找到日期資料夾：{sorted(date_set)}")
    print(f"總共找到 {len(log_files)} 個 log 檔。")
    return log_files


# ===============================================================
# Session 分類（日盤 / 夜盤）
# ===============================================================
def classify_session(time_str: str) -> str:
    """
    根據時間判斷是日盤 (DAY) 還是夜盤 (NIGHT)
    """
    h = int(time_str[:2])
    m = int(time_str[3:5])

    # 日盤 08:45–13:45
    if (h == 8 and m >= 45) or (9 <= h <= 12) or (h == 13 and m <= 45):
        return "DAY"

    # 夜盤 15:00–23:59
    if 15 <= h <= 23:
        return "NIGHT"

    # 夜盤 00:00–05:00
    if 0 <= h <= 5:
        return "NIGHT"

    return "NONE"


# ===============================================================
# Session 狀態初始化
# ===============================================================
def init_session_state() -> Dict[str, Any]:
    """初始化單一 Session 的狀態字典"""
    return {
        "position": 0,          # 目前倉位：0=空手, 1=多單, -1=空單
        "entry_price": None,    # 進場價格
        "entry_time": None,     # 進場時間

        "day_high": None,       # 當日最高價 (用於停損)
        "day_low": None,        # 當日最低價 (用於停損)

        "close_price": None,    # 收盤價
        "close_time": None,     # 收盤時間

        "pnl_short": 0.0,       # 空單累積損益
        "pnl_long": 0.0,        # 多單累積損益
        "trades": [],           # 交易紀錄列表 List[Trade]

        # 新增：1000筆 Block 統計
        "block": BlockStats(),
        "last_txf_vol": None,   # 上一筆 TXF 總量
        "last_mxf_vol": None,   # 上一筆 MXF 總量

        # 新增：持倉期間最高/最低價 (用於計算最大浮盈/浮虧)
        "trade_high": None,
        "trade_low": None,
    }


# ===============================================================
# 時間轉秒數，用於持倉時間統計
# ===============================================================
def time_str_to_seconds(t: str) -> float:
    """將 HH:MM:SS.mmm 時間字串轉換為當天秒數"""
    # "HH:MM:SS.mmm"
    h = int(t[:2])
    m = int(t[3:5])
    s = int(t[6:8])
    ms = int(t[9:12])
    return h * 3600 + m * 60 + s + ms / 1000.0


# ===============================================================
# 單一 Session 的 Tick 邏輯
# ===============================================================
def run_tick(sess: Dict[str, Any], q: QuoteSnapshot) -> None:
    """
    處理每一筆 Quote。
    """

    # 更新收盤價 (以 TXF 為主，或最後一筆)
    if q.symbol == "TXF":
        sess["close_price"] = q.matpri
        sess["close_time"] = q.time_str

        # 更新 Day High/Low
        if sess["day_high"] is None or q.matpri > sess["day_high"]:
            sess["day_high"] = q.matpri
        if sess["day_low"] is None or q.matpri < sess["day_low"]:
            sess["day_low"] = q.matpri

    # --- 1. 檢查成交量變化 ---
    last_vol_key = "last_txf_vol" if q.symbol == "TXF" else "last_mxf_vol"
    prev_vol = sess[last_vol_key]

    if prev_vol is None:
        sess[last_vol_key] = q.total_vol
        return # 第一筆只記錄，無法算差額

    vol_diff = q.total_vol - prev_vol
    sess[last_vol_key] = q.total_vol

    if vol_diff <= 0:
        return # 沒有成交量增加，跳過

    # --- 2. 判斷內外盤 (Active Buy/Sell) ---
    ask_price = q.bestsp[0] if q.bestsp else None
    bid_price = q.bestbp[0] if q.bestbp else None
    
    direction_val = 0
    if ask_price and q.matpri >= ask_price:
        direction_val = 1 # Buy (外盤)
    elif bid_price and q.matpri <= bid_price:
        direction_val = -1 # Sell (內盤)
    
    # 累加 Diff
    block = sess["block"]
    if q.symbol == "TXF":
        block.txf_diff += (direction_val * vol_diff) # 這裡使用成交量加權
    else:
        block.mxf_diff += (direction_val * vol_diff)

    # 累加 Block 計數 (大小台合計)
    block.count += 1
    
    # 紀錄價格
    block.prices.append(q.matpri)
    block.times.append(q.time_str)

    # --- 3. 檢查停損 (隨時檢查) ---
    pos = sess["position"]
    if pos != 0:
        # 更新持倉期間最高/最低價
        if sess["trade_high"] is None or q.matpri > sess["trade_high"]:
            sess["trade_high"] = q.matpri
        if sess["trade_low"] is None or q.matpri < sess["trade_low"]:
            sess["trade_low"] = q.matpri

        # 持空 (-1): 停損 = 股價創新高 (Day High)
        if pos == -1:
            if sess["day_high"] is not None and q.matpri >= sess["day_high"]:
                # 觸發停損
                execute_exit(sess, q.matpri, q.time_str, "stop_loss_new_high")
        
        # 持多 (1): 停損 = 股價創新低 (Day Low)
        elif pos == 1:
            if sess["day_low"] is not None and q.matpri <= sess["day_low"]:
                # 觸發停損
                execute_exit(sess, q.matpri, q.time_str, "stop_loss_new_low")

    # --- 4. 每 1000 筆結算 ---
    if block.count >= 1000:
        process_block(sess, q)
        block.reset()


def process_block(sess: Dict[str, Any], q: QuoteSnapshot):
    """
    處理 1000 筆 Block 結束後的邏輯：判斷趨勢、產生訊號、執行交易
    """
    block = sess["block"]
    
    # 1. 判斷 Trend (趨勢)
    if not block.prices:
        return

    min_p = min(block.prices)
    max_p = max(block.prices)
    
    min_idx = block.prices.index(min_p)
    max_idx = block.prices.index(max_p)
    
    trend = "NONE"
    if min_idx < max_idx:
        trend = "UP"
    elif min_idx > max_idx:
        trend = "DOWN"
    
    # 2. 判斷 Signal (訊號)
    signal = 0
    
    # 放空條件: Trend UP 且背離 (小台買, 大台賣)
    # if trend == "UP":
    if block.mxf_diff > 0 and block.txf_diff < 0:
        signal = -1 # Short
            
    # 作多條件: Trend DOWN 且背離 (小台賣, 大台買)
    # elif trend == "DOWN":
    if block.mxf_diff < 0 and block.txf_diff > 0:
        signal = 1 # Long

    if signal != 0:
        print(f"[{q.time_str}] 訊號偵測: Signal={signal}, 價格={q.matpri}, TXF差={block.txf_diff}, MXF差={block.mxf_diff}")

    # 3. 執行交易
    pos = sess["position"]
    
    if pos == 0:
        if signal != 0:
            sess["position"] = signal
            sess["entry_price"] = q.matpri
            sess["entry_time"] = q.time_str
            # 初始化持倉期間最高/最低價
            sess["trade_high"] = q.matpri
            sess["trade_low"] = q.matpri
            
            action = "多單進場" if signal == 1 else "空單進場"
            print(f"[{q.time_str}] {action}: 價格={q.matpri}")
    
    elif pos == -1:
        # 持空時，出現反向訊號 (Long Signal) -> 平倉並反手
        if signal == 1:
            execute_exit(sess, q.matpri, q.time_str, "reverse_signal")
            # 反手做多
            sess["position"] = 1
            sess["entry_price"] = q.matpri
            sess["entry_time"] = q.time_str
            # 初始化持倉期間最高/最低價
            sess["trade_high"] = q.matpri
            sess["trade_low"] = q.matpri
            print(f"[{q.time_str}] 多單進場 (反手): 價格={q.matpri}")

    elif pos == 1:
        # 持多時，出現反向訊號 (Short Signal) -> 平倉並反手
        if signal == -1:
            execute_exit(sess, q.matpri, q.time_str, "reverse_signal")
            # 反手做空
            sess["position"] = -1
            sess["entry_price"] = q.matpri
            sess["entry_time"] = q.time_str
            # 初始化持倉期間最高/最低價
            sess["trade_high"] = q.matpri
            sess["trade_low"] = q.matpri
            print(f"[{q.time_str}] 空單進場 (反手): 價格={q.matpri}")

    # 4. 列印狀態 (移除，只保留進出場)
    pass


def execute_exit(sess: Dict[str, Any], price: int, time_str: str, reason: str):
    """執行平倉邏輯"""
    entry_price = sess["entry_price"]
    direction = sess["position"]
    
    if direction == 0:
        return

    pnl = 0
    max_floating_profit = 0
    max_floating_loss = 0

    if direction == 1: # Long
        pnl = price - entry_price
        sess["pnl_long"] += pnl
        # 多單：最高價-進場價=最大浮盈, 最低價-進場價=最大浮虧
        if sess["trade_high"] is not None:
            max_floating_profit = sess["trade_high"] - entry_price
        if sess["trade_low"] is not None:
            max_floating_loss = sess["trade_low"] - entry_price

    elif direction == -1: # Short
        pnl = entry_price - price
        sess["pnl_short"] += pnl
        # 空單：進場價-最低價=最大浮盈, 進場價-最高價=最大浮虧
        if sess["trade_low"] is not None:
            max_floating_profit = entry_price - sess["trade_low"]
        if sess["trade_high"] is not None:
            max_floating_loss = entry_price - sess["trade_high"]

    print(f"[{time_str}] 平倉: 價格={price}, 損益={pnl}, 原因={reason}, 最大浮盈={max_floating_profit}, 最大浮虧={max_floating_loss}")
        
    sess["trades"].append(
        Trade(
            date="", # 稍後填
            file="",
            session="",
            direction=direction,
            entry_time=sess["entry_time"],
            exit_time=time_str,
            entry_price=entry_price,
            exit_price=price,
            pnl=pnl,
            exit_reason=reason,
        )
    )
    
    sess["position"] = 0
    sess["entry_price"] = None
    sess["entry_time"] = None
    sess["trade_high"] = None
    sess["trade_low"] = None


# ===============================================================
# 單一檔案回測
# ===============================================================
def backtest_single_file(path: str) -> Dict[str, Any]:
    """
    對單一 Log 檔進行回測
    """
    day = init_session_state()
    night = init_session_state()

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            q = parse_quote(line)
            if q is None:
                continue

            sess_name = classify_session(q.time_str)
            if sess_name == "NONE":
                continue

            if sess_name == "DAY":
                run_tick(day, q)
            else:
                # 遇到夜盤時，若日盤仍有倉位，先進行結算 (修正 Log 順序)
                if day["position"] != 0 and day["close_price"] is not None:
                    execute_exit(day, day["close_price"], day["close_time"], "close_price_settlement")
                
                run_tick(night, q)

    # 未平倉以最後收盤價結算
    for sess in (day, night):
        if sess["position"] != 0 and sess["close_price"] is not None:
            # 結算時 diff 設為 0 或最後狀態 (這裡簡化設為 0)
            execute_exit(sess, sess["close_price"], sess["close_time"], "close_price_settlement")

    return {"day": day, "night": night}


# ===============================================================
# 多檔回測
# ===============================================================
def backtest_multi(files: List[str]) -> pd.DataFrame:
    """
    對多個檔案進行回測並彙整結果
    """
    all_trades: List[Trade] = []

    for path in files:
        # 解析日期 (假設父資料夾名稱為日期 YYYYMMDD)
        date_folder = os.path.basename(os.path.dirname(path))
        if not (len(date_folder) == 8 and date_folder.isdigit()):
             # 如果無法從資料夾取得，嘗試從檔名或其他方式，這裡預設為 Unknown
             date_folder = "Unknown"

        print(f"處理檔案 {date_folder} {os.path.basename(path)}...")
        result = backtest_single_file(path)
        fname = os.path.basename(path)

        for session_name in ("DAY", "NIGHT"):
            sess = result["day"] if session_name == "DAY" else result["night"]

            for t in sess["trades"]:
                t.date = date_folder # 填入日期
                t.file = fname
                t.session = session_name
                all_trades.append(t)

            print(f"  {session_name}: "
                f"空單損益={sess['pnl_short']:.2f}, "
                f"多單損益={sess['pnl_long']:.2f}, "
                f"總計={sess['pnl_short'] + sess['pnl_long']:.2f}")


    rows = []
    for t in all_trades:
        rows.append({
            "date": t.date,
            "file": t.file,
            "session": t.session,
            "direction": "SHORT" if t.direction == -1 else "LONG",
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "exit_reason": t.exit_reason,
        })

    df = pd.DataFrame(rows)
    return df


# ===============================================================
# 統計：持倉時間 / 勝率 / 最大連續虧損
# ===============================================================
def compute_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """計算回測統計數據"""
    stats: Dict[str, Any] = {}

    closed = df.dropna(subset=["pnl", "exit_time"]).copy()
    if closed.empty:
        stats["avg_hold_seconds"] = None
        stats["avg_hold_minutes"] = None
        stats["win_rate"] = None
        stats["max_consecutive_loss"] = None
        stats["closed_trades"] = closed
        return stats

    hold_seconds_list = []
    for _, row in closed.iterrows():
        t_entry = time_str_to_seconds(row["entry_time"])
        t_exit = time_str_to_seconds(row["exit_time"])
        hold_seconds_list.append(max(0.0, t_exit - t_entry))

    closed["hold_seconds"] = hold_seconds_list
    stats["closed_trades"] = closed

    stats["avg_hold_seconds"] = sum(hold_seconds_list) / len(hold_seconds_list)
    stats["avg_hold_minutes"] = stats["avg_hold_seconds"] / 60.0

    wins = (closed["pnl"] > 0).sum()
    total = len(closed)
    stats["win_rate"] = wins / total if total > 0 else None

    max_consec_loss = 0
    cur = 0
    
    # 新增統計：最大連續虧損點數 (含時間)
    max_consec_loss_amount = 0.0
    cur_consec_loss_amount = 0.0
    
    # 輔助變數：記錄日期+時間
    consec_start_dt = None
    max_consec_loss_start_dt = None
    max_consec_loss_end_dt = None

    for i, row in closed.iterrows():
        pnl = row["pnl"]
        dt_str = f"{row['date']} {row['exit_time']}" # 組合日期時間

        if pnl < 0:
            cur += 1
            if cur == 1:
                consec_start_dt = dt_str # 記錄這波連虧的開始時間 (出場時間)
            
            cur_consec_loss_amount += pnl
            
            if cur > max_consec_loss:
                max_consec_loss = cur
            
            if cur_consec_loss_amount < max_consec_loss_amount: # 虧損是負值，越小代表虧越多
                max_consec_loss_amount = cur_consec_loss_amount
                max_consec_loss_start_dt = consec_start_dt
                max_consec_loss_end_dt = dt_str
        else:
            cur = 0
            cur_consec_loss_amount = 0.0
            consec_start_dt = None

    stats["max_consecutive_loss"] = max_consec_loss
    stats["max_consecutive_loss_amount"] = max_consec_loss_amount
    stats["max_consecutive_loss_period"] = f"{max_consec_loss_start_dt} ~ {max_consec_loss_end_dt}"

    # 新增統計：最大單筆虧損點數 (含時間)
    if not closed.empty:
        min_pnl_row = closed.loc[closed["pnl"].idxmin()]
        stats["max_single_loss_amount"] = min_pnl_row["pnl"]
        stats["max_single_loss_time"] = f"{min_pnl_row['date']} {min_pnl_row['exit_time']}"
    else:
        stats["max_single_loss_amount"] = 0.0
        stats["max_single_loss_time"] = None

    return stats


# ===============================================================
# 損益曲線
# ===============================================================
def plot_equity_curve(df: pd.DataFrame, title: str = "Equity Curve", base_name: str = "") -> None:
    """繪製並儲存損益曲線圖"""
    closed = df.dropna(subset=["pnl"]).copy()
    if closed.empty:
        print("無任何平倉交易，無法繪製損益曲線。")
        return

    closed = closed.reset_index(drop=True)
    closed["cum_pnl"] = closed["pnl"].cumsum()

    plt.figure()
    plt.plot(range(1, len(closed) + 1), closed["cum_pnl"])
    plt.xlabel("Trade #")
    plt.ylabel("Cumulative PnL")
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"equity_curve_{base_name}.png")
    print(f"損益曲線已儲存為 equity_curve_{base_name}.png")
    # plt.show() # 避免阻塞


# ===============================================================
# main
# ===============================================================
def main():
    root_dir = choose_log_root()
    if not root_dir:
        print("未選擇 Logs 根目錄，程式結束。")
        return

    date_ranges, raw_text = input_date_ranges()
    if not date_ranges:
        print("未輸入有效日期區間，程式結束。")
        return

    files = collect_log_files(root_dir, date_ranges)
    if not files:
        print("指定日期區間內沒有找到任何 log 檔。")
        return

    df = backtest_multi(files)
    if df.empty:
        print("沒有任何交易紀錄。")
        return

    # 統計與輸出
    stats = compute_stats(df)
    closed = stats["closed_trades"]

    base_name = raw_text.replace(",", "_")  
    # csv_name = f"trades_summary_{base_name}.csv"
    xlsx_name = f"trades_summary_{base_name}.xlsx"
    # df.to_csv(csv_name, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_name, index=False)
    print(f"已輸出 {xlsx_name}")
    # print("已取消 CSV/Excel 輸出。")

    print("\n=========== 統計結果（所有檔案 + 日/夜盤） ===========")
    print(f"總平倉筆數：{len(closed)}")
    if len(closed) > 0:
        print(f"總損益：{closed['pnl'].sum():.2f}")
        print(f"平均持倉時間：{stats['avg_hold_seconds']:.2f} 秒 (~ {stats['avg_hold_minutes']:.2f} 分鐘)")
        print(f"勝率：{stats['win_rate'] * 100:.2f}%")
    print(f"最大連續虧損筆數：{stats['max_consecutive_loss']}")
    print(f"最大連續虧損點數：{stats['max_consecutive_loss_amount']:.2f} (期間: {stats['max_consecutive_loss_period']})")
    print(f"最大單筆虧損點數：{stats['max_single_loss_amount']:.2f} (時間: {stats['max_single_loss_time']})")
    print("=====================================================")

    plot_equity_curve(df, title=f"TXF/MXF 1000-Tick {base_name}", base_name=base_name)


if __name__ == "__main__":
    main()
