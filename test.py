import os
import glob
import re
import tkinter as tk
from tkinter import filedialog
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import pandas as pd
import matplotlib.pyplot as plt


# ===============================================================
# 資料結構
# ===============================================================
@dataclass
class QuoteSnapshot:
    symbol: str      # "TXF" or "MXF"
    time_str: str    # "HH:MM:SS.mmm"
    matpri: int
    bestbq: List[int]
    bestbp: List[int]
    bestsq: List[int]
    bestsp: List[int]


@dataclass
class Trade:
    file: str        # 檔名
    session: str     # "DAY" / "NIGHT"
    direction: int   # -1 = 空, 1 = 多
    entry_time: str
    exit_time: Optional[str]
    entry_price: int
    exit_price: Optional[int]
    pnl: Optional[float]
    exit_reason: Optional[str]


# ===============================================================
# 解析 REGEX
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
    return [int(x) for x in s.split(",") if x.strip().isdigit()]


# ===============================================================
# 解析 TXF / MXF 報價
# ===============================================================
def parse_quote(line: str) -> Optional[QuoteSnapshot]:

    if "Symbol=TXF" not in line and "Symbol=MXF" not in line:
        return None

    m = QUOTE_REGEX.search(line)
    if not m:
        return None

    # 剔除盤前
    if int(m.group("tmatqty")) == -1:
        return None

    raw = m.group("symbol")
    if raw.startswith("TXF"):
        symbol = "TXF"
    elif raw.startswith("MXF"):
        symbol = "MXF"
    else:
        return None

    # 安全解析時間：從整行找 00:00:00.000 樣式
    time_match = re.search(r"(\d{2}:\d{2}:\d{2}\.\d{3})", line)
    if not time_match:
        return None
    time_str = time_match.group(1)

    return QuoteSnapshot(
        symbol=symbol,
        time_str=time_str,
        matpri=int(m.group("matpri")),
        bestbq=parse_levels(m.group("bestbq")),
        bestbp=parse_levels(m.group("bestbp")),
        bestsq=parse_levels(m.group("bestsq")),
        bestsp=parse_levels(m.group("bestsp")),
    )



# ===============================================================
# 選擇 Logs 根目錄 + 輸入日期區間
# ===============================================================
def choose_log_root() -> Optional[str]:
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askdirectory(
        title="選擇 Logs 根目錄 (例如 H:\\Coding\\python\\TickBarsGUI\\Logs)"
    )
    root.destroy()
    return path if path else None

def input_date_ranges() -> (List[tuple], str):
    """
    讓你在 console 輸入日期區間：
    - 單一區間：20251101-20251105
    - 單一天：20251103
    - 多個區間：20251101-20251105,20251110-20251112
    - 回傳 (區間list, 原始輸入字串)
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
    在 root_dir 下面找日期資料夾 (yyyyMMdd)，
    如果在指定日期區間中，就找裡面的 *.log / *.txt 檔案。
    """
    if not date_ranges:
        return []

    log_files: List[str] = []
    date_set = set()

    for entry in os.listdir(root_dir):
        full_path = os.path.join(root_dir, entry)
        if not os.path.isdir(full_path):
            continue
        # 資料夾名稱必須是 8 位數字 (yyyymmdd)
        if len(entry) == 8 and entry.isdigit():
            # 檢查是否落在任一區間
            in_range = False
            for (start, end) in date_ranges:
                if start <= entry <= end:
                    in_range = True
                    break
            if not in_range:
                continue

            date_set.add(entry)
            # 只抓 event*.log，不抓其他 log
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
    return {
        "position": 0,
        "entry_price": None,
        "entry_time": None,

        "high_for_short": None,   # 作空創高判斷
        "low_for_long": None,     # 作多創低判斷

        "day_high": None,
        "day_high_time": None,
        "day_low": None,
        "day_low_time": None,

        "close_price": None,
        "close_time": None,

        "pnl_short": 0.0,
        "pnl_long": 0.0,
        "trades": [],             # List[Trade]
    }


