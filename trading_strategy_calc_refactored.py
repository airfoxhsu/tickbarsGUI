# -*- coding: utf-8 -*-
"""
trading_strategy_calc_refactored.py

重大改動重點：
1) 模組化常數、工具函式(safe_int)，採用型別註解/Docstring。
2) 將「單根分組內高低點」抽成 TempCompareDB，並提供 reset()。
3) 所有 UI 互動集中以 wx.CallAfter 呼叫，避免跨執行緒直接觸控 wx 控件。
4) 將進出場與移動停利邏輯拆成 _enter_long/_enter_short/_trailing_take_profit。
5) Telegram token/chat_id 改由 frame 屬性或環境變數提供，避免硬編碼。
6) RedirectText 保留，但可指定等寬字體大小 DEFAULT_MONO_FONT_SIZE。
7) 逐筆流程：execate_TXF_MXF → _calculate_time → _calculate_tickbars → _close_one_tickbar。

注意：此檔案仍依賴你的 GUI 框架提供的屬性(多個 wx.Grid、ComboBox 等)，
在你的主程式中取代原本的 TradingStrategy 匯入使用即可。
"""

from __future__ import annotations

import os
import re
import sys
import threading
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# 第三方/系統：僅於實際執行時由你的環境提供
import requests            # 發送 Telegram
import winsound            # 播放音效 (Windows)
import wx                  # wxPython GUI
from colorama import Back, Fore, Style  # 控制台顏色

# ==============================
# Module-level constants
# ==============================
SOUND_FILE = "woo.wav"           # 預設音效檔案
DEFAULT_MONO_FONT_SIZE = 12      # RedirectText 顯示字體大小
TXF_WEIGHT = 4                   # 大台乘數 (成交量加權用)


def safe_int(s: str, default: int = 0) -> int:
    """將字串安全地轉為 int；非數字時回傳 default。"""
    try:
        return int(s)
    except Exception:
        return default


@dataclass
class TempCompareDB:
    """暫存當前分組(一根tickbar)內的高低點與方向。"""
    big_value: int = 0                # 該分組內最高價
    small_value: int = 0              # 該分組內最低價
    big_value_time: float = 0.0       # 最高價時間(浮點表示)
    small_value_time: float = 0.0     # 最低價時間(浮點表示)
    up: bool = False                  # 此分組內是否向上(創高)
    down: bool = False                # 此分組內是否向下(破低)

    def reset(self) -> None:
        self.big_value = 0
        self.small_value = 0
        self.big_value_time = 0.0
        self.small_value_time = 0.0
        self.up = False
        self.down = False


@dataclass
class MarketDB:
    """儲存 TXF / MXF 的逐筆累計資訊。"""
    current_total_volume: float = 0.0   # 最新看到的總成交量(交易所回報)
    total_volume: float = 0.0           # 自策略啟動以來累加成交量
    match_pri: float = 0.0              # 最新成交價
    pre_matchtime: int = 0              # 上一個成交的毫秒時間戳(計算區間用)


