"""
strategy_core.py
----------------
TradingStrategy 主體：接收 tick、計算均價、產生訊號，並呼叫 OrderManager/Notifier/UIUpdater。
"""

from .calculator import parse_time_string, to_ms, calc_fibonacci_levels
from .log_cleaner import cleanup_yuanta_logs, clean_logs_except_today
from .order_manager import OrderManager
from .ui_updater import UIUpdater
from .notifier import Notifier, RedirectText
import sys
import json
import threading  # 預留給未來背景工作（目前沒有使用，但保留結構）
import datetime   # 預留給未來時間相關計算（目前沒有使用，但保留結構）
from typing import Dict

import wx
from colorama import Fore, Style, Back
# === 安全顏色解析器（取代 eval） ===
COLORAMA_MAP = {
    "Fore.RED": Fore.RED,
    "Fore.GREEN": Fore.GREEN,
    "Fore.YELLOW": Fore.YELLOW,
    "Fore.CYAN": Fore.CYAN,
    "Fore.WHITE": Fore.WHITE,
    "Fore.BLACK": Fore.BLACK,
    "Fore.MAGENTA": Fore.MAGENTA,

    "Style.BRIGHT": Style.BRIGHT,
    "Style.RESET_ALL": Style.RESET_ALL,

    "Back.WHITE": Back.WHITE,
    "Back.RED": Back.RED,
    "Back.BLUE": Back.BLUE,
    "Back.GREEN": Back.GREEN,
}


def resolve_color(color_string: str) -> str:
    """
    將像是 "Fore.RED + Style.BRIGHT" 這類字串，安全轉成 colorama ANSI 字串。

    不使用 eval，而是：
    - 以 "+" 拆開每一段 token
    - 透過 COLORAMA_MAP 對應 Fore/Style/Back 物件
    """
    if not color_string:
        return ""
    parts = [p.strip() for p in color_string.split("+")]
    out = ""
    for p in parts:
        if p in COLORAMA_MAP:
            out += COLORAMA_MAP[p]
    return out
# === 安全顏色解析器結束 ===