# ===============================================================
# 時間轉秒數，用於持倉時間統計
# ===============================================================
def time_str_to_seconds(t: str) -> float:
    # "HH:MM:SS.mmm"
    h = int(t[:2])
    m = int(t[3:5])
    s = int(t[6:8])
    ms = int(t[9:12])
    return h * 3600 + m * 60 + s + ms / 1000.0


# ===============================================================
# 單一 Session 的 Tick 邏輯
# ===============================================================
def run_tick(sess: Dict[str, Any], txf: QuoteSnapshot, mxf: Optional[QuoteSnapshot]) -> None:

    # 更新收盤
    sess["close_price"] = txf.matpri
    sess["close_time"] = txf.time_str

    # 更新最高 / 最低
    if sess["day_high"] is None or txf.matpri > sess["day_high"]:
        sess["day_high"] = txf.matpri
        sess["day_high_time"] = txf.time_str

    if sess["day_low"] is None or txf.matpri < sess["day_low"]:
        sess["day_low"] = txf.matpri
        sess["day_low_time"] = txf.time_str

    # 創高（作空）
    is_new_high = False    # 給今天作空專用
    if sess["high_for_short"] is None or txf.matpri >= sess["high_for_short"]:
        sess["high_for_short"] = txf.matpri
        is_new_high = True

    # 創低（作多）
    is_new_low = False
    if sess["low_for_long"] is None or txf.matpri <= sess["low_for_long"]:
        sess["low_for_long"] = txf.matpri
        is_new_low = True

    if mxf is None:
        return

    same_bid = txf.bestbp[0] == mxf.bestbp[0]
    same_ask = txf.bestsp[0] == mxf.bestsp[0]

    big_buy = sum(txf.bestbq)
    big_sell = sum(txf.bestsq)
    small_buy = sum(mxf.bestbq)
    small_sell = sum(mxf.bestsq)

    signal = 0

    # 創高 → 作空訊號
    if is_new_high and same_bid and same_ask:
        if small_buy > small_sell and big_buy < big_sell:
            signal = -1

    # 創低 → 作多訊號
    if signal == 0 and is_new_low and same_bid and same_ask:
        if small_buy < small_sell and big_buy > big_sell:
            signal = 1

    pos = sess["position"]

    # 空手 → 開倉
    if pos == 0:
        if signal != 0:
            sess["position"] = signal
            sess["entry_price"] = txf.matpri
            sess["entry_time"] = txf.time_str
        return

    # 持空 → 出現多訊號平倉（不反手）
    if pos == -1 and signal == 1:
        exit_price = txf.matpri
        pnl = sess["entry_price"] - exit_price
        sess["pnl_short"] += pnl

        sess["trades"].append(
            Trade(
                file="",   # 稍後填
                session="",  # 稍後填
                direction=-1,
                entry_time=sess["entry_time"],
                exit_time=txf.time_str,
                entry_price=sess["entry_price"],
                exit_price=exit_price,
                pnl=pnl,
                exit_reason="reverse_long_signal",
            )
        )

        sess["position"] = 0
        sess["entry_price"] = None
        sess["entry_time"] = None
        return

    # 持多 → 出現空訊號平倉（不反手）
    if pos == 1 and signal == -1:
        exit_price = txf.matpri
        pnl = exit_price - sess["entry_price"]
        sess["pnl_long"] += pnl

        sess["trades"].append(
            Trade(
                file="",
                session="",
                direction=1,
                entry_time=sess["entry_time"],
                exit_time=txf.time_str,
                entry_price=sess["entry_price"],
                exit_price=exit_price,
                pnl=pnl,
                exit_reason="reverse_short_signal",
            )
        )

        sess["position"] = 0
        sess["entry_price"] = None
        sess["entry_time"] = None
        return