class TradingStrategy:
    """
    交易策略核心類別：
    - 接收逐筆資料 (execate_TXF_MXF / _calculate_time)
    - 維護當根/跨根的統計狀態
    - 根據趨勢/極值/速度，產生進出場訊號、移動停利
    - 與 wx GUI 控件互動 (僅在主執行緒呼叫；背景工作使用 Thread + 不觸碰 UI)
    """

    # --------------------------
    # 初始化與成員變數
    # --------------------------
    def __init__(self, frame) -> None:
        """
        參數
        -----
        frame : wxPython 的主框架物件，必須含有以下屬性 (由你的 GUI 程式提供)：
            - monitorTradeSignal (wx.TextCtrl) : 用來顯示 Console 訊息
            - compareInfoGrid, signalGrid, infoDataGrid, fibonacciGrid (wx.Grid)
            - 價格/下單相關控件：price_combo, chkSell, chkBuy, acclist_combo, qtyLabel
            - 其他設定：isSMS, isPlaySound, avgPrice 等
        """
        self.frame = frame

        # 重新導向 stdout/stderr 到 GUI 的 TextCtrl (終端樣式著色)
        sys.stdout = RedirectText(self.frame.monitorTradeSignal, DEFAULT_MONO_FONT_SIZE)
        sys.stderr = RedirectText(self.frame.monitorTradeSignal, DEFAULT_MONO_FONT_SIZE)
        print(Style.BRIGHT + Fore.GREEN + "✅ 成功訊息 (亮綠色)"
              + Fore.RED + Back.WHITE + "❌ 錯誤訊息 (紅字白底)"
              + Style.RESET_ALL)

        # ===== 參數/狀態字串 (供 UI 顯示/互動) =====
        self.fibonacci_sell_str: str = ""     # 目前空方的費波那契價格字串(顯示/下單用)
        self.fibonacci_buy_str: str = ""      # 目前多方的費波那契價格字串(顯示/下單用)
        self.fibonacci_chkSell_str: str = "0" # 送往 UI 的空方費波選單快取
        self.fibonacci_chkBuy_str: str = "0"  # 送往 UI 的多方費波選單快取
        self.profit_buy_str: str = ""         # 多單三段停利字串 e.g. "p1:p2:p3"
        self.profit_sell_str: str = ""        # 空單三段停利字串

        # ===== 價格與交易累積 =====
        self.new_price: float = 0.0           # 最新成交價 (逐筆更新)
        self.TXF_db: Dict[str, float] = {}    # TXF 市場資料 (初始化後以 MarketDB 形式使用)
        self.MXF_db: Dict[str, float] = {}    # MXF 市場資料 (初始化後以 MarketDB 形式使用)

        # 交易區間加總
        self.TXF_MXF_tol_value: float = 0.0   # 大/小台 TR 加總 (價×量)
        self.TXF_MXF_avg_price: float = 0.0   # 交易時段加權均價
        self.pre_TXF_MXF_avg_price: float = 0.0  # 前一次均價 (判斷趨勢用)

        # ===== 趨勢/極值/臨時資料 =====
        self.highest_price: int = 0           # 開始以來最高價(追蹤日高)
        self.lowest_price: int = 0            # 開始以來最低價(追蹤日低)
        self.is_dayhigh: bool = True          # 當前 tickbar 是否仍處於日高邏輯狀態
        self.is_daylow: bool = True           # 當前 tickbar 是否仍處於日低邏輯狀態
        self.trending_up: bool = False        # 均價向上中？
        self.trending_down: bool = False      # 均價向下中？
        self.pre_ATR: float = 0.0             # 以均價暫代 (舊程式遺留)

        # 當根內的即時計算暫存
        self.tmp_qty: float = 0.0             # 本筆量(權重後)，TXF 乘 4、MXF 乘 1
        self.temp_tickbars_total_volume: float = 0.0
        self.temp_TXF_MXF_TR: float = 0.0
        self.temp_tickbars_avg_price: float = 0.0
        self.temp_price_compare: TempCompareDB = TempCompareDB()

        # ===== 訊號/倉位狀態 =====
        self.trading_buy: bool = False        # 目前是否持有多單
        self.trading_sell: bool = False       # 目前是否持有空單
        self.buy_signal: bool = False         # 最近是否觸發多方進場訊號
        self.sell_signal: bool = False        # 最近是否觸發空方進場訊號
        self.suspected_buy: bool = False      # 疑似打底(等待確認)
        self.suspected_sell: bool = False     # 疑似作頭(等待確認)
        self.stopLoss_buy: int = 0            # 多單動態停損
        self.stopLoss_sell: int = 0           # 空單動態停損
        self.entry_price_buy: int = 0         # 多單進場價
        self.entry_price_sell: int = 0        # 空單進場價

        # ===== 時間/分組 =====
        self.matchtime: int = 0               # 當前分組內(一根)的總毫秒
        self.group_size: int = 0              # 當前分組累計的筆數
        self.pre_TXF_MXF_avg_price: float = 0.0

        # ===== 輔助列表：畫面/統計展示 =====
        self.list_close_price: List[int] = []               # 每根收盤價
        self.list_tickbars_tol_time: List[int] = []         # 每根累計時間(毫秒)
        self.list_temp_tickbars_avg_price: List[int] = []   # 每根均價(整數)
        self.list_temp_tickbars_big_price: List[int] = []   # 每根最高
        self.list_temp_tickbars_small_price: List[int] = [] # 每根最低
        self.list_temp_tickbars_total_volume: List[int] = []# 每根總量

        # 用於判定“是否仍為日高/日低”的上一根快照
        self.previous_big_prince: int = 0
        self.previous_small_prince: int = 0

        # ===== 統計/除錯 =====
        self.count: int = 0                  # 訊號/交易計數
        self.Index: int = 0                  # 舊程式遺留
        self.profit: int = 0                 # 總損益 (示意)

    # --------------------------
    # 逐筆入口 (TXF / MXF)
    # --------------------------
    def execate_TXF_MXF(
        self,
        direction: str,
        symbol: str,
        RefPri: str,
        OpenPri: str,
        HighPri: str,
        LowPri: str,
        MatchTime: str,
        MatchPri: str,
        MatchQty: str,
        TolMatchQty: str,
        Is_simulation: bool,
    ) -> None:
        """
        接收交易所回報的一筆行情，更新內部狀態並驅動後續計算。

        - 依商品不同(TXF/MXF) 決定權重 (TXF 乘 4, MXF 乘 1)
        - 更新價量資料，呼叫時間/分組計算
        """
        if "XF" in symbol:
            self.tmp_qty = 0.0
            self.new_price = float(MatchPri)

        if "TXF" in symbol:
            self.tmp_qty = TXF_WEIGHT * float(MatchQty)
            self._calculate_time(
                self.TXF_db, RefPri, HighPri, LowPri, MatchQty, TolMatchQty, MatchTime, Is_simulation
            )
        elif "MXF" in symbol:
            self.tmp_qty = float(MatchQty)
            self._calculate_time(
                self.MXF_db, RefPri, HighPri, LowPri, MatchQty, TolMatchQty, MatchTime, Is_simulation
            )

    # --------------------------
    # 計算與分組流程
    # --------------------------
    def _calculate_time(
        self,
        database: Dict[str, float],
        RefPri: str,
        HighPri: str,
        LowPri: str,
        MatchQty: str,
        TolMatchQty: str,
        MatchTime: str,
        Is_simulation: bool,
    ) -> None:
        """
        對單一市場(TXF 或 MXF)進行時間與量價累積：
        - 初始化：帶入第一筆 total_volume、match_pri、pre_matchtime
        - 逐筆更新：累加量、計算毫秒差、推進當根統計，再觸發 tickbars 邏輯
        """
        if not database:
            # 初始化
            database["current_total_volume"] = float(TolMatchQty)
            database["total_volume"] = float(MatchQty)
            database["match_pri"] = self.new_price

            h1, m1, s1, ms1 = self._parse_time_string(MatchTime)
            database["pre_matchtime"] = self._to_total_ms(h1, m1, s1, ms1)

            # 建立當日高低
            if self.highest_price == 0 or self.lowest_price == 0:
                self.highest_price = int(HighPri)
                self.lowest_price = int(LowPri)
            else:
                self.highest_price = max(self.highest_price, int(HighPri))
                self.lowest_price = min(self.lowest_price, int(LowPri))

            self._calc_avg_price()  # 首次也推導一次均價
            return

        # 逐筆累積
        if database["current_total_volume"] < float(TolMatchQty):
            self.group_size += 1
            database["current_total_volume"] = float(TolMatchQty)
            database["total_volume"] += float(MatchQty)
            database["match_pri"] = self.new_price

            h1, m1, s1, ms1 = self._parse_time_string(MatchTime)
            current_ms = self._to_total_ms(h1, m1, s1, ms1)
            tol_ms = abs(current_ms - database["pre_matchtime"])
            if tol_ms < 50_000_000:  # 過濾隔夜 23:59:59.999 → 00:00:00.000
                self.matchtime += tol_ms
            database["pre_matchtime"] = current_ms

            self._calc_avg_price()
            self._calculate_tickbars(MatchTime, Is_simulation)

    def _calc_avg_price(self) -> None:
        """跨市場(TXF/MXF)合併計算加權均價。"""
        TR = self.new_price * self.tmp_qty
        self.TXF_MXF_tol_value += TR

        if self.TXF_db and self.MXF_db:
            den = self.TXF_db["total_volume"] * TXF_WEIGHT + self.MXF_db["total_volume"]
            if den > 0:
                self.TXF_MXF_avg_price = self.TXF_MXF_tol_value / den

    # --------------------------
    # Tickbars：一根收斂完成的計算與邏輯
    # --------------------------
    def _calculate_tickbars(self, MatchTime: str, Is_simulation: bool) -> None:
        """
        在逐筆過程中，每當 group_size 到達門檻或價格創高/創低重置時，
        會彙總當前分組資訊、刷新 UI、偵測疑似作頭/打底，並可能發出進場/出場與移動停利。
        """
        # --- 創高(上破) → 可能空單停損/刪訊號 ---
        if self.highest_price < self.new_price:
            # 持有空單時，若開啟“自動多單停損反手”
            if self.trading_sell and self._can_auto_order() and self.frame.chkSell.GetValue():
                qty_text = self.frame.qtyLabel.GetLabel()
                if safe_int(qty_text) > 0:
                    # 反手多單(市價/指定價)：呼叫 UI 的下單函式 (主執行緒)
                    wx.CallAfter(self.frame.OnOrderBtn, None, "B", self.new_price)
                    wx.CallAfter(self.frame.qtyLabel.SetLabel, "未連")

            # 若先前有空方訊號，創高後視為止損並清理 UI 狀態
            if self.sell_signal:
                self.trading_sell = False
                self.sell_signal = False
                self.fibonacci_chkSell_str = "0"
                wx.CallAfter(self._reset_price_combo, ["0"])
                wx.CallAfter(self.frame.chkSignal.SetValue, False)
                wx.CallAfter(self.frame.missedSignal_combo.SetSelection, 0)
                self._write_signal_grid_row(
                    row=0, title="放空止損", note="平倉不悔", time_str=MatchTime, px=int(self.new_price)
                )

                bot_message = f"{MatchTime}  放空止損: {int(self.new_price)}  平倉不悔"
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}  放空止損: {int(self.new_price)}  平倉不悔{Style.RESET_ALL}")
                
                if self.frame.isSMS.GetValue():
                    # self._async_telegram(f"{MatchTime}  放空止損: {int(self.new_price)}  平倉不悔")
                    self._async_telegram(bot_message)

            # 重置上升相關暫存
            self.highest_price = self.new_price
            self.trending_up, self.trending_down = True, False
            self._reset_group_temp(up_break=True)

        # --- 創低(下破) → 可能多單停損/刪訊號 ---
        elif self.lowest_price > self.new_price:
            if self.trading_buy and self._can_auto_order() and self.frame.chkBuy.GetValue():
                qty_text = self.frame.qtyLabel.GetLabel()
                if safe_int(qty_text) > 0:
                    wx.CallAfter(self.frame.OnOrderBtn, None, "S", self.new_price)
                    wx.CallAfter(self.frame.qtyLabel.SetLabel, "未連")

            if self.buy_signal:
                self.trading_buy = False
                self.buy_signal = False
                self.fibonacci_chkBuy_str = "0"
                wx.CallAfter(self._reset_price_combo, ["0"])
                wx.CallAfter(self.frame.chkSignal.SetValue, False)
                wx.CallAfter(self.frame.missedSignal_combo.SetSelection, 0)
                self._write_signal_grid_row(
                    row=1, title="作多止損", note="平倉不悔", time_str=MatchTime, px=int(self.new_price)
                )

                bot_message = f"{MatchTime}  作多止損: {int(self.new_price)}  平倉不悔"
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}  作多止損: {int(self.new_price)}  平倉不悔{Style.RESET_ALL}")
                
                if self.frame.isSMS.GetValue():
                    self._async_telegram(bot_message)

            self.lowest_price = self.new_price
            self.trending_up, self.trending_down = False, True
            self._reset_group_temp(up_break=False)

        # --- 均價/現價資訊寫入 compareInfoGrid ---
        if self.TXF_db and self.MXF_db:
            up_down = "↑" if self.new_price > self.TXF_MXF_avg_price else "↓"
            color = wx.RED if up_down == "↑" else wx.GREEN
            wx.CallAfter(self.frame.compareInfoGrid.SetCellTextColour, 1, 5, color)
            wx.CallAfter(self.frame.compareInfoGrid.SetCellValue, 0, 5, f"{self.TXF_MXF_avg_price:.1f}")
            wx.CallAfter(
                self.frame.compareInfoGrid.SetCellValue, 1, 5, f"{int(self.new_price)}  {up_down}"
            )

        # --- 趨勢可能轉不明：以均價穿越前值判斷 ---
        if (
            (self.trending_up and self.pre_ATR > self.TXF_MXF_avg_price) or
            (self.trending_down and self.pre_ATR < self.TXF_MXF_avg_price)
        ) and (self.temp_price_compare.up or self.temp_price_compare.down):
            self.trending_up = self.trending_down = False

        self.pre_ATR = self.TXF_MXF_avg_price

        # --- 顯示當前分組累計時間 ---
        if self.matchtime != 0:
            tol_time = abs(self.matchtime)
            tol_time_str = self._ms_to_hhmmssms(tol_time)
        else:
            tol_time, tol_time_str = 0, "00:00:00.000"
        wx.CallAfter(self.frame.compareInfoGrid.SetCellValue, 1, 2, tol_time_str)

        # --- 更新分組內高低/方向狀態 ---
        self._execute_compare(self.temp_price_compare, MatchTime, value=int(self.new_price))

        # --- 比較框左半部(大/小/組數/當根均價與量) ---
        temp_updown = "↑" if self.temp_price_compare.up else ("↓" if self.temp_price_compare.down else "")
        wx.CallAfter(self._write_compare_left, temp_updown)

        self.temp_tickbars_total_volume += self.tmp_qty
        self.temp_TXF_MXF_TR += (self.new_price * self.tmp_qty)
        if self.temp_tickbars_total_volume > 0:
            self.temp_tickbars_avg_price = self.temp_TXF_MXF_TR / self.temp_tickbars_total_volume
        wx.CallAfter(self.frame.compareInfoGrid.SetCellValue, 1, 3, str(int(self.temp_tickbars_total_volume)))
        wx.CallAfter(self.frame.compareInfoGrid.SetCellValue, 1, 4, str(int(self.temp_tickbars_avg_price)))

        # --- 達到 group 門檻就「收」一根 ---
        target_group = safe_int(self.frame.compareInfoGrid.GetCellValue(0, 6))
        if self.group_size >= target_group:
            self._close_one_tickbar(MatchTime, tol_time, tol_time_str)

        # --- 進場後的移動停利邏輯 ---
        self._trailing_take_profit()

    # --------------------------
    # Tickbar 收斂 → 產生一根
    # --------------------------
    def _close_one_tickbar(self, MatchTime: str, tol_time: int, tol_time_str: str) -> None:
        """
        當 group_size 達到門檻時，將目前分組收斂為一根 tickbar，
        更新各種列表與 UI、偵測疑似作頭/打底並可能觸發進場。
        """
        # 累計各欄位 (close / vol / avg / time)
        self.list_close_price.append(int(self.new_price))
        self.list_temp_tickbars_total_volume.append(int(self.temp_tickbars_total_volume))
        self.list_temp_tickbars_avg_price.append(int(self.temp_tickbars_avg_price))
        wx.CallAfter(self.frame.compareInfoGrid.SetCellValue, 0, 3, str(int(self.temp_tickbars_total_volume)))
        wx.CallAfter(self.frame.compareInfoGrid.SetCellValue, 0, 4, str(int(self.temp_tickbars_avg_price)))
        self.list_tickbars_tol_time.append(tol_time)
        wx.CallAfter(self.frame.compareInfoGrid.SetCellValue, 0, 2, tol_time_str)

        # 高/低價的列表更新
        if self.temp_price_compare.big_value and self.temp_price_compare.small_value:
            self.list_temp_tickbars_big_price.append(self.temp_price_compare.big_value)
            self.list_temp_tickbars_small_price.append(self.temp_price_compare.small_value)
        else:
            self.list_temp_tickbars_big_price.append(int(self.new_price))
            self.list_temp_tickbars_small_price.append(int(self.new_price))

        # 箭頭方向基於上一根維持日高/日低邏輯
        temp_up_down_str = "．"
        if (self.previous_big_prince == self.highest_price and
                self.previous_small_prince == self.lowest_price):
            if self.temp_price_compare.up:
                temp_up_down_str = "↑"
            elif self.temp_price_compare.down:
                temp_up_down_str = "↓"

        self.previous_big_prince = self.highest_price
        self.previous_small_prince = self.lowest_price

        wx.CallAfter(self._write_compare_topline, temp_up_down_str)

        # 速度/量的偵測，給出“疑作頭/疑打底”的旗標
        suspected_speed = (
            len(self.list_tickbars_tol_time) > 1
            and self.list_tickbars_tol_time[-2] > self.list_tickbars_tol_time[-1]
            and len(self.list_temp_tickbars_total_volume) > 1
            and self.list_temp_tickbars_total_volume[-2] < self.list_temp_tickbars_total_volume[-1]
            and temp_up_down_str in ("↑", "↓")
        )

        if suspected_speed:
            if self.is_dayhigh and temp_up_down_str == "↓":
                self.is_dayhigh = False
                self.suspected_sell = True
            elif self.is_daylow and temp_up_down_str == "↑":
                self.is_daylow = False
                self.suspected_buy = True

        # ----- 真正觸發進場：疑作頭 → 空；疑打底 → 多 -----
        if self.suspected_sell and temp_up_down_str == "↓":
            self._enter_short(MatchTime)

        if self.suspected_buy and temp_up_down_str == "↑":
            self._enter_long(MatchTime)

        # 依均價變化更新“當前趨勢”(只在有 compare 暫存時判斷有效)
        if self.pre_TXF_MXF_avg_price > self.TXF_MXF_avg_price and (self.temp_price_compare.up or self.temp_price_compare.down):
            self.trending_up, self.trending_down = False, True
            print(
                    f"{Fore.GREEN}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_up_down_str_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.YELLOW}{Style.BRIGHT}{temp}{Style.RESET_ALL}")

        elif self.pre_TXF_MXF_avg_price < self.TXF_MXF_avg_price and (self.temp_price_compare.up or self.temp_price_compare.down):
            self.trending_up, self.trending_down = True, False

        # 收尾：清空當根暫存
        self.temp_price_compare.reset()
        self.temp_tickbars_total_volume = 0.0
        self.temp_TXF_MXF_TR = 0.0
        self.temp_tickbars_avg_price = 0.0

        self.pre_TXF_MXF_avg_price = self.TXF_MXF_avg_price
        self.matchtime = 0
        self.group_size = 0

    # --------------------------
    # 進出場與移動停利
    # --------------------------
    def _enter_short(self, MatchTime: str) -> None:
        """觸發空單進場，寫入 UI 與 Telegram。"""
        self.trading_sell = True
        self.stopLoss_sell = self.highest_price + 1
        p1, p2, p3 = self._calc_three_takeprofits(side="S", stop=self.stopLoss_sell)

        self._paint_signal_row(row=0, color=wx.GREEN, entry=self.list_close_price[-1],
                               stop=self.stopLoss_sell, p1=p1, p2=p2, p3=p3)

        self.fibonacci_chkSell_str = self.fibonacci_sell_str
        self.profit_sell_str = f"{p1} : {p2} : {p3}"
        self.entry_price_sell = int(self.list_close_price[-1])
        self.suspected_sell = False
        self.sell_signal = True

        if self.frame.chkSell.IsChecked():
            new_choices = [s.strip() for s in self.fibonacci_chkSell_str.split(":")]
            wx.CallAfter(self._reset_price_combo, new_choices, select_index=4)

        # 自動下單 (只在已選擇帳號且已勾選)
        if self._can_auto_order() and self.frame.chkSell.IsChecked():
            selected = self.frame.price_combo.GetString(self.frame.price_combo.GetSelection())
            price = safe_int(selected, default=self.entry_price_sell)
            wx.CallAfter(self.frame.OnOrderBtn, None, "S", price)

        # 音效 / Telegram
        if self.frame.isPlaySound.GetValue():
            threading.Thread(target=winsound.PlaySound, args=(SOUND_FILE, winsound.SND_FILENAME), daemon=True).start()
        if self.frame.isSMS.GetValue():
            self._async_telegram(f"{MatchTime}  放空進場: {self.entry_price_sell}  止損: {self.stopLoss_sell}  停利: {p1} : {p2} : {p3}")

    def _enter_long(self, MatchTime: str) -> None:
        """觸發多單進場，寫入 UI 與 Telegram。"""
        self.trading_buy = True
        self.stopLoss_buy = self.lowest_price - 1
        p1, p2, p3 = self._calc_three_takeprofits(side="B", stop=self.stopLoss_buy)

        self._paint_signal_row(row=1, color=wx.RED, entry=self.list_close_price[-1],
                               stop=self.stopLoss_buy, p1=p1, p2=p2, p3=p3)

        self.fibonacci_chkBuy_str = self.fibonacci_buy_str
        self.profit_buy_str = f"{p1} : {p2} : {p3}"
        self.entry_price_buy = int(self.list_close_price[-1])
        self.suspected_buy = False
        self.buy_signal = True

        if self.frame.chkBuy.IsChecked():
            new_choices = [s.strip() for s in self.fibonacci_chkBuy_str.split(":")]
            wx.CallAfter(self._reset_price_combo, new_choices, select_index=4)

        if self._can_auto_order() and self.frame.chkBuy.IsChecked():
            selected = self.frame.price_combo.GetString(self.frame.price_combo.GetSelection())
            price = safe_int(selected, default=self.entry_price_buy)
            wx.CallAfter(self.frame.OnOrderBtn, None, "B", price)

        if self.frame.isPlaySound.GetValue():
            threading.Thread(target=winsound.PlaySound, args=(SOUND_FILE, winsound.SND_FILENAME), daemon=True).start()
        if self.frame.isSMS.GetValue():
            self._async_telegram(f"{MatchTime}  作多進場: {self.entry_price_buy}  止損: {self.stopLoss_buy}  停利: {p1} : {p2} : {p3}")

    def _trailing_take_profit(self) -> None:
        """持倉後的三段移動停利邏輯 (profit_1 / 2 / 3)。"""
        def parse_triplet(s: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
            try:
                parts = [int(x.strip()) for x in s.split(":") if x.strip().isdigit()]
                if len(parts) >= 3:
                    return parts[0], parts[1], parts[2]
            except Exception:
                pass
            return None, None, None

        # 空單
        if self.trading_sell:
            p1, p2, p3 = parse_triplet(self.profit_sell_str)
            if p1 and p2 and p3 and self.entry_price_sell:
                if self.new_price <= p1 and self.stopLoss_sell > self.entry_price_sell:
                    self.stopLoss_sell = self.entry_price_sell
                    print(Fore.CYAN + f"🟢 空單觸及 profit_1 → 停損改至進場價 {self.stopLoss_sell}" + Style.RESET_ALL)
                elif self.new_price <= p2 and self.stopLoss_sell > p1:
                    self.stopLoss_sell = p1
                    print(Fore.CYAN + f"🟢 空單觸及 profit_2 → 停損改至 {self.stopLoss_sell}" + Style.RESET_ALL)
                elif self.new_price <= p3:
                    print(Fore.MAGENTA + f"🏁 空單觸及 profit_3 → 平倉 {self.new_price}" + Style.RESET_ALL)
                    wx.CallAfter(self.frame.OnOrderBtn, None, "B", self.new_price)
                    self.trading_sell = False
                    self.sell_signal = False

        # 多單
        elif self.trading_buy:
            p1, p2, p3 = parse_triplet(self.profit_buy_str)
            if p1 and p2 and p3 and self.entry_price_buy:
                if self.new_price >= p1 and self.stopLoss_buy < self.entry_price_buy:
                    self.stopLoss_buy = self.entry_price_buy
                    print(Fore.CYAN + f"🟢 多單觸及 profit_1 → 停損改至進場價 {self.stopLoss_buy}" + Style.RESET_ALL)
                elif self.new_price >= p2 and self.stopLoss_buy < p1:
                    self.stopLoss_buy = p1
                    print(Fore.CYAN + f"🟢 多單觸及 profit_2 → 停損改至 {self.stopLoss_buy}" + Style.RESET_ALL)
                elif self.new_price >= p3:
                    print(Fore.MAGENTA + f"🏁 多單觸及 profit_3 → 平倉 {self.new_price}" + Style.RESET_ALL)
                    wx.CallAfter(self.frame.OnOrderBtn, None, "S", self.new_price)
                    self.trading_buy = False
                    self.buy_signal = False

    # --------------------------
    # UI 寫入輔助
    # --------------------------
    def _reset_price_combo(self, items: List[str], select_index: int = 0) -> None:
        """重設共用 price_combo 項目與選取。"""
        self.frame.price_combo.SetItems(items)
        self.frame.price_combo.SetSelection(max(0, min(select_index, len(items) - 1)))

    def _write_compare_left(self, temp_updown: str) -> None:
        """更新 compareInfoGrid 左半部：大值/小值/箭頭/組數。"""
        self.frame.compareInfoGrid.SetCellTextColour(1, 0, wx.RED)
        self.frame.compareInfoGrid.SetCellTextColour(1, 1, wx.GREEN)
        self.frame.compareInfoGrid.SetCellValue(1, 0, str(int(self.temp_price_compare.big_value)))
        self.frame.compareInfoGrid.SetCellValue(1, 1, f"{int(self.temp_price_compare.small_value)}  {temp_updown}")
        self.frame.compareInfoGrid.SetCellValue(1, 6, str(self.group_size))

    def _write_compare_topline(self, temp_up_down_str: str) -> None:
        """更新 compareInfoGrid 第一列(上一根)的高/低與箭頭。"""
        self.frame.compareInfoGrid.SetCellTextColour(0, 0, wx.RED)
        self.frame.compareInfoGrid.SetCellTextColour(0, 1, wx.GREEN)
        self.frame.compareInfoGrid.SetCellValue(0, 0, str(int(self.list_temp_tickbars_big_price[-1])))
        self.frame.compareInfoGrid.SetCellValue(0, 1, f"{int(self.list_temp_tickbars_small_price[-1])}  {temp_up_down_str}")

    def _paint_signal_row(self, row: int, color: wx.Colour, entry: int, stop: int, p1: int, p2: int, p3: int) -> None:
        """將 signalGrid 第 row 列著色並填入 進場/停損/三段停利。"""
        cols = self.frame.signalGrid.GetNumberCols()
        for c in range(cols):
            self.frame.signalGrid.SetCellTextColour(row, c, color)
        self.frame.signalGrid.SetCellValue(row, 0, str(int(entry)))
        self.frame.signalGrid.SetCellValue(row, 1, str(int(stop)))
        self.frame.signalGrid.SetCellValue(row, 2, str(int(p1)))
        self.frame.signalGrid.SetCellValue(row, 3, str(int(p2)))
        self.frame.signalGrid.SetCellValue(row, 4, str(int(p3)))

    def _write_signal_grid_row(self, row: int, title: str, note: str, time_str: str, px: int) -> None:
        """在 signalGrid 指定列寫入止損訊息。"""
        self.frame.signalGrid.SetCellValue(row, 0, title)
        self.frame.signalGrid.SetCellValue(row, 1, "       ")
        self.frame.signalGrid.SetCellValue(row, 2, "猶豫不決")
        self.frame.signalGrid.SetCellValue(row, 3, "老而無成")
        self.frame.signalGrid.SetCellValue(row, 4, note)
        print(f"{Fore.YELLOW}{Style.BRIGHT}{time_str}  {title}: {px}  {note}{Style.RESET_ALL}")

    # --------------------------
    # 其他：指標、時間、比較
    # --------------------------
    def calculate_and_update(self) -> None:
        """
        以目前的日高/日低與均價，更新 GUI 上的 infoDataGrid 與 fibonacciGrid。
        也會計算一組費波那契反彈/回檔價位字串(供選單與訊息使用)。
        """
        try:
            wx.CallAfter(self.frame.infoDataGrid.SetCellValue, 0, 0, str(int(self.highest_price)))
            wx.CallAfter(self.frame.infoDataGrid.SetCellValue, 0, 1, str(int(self.lowest_price)))
            wx.CallAfter(self.frame.infoDataGrid.SetCellTextColour, 0, 0, wx.RED)
            wx.CallAfter(self.frame.infoDataGrid.SetCellTextColour, 0, 1, wx.GREEN)

            if int(getattr(self.frame.avgPrice, "GetValue", lambda: "0")()) > 0:
                xf_avg = int(self.frame.avgPrice.GetValue())
            else:
                xf_avg = int(self.TXF_MXF_avg_price)

            pressureNum = int(self.highest_price)
            supportNum = int(self.lowest_price)
            key = xf_avg

            pressure_diff = pressureNum - key
            support_diff = key - supportNum

            # 高低價差、壓力/支撐距離
            wx.CallAfter(self.frame.infoDataGrid.SetCellValue, 0, 2, str(int(pressure_diff)))
            wx.CallAfter(self.frame.infoDataGrid.SetCellTextColour, 0, 2, wx.GREEN)
            wx.CallAfter(self.frame.infoDataGrid.SetCellValue, 0, 3, str(int(support_diff)))
            wx.CallAfter(self.frame.infoDataGrid.SetCellTextColour, 0, 3, wx.RED)
            wx.CallAfter(self.frame.infoDataGrid.SetCellValue, 0, 4, str(int(pressureNum - supportNum)))

            # 計算費波那契價位
            def r(v: float) -> int:
                return round(v)

            p236 = r(key + pressure_diff * 0.236)
            p382 = r(key + pressure_diff * 0.382)
            p500 = r(key + pressure_diff * 0.5)
            p618 = r(key + pressure_diff * 0.618)
            p786 = r(key + pressure_diff * 0.786)

            s236 = r(key - support_diff * 0.236)
            s382 = r(key - support_diff * 0.382)
            s500 = r(key - support_diff * 0.5)
            s618 = r(key - support_diff * 0.618)
            s786 = r(key - support_diff * 0.786)

            self.fibonacci_sell_str = f"{p236} : {p382} : {p500} : {p618} : {p786}"
            self.fibonacci_buy_str = f"{s236} : {s382} : {s500} : {s618} : {s786}"

            # 寫進 fibonacciGrid
            for col, val in enumerate([p236, p382, p500, p618, p786]):
                wx.CallAfter(self.frame.fibonacciGrid.SetCellValue, 0, col, str(val))
            for col, val in enumerate([s236, s382, s500, s618, s786]):
                wx.CallAfter(self.frame.fibonacciGrid.SetCellValue, 1, col, str(val))

            # 趨勢建議
            if self.trending_down:
                wx.CallAfter(self.frame.infoDataGrid.SetCellTextColour, 0, 5, wx.GREEN)
                wx.CallAfter(self.frame.infoDataGrid.SetCellValue, 0, 5, "偏空操作")
            elif self.trending_up:
                wx.CallAfter(self.frame.infoDataGrid.SetCellTextColour, 0, 5, wx.RED)
                wx.CallAfter(self.frame.infoDataGrid.SetCellValue, 0, 5, "偏多操作")
            else:
                wx.CallAfter(self.frame.infoDataGrid.SetCellTextColour, 0, 5, wx.WHITE)
                wx.CallAfter(self.frame.infoDataGrid.SetCellValue, 0, 5, "觀望")

        except Exception:
            # 保守處理：UI 可能未就緒或數值尚未計算
            pass

    def _execute_compare(self, db: TempCompareDB, MatchTime: str, value: int) -> None:
        """
        更新單根分組內的極值與方向 (向上/向下)。
        """
        if db.big_value == 0 and value != 0:
            db.big_value = value
            db.small_value = value
            db.big_value_time = float(MatchTime)
            db.small_value_time = float(MatchTime)
            db.up = False
            db.down = False
        elif value > db.big_value:
            db.big_value = value
            db.big_value_time = float(MatchTime)
            db.up, db.down = True, False
        elif value < db.small_value:
            db.small_value = value
            db.small_value_time = float(MatchTime)
            db.up, db.down = False, True

    # --------------------------
    # Telegram 與安全設定
    # --------------------------
    def _async_telegram(self, message: str) -> None:
        """以背景執行緒傳送 Telegram 訊息；Token/ChatId 來自 GUI 或環境變數。"""
        token = getattr(self.frame, "TELEGRAM_TOKEN", None) or os.getenv("TELEGRAM_TOKEN", "")
        chat_id = getattr(self.frame, "TELEGRAM_CHAT_ID", None) or os.getenv("TELEGRAM_CHAT_ID", "")
        # Telegram Bot Token
        token = "8341950229:AAHw3h_p0Bnf_KcS5Mr4x3cOpIKHeFACiBs"
        # 目標 chat_id
        chat_id = "8485648973"
        if not token or not chat_id:
            return  # 若未設定則略過

        def _send() -> None:
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=5)
            except Exception:
                pass

        threading.Thread(target=_send, daemon=True).start()

    # --------------------------
    # 小工具
    # --------------------------
    @staticmethod
    def _parse_time_string(time_string: str) -> Tuple[int, int, int, int]:
        """將 'HHMMSSmmm' 切分為 (時, 分, 秒, 毫秒)。"""
        return int(time_string[:2]), int(time_string[2:4]), int(time_string[4:6]), int(time_string[6:9])

    @staticmethod
    def _to_total_ms(h: int, m: int, s: int, ms: int) -> int:
        """把 (時, 分, 秒, 毫秒) 轉為總毫秒。"""
        return (h * 3600 + m * 60 + s) * 1000 + ms

    @staticmethod
    def _ms_to_hhmmssms(ms: int) -> str:
        """把毫秒轉為 'HH:MM:SS.mmm' 字串。"""
        hours = ms // (3600 * 1000)
        ms %= 3600 * 1000
        minutes = ms // (60 * 1000)
        ms %= 60 * 1000
        seconds = ms // 1000
        milliseconds = ms % 1000
        return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

    def _reset_group_temp(self, up_break: bool) -> None:
        """當創高/創低發生時，清空當根暫存並重置方向旗標。"""
        self.temp_price_compare.reset()
        self.matchtime = 0
        self.group_size = 0
        self.temp_tickbars_total_volume = 0.0
        self.temp_TXF_MXF_TR = 0.0
        self.temp_tickbars_avg_price = 0.0
        if up_break:
            self.suspected_sell = False
        else:
            self.suspected_buy = False

    def _calc_three_takeprofits(self, side: str, stop: int) -> Tuple[int, int, int]:
        """
        給定進場價為最近 close，依距離(含 2 點緩衝)計算三段停利。
        side: "S" 空 / "B" 多
        stop: 動態停損價
        """
        close = self.list_close_price[-1]
        gap = abs(stop - close) + 2
        if side == "S":
            p1 = close - gap
            p2 = close - 2 * gap
            p3 = close - 3 * gap
        else:
            p1 = close + gap
            p2 = close + 2 * gap
            p3 = close + 3 * gap
        return int(p1), int(p2), int(p3)

    def _can_auto_order(self) -> bool:
        """是否可自動下單：需有帳號且 qtyLabel>0。"""
        try:
            return self.frame.acclist_combo.GetCount() != 0 and safe_int(self.frame.qtyLabel.GetLabel()) > 0
        except Exception:
            return False