class TradingStrategy:
    """
    交易策略核心類別：負責「整理 tick 資料、維護區間狀態、計算費波、產生進出場訊號」。

    主要流程（從外部角度看）：
    1. 外部程式每來一筆 TXF/MXF tick，就呼叫 :meth:`execate_TXF_MXF`。
    2. `execate_TXF_MXF` 會依商品（TXF/MXF）更新對應資料庫，並呼叫 :meth:`calculate_time`。
    3. :meth:`calculate_time` 會在確定「成交量有前進」後，累積時間並呼叫 :meth:`calculate_tickbars`。
    4. :meth:`calculate_tickbars` 會：
       - 更新區間高低價、均價、TR、成交量。
       - 檢查日高日低突破，決定是否要重置區間與觸發停損。
       - 每筆 tick 檢查：移動停利、停損觸發、是否觸價進場。
       - 如果 group_size 達到門檻（例如 1000 筆），呼叫 :meth:`show_tickbars` 產生「一根 tickbar 的訊號」。
    5. :meth:`show_tickbars` 會依原來邏輯判斷：
       - 是否形成疑似頭部/底部。
       - 是否要發出「作多/作空的 signal_trade 訊號」給 OrderManager。
       - 最後呼叫 :meth:`print_trade_info` 以彩色格式印出全部資訊。
    6. :meth:`calculate_and_update` 負責更新 Fibonacci 費波價、infoDataGrid 與趨勢建議。
    """

    def __init__(self, frame: wx.Frame):
        """
        建立一個 TradingStrategy 物件。

        參數
        -----
        frame : wx.Frame
            主視窗物件，裡面包含各種 GUI 控制項，例如：
            - `monitorTradeSignal`：顯示終端訊息的 TextCtrl。
            - `compareInfoGrid` / `avgPrice` 等，用來顯示各種數據。
        """
        # ===== 連結 GUI 與輸出 =====
        self.frame = frame  # 主視窗參考，用來存取所有 GUI 控制項

        # 將 stdout / stderr 導入 GUI 終端視窗，之後的 print 都會顯示在 monitorTradeSignal
        sys.stdout = RedirectText(self.frame.monitorTradeSignal)
        sys.stderr = RedirectText(self.frame.monitorTradeSignal)

        # ===== 管理物件 =====
        # 通知物件：負責印 log、推播 Telegram 等
        config = load_json("./config.json")
        self.notifier = Notifier(
            frame=self.frame,
            telegram_token=config.get("telegram_token"),  # Telegram 機器人 token
            telegram_chat_id=config.get(
                "telegram_chat_id"),  # Telegram 接收訊息的 chat_id
        )
        # UI 更新物件：只專心負責更新各種 Grid / Label
        self.ui = UIUpdater(self.frame)
        # 下單控制物件：負責進出場、停損停利邏輯與下單 API 的整合
        self.order = OrderManager(self.frame, self.ui, self.notifier)

        # ===== 狀態變數 =====
        # 1) 單一商品資料庫：用 dict 存當前累積量與時間等資訊
        self.TXF_database: Dict = {}  # TXF 商品的成交量 / 時間 / 價格資料
        self.MXF_database: Dict = {}  # MXF 商品的成交量 / 時間 / 價格資料

        # 2) 合併均價相關
        self.TXF_MXF_tol_value: float = 0.0   # TXF / MXF 的 TR 加總（price * qty）
        self.TXF_MXF_avg_price: float = 0.0   # 目前合併加權均價
        self.pre_TXF_MXF_avg_price: float = 0.0  # 上一根 tickbar 結束時的均價（用來判斷趨勢方向）

        # 3) 日內高 / 低價
        self.highest_price: int = 0              # 今日為止最高價
        self.lowest_price: int = 0               # 今日為止最低價
        self.previous_highest_price: int = 0     # 前一根 tickbar 記錄的日高
        self.previous_lowest_price: int = 0      # 前一根 tickbar 記錄的日低
        self.is_dayhigh: bool = True             # 日高是否仍有效（還沒被新的更高價突破）
        self.is_daylow: bool = True              # 日低是否仍有效（還沒被新的更低價跌破）

        # 4) group 與時間（用來組一根 tickbar 的狀態）
        self.matchtime: int = 0      # 累積毫秒數（本區間內的成交時間總長）
        self.group_size: int = 0     # 本區間內已累積的 tick 數
        self.tmp_qty: float = 0.0    # 本筆 tick 的口數（TXF 會乘以 4）
        self.new_price: float = 0.0  # 本筆 tick 的成交價

        # 5) tickbars 的歷史列表（每根 tickbar 完成後就 append 一筆）
        self.list_close_price = []                     # 每根 tickbar 收盤價列表
        self.list_tickbars_tol_time = []               # 每根 tickbar 的時間長度（毫秒）列表
        self.list_temp_tickbars_total_volume = []      # 每根 tickbar 的成交量列表
        self.list_temp_tickbars_big_price = []         # 每根 tickbar 的區間最高價列表
        self.list_temp_tickbars_small_price = []       # 每根 tickbar 的區間最低價列表
        self.list_temp_tickbars_avg_price = []         # 每根 tickbar 的區間均價列表

        # 6) 區間比較資料（當前尚未結束的這一段）
        self.temp_price_compare_database: Dict = {}  # 暫存目前這一個區間內的 high/low 等資訊
        self.temp_tickbars_total_volume: float = 0.0  # 目前區間內累積成交量
        self.temp_TXF_MXF_TR: float = 0.0             # 目前區間內 TR 加總（price * qty）
        self.temp_tickbars_avg_price: float = 0.0     # 目前區間內的加權平均價

        # 7) 「然而平均」——日高 / 日低附近的平均價格（用來判斷頭部 / 底部）
        self.temp_howeverHighest_total_volume: float = 0.0  # 日高附近累積成交量
        self.temp_TXF_MXF_howeverHighest: float = 0.0       # 日高附近 TR 加總
        self.temp_howeverHighest_avg_price: float = 0.0     # 日高附近平均價

        self.temp_howeverLowest_total_volume: float = 0.0   # 日低附近累積成交量
        self.temp_TXF_MXF_howeverLowest: float = 0.0        # 日低附近 TR 加總
        self.temp_howeverLowest_avg_price: float = 0.0      # 日低附近平均價

        # 8) 趨勢相關
        self.trending_up: bool = False    # 目前判定為偏多趨勢
        self.trending_down: bool = False  # 目前判定為偏空趨勢
        self.pre_ATR: float = 0.0         # 這裡當作「前一筆合併均價」使用，用來偵測均價是否翻轉

        # 9) Fibonacci 文字（顯示在 GUI 上）
        self.fibonacci_sell_str: str = ""  # 費波賣出價字串（例如："18000 : 17980 : ..."）
        self.fibonacci_buy_str: str = ""   # 費波買進價字串

        # 10) 疑似頭部 / 底部旗標（由 tickbar 速度 + 量價判斷觸發）
        self.suspected_sell: bool = False  # True 代表目前偵測到「疑似頭部」，準備找空點
        self.suspected_buy: bool = False   # True 代表目前偵測到「疑似底部」，準備找多點

        # 11) 舊版相容：給 YuantaOrdAPI.OnChkDeal 用的費波字串
        #     代表「當前多單 / 空單採用的那組 fibonacci 價格」
        self.fibonacci_chkBuy_str: str = "0"   # 目前多單使用的 Fibonacci 字串
        self.fibonacci_chkSell_str: str = "0"  # 目前空單使用的 Fibonacci 字串

        # 給 YuantaOrdAPI.Onktcheck 用的停利字串
        # 代表「當前多單 / 空單採用的那組 停利 價格」
        # self.stop_profit_chkBuy_str: str = "0"   # 目前多單使用的 停利 字串
        # self.stop_profit_chkSell_str: str = "0"  # 目前空單使用的 停利 字串

        # 啟動程式時清理一次，保留 1 天
        cleanup_yuanta_logs(".", keep_days=1)
        # 清理 Logs/<日期>/ 底下的所有檔案，但保留今天和所有 event.log。
        clean_logs_except_today()

        # 啟動自動收盤平倉監控（背景執行緒，由 OrderManager 內部管理）
        self.order.start_auto_liquidation()

        # 初始化完成訊息
        self.notifier.log(
            "✅ TradingStrategy 初始化完成",
            Fore.GREEN + Style.BRIGHT
        )

    # ===== 舊版相容屬性：直接轉接到 OrderManager 裡的狀態 =====
    @property
    def trading_buy(self) -> bool:
        """
        是否目前有「多單持倉」的旗標。

        這個屬性實際上是轉接到 ``self.order.trading_buy``，
        目的是讓舊版程式仍然可以用 ``self.trading_buy`` 讀寫。
        """
        return self.order.trading_buy

    @trading_buy.setter
    def trading_buy(self, v: bool) -> None:
        self.order.trading_buy = v

    @property
    def trading_sell(self) -> bool:
        """
        是否目前有「空單持倉」的旗標。

        實際資料儲存在 ``self.order.trading_sell`` 中。
        """
        return self.order.trading_sell

    @trading_sell.setter
    def trading_sell(self, v: bool) -> None:
        self.order.trading_sell = v

    # ===== 舊版相容方法 =====
    def telegram_bot_sendtext(self, msg: str) -> None:
        """
        舊版介面：發送 Telegram 訊息。

        新版實作：直接呼叫 :class:`Notifier` 內的 `send_telegram_if_enabled`。

        參數
        -----
        msg : str
            要發送的文字訊息。
        """
        self.notifier.send_telegram_if_enabled(msg)

    # =========================================================
    # Tick 入口
    # =========================================================

    def execate_TXF_MXF(self,
                        direction,
                        symbol: str,
                        RefPri, OpenPri, HighPri, LowPri,
                        MatchTime: str,
                        MatchPri,
                        MatchQty,
                        TolMatchQty,
                        Is_simulation) -> None:
        """
        外部呼叫入口：每來一筆 TXF/MXF tick 就呼叫這裡。

        這裡做三件事：
        1. 根據 `symbol` 判斷是 TXF 還是 MXF，設定本筆 `tmp_qty` 與 `new_price`。
        2. 把 tick 丟到對應商品的 :meth:`calculate_time` 裡處理成交量與時間。
        3. 讓後續邏輯決定是否產生 tickbar、進出場訊號。

        參數只要維持原本格式即可，這裡不改變既有邏輯。
        """
        # 先根據商品更新本筆 tick 的價格與口數
        if "XF" in symbol:
            # 標的名稱包含 XF（TXF / MXF 共用）：先更新本筆價格
            self.tmp_qty = 0                      # 先設為 0，真正的口數在 TXF / MXF 分支中設定
            self.new_price = float(MatchPri)      # 本筆成交價

        if "TXF" in symbol:
            # TXF：每一口視為 4 口 MXF 的等價量，所以乘以 4
            self.tmp_qty = 4 * float(MatchQty)
            self.calculate_time(
                self.TXF_database,
                RefPri, HighPri, LowPri,
                MatchQty, TolMatchQty, MatchTime, Is_simulation
            )
        elif "MXF" in symbol:
            # MXF：口數直接使用
            self.tmp_qty = float(MatchQty)
            self.calculate_time(
                self.MXF_database,
                RefPri, HighPri, LowPri,
                MatchQty, TolMatchQty, MatchTime, Is_simulation
            )

    # =========================================================
    # 成交量與時間累積
    # =========================================================

    def calculate_time(self,
                       database: Dict,
                       RefPri, HighPri, LowPri,
                       MatchQty, TolMatchQty,
                       MatchTime: str,
                       Is_simulation) -> None:
        """
        管理 TXF / MXF 各自的成交量與時間累積，並在「有新成交量」時觸發 :meth:`calculate_tickbars`。

        簡單說：
        - 第一次看到某商品的 tick：初始化它的資料庫（current_total_volume、total_volume 等）。
        - 之後每次 tick，如果 `TolMatchQty` 有往前推進，就：
          1. 累積 group_size（本區間內 tick 數）。
          2. 更新 total_volume / match_pri。
          3. 計算與前一筆 tick 的時間差，累積到 `self.matchtime`。
          4. 呼叫 :meth:`calc_avg_price` 更新合併均價。
          5. 呼叫 :meth:`calculate_tickbars` 進一步處理 tickbar 邏輯。
        """
        # 如果這個商品是第一次出現，先進行初始化
        if not database:
            database["current_total_volume"] = float(
                TolMatchQty)  # 當前商品目前看到的總成交量
            database["total_volume"] = float(
                MatchQty)             # 本策略開始以來累積的成交量
            database["match_pri"] = self.new_price                 # 最新成交價

            # 解析時間字串，存成毫秒
            h, m, s, ms = parse_time_string(MatchTime)
            database["pre_matchtime"] = to_ms(
                h, m, s, ms)         # 記錄本商品上一筆 tick 的時間（初始化）

            # 同時更新全市場的日高 / 日低
            hp = int(HighPri)
            lp = int(LowPri)
            if self.highest_price == 0 or hp > self.highest_price:
                self.highest_price = hp
            if self.lowest_price == 0 or lp < self.lowest_price:
                self.lowest_price = lp

            # 初始化時就先計算一次合併均價
            self.calc_avg_price()

        # 之後每次 tick，如果看到的總成交量有變大，表示有新增成交量
        elif database["current_total_volume"] < float(TolMatchQty):
            self.group_size += 1                                   # 本區間內累積的 tick 數 +1
            database["current_total_volume"] = float(
                TolMatchQty)  # 更新目前看到的總成交量
            # 將本筆成交量加到累積量
            database["total_volume"] += float(MatchQty)
            database["match_pri"] = self.new_price                 # 記錄最新成交價

            # 計算本筆與前一筆 tick 的時間差，累積到 matchtime
            h, m, s, ms = parse_time_string(MatchTime)
            now_ms = to_ms(h, m, s, ms)
            # 本筆距離前一筆的時間差（毫秒）
            diff = abs(now_ms - database["pre_matchtime"])

            # 過濾隔夜數據：若時間差過大（可能是 23:59 → 00:00），則不納入本日計算
            if diff < 50000000:
                self.matchtime += diff
            database["pre_matchtime"] = now_ms                    # 更新前一筆時間

            # 重新計算合併均價，並進入 tickbar 邏輯
            self.calc_avg_price()
            self.calculate_tickbars(MatchTime, Is_simulation)

    def calc_avg_price(self) -> None:
        """
        計算「TXF + MXF」的加權平均價。

        公式：
        - 每筆 tick 先算 TR = price * qty，累積在 ``self.TXF_MXF_tol_value``。
        - 若 TXF / MXF 兩個商品都有資料，則：
          ``合併均價 = (所有 TR 加總) / (TXF 成交量 * 4 + MXF 成交量)``。
        """
        # 本筆 TR
        TR = self.new_price * self.tmp_qty
        self.TXF_MXF_tol_value += TR

        # 只有在 TXF / MXF 都已經有資料時，才計算合併均價
        if self.TXF_database and self.MXF_database:
            total = (self.TXF_database["total_volume"] * 4 +
                     self.MXF_database["total_volume"])
            if total > 0:
                self.TXF_MXF_avg_price = self.TXF_MXF_tol_value / total

    # =========================================================
    # Tickbars 控制
    # =========================================================

    def calculate_tickbars(self, MatchTime: str, Is_simulation) -> None:
        """
        每有「新成交量」時會被呼叫：更新高低價、趨勢、區間資訊，並檢查是否形成一根新的 tickbar。

        主要步驟：
        1. 檢查是否突破日高 / 日低，必要時觸發停損與重置區間。
        2. 每筆 tick 檢查：
           - 移動停利 :meth:`self.order.update_trailing_profit`
           - 止損觸發 :meth:`self.order.check_stoploss_triggered`
           - 是否觸價真正進場 :meth:`check_entry_on_tick`
        3. 更新合併均價與現價關係，決定箭頭方向 (↑ / ↓)。
        4. 更新區間資料：高低價、TR、成交量與均價。
        5. 把最新狀態丟給 :class:`UIUpdater` 更新 GUI。
        6. 累積「然而平均」（日高附近 / 日低附近的平均價）。
        7. 當 `group_size` 達到門檻（例如 1000 筆）時，呼叫 :meth:`show_tickbars` 產生一根 tickbar。
        8. 最後呼叫 :meth:`calculate_and_update` 更新 Fibonacci 與建議方向。
        """
        # ===== 1) 日高 / 日低突破處理 =====
        # 日高創新高 → 若有空單訊號則停損，並重置高檔區間
        if self.highest_price < self.new_price:
            if self.order.sell_signal:
                self.order.exit_stoploss("空", int(self.new_price), MatchTime)
            self.highest_price = int(self.new_price)
            self.trending_up = True
            self.trending_down = False
            self._reset_temp_zone(high=True)

        # 日低創新低 → 若有多單訊號則停損，並重置低檔區間
        elif self.lowest_price > self.new_price:
            if self.order.buy_signal:
                self.order.exit_stoploss("多", int(self.new_price), MatchTime)
            self.lowest_price = int(self.new_price)
            self.trending_up = False
            self.trending_down = True
            self._reset_temp_zone(high=False)

        # ===== 2) 逐筆 tick 檢查停利 / 停損 / 觸價進場 =====
        # 移動停利：讓停利價隨著行情推進
        self.order.update_trailing_profit(self.new_price, MatchTime)

        # 檢查止損是否被觸發（每筆 tick 都檢查一次）
        self.order.check_stoploss_triggered(int(self.new_price), MatchTime)

        # 檢查是否觸發「事先設定好」的進場價（signal_trade → execute_trade）
        self.check_entry_on_tick(MatchTime)

        # ===== 3) 均價 vs 現價箭頭 =====
        up_down_str = ""  # 顯示在 GUI 的箭頭：現價高於均價用 "↑"，低於均價用 "↓"
        if self.TXF_database and self.MXF_database:
            if self.new_price > self.TXF_MXF_avg_price:
                up_down_str = "↑"
                self.frame.compareInfoGrid.SetCellTextColour(1, 5, wx.RED)
            elif self.new_price < self.TXF_MXF_avg_price:
                up_down_str = "↓"
                self.frame.compareInfoGrid.SetCellTextColour(1, 5, wx.GREEN)

        # ===== 4) 趨勢轉折判斷 =====
        # 當原本認定為多頭，卻發現均價跌破 pre_ATR；或原本為空頭，卻發現均價突破 pre_ATR 時，
        # 且目前仍有區間資料，就把 trending_up / trending_down 清空。
        if (
            (self.trending_up and self.pre_ATR > self.TXF_MXF_avg_price) or
            (self.trending_down and self.pre_ATR < self.TXF_MXF_avg_price)
        ) and self.temp_price_compare_database:
            self.trending_up = False
            self.trending_down = False

        # 更新 pre_ATR（此處當作前一筆合併均價）
        self.pre_ATR = self.TXF_MXF_avg_price

        # ===== 5) 計算目前區間累積時間字串 =====
        if self.matchtime != 0:
            diff_ms = abs(self.matchtime)
            tol_time = diff_ms  # 方便後續直接存入列表
            h = diff_ms // (3600 * 1000)
            diff_ms %= 3600 * 1000
            m = diff_ms // (60 * 1000)
            diff_ms %= 60 * 1000
            s = diff_ms // 1000
            ms = diff_ms % 1000
            tol_time_str = f"{h:02}:{m:02}:{s:02}.{ms:03}"
        else:
            tol_time = 0
            tol_time_str = "00:00:00.000"

        # ===== 6) 更新區間高低資料與成交量 / 均價 =====
        # 更新本區間的最大價、最小價與對應的 up / down 旗標
        self.execute_compare(self.temp_price_compare_database,
                             MatchTime,
                             self.new_price)

        # 累積本區間成交量與 TR
        self.temp_tickbars_total_volume += self.tmp_qty
        self.temp_TXF_MXF_TR += (self.new_price * self.tmp_qty)
        if self.temp_tickbars_total_volume > 0:
            self.temp_tickbars_avg_price = (
                self.temp_TXF_MXF_TR / self.temp_tickbars_total_volume
            )

        # 把最新狀態丟給 UIUpdater，讓 GUI 立即反映
        self.ui.update_compare_on_tick(
            avg_price=self.TXF_MXF_avg_price,
            new_price=self.new_price,
            up_down=up_down_str,
            tol_time_str=tol_time_str,
            group_size=self.group_size,
            temp_db=self.temp_price_compare_database,
            temp_total_volume=self.temp_tickbars_total_volume,
            temp_avg_price=self.temp_tickbars_avg_price
        )

        # ===== 7) 累積「然而平均」：頭部 / 底部的成交平均價 =====
        # 沒有空單訊號時才繼續累積高檔「然而平均」
        if not self.order.sell_signal:
            self._accumulate_however_high()
        # 沒有多單訊號時才繼續累積低檔「然而平均」
        if not self.order.buy_signal:
            self._accumulate_however_low()

        # ===== 8) group 門檻檢查：是否形成一根 tickbar =====
        try:
            # 從 GUI 讀取 group 門檻（例如 1000 筆），讀不到就預設 1000
            threshold = int(self.frame.compareInfoGrid.GetCellValue(0, 6))
        except ValueError:
            threshold = 1000

        # 當 group_size 滿足門檻時，產生一根 tickbar
        if self.group_size >= threshold:
            self.show_tickbars(MatchTime, tol_time, tol_time_str)

        # ===== 9) 每筆 tick 都更新 Fibonacci 與建議方向 =====
        self.calculate_and_update()

    # =========================================================
    # 每筆 tick 依據訊號檢查是否觸發真實進場
    # =========================================================
    def check_entry_on_tick(self, MatchTime: str) -> None:
        """
        每筆 tick 檢查是否達到先前 :meth:`OrderManager.signal_trade` 設定的進場價，決定是否執行 execute_trade。

        邏輯：
        - 放空：
          若已經出現放空訊號 ``sell_signal == True``，且目前沒有空單持倉
          （``trading_sell == False``），當現價 ``>= entry_price_sell`` 即觸發放空。
        - 作多：
          若已經出現作多訊號 ``buy_signal == True``，且目前沒有多單持倉
          （``trading_buy == False``），當現價 ``<= entry_price_buy`` 即觸發買進。
        """
        price = int(self.new_price)  # 目前成交價（四捨五入為整數價）

        # ===== 放空：等反彈到預設放空價（含）以上 =====
        # sell_signal：代表之前 signal_trade 判斷過一次「有空點」，但尚未真正進場。
        if getattr(self.order, "sell_signal", False) and not getattr(self.order, "trading_sell", False):
            entry = int(getattr(self.order, "entry_price_sell", 0)
                        or 0)  # 預設放空價
            if entry > 0 and price > entry:
                # 觸價成交 log
                self.notifier.log(
                    f"{MatchTime}  放空觸價成交 現價:{price}  觸發價:{entry}",
                    Fore.GREEN + Style.BRIGHT
                )
                # 呼叫 OrderManager.execute_trade 真正進場
                if hasattr(self.order, "execute_trade"):
                    self.order.execute_trade(
                        direction="空",
                        trigger_price=entry,
                        match_time=MatchTime,
                    )

        # ===== 作多：等回檔到預設作多價（含）以下 =====
        if getattr(self.order, "buy_signal", False) and not getattr(self.order, "trading_buy", False):
            entry = int(getattr(self.order, "entry_price_buy", 0)
                        or 0)  # 預設作多價
            if entry > 0 and price < entry:
                self.notifier.log(
                    f"{MatchTime}  作多觸價成交 現價:{price}  觸發價:{entry}",
                    Fore.RED + Style.BRIGHT
                )
                if hasattr(self.order, "execute_trade"):
                    self.order.execute_trade(
                        direction="多",
                        trigger_price=entry,
                        match_time=MatchTime,
                    )

    # =========================================================
    # show_tickbars：每根 tickbar(如 1000 筆) 完成時產生進場訊號
    # =========================================================

    def show_tickbars(self, MatchTime, tol_time, tol_time_str) -> None:
        """
        一根 tickbar 成形時的完整邏輯（沿用原始版）：

        功能總結：
        1. 更新本根 tickbar 的收盤、量、均價、高低價等列表。
        2. 判斷：
           - 高低價漲跌（與前一根比較）。
           - 成交量增減。
           - 時間快慢（前一根 vs 本根）。
           - 日高 / 日低是否搭配箭頭形成「疑似頭部 / 底部」。
        3. 若符合速度 + 量 + 箭頭條件，設定：
           - ``suspected_sell``：疑似頭部 → 準備找空點。
           - ``suspected_buy``：疑似底部 → 準備找多點。
        4. 若疑似頭部 / 底部成立，則進一步檢查費波第 4 階價位，
           呼叫 :meth:`OrderManager.signal_trade` 產生「先記錄、等待觸價」的進場訊號。
        5. 依多空趨勢 (pre_TXF_MXF_avg_price vs TXF_MXF_avg_price) 決定主色與文字，
           最後呼叫 :meth:`print_trade_info` 把整包資訊印出。
        6. 最後重置本區間暫存，準備下一根 tickbar。
        """
        temp = ""  # 用來存 `signal_trade` 回傳的文字（例如："進場多"、"進場空"）

        # 一些「判斷用」的數值旗標
        mark_temp_big_price_num = 0       # 區間高價較前一根是上漲(2) / 下跌(1) / 無(0)
        mark_temp_small_price_num = 0     # 區間低價較前一根是上漲(2) / 下跌(1) / 無(0)
        mark_temp_total_volume_num = 0    # 本根成交量是否比前一根放大(1)
        mark_speedtime_num = 0            # 是否符合「速度條件」(1)

        # 顏色設定的字串（之後用 eval() 還原 colorama 顏色）
        mark_tol_time_color = "Style.RESET_ALL"
        mark_temp_highest_arrow_color = "Style.RESET_ALL"
        mark_temp_lowest_arrow_color = "Style.RESET_ALL"
        mark_temp_big_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_small_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_close_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_compare_avg_price_color = "Fore.YELLOW + Style.BRIGHT"

        # ===== 1) 收盤 / 量 / 均價列表更新 =====
        self.list_close_price.append(self.new_price)
        self.list_temp_tickbars_total_volume.append(
            self.temp_tickbars_total_volume)
        self.list_temp_tickbars_avg_price.append(
            int(self.temp_tickbars_avg_price))

        # 更新 GUI 的當前區間量與均價
        self.frame.compareInfoGrid.SetCellValue(
            0, 3, str(int(self.temp_tickbars_total_volume)))
        self.frame.compareInfoGrid.SetCellValue(
            0, 4, str(int(self.temp_tickbars_avg_price)))

        self.list_tickbars_tol_time.append(tol_time)
        self.frame.compareInfoGrid.SetCellValue(0, 2, tol_time_str)

        # ===== 2) 高低價來源：有區間資料用區間，否則用現價 =====
        if self.temp_price_compare_database:
            self.list_temp_tickbars_big_price.append(
                self.temp_price_compare_database['big_value'])
            self.list_temp_tickbars_small_price.append(
                self.temp_price_compare_database['small_value'])
        else:
            self.list_temp_tickbars_big_price.append(self.new_price)
            self.list_temp_tickbars_small_price.append(self.new_price)

        # ===== 3) 箭頭判斷：用來顯示本根是否有「往上 / 往下」的味道 =====
        temp_highest_arrow = "．"  # 預設為小點
        temp_lowest_arrow = "．"

        if self.previous_highest_price == self.highest_price:
            if self.temp_price_compare_database.get('up'):
                temp_highest_arrow = "↑"
            elif self.temp_price_compare_database.get('down'):
                temp_highest_arrow = "↓"

        if self.previous_lowest_price == self.lowest_price:
            if self.temp_price_compare_database.get('up'):
                temp_lowest_arrow = "↑"
            elif self.temp_price_compare_database.get('down'):
                temp_lowest_arrow = "↓"

        # 更新上一根日高 / 日低記錄
        self.previous_highest_price = self.highest_price
        self.previous_lowest_price = self.lowest_price

        # ===== 4) 更新 compare 高低列顯示 =====
        self.frame.compareInfoGrid.SetCellTextColour(0, 0, wx.RED)
        self.frame.compareInfoGrid.SetCellTextColour(0, 1, wx.GREEN)
        self.frame.compareInfoGrid.SetCellValue(
            0, 0, f"{int(self.list_temp_tickbars_big_price[-1])}  {temp_highest_arrow}"
        )
        self.frame.compareInfoGrid.SetCellValue(
            0, 1, f"{int(self.list_temp_tickbars_small_price[-1])}  {temp_lowest_arrow}"
        )

        # ===== 5) 更新日高 / 日低旗標（is_dayhigh / is_daylow）=====
        if (len(self.list_temp_tickbars_big_price) > 1 and
                self.list_temp_tickbars_big_price[-1] == self.highest_price):
            self.is_dayhigh = True
        if (len(self.list_temp_tickbars_small_price) > 1 and
                self.list_temp_tickbars_small_price[-1] == self.lowest_price):
            self.is_daylow = True

        # ===== 6) tickbar 高價漲跌判斷 =====
        if len(self.list_temp_tickbars_big_price) > 1:
            if self.list_temp_tickbars_big_price[-2] >= self.list_temp_tickbars_big_price[-1]:
                mark_temp_big_price_num = 1  # 高點沒有創高
            elif self.list_temp_tickbars_big_price[-2] < self.list_temp_tickbars_big_price[-1]:
                mark_temp_big_price_num = 2  # 高點有創高

        # ===== 7) tickbar 低價漲跌判斷 =====
        if len(self.list_temp_tickbars_small_price) > 1:
            if self.list_temp_tickbars_small_price[-2] > self.list_temp_tickbars_small_price[-1]:
                mark_temp_small_price_num = 1  # 低點有創低
            elif self.list_temp_tickbars_small_price[-2] <= self.list_temp_tickbars_small_price[-1]:
                mark_temp_small_price_num = 2  # 低點沒有創低

        # ===== 8) tickbar 成交量增減判斷 =====
        if (len(self.list_temp_tickbars_total_volume) > 1 and
                self.list_temp_tickbars_total_volume[-2] < self.list_temp_tickbars_total_volume[-1]):
            mark_temp_total_volume_num = 1  # 本根量 > 前一根量

        # ===== 9) 時間快慢 + 量增 + 箭頭 → 速度判斷 =====
        if len(self.list_tickbars_tol_time) > 1:
            prev_t = self.list_tickbars_tol_time[-2]
            curr_t = self.list_tickbars_tol_time[-1]

            # 如果本根時間明顯縮短（前一根時間 / 2 > 本根），且量有放大 + 有特定箭頭，就標示時間顏色
            if prev_t / 2 > curr_t and mark_temp_total_volume_num == 1 and temp_highest_arrow == "↓":
                mark_tol_time_color = "Fore.BLACK + Back.WHITE"
            if prev_t / 2 > curr_t and mark_temp_total_volume_num == 1 and temp_lowest_arrow == "↑":
                mark_tol_time_color = "Fore.BLACK + Back.WHITE"

            # 速度條件成立：時間變快、量放大、且搭配日高 / 日低箭頭，則標記箭頭顏色並把速度旗標設為 1
            if prev_t > curr_t and mark_temp_total_volume_num == 1 and temp_highest_arrow == "↓":
                mark_temp_highest_arrow_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"
                mark_speedtime_num = 1

            if prev_t > curr_t and mark_temp_total_volume_num == 1 and temp_lowest_arrow == "↑":
                mark_temp_lowest_arrow_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"
                mark_speedtime_num = 1

        # ===== 10) 若速度條件成立 → 設定疑似頭部 / 底部 =====
        if mark_speedtime_num == 1:
            # 疑似頭部（日高 + 往下箭頭）→ 準備找空點
            if self.is_dayhigh and temp_highest_arrow == "↓":
                self.is_dayhigh = False
                self.suspected_sell = True
            # 疑似底部（日低 + 往上箭頭）→ 準備找多點
            elif self.is_daylow and temp_lowest_arrow == "↑":
                self.is_daylow = False
                self.suspected_buy = True

            # ===== 放空進場訊號：作空等反彈，使用 Fibonacci 階梯往上貼齊作為進場觸發價 =====
            sell_levels = [
                int(s.strip())
                for s in self.fibonacci_sell_str.split(":")
                if s.strip().isdigit()
            ]
            if (
                self.suspected_sell
                and temp_highest_arrow == "↓"
                and len(sell_levels) > 3
                and sell_levels[2] > self.temp_howeverHighest_avg_price
                and not getattr(self.order, "trading_sell", False)
            ):
                # 符合放空訊號條件：把顏色切成綠底白字（代表空方）
                mark_temp_close_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
                mark_temp_big_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
                entry_price = int(self.list_close_price[-1])  # 進場參考價（當前收盤）

                # ===== 1. 取 trigger_price：第一個 ≥ base_value 的 sell_level =====
                base_value = int(self.temp_howeverHighest_avg_price)
                # 找出所有 ≥ base_value 的 Fib 價位
                greater_or_equal_levels = [lvl for lvl in sell_levels if lvl > base_value]
                if greater_or_equal_levels:
                    # 最接近、但不小於 base_value 的 Fib 階
                    trigger_price = min(greater_or_equal_levels)
                else:
                    # 如果平均價已經高於所有 Fib 階，就用最大那一階
                    trigger_price = sell_levels[-1]

                # ===== 2. stop_loss：trigger_price 往上二階 =====
                tp_index = sell_levels.index(trigger_price)
                stop_index = tp_index + 2

                if stop_index < len(sell_levels):
                    stop_loss = sell_levels[stop_index]
                else:
                    # 如果沒有第二階可用，回退到原始邏輯
                    stop_loss = self.highest_price + 1

                if hasattr(self.order, "signal_trade"):
                    temp = self.order.signal_trade(
                        direction="空",
                        entry_price=entry_price,
                        trigger_price=trigger_price,
                        stop_loss=stop_loss,
                        fibonacci_str=self.fibonacci_sell_str,
                        match_time=MatchTime,
                    )
                # 把這次使用的費波字串記錄下來，給舊版 OnChkDeal 使用
                self.fibonacci_chkSell_str = self.fibonacci_sell_str
                self.suspected_sell = False  # 本次頭部訊號已處理完，重置旗標

            # ===== 作多進場訊號：作多等回檔，使用 Fibonacci 階作為貼齊進場價 =====
            buy_levels = [
                int(s.strip())
                for s in self.fibonacci_buy_str.split(":")
                if s.strip().isdigit()
            ]
            if (
                self.suspected_buy
                and temp_lowest_arrow == "↑"
                and len(buy_levels) > 3
                and int(buy_levels[2]) < self.temp_howeverLowest_avg_price
                and not getattr(self.order, "trading_buy", False)
            ):
                mark_temp_close_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
                mark_temp_small_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
                entry_price = int(self.list_close_price[-1])
                # ===== 1. 取 trigger_price：往下貼齊到最近的 Fibonacci 階 =====
                base_value = int(self.temp_howeverLowest_avg_price)

                # 找出所有「小於等於平均最低價」的階層（因為等回檔往下）
                lower_or_equal_levels = [lvl for lvl in buy_levels if lvl < base_value]

                if lower_or_equal_levels:
                    # 取最大（離 base_value 最近，但不高於 base_value）
                    trigger_price = max(lower_or_equal_levels)
                else:
                    # 如果平均價比最淺回檔還高，就用「最下面那階」（buy_levels 是由大到小，因此最後一個是最低價）
                    trigger_price = buy_levels[-1]

                # ===== 2. 停損：從 trigger_price 往下二階 =====
                tp_index = buy_levels.index(trigger_price)
                stop_index = tp_index + 2  # 注意：buy_levels 由大到小，往下二階 → index + 2

                if stop_index < len(buy_levels):
                    stop_loss = buy_levels[stop_index]
                else:
                    # 沒有更低的兩階，就退回原本邏輯
                    stop_loss = self.lowest_price - 1

                if hasattr(self.order, "signal_trade"):
                    temp = self.order.signal_trade(
                        direction="多",
                        entry_price=entry_price,
                        trigger_price=trigger_price,
                        stop_loss=stop_loss,
                        fibonacci_str=self.fibonacci_buy_str,
                        match_time=MatchTime,
                    )
                self.fibonacci_chkBuy_str = self.fibonacci_buy_str
                self.suspected_buy = False

        # ===== 11) 依均價方向輸出完整資訊（決定主色與 trend_color）=====
        if self.pre_TXF_MXF_avg_price > self.TXF_MXF_avg_price and self.temp_price_compare_database:
            # 均價向下 → 視為偏空趨勢
            self.trending_up = False
            self.trending_down = True
            color_main = Fore.GREEN  # 整體主色偏綠（空方）
            if any(c in temp for c in ["進場多", "進場空"]):
                # 若 temp 文字裡有進場訊號，trend_color 依多空調整
                trend_color = Fore.GREEN if any(
                    c in temp for c in "空") else Fore.RED
            else:
                trend_color = Fore.GREEN
                mark_temp_close_price_color = "Fore.GREEN + Style.BRIGHT"
            self.print_trade_info(
                MatchTime, temp, color_main, trend_color,
                mark_tol_time_color, tol_time_str,
                mark_temp_big_price_color, mark_temp_small_price_color,
                mark_temp_highest_arrow_color, mark_temp_lowest_arrow_color,
                mark_temp_close_price_color, mark_temp_compare_avg_price_color,
                temp_highest_arrow, temp_lowest_arrow
            )

        elif self.pre_TXF_MXF_avg_price < self.TXF_MXF_avg_price and self.temp_price_compare_database:
            # 均價向上 → 視為偏多趨勢
            self.trending_up = True
            self.trending_down = False
            color_main = Fore.RED  # 整體主色偏紅（多方）
            if any(c in temp for c in ["進場多", "進場空"]):
                trend_color = Fore.RED if any(
                    c in temp for c in "多") else Fore.GREEN
            else:
                trend_color = Fore.RED
                mark_temp_close_price_color = "Fore.RED + Style.BRIGHT"
            self.print_trade_info(
                MatchTime, temp, color_main, trend_color,
                mark_tol_time_color, tol_time_str,
                mark_temp_big_price_color, mark_temp_small_price_color,
                mark_temp_highest_arrow_color, mark_temp_lowest_arrow_color,
                mark_temp_close_price_color, mark_temp_compare_avg_price_color,
                temp_highest_arrow, temp_lowest_arrow
            )

        # ===== 12) reset 區間暫存，準備下一根 tickbar =====
        self.temp_price_compare_database = {}
        self.temp_tickbars_total_volume = 0
        self.temp_TXF_MXF_TR = 0
        self.temp_tickbars_avg_price = 0
        self.pre_TXF_MXF_avg_price = self.TXF_MXF_avg_price
        self.matchtime = 0
        self.group_size = 0

    # =========================================================
    # 區間與 Fibonacci 輔助
    # =========================================================

    def _reset_temp_zone(self, high: bool) -> None:
        """
        重置當前區間的暫存資料。

        這個函式會在「日高 / 日低被突破」時呼叫：
        - 把與目前區間有關的變數（成交量、TR、均價、時間、group_size）全部歸零。
        - 若 `high=True`，同時清除「高檔然而平均」；反之則清除「低檔然而平均」。
        """
        self.temp_price_compare_database = {}
        self.temp_tickbars_total_volume = 0
        self.temp_TXF_MXF_TR = 0
        self.temp_tickbars_avg_price = 0
        self.matchtime = 0
        self.group_size = 0
        if high:
            self.temp_howeverHighest_total_volume = 0
            self.temp_TXF_MXF_howeverHighest = 0
            self.temp_howeverHighest_avg_price = 0
            self.fibonacci_chkSell_str = "0"  # 目前空單使用的 Fibonacci 字串
        else:
            self.temp_howeverLowest_total_volume = 0
            self.temp_TXF_MXF_howeverLowest = 0
            self.temp_howeverLowest_avg_price = 0
            self.fibonacci_chkBuy_str = "0"   # 目前多單使用的 Fibonacci 字串

    def _accumulate_however_high(self) -> None:
        """
        累積「日高附近」的成交量與 TR，並更新其平均價。

        直覺理解：
        - 當行情在高檔區間震盪時，這裡會記錄「在高檔附近到底成交了多少量、平均價在哪裡」。
        - 之後在判斷疑似頭部時，會拿這個平均價來比較。
        """
        self.temp_howeverHighest_total_volume += self.tmp_qty
        self.temp_TXF_MXF_howeverHighest += (self.new_price * self.tmp_qty)
        if self.temp_howeverHighest_total_volume > 0:
            self.temp_howeverHighest_avg_price = (
                self.temp_TXF_MXF_howeverHighest /
                self.temp_howeverHighest_total_volume
            )

    def _accumulate_however_low(self) -> None:
        """
        累積「日低附近」的成交量與 TR，並更新其平均價。

        用途類似 :meth:`_accumulate_however_high`，只是針對的是低檔區間。
        """
        self.temp_howeverLowest_total_volume += self.tmp_qty
        self.temp_TXF_MXF_howeverLowest += (self.new_price * self.tmp_qty)
        if self.temp_howeverLowest_total_volume > 0:
            self.temp_howeverLowest_avg_price = (
                self.temp_TXF_MXF_howeverLowest /
                self.temp_howeverLowest_total_volume
            )

    def execute_compare(self, database: Dict, MatchTime: str, value: float) -> None:
        """
        更新「區間比較資料」。

        這個小型資料庫包含：
        - ``big_value`` / ``small_value``：本區間內目前為止的最大 / 最小價。
        - ``big_value_time`` / ``small_value_time``：對應的時間。
        - ``up`` / ``down``：本次更新時，是往上突破還是往下跌破。

        之後在 :meth:`show_tickbars` 中會使用這些資訊來判斷箭頭與頭部 / 底部。
        """
        if not value:
            return
        if not database:
            # 第一次進來，初始化高低價與時間，以及 up / down 旗標
            database["big_value"] = value
            database["small_value"] = value
            database["big_value_time"] = float(MatchTime)
            database["small_value_time"] = float(MatchTime)
            database["up"] = False
            database["down"] = False
        elif value > database["big_value"]:
            # 創新高
            database["big_value"] = value
            database["big_value_time"] = float(MatchTime)
            database["up"] = True
            database["down"] = False
        elif value < database["small_value"]:
            # 創新低
            database["small_value"] = value
            database["small_value_time"] = float(MatchTime)
            database["up"] = False
            database["down"] = True

    def calculate_and_update(self) -> None:
        """
        更新 Fibonacci 費波價、infoDataGrid 與「趨勢建議」。

        主要流程：
        1. 決定關鍵價 `keypri`：
           - 若 GUI 的 `avgPrice` 有填值，就以它為主。
           - 否則使用目前的合併均價 ``self.TXF_MXF_avg_price``。
        2. 呼叫 :func:`calc_fibonacci_levels` 得到多空兩組 Fibonacci 價位。
           - 並把結果更新到 GUI 的費波 Grid。
        3. 計算日高 / 日低與 keypri 的價差，更新 infoDataGrid。
        4. 根據現在的 `trending_up / trending_down` 把建議方向顯示在 GUI：多 / 空 / 無。
        """
        try:
            # 沒有日高日低就不更新（表示資料還不完整）
            if self.highest_price == 0 or self.lowest_price == 0:
                return

            # 決定關鍵價：GUI > 合併均價
            if int(self.frame.avgPrice.GetValue()) > 0:
                keypri = int(self.frame.avgPrice.GetValue())
            else:
                keypri = int(self.TXF_MXF_avg_price)

            # 計算 Fibonacci 多空價位
            levels = calc_fibonacci_levels(
                high_price=self.highest_price,
                low_price=self.lowest_price,
                key_price=keypri
            )
            # 轉成字串，方便舊版程式或 log 使用
            self.fibonacci_sell_str = " : ".join(
                str(v) for v in levels["sell"])
            self.fibonacci_buy_str = " : ".join(str(v) for v in levels["buy"])
            # 更新 GUI 費波 Grid
            self.ui.update_fibonacci_grid(levels["sell"], levels["buy"])

            # 計算日高 / 日低與 keypri 的價差
            diff_up = self.highest_price - keypri
            diff_down = keypri - self.lowest_price
            diff_total = self.highest_price - self.lowest_price
            self.ui.update_info_grid_basic(
                high_price=self.highest_price,
                low_price=self.lowest_price,
                diff_up=diff_up,
                diff_down=diff_down,
                diff_total=diff_total
            )

            # 更新「趨勢建議」欄位
            if self.trending_down:
                self.ui.update_trend_suggestion("空")
            elif self.trending_up:
                self.ui.update_trend_suggestion("多")
            else:
                self.ui.update_trend_suggestion("無")
        except Exception:
            # 為了不中斷主流程，這裡維持原有做法：遇到例外時直接略過
            pass

    # =========================================================
    # 統一輸出函式（沿用原始 print_trade_info 邏輯）
    # =========================================================

    def print_trade_info(self, MatchTime, temp, color_main, trend_color,
                         mark_tol_time_color, tol_time_str,
                         mark_temp_big_price_color, mark_temp_small_price_color,
                         mark_temp_highest_arrow_color, mark_temp_lowest_arrow_color,
                         mark_temp_close_price_color, mark_temp_compare_avg_price_color,
                         temp_highest_arrow, temp_lowest_arrow) -> None:
        """
        將 tickbar 關鍵資訊、價差、訊號等以彩色格式輸出。

        設計重點：
        - 完全保留原本輸出格式，方便你沿用既有觀察習慣。
        - 使用 ``colorama`` 搭配 ``eval()``，把字串型態的顏色指令還原回來。
        - 所有數值都在這裡統一轉成整數或指定格式，便於閱讀。

        參數說明（直覺版）：
        - MatchTime : 本根 tickbar 結束時間（字串）。
        - temp      : 訊號文字，例如："進場多"、"進場空" 或空字串。
        - color_main: 每一行前面的主顏色（代表多空傾向）。
        - trend_color: 用在「現:」「高: 低:」與 temp 訊號上的強調色。
        - 其餘 mark_* 參數：都是字串形式的 colorama 表達式，用來控制各段文字的顏色。
        - temp_highest_arrow / temp_lowest_arrow：本根 tickbar 在日高 / 日低的箭頭符號。
        """
        # 若高低價列表還沒有資料，直接略過，避免 IndexError
        if not self.list_temp_tickbars_big_price or not self.list_temp_tickbars_small_price:
            return

        # 把常用資料先取出來，並轉成好閱讀的格式
        avg_price = f"{self.TXF_MXF_avg_price:>9.4f}"
        big = int(self.list_temp_tickbars_big_price[-1])
        small = int(self.list_temp_tickbars_small_price[-1])
        high = int(self.highest_price)
        low = int(self.lowest_price)
        newp = int(self.new_price)
        vol = int(self.temp_tickbars_total_volume or 0)
        avg = int(self.temp_tickbars_avg_price or self.new_price)
        hi_avg = int(self.temp_howeverHighest_avg_price or self.new_price)
        lo_avg = int(self.temp_howeverLowest_avg_price or self.new_price)

        # 主輸出行：這一行的排版與顏色安排沿用舊版，方便你直接比對
        print((
            f"{color_main}{Style.BRIGHT}{MatchTime}  {avg_price}{Style.RESET_ALL}  "
            f"{resolve_color(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  "
            f"{Fore.YELLOW}{Style.BRIGHT}{big:<5d}{Style.RESET_ALL} : "
            f"{Fore.YELLOW}{Style.BRIGHT}{small:<5d}{Style.RESET_ALL}  "
            f"{resolve_color(mark_temp_highest_arrow_color)}{temp_highest_arrow}{Style.RESET_ALL}  "
            f"{resolve_color(mark_temp_lowest_arrow_color)}{temp_lowest_arrow}{Style.RESET_ALL}  "
            f"{trend_color}{Style.BRIGHT}現:{Style.RESET_ALL}"
            f"{resolve_color(mark_temp_close_price_color)} {newp}{Style.RESET_ALL}  "
            f"{Fore.YELLOW}{Style.BRIGHT}{vol:>5d} : "
            f"{resolve_color(mark_temp_compare_avg_price_color)}{avg:<5d}{Style.RESET_ALL}  "
            f"{resolve_color(mark_temp_big_price_color)}{hi_avg:<5d}{Style.RESET_ALL} : "
            f"{resolve_color(mark_temp_small_price_color)}{lo_avg:<5d}{Style.RESET_ALL}  "
            f"高: {high}  低: {low}  {trend_color}{Style.BRIGHT}{temp}{Style.RESET_ALL}"
        ))

        # 以下為舊版額外輸出進場訊息的區塊，若之後想再開啟可以直接把註解拿掉。
        # if temp == "進場空":
        #     print(
        #         f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  "
        #         f"{Fore.GREEN}{Style.BRIGHT}放空 {int(self.list_close_price[-1])}{Style.RESET_ALL}  "
        #         f"{Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_sell_str}  "
        #         f"止損: {int(self.order.stopLoss_sell)}  "
        #         f"停利: {self.order.profit_sell_str}{Style.RESET_ALL}"
        #     )
        # elif temp == "進場多":
        #     print(
        #         f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  "
        #         f"{Fore.RED}{Style.BRIGHT}買進 {int(self.list_close_price[-1])}{Style.RESET_ALL}  "
        #         f"{Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_buy_str}  "
        #         f"止損: {int(self.order.stopLoss_buy)}  "
        #         f"停利: {self.order.profit_buy_str}{Style.RESET_ALL}"
        #     )


def load_json(fpath):
    with open(fpath, "r", encoding="UTF-8") as f:
        return json.load(f)