# ===============================================================
# 單一檔案回測
# ===============================================================
def backtest_single_file(path: str) -> Dict[str, Any]:
    day = init_session_state()
    night = init_session_state()
    last_mxf: Optional[QuoteSnapshot] = None

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            q = parse_quote(line)
            if q is None:
                continue

            sess_name = classify_session(q.time_str)
            if sess_name == "NONE":
                continue

            if q.symbol == "MXF":
                last_mxf = q
                continue

            if q.symbol == "TXF":
                if sess_name == "DAY":
                    run_tick(day, q, last_mxf)
                else:
                    run_tick(night, q, last_mxf)

    # 未平倉以最後收盤價結算
    for sess in (day, night):
        if sess["position"] != 0 and sess["close_price"] is not None:
            exit_price = sess["close_price"]
            exit_time = sess["close_time"]

            if sess["position"] == -1:
                pnl = sess["entry_price"] - exit_price
                sess["pnl_short"] += pnl
                direction = -1
            else:
                pnl = exit_price - sess["entry_price"]
                sess["pnl_long"] += pnl
                direction = 1

            sess["trades"].append(
                Trade(
                    file="",   # 之後填
                    session="",  # 之後填
                    direction=direction,
                    entry_time=sess["entry_time"],
                    exit_time=exit_time,
                    entry_price=sess["entry_price"],
                    exit_price=exit_price,
                    pnl=pnl,
                    exit_reason="close_price_settlement",
                )
            )

    return {"day": day, "night": night}


# ===============================================================
# 多檔回測
# ===============================================================
def backtest_multi(files: List[str]) -> pd.DataFrame:
    all_trades: List[Trade] = []

    for path in files:
        result = backtest_single_file(path)
        fname = os.path.basename(path)

        for session_name in ("DAY", "NIGHT"):
            sess = result["day"] if session_name == "DAY" else result["night"]

            for t in sess["trades"]:
                t.file = fname
                t.session = session_name
                all_trades.append(t)

            fname = os.path.basename(path)
            date_folder = os.path.basename(os.path.dirname(path))

            print(f"{date_folder} {fname} - {session_name}: "
                f"ShortPnL={sess['pnl_short']:.2f}, "
                f"LongPnL={sess['pnl_long']:.2f}, "
                f"Total={sess['pnl_short'] + sess['pnl_long']:.2f}")


    rows = []
    for t in all_trades:

        # 從 file 路徑取得日期資料夾
        # path example: H:\Coding\python\Logs\20251103\event.log
        # date_folder = "20251103"
        date_folder = os.path.basename(os.path.dirname(os.path.join(root_dir, t.file))) \
                    if "\\" in t.file or "/" in t.file else t.file[:8]

        rows.append({
            "date": date_folder,   # <── 新增在最前面
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
    for v in closed["pnl"]:
        if v < 0:
            cur += 1
            if cur > max_consec_loss:
                max_consec_loss = cur
        else:
            cur = 0
    stats["max_consecutive_loss"] = max_consec_loss

    return stats


# ===============================================================
# 損益曲線
# ===============================================================
def plot_equity_curve(df: pd.DataFrame, title: str = "Equity Curve") -> None:
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
    plt.savefig("equity_curve.png")
    print("損益曲線已儲存為 equity_curve.png")
    plt.show()


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

    csv_name = f"trades_summary_{base_name}.csv"
    xlsx_name = f"trades_summary_{base_name}.xlsx"

    df.to_csv(csv_name, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_name, index=False)
    print(f"已輸出 {csv_name} 和 {xlsx_name}")

    print("\n=========== 統計結果（所有檔案 + 日/夜盤） ===========")
    print(f"總平倉筆數：{len(closed)}")
    if len(closed) > 0:
        print(f"總損益：{closed['pnl'].sum():.2f}")
        print(f"平均持倉時間：{stats['avg_hold_seconds']:.2f} 秒 (~ {stats['avg_hold_minutes']:.2f} 分鐘)")
        print(f"勝率：{stats['win_rate'] * 100:.2f}%")
        print(f"最大連續虧損筆數：{stats['max_consecutive_loss']}")
    print("=====================================================")

    plot_equity_curve(df, title="TXF/MXF Strategy Equity Curve")


if __name__ == "__main__":
    main()