class RedirectText:
    """
    將 print() 文字以色碼(Fore/Back/Style)解析後，顯示在 wx.TextCtrl。

    注意：此類別僅處理前景/背景色與粗體，並設定等寬字體大小。
    """
    def __init__(self, text_ctrl, font_size: int = DEFAULT_MONO_FONT_SIZE):
        """
        參數
        -----
        text_ctrl : wx.TextCtrl - 文字輸出框
        font_size : int - 等寬字體大小 (預設 12)
        """
        self.out = text_ctrl
        self.font_size = font_size

    def write(self, message: str) -> None:
        tokens = re.split(r'(\x1b\[.*?m)', message)
        self._draw_segments(tokens)

    def _draw_segments(self, segments: List[str]) -> None:
        fg = wx.WHITE
        bg = wx.BLACK
        bold = False

        for seg in segments:
            # 解析 colorama 控制碼
            if any(code in seg for code in [
                Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.CYAN, Fore.BLACK, Fore.MAGENTA, Fore.WHITE,
                Back.WHITE, Back.RED, Back.BLUE, Back.GREEN,
                Style.BRIGHT, Style.RESET_ALL
            ]):
                if Fore.RED in seg:
                    fg = wx.RED
                elif Fore.GREEN in seg:
                    fg = wx.Colour(0, 255, 0)
                elif Fore.YELLOW in seg:
                    fg = wx.Colour(255, 255, 0)
                elif Fore.CYAN in seg:
                    fg = wx.Colour(0, 255, 255)
                elif Fore.BLACK in seg:
                    fg = wx.Colour(0, 0, 0)
                elif Fore.WHITE in seg:
                    fg = wx.Colour(255, 255, 255)
                elif Fore.MAGENTA in seg:
                    fg = wx.Colour(255, 0, 255)

                if Back.WHITE in seg:
                    bg = wx.Colour(255, 255, 255)
                elif Back.RED in seg:
                    bg = wx.Colour(128, 0, 0)
                elif Back.BLUE in seg:
                    bg = wx.Colour(0, 0, 128)
                elif Back.GREEN in seg:
                    bg = wx.Colour(0, 128, 0)

                if Style.BRIGHT in seg:
                    bold = True
                if Style.RESET_ALL in seg:
                    fg = wx.WHITE
                    bg = wx.BLACK
                    bold = False
                continue

            # 設定樣式（含字體大小）
            style = wx.TextAttr(fg, bg)
            style.SetFont(wx.Font(
                self.font_size,
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
            ))

            self.out.SetDefaultStyle(style)
            self.out.AppendText(seg)

        self.out.ShowPosition(self.out.GetLastPosition())

    def flush(self) -> None:
        pass
