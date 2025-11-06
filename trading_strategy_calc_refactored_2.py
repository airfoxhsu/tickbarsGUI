
"""
trading_strategy_calc_refactored.py

嚴謹重構重點（保留所有 print 輸出邏輯不刪除）：
- 加上完整模組／類別／函式 docstring（以費曼方式描述：這段做什麼、為何需要、輸入輸出是什麼）。
- 為 __init__ 裡的「每一個成員變數」加註解（用途、型別、何時改變）。
- 為所有公開方法加入型別註解與說明。
- 將「時間處理」、「均價計算」、「極值／趨勢比較」等重複邏輯收斂為小函式（原本就獨立者保留）。
- 嚴格不刪除任何 print() 相關程式碼（原封不動保留原始字串與格式）。

注意：
- 本檔案假設外部 GUI 物件（self.frame）結構與欄位皆與原版一致（例如 compareInfoGrid、signalGrid 等）。
- 由於 print 內容大量使用 colorama 轉義字元與 eval() 串接色彩字串，為了 100% 保留原本輸出行為，相關敘述照原始碼保留。
"""

from __future__ import annotations

import re
import sys
import threading
import winsound
from typing import Dict, List, Tuple, Optional

# 第三方套件（原始碼已使用）
from colorama import Fore, Style, Back
import wx
import requests


class TradingStrategy:
    """
    交易策略主引擎：
    - 接收逐筆行情（TXF / MXF），持續累計成交量、成交價值，計算「交易時段總均價」。
    - 動態追蹤區間高低點、每組 tickbars 的統計（總量/均價/時間），並用「疑作頭/疑打底」偵測可能的進出訊號。
    - 依據進場後的 profit_1 / profit_2 / profit_3（停利階梯）自動移動停損至進場價或前一級停利，並在達成 profit_3 時自動平倉。
    - 所有 print 訊息（含色彩、字串格式）完整保留，用於你的 GUI 內嵌終端視窗做即時觀察。

    參數：
    frame: 外部 GUI 物件，需提供若干 wx 元件欄位（例如 monitorTradeSignal、compareInfoGrid、signalGrid 等）。
    """

    def __init__(self, frame) -> None:
        """
        初始化所有狀態。每個成員變數都附上註解（用途/型別/何時變更）。
        """
        # ────── GUI / 輸出導向 ──────
        self.frame = frame                               # (Any) 由外部建立的 wx 主框架，含各種 Grid / 控制項。
        sys.stdout = RedirectText(self.frame.monitorTradeSignal)  # 導向 stdout 到 GUI 的 TextCtrl。
        sys.stderr = RedirectText(self.frame.monitorTradeSignal)  # 導向 stderr 到 GUI 的 TextCtrl。

        # 啟動訊息（顏色示範；請不要移除）
        print(Style.BRIGHT + Fore.GREEN + "✅ 成功訊息 (亮綠色)"
              + Fore.RED + Back.WHITE + "❌ 錯誤訊息 (紅字白底)"
              + Style.RESET_ALL)

        # ────── 使用者可動態配置的字串與暫存 ──────
        self.fibonacci_sell_str: str = ""                # 放空時費波那契五段價位「字串」(a:b:c:d:e)；由 calculate_and_update 計算後填入。
        self.fibonacci_buy_str: str = ""                 # 作多時費波那契五段價位「字串」(a:b:c:d:e)；由 calculate_and_update 計算後填入。
        self.fibonacci_chkSell_str: str = "0"            # 當前「放空」下單用的價位選單來源（":" 分隔），預設 "0"。
        self.fibonacci_chkBuy_str: str = "0"             # 當前「作多」下單用的價位選單來源（":" 分隔），預設 "0"。
        self.profit_buy_str: str = ""                    # 多單三段停利字串 "p1 : p2 : p3"。
        self.profit_sell_str: str = ""                   # 空單三段停利字串 "p1 : p2 : p3"。

        # ────── 場景累計（交易時段等級） ──────
        self.total_spread: int = 0                       # （保留）整體價差（未使用在印出；保留以相容舊程式）。
        self.new_price: float = 0.0                      # 最新成交價（每次逐筆更新）。
        self.TXF_database: Dict[str, float] = {}         # TXF 聚合資料（current_total_volume / total_volume / match_pri / pre_matchtime）。
        self.MXF_database: Dict[str, float] = {}         # MXF 聚合資料。
        self.spread_compare_database: Dict = {}          # （保留）價差比較暫存（目前未使用）。
        self.ohlc_database: Dict = {}                    # （保留）OHLC 暫存（目前未使用）。
        self.long_signal: Dict[str, float] = {}          # （保留）多訊號暫存（示範用途）。
        self.short_signal: Dict[str, float] = {}         # （保留）空訊號暫存（示範用途）。

        # ────── 指標／趨勢追蹤 ──────
        self.Index: int = 0                              # （保留）策略內部索引（示範計數用途）。
        self.profit: int = 0                             # （保留）累積損益（示範用於 handle_entry_signal/handle_short_exit）。
        self.is_dayhigh: bool = True                     # 是否「目前 tickbars 的最高價」仍創高狀態（用於疑作頭判斷）。
        self.is_daylow: bool = True                      # 是否「目前 tickbars 的最低價」仍創低狀態（用於疑打底判斷）。

        self.TXF_MXF_tol_value: float = 0.0              # 大小台成交價值累積（加權：TXF 4*qty + MXF 1*qty）。
        self.TXF_MXF_avg_price: float = 0.0              # 交易時段總均價（以成交價值 / 加權總量計算）。
        self.pre_TXF_MXF_avg_price: float = 0.0          # 前一個均價（用於判斷漲跌/方向）。
        self.TRi: List[float] = []                       # （保留）真實波幅序列（未啟用）。
        self.ATR: float = 0.0                            # （保留）平均真實波幅（未啟用）。
        self.trending_down: bool = False                 # 當前趨勢是否向下（由均價比較與 temp_price_compare_database 觸發）。
        self.trending_up: bool = False                   # 當前趨勢是否向上。
        self.pre_ATR: float = 0.0                        # （保留）上一期 ATR 或均價比較基準（此處用作均價基準）。
        self.entry_signal: bool = False                  # （保留）是否達到進場信號（示範）。

        # 多空獨立進場價（你的既有需求）
        self.entry_price_buy: int = 0                    # 多單進場價（整數）
        self.entry_price_sell: int = 0                   # 空單進場價（整數）
        self.temp_entry_price: int = 0                   # 近期均價（顯示在 compareInfoGrid 上，亦作提醒）。

        self.temp_total_spread: int = 0                  # （保留）短期價差。
        self.warning_signal: bool = False                # （保留）警告旗標。
        self.temp_ATR_up: bool = False                   # （保留）暫時 ATR 向上訊號。
        self.temp_ATR_down: bool = False                 # （保留）暫時 ATR 向下訊號。

        # —— tickbars 內部暫存 ——
        self.temp_price_compare_database: Dict[str, float | bool] = {}  # 追蹤當前組內的高低點與方向（up/down）。
        self.temp_big_value: int = 0                                      # （保留）暫存大值。
        self.temp_small_value: int = 0                                    # （保留）暫存小值。
        self.highest_price: int = 0                                       # 截至目前為止的最高價。
        self.lowest_price: int = 0                                        # 截至目前為止的最低價。

        # —— tickbars 序列資料 ——
        self.list_close_price: List[int] = []                # 每根 tickbar 的收盤價（用 int(new_price) 追加）。
        self.list_tickbars_tol_time: List[int] = []          # 每根 tickbar 的耗時（毫秒）。
        self.list_temp_tickbars_avg_price: List[int] = []    # 每根 tickbar 的平均價（int）。
        self.list_temp_tickbars_big_price: List[int] = []    # 每根 tickbar 的最高價（int）。
        self.list_temp_tickbars_small_price: List[int] = []  # 每根 tickbar 的最低價（int）。
        self.list_temp_tickbars_total_volume: List[int] = [] # 每根 tickbar 的總成交量（int）。

        self.previous_big_prince: int = 0                    # 上一根最高價（判斷是否持續創高）。
        self.previous_small_prince: int = 0                  # 上一根最低價（判斷是否持續創低）。

        # —— 批次計數 / 速度資訊 ——
        self.conform_total_volume: int = 0                   # （保留）符合條件時的量。
        self.count: int = 0                                  # 次數計數（示範用於 handle_entry_signal/exit）。
        self.pre_matchtime: int = 0                          # （保留）上一筆撮合時間（毫秒）。
        self.matchtime: int = 0                              # 累計本組內的毫秒差（每增加一筆累計）。
        self.group_size: int = 0                             # 本組累計的筆數（用 compareInfoGrid 第 7 欄控制顯示）。
        self.time_diff: int = 0                              # （保留）一般時間差。
        self.time_price_per: float = 0.0                     # （保留）時間／價格比。
        self.time_diff_str: str = "00:00:00.000"             # （保留）時間差字串。

        # —— 訊號與單邊持倉狀態 ——
        self.list_signal_str: List[str] = []                 # （保留）訊號字串列表。
        self.trading_buy: bool = False                       # 是否持有多單。
        self.trading_sell: bool = False                      # 是否持有空單。
        self.stopLoss_sell: int = 0                          # 空單停損價（會隨 profit_1 / profit_2 逐步上移）。
        self.stopLoss_buy: int = 0                           # 多單停損價（會隨 profit_1 / profit_2 逐步下移）。

        # —— 本組即時計算累加（不跨組）——
        self.temp_tickbars_total_volume: int = 0             # 本組成交量累加（加權後）。
        self.temp_TXF_MXF_TR: float = 0.0                    # 本組成交價值累加（price * qty）。
        self.temp_tickbars_avg_price: float = 0.0            # 本組加權平均價（TR / volume）。
        self.list_temp_tickbars_avg_price: List[int] = []    # （再次宣告在原始碼中重複；此處保留一份即可）
        self.list_speedtime_big_price: List[int] = []        # （保留）加速階段的高點列表。
        self.list_speedtime_small_price: List[int] = []      # （保留）加速階段的低點列表。
        self.list_temp_up_down_str: List[str] = []           # （保留）方向字串列表。

        # —— 疑似訊號（疑作頭/疑打底） ——
        self.suspected_buy: bool = False                     # 偵測到「疑打底」。
        self.suspected_sell: bool = False                    # 偵測到「疑作頭」。
        self.sell_signal: bool = False                       # 已觸發放空訊號（用於止損/清單重設）。
        self.buy_signal: bool = False                        # 已觸發作多訊號。

        # 內部暫存：逐筆更新時用到的加權數量（TXF 4 倍、MXF 1 倍）
        self.tmp_qty: float = 0.0

    # ─────────────────────────────────────────────────────────────────────
    # 事件入口：逐筆行情處理
    # ─────────────────────────────────────────────────────────────────────
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
        Is_simulation: bool
    ) -> None:
        """
        接收逐筆成交，依商品別（TXF / MXF）設定加權張數，並更新大小台資料庫與時間統計。
        - TXF 的加權數量 = 4 * MatchQty
        - MXF 的加權數量 = 1 * MatchQty

        重要：
        - self.new_price 以 MatchPri 更新；後續計算都使用 float(self.new_price)
        - 每當 TXF 或 MXF 有新增成交量（TolMatchQty 變大），會呼叫 calculate_time()
        """
        if "XF" in symbol:
            self.tmp_qty = 0
            self.new_price = float(MatchPri)
        if "TXF" in symbol:
            self.tmp_qty = 4 * float(MatchQty)
            self.calculate_time(self.TXF_database, RefPri, HighPri, LowPri,
                                MatchQty, TolMatchQty, MatchTime, Is_simulation)
        elif "MXF" in symbol:
            self.tmp_qty = float(MatchQty)
            self.calculate_time(self.MXF_database, RefPri, HighPri, LowPri,
                                MatchQty, TolMatchQty, MatchTime, Is_simulation)

    # ─────────────────────────────────────────────────────────────────────
    # tickbars 主邏輯（保留原始印出內容）
    # ─────────────────────────────────────────────────────────────────────
    def calculate_tickbars(self, MatchTime: str, Is_simulation: bool) -> None:
        """
        每當有新的一筆（且 TolMatchQty 成長）就會被 calculate_time 呼叫：
        - 更新日內最高/最低價並重置本組統計。
        - 推進 compareInfoGrid 的顯示（均價/現價/耗時/組內 big/small）。
        - 當 group_size 達到 compareInfoGrid(0,6) 設定值，就觸發 show_tickbars 做一次「收組」印出與訊號檢查。

        額外：
        - 在函式結尾保留「移動停利」邏輯（多空各自一套），以 profit_1 / profit_2 / profit_3 判斷。
        """
        if self.highest_price < self.new_price:
            if self.trading_sell == True: 
                if self.frame.acclist_combo.GetCount() != 0 and self.frame.chkSell.GetValue() == True:
                    val = self.frame.qtyLabel.GetLabel()
                    qty = int(val) if val.isdigit() else 0
                    if qty > 0:
                        self.frame.OnOrderBtn(event=None, S_Buys="B", price=self.new_price)
                        self.frame.qtyLabel.SetLabel("未連") 
            if self.sell_signal== True:    
                self.trading_sell = False
                self.sell_signal= False
                self.fibonacci_chkSell_str = "0"
                new_choices = ["0"]  # 或給預設選單
                self.frame.price_combo.SetItems(new_choices)
                self.frame.price_combo.SetSelection(0)
                self.frame.chkSignal.SetValue(False)
                self.frame.missedSignal_combo.SetSelection(0)

                self.frame.signalGrid.SetCellValue(0, 0, "放空止損")
                self.frame.signalGrid.SetCellValue(0, 1, "       ")
                self.frame.signalGrid.SetCellValue(0, 2, "猶豫不決")
                self.frame.signalGrid.SetCellValue(0, 3, "老而無成")
                self.frame.signalGrid.SetCellValue(0, 4, "平倉不悔")

                bot_message = f"{MatchTime}  放空止損: {int(self.new_price)}  平倉不悔"
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}  放空止損: {int(self.new_price)}  平倉不悔{Style.RESET_ALL}")
                if self.frame.isSMS.GetValue() == True:
                    threading.Thread(target=self.telegram_bot_sendtext, args=(
                        bot_message,), daemon=True).start()

            self.highest_price = self.new_price
            self.trending_up = True
            self.trending_down = False
            self.temp_entry_price = 0
            self.suspected_sell = False
            self.matchtime = 0
            self.group_size = 0
            self.temp_price_compare_database = {}
            self.temp_tickbars_total_volume = 0
            self.temp_TXF_MXF_TR = 0
            self.temp_tickbars_avg_price = 0
        elif self.lowest_price > self.new_price:
            if self.trading_buy == True:
                if self.frame.acclist_combo.GetCount() != 0 and self.frame.chkBuy.GetValue() == True:
                    val = self.frame.qtyLabel.GetLabel()
                    qty = int(val) if val.isdigit() else 0
                    if qty > 0:
                        self.frame.OnOrderBtn(event=None, S_Buys="S", price=self.new_price)
                        self.frame.qtyLabel.SetLabel("未連")
            if self.buy_signal== True:
                self.trading_buy = False
                self.buy_signal= False
                self.fibonacci_chkBuy_str = "0"
                new_choices = ["0"]  # 或給預設選單
                self.frame.price_combo.SetItems(new_choices)
                self.frame.price_combo.SetSelection(0)
                self.frame.chkSignal.SetValue(False)
                self.frame.missedSignal_combo.SetSelection(0)

                self.frame.signalGrid.SetCellValue(1, 0, "作多止損")
                self.frame.signalGrid.SetCellValue(1, 1, "       ")
                self.frame.signalGrid.SetCellValue(1, 2, "猶豫不決")
                self.frame.signalGrid.SetCellValue(1, 3, "老而無成")
                self.frame.signalGrid.SetCellValue(1, 4, "平倉不悔")

                bot_message = f"{MatchTime}  作多止損: {int(self.new_price)}  平倉不悔"
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}  作多止損: {int(self.new_price)}  平倉不悔{Style.RESET_ALL}")
                if self.frame.isSMS.GetValue() == True:
                    threading.Thread(target=self.telegram_bot_sendtext, args=(
                        bot_message,), daemon=True).start()

            self.lowest_price = self.new_price
            self.trending_up = False
            self.trending_down = True
            self.temp_entry_price = 0
            self.suspected_buy = False
            self.matchtime = 0
            self.group_size = 0
            self.temp_price_compare_database = {}
            self.temp_tickbars_total_volume = 0
            self.temp_TXF_MXF_TR = 0
            self.temp_tickbars_avg_price = 0

        up_down_str = ""
        if self.TXF_database and self.MXF_database:
            if self.new_price > self.TXF_MXF_avg_price:
                up_down_str = "↑"
                self.frame.compareInfoGrid.SetCellTextColour(1, 5, wx.RED)
            elif self.new_price < self.TXF_MXF_avg_price:
                up_down_str = "↓"
                self.frame.compareInfoGrid.SetCellTextColour(1, 5, wx.GREEN)
            self.frame.compareInfoGrid.SetCellValue(
                0, 5, str(float(round(self.TXF_MXF_avg_price, 1))))
            self.frame.compareInfoGrid.SetCellValue(
                1, 5, str(int(self.new_price))+"  "+up_down_str)

            self.temp_entry_price = int(self.TXF_MXF_avg_price)

        # 趨勢由明轉不明（以 pre_ATR 做前值基準）
        if (self.trending_up and self.pre_ATR > self.TXF_MXF_avg_price) or (self.trending_down and self.pre_ATR < self.TXF_MXF_avg_price) and self.temp_price_compare_database:
            self.trending_up = False
            self.trending_down = False
        self.pre_ATR = self.TXF_MXF_avg_price

        # 毫秒差 to HH:MM:SS.mmm
        if self.matchtime != 0:
            diff_ms = abs(self.matchtime)
            tol_time = diff_ms
            hours = diff_ms // (3600 * 1000)
            diff_ms %= 3600 * 1000
            minutes = diff_ms // (60 * 1000)
            diff_ms %= 60 * 1000
            seconds = diff_ms // 1000
            milliseconds = diff_ms % 1000
            tol_time_str = f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"
        else:
            tol_time_str = "00:00:00.000"
            tol_time = 0

        self.frame.compareInfoGrid.SetCellValue(1, 2, tol_time_str)
        self.execute_compare(self.temp_price_compare_database, MatchTime, value=self.new_price)

        temp_up_down_str = ""
        if self.temp_price_compare_database['up']:
            temp_up_down_str = "↑"
        elif self.temp_price_compare_database['down']:
            temp_up_down_str = "↓"

        self.frame.compareInfoGrid.SetCellTextColour(1, 0, wx.RED)
        self.frame.compareInfoGrid.SetCellTextColour(1, 1, wx.GREEN)
        self.frame.compareInfoGrid.SetCellValue(
            1, 0, str(int(self.temp_price_compare_database['big_value'])))
        self.frame.compareInfoGrid.SetCellValue(1, 1, str(
            int(self.temp_price_compare_database['small_value']))+"  "+temp_up_down_str)
        self.frame.compareInfoGrid.SetCellValue(1, 6, str(self.group_size))

        self.temp_tickbars_total_volume += self.tmp_qty
        self.temp_TXF_MXF_TR += (self.new_price * self.tmp_qty)
        self.temp_tickbars_avg_price = self.temp_TXF_MXF_TR / (self.temp_tickbars_total_volume)
        self.frame.compareInfoGrid.SetCellValue(1, 3, str(int(self.temp_tickbars_total_volume)))
        self.frame.compareInfoGrid.SetCellValue(1, 4, str(int(self.temp_tickbars_avg_price)))

        value = int(self.frame.compareInfoGrid.GetCellValue(0, 6))
        if self.group_size >= value:
            self.show_tickbars(MatchTime, tol_time, tol_time_str)

        # === [新增] 即時停利判斷（保留） ===
        def _parse_profit_triplet(s: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
            try:
                parts = [int(x.strip()) for x in s.split(":") if x.strip().isdigit()]
                if len(parts) >= 3:
                    return parts[0], parts[1], parts[2]
            except Exception:
                pass
            return None, None, None

        # 空單移動停利邏輯
        if self.trading_sell:
            p1, p2, p3 = _parse_profit_triplet(self.profit_sell_str)
            if p1 and p2 and p3 and self.entry_price_sell:
                if self.new_price <= p1 and self.stopLoss_sell > self.entry_price_sell:
                    self.stopLoss_sell = self.entry_price_sell
                    print(Fore.CYAN + f"🟢 空單觸及 profit_1 → 停損改至進場價 {self.stopLoss_sell}" + Style.RESET_ALL)
                elif self.new_price <= p2 and self.stopLoss_sell > p1:
                    self.stopLoss_sell = p1
                    print(Fore.CYAN + f"🟢 空單觸及 profit_2 → 停損改至 {self.stopLoss_sell}" + Style.RESET_ALL)
                elif self.new_price <= p3:
                    print(Fore.MAGENTA + f"🏁 空單觸及 profit_3 → 平倉 {self.new_price}" + Style.RESET_ALL)
                    self.frame.OnOrderBtn(event=None, S_Buys="B", price=self.new_price)
                    self.trading_sell = False
                    self.sell_signal = False

        # 多單移動停利邏輯
        elif self.trading_buy:
            p1, p2, p3 = _parse_profit_triplet(self.profit_buy_str)
            if p1 and p2 and p3 and self.entry_price_buy:
                if self.new_price >= p1 and self.stopLoss_buy < self.entry_price_buy:
                    self.stopLoss_buy = self.entry_price_buy
                    print(Fore.CYAN + f"🟢 多單觸及 profit_1 → 停損改至進場價 {self.stopLoss_buy}" + Style.RESET_ALL)
                elif self.new_price >= p2 and self.stopLoss_buy < p1:
                    self.stopLoss_buy = p1
                    print(Fore.CYAN + f"🟢 多單觸及 profit_2 → 停損改至 {self.stopLoss_buy}" + Style.RESET_ALL)
                elif self.new_price >= p3:
                    print(Fore.MAGENTA + f"🏁 多單觸及 profit_3 → 平倉 {self.new_price}" + Style.RESET_ALL)
                    self.frame.OnOrderBtn(event=None, S_Buys="S", price=self.new_price)
                    self.trading_buy = False
                    self.buy_signal = False

    # （原始印出函式，完整保留內文與 print）
    def show_tickbars(self, MatchTime: str, tol_time: int, tol_time_str: str) -> None:
        """
        「收組」：當 group_size 達到門檻，彙整本組的最高/最低/均價/量與方向，
        並判斷「疑作頭／疑打底 → 進場空／進場多」的條件；
        產生訊號後即時更新 signalGrid、price_combo、以及可選擇自動送單與 Telegram 推播。
        """
        temp = ""
        mark_timediff_num = 0
        mark_timediff_price_per_num = 0
        mark_temp_big_price_num = 0
        mark_temp_small_price_num = 0
        mark_temp_close_avg_price_num = 0
        mark_temp_tickbars_avg_price_num = 0
        mark_temp_total_volume_num = 0
        mark_speedtime_num = 0
        temp_avg_price = 0

        mark_tol_time_color = "Style.RESET_ALL"
        mark_temp_up_down_str_color = "Style.RESET_ALL"
        mark_temp_big_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_small_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_close_price_color = "Fore.YELLOW + Style.BRIGHT"

        self.list_close_price.append(self.new_price)
        self.list_temp_tickbars_total_volume.append(
            self.temp_tickbars_total_volume)
        self.list_temp_tickbars_avg_price.append(
            int(self.temp_tickbars_avg_price))

        self.frame.compareInfoGrid.SetCellValue(
            0, 3, str(int(self.temp_tickbars_total_volume)))
        self.frame.compareInfoGrid.SetCellValue(
            0, 4, str(int(self.temp_tickbars_avg_price)))

        self.list_tickbars_tol_time.append(tol_time)

        if self.temp_price_compare_database:
            self.list_temp_tickbars_big_price.append(
                self.temp_price_compare_database['big_value'])
            self.list_temp_tickbars_small_price.append(
                self.temp_price_compare_database['small_value'])
        else:
            self.list_temp_tickbars_big_price.append(self.new_price)
            self.list_temp_tickbars_small_price.append(self.new_price)

        self.frame.compareInfoGrid.SetCellValue(0, 2, tol_time_str)

        temp_up_down_str = "．"
        if self.previous_big_prince == self.highest_price and self.previous_small_prince == self.lowest_price:
            if self.temp_price_compare_database['up']:
                temp_up_down_str = "↑"
            elif self.temp_price_compare_database['down']:
                temp_up_down_str = "↓"

        self.previous_big_prince = self.highest_price
        self.previous_small_prince = self.lowest_price

        self.frame.compareInfoGrid.SetCellTextColour(0, 0, wx.RED)
        self.frame.compareInfoGrid.SetCellTextColour(0, 1, wx.GREEN)
        self.frame.compareInfoGrid.SetCellValue(
            0, 0, str(int(self.list_temp_tickbars_big_price[-1])))
        self.frame.compareInfoGrid.SetCellValue(
            0, 1, str(int(self.list_temp_tickbars_small_price[-1]))+"  "+temp_up_down_str)

        if len(self.list_temp_tickbars_big_price) > 1 and self.list_temp_tickbars_big_price[-1] == self.highest_price:
            self.is_dayhigh = True
        if len(self.list_temp_tickbars_small_price) > 1 and self.list_temp_tickbars_small_price[-1] == self.lowest_price:
            self.is_daylow = True

        # 判斷收盤價與均價的相對位置（1=空，2=多）
        if self.list_close_price[-1] < self.list_temp_tickbars_avg_price[-1]:
            mark_temp_close_avg_price_num = 1
        elif self.list_close_price[-1] > self.list_temp_tickbars_avg_price[-1]:
            mark_temp_close_avg_price_num = 2

        # 判斷 tickbars 高/低/均價 漲跌
        if len(self.list_temp_tickbars_big_price) > 1 and self.list_temp_tickbars_big_price[-2] >= self.list_temp_tickbars_big_price[-1]:
            mark_temp_big_price_num = 1
        elif len(self.list_temp_tickbars_big_price) > 1 and self.list_temp_tickbars_big_price[-2] < self.list_temp_tickbars_big_price[-1]:
            mark_temp_big_price_num = 2

        if len(self.list_temp_tickbars_small_price) > 1 and self.list_temp_tickbars_small_price[-2] > self.list_temp_tickbars_small_price[-1]:
            mark_temp_small_price_num = 1
        elif len(self.list_temp_tickbars_small_price) > 1 and self.list_temp_tickbars_small_price[-2] <= self.list_temp_tickbars_small_price[-1]:
            mark_temp_small_price_num = 2

        if len(self.list_temp_tickbars_avg_price) > 1 and self.list_temp_tickbars_avg_price[-2] > self.list_temp_tickbars_avg_price[-1]:
            mark_temp_tickbars_avg_price_num = 1
        elif len(self.list_temp_tickbars_avg_price) > 1 and self.list_temp_tickbars_avg_price[-2] < self.list_temp_tickbars_avg_price[-1]:
            mark_temp_tickbars_avg_price_num = 2

        # 量增
        if len(self.list_temp_tickbars_total_volume) > 1 and self.list_temp_tickbars_total_volume[-2] < self.list_temp_tickbars_total_volume[-1]:
            mark_temp_total_volume_num = 1

        # 速度加快（時間變短 + 量增 + 有方向）
        if len(self.list_tickbars_tol_time) > 1 and self.list_tickbars_tol_time[-2] > self.list_tickbars_tol_time[-1] and mark_temp_total_volume_num == 1 and (temp_up_down_str == "↑" or temp_up_down_str == "↓"):
            mark_temp_up_down_str_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"
            mark_speedtime_num = 1

        if mark_speedtime_num == 1:
            if self.is_dayhigh and temp_up_down_str == "↓":
                self.is_dayhigh = False
                self.suspected_sell = True
            elif self.is_daylow and temp_up_down_str == "↑":
                self.is_daylow = False
                self.suspected_buy = True

        if len(self.list_tickbars_tol_time) > 1 and (self.list_tickbars_tol_time[-2]/2) > self.list_tickbars_tol_time[-1]:
            mark_tol_time_color = "Fore.BLACK + Back.WHITE"

        # —— 進場空 ——
        if self.suspected_sell == True and temp_up_down_str == "↓":
            self.trading_sell = True
            mark_temp_close_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
            self.stopLoss_sell = self.highest_price+1
            profit_1 = self.list_close_price[-1] - (abs(self.stopLoss_sell-self.list_close_price[-1])+2)
            profit_2 = self.list_close_price[-1] - ((abs(self.stopLoss_sell-self.list_close_price[-1])+2)*2)
            profit_3 = self.list_close_price[-1] - ((abs(self.stopLoss_sell-self.list_close_price[-1])+2)*3)

            cols = self.frame.signalGrid.GetNumberCols()
            for c in range(cols):
                self.frame.signalGrid.SetCellTextColour(0, c, wx.GREEN)
            self.frame.signalGrid.SetCellValue(0, 0, str(int(self.list_close_price[-1])))
            self.frame.signalGrid.SetCellValue(0, 1, str(int(self.stopLoss_sell)))
            self.frame.signalGrid.SetCellValue(0, 2, str(int(profit_1)))
            self.frame.signalGrid.SetCellValue(0, 3, str(int(profit_2)))
            self.frame.signalGrid.SetCellValue(0, 4, str(int(profit_3)))

            self.fibonacci_chkSell_str = self.fibonacci_sell_str
            self.profit_sell_str = f"{int(profit_1)} : {int(profit_2)} : {int(profit_3)}"

            if self.frame.chkSell.IsChecked():
                new_choices = [s.strip() for s in self.fibonacci_chkSell_str.split(":")]
                self.frame.price_combo.SetItems(new_choices)
                self.frame.price_combo.SetSelection(4)

            temp = "進場空"
            self.entry_price_sell = int(self.list_close_price[-1])  # 記錄空單進場價
            self.suspected_sell = False
            self.sell_signal=True
            if self.frame.chkSell.IsChecked() and self.frame.acclist_combo.GetCount() != 0:
                val = self.frame.price_combo.GetString(self.frame.price_combo.GetSelection())
                price = int(val) if val.isdigit() else 0
                self.frame.OnOrderBtn(event=None, S_Buys="S", price=price)

            if self.frame.isPlaySound.GetValue() == True:
                threading.Thread(target=winsound.PlaySound, args=("woo.wav", winsound.SND_FILENAME), daemon=True).start()

            if self.frame.isSMS.GetValue() == True:
                bot_message = f"{MatchTime}  放空進場: {int(self.list_close_price[-1])}  止損: {int(self.stopLoss_sell)}  停利: {int(profit_1)} : {int(profit_2)} : {int(profit_3)}"
                threading.Thread(target=self.telegram_bot_sendtext, args=(bot_message,), daemon=True).start()

        # —— 進場多 ——
        if self.suspected_buy == True and temp_up_down_str == "↑":
            self.trading_buy = True
            mark_temp_close_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
            self.stopLoss_buy = self.lowest_price-1
            profit_1 = self.list_close_price[-1] + (abs(self.stopLoss_buy-self.list_close_price[-1])+2)
            profit_2 = self.list_close_price[-1] + ((abs(self.stopLoss_buy-self.list_close_price[-1])+2)*2)
            profit_3 = self.list_close_price[-1] + ((abs(self.stopLoss_buy-self.list_close_price[-1])+2)*3)

            cols = self.frame.signalGrid.GetNumberCols()
            for c in range(cols):
                self.frame.signalGrid.SetCellTextColour(1, c, wx.RED)
            self.frame.signalGrid.SetCellValue(1, 0, str(int(self.list_close_price[-1])))
            self.frame.signalGrid.SetCellValue(1, 1, str(int(self.stopLoss_buy)))
            self.frame.signalGrid.SetCellValue(1, 2, str(int(profit_1)))
            self.frame.signalGrid.SetCellValue(1, 3, str(int(profit_2)))
            self.frame.signalGrid.SetCellValue(1, 4, str(int(profit_3)))

            self.fibonacci_chkBuy_str = self.fibonacci_buy_str
            self.profit_buy_str = f"{int(profit_1)} : {int(profit_2)} : {int(profit_3)}"

            if self.frame.chkBuy.IsChecked():
                new_choices = [s.strip() for s in self.fibonacci_chkBuy_str.split(":")]
                self.frame.price_combo.SetItems(new_choices)
                self.frame.price_combo.SetSelection(4)

            temp = "進場多"
            self.entry_price_buy = int(self.list_close_price[-1])   # 記錄多單進場價
            self.suspected_buy = False
            self.buy_signal=True
            if self.frame.chkBuy.IsChecked() and self.frame.acclist_combo.GetCount() != 0:
                val = self.frame.price_combo.GetString(self.frame.price_combo.GetSelection())
                price = int(val) if val.isdigit() else 0
                self.frame.OnOrderBtn(event=None, S_Buys="B", price=price)

            if self.frame.isPlaySound.GetValue() == True:
                threading.Thread(target=winsound.PlaySound, args=("woo.wav", winsound.SND_FILENAME), daemon=True).start()

            if self.frame.isSMS.GetValue() == True:
                bot_message = f"{MatchTime}  作多進場: {int(self.list_close_price[-1])}  止損: {int(self.stopLoss_buy)}  停利: {int(profit_1)} : {int(profit_2)} : {int(profit_3)}"
                threading.Thread(target=self.telegram_bot_sendtext, args=(bot_message,), daemon=True).start()

        # —— 方向性彙整與印出（原樣保留）——
        if self.pre_TXF_MXF_avg_price > self.TXF_MXF_avg_price and self.temp_price_compare_database:
            self.trending_up = False
            self.trending_down = True
            if temp == "進場空":
                print(
                    f"{Fore.GREEN}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_up_down_str_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現:{Style.RESET_ALL}{eval(mark_temp_close_price_color)} {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.GREEN}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}放空 {int(self.list_close_price[-1])}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_sell_str}   止損: {int(self.stopLoss_sell)}   停利: {self.profit_sell_str}{Style.RESET_ALL}")

            elif temp == "進場多":
                print(
                    f"{Fore.GREEN}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_up_down_str_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現:{Style.RESET_ALL}{eval(mark_temp_close_price_color)} {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.RED}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}買進 {int(self.list_close_price[-1])}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_buy_str}   止損: {int(self.stopLoss_buy)}   停利: {self.profit_buy_str}{Style.RESET_ALL}")
            else:
                print(
                    f"{Fore.GREEN}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_up_down_str_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.YELLOW}{Style.BRIGHT}{temp}{Style.RESET_ALL}")

        elif self.pre_TXF_MXF_avg_price < self.TXF_MXF_avg_price and self.temp_price_compare_database:
            self.trending_up = True
            self.trending_down = False
            if temp == "進場多":
                print(
                    f"{Fore.RED}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_up_down_str_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}現:{Style.RESET_ALL}{eval(mark_temp_close_price_color)} {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.RED}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}買進 {int(self.list_close_price[-1])}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_buy_str}   止損: {int(self.stopLoss_buy)}   停利: {self.profit_buy_str}{Style.RESET_ALL}")
            elif temp == "進場空":
                print(
                    f"{Fore.RED}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_up_down_str_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}現:{Style.RESET_ALL}{eval(mark_temp_close_price_color)} {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.GREEN}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}放空 {int(self.list_close_price[-1])}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_sell_str}   止損: {int(self.stopLoss_sell)}   停利: {self.profit_sell_str}{Style.RESET_ALL}")

            else:
                print(
                    f"{Fore.RED}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_up_down_str_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.YELLOW}{Style.BRIGHT}{temp}{Style.RESET_ALL}")

        # 重置本組暫存
        self.temp_price_compare_database = {}
        self.temp_tickbars_total_volume = 0
        self.temp_TXF_MXF_TR = 0
        self.temp_tickbars_avg_price = 0

        self.pre_TXF_MXF_avg_price = self.TXF_MXF_avg_price
        self.matchtime = 0
        self.group_size = 0

    # ─────────────────────────────────────────────────────────────────────
    # 時間轉換工具
    # ─────────────────────────────────────────────────────────────────────
    def parse_time_string(self, time_string: str) -> Tuple[int, int, int, int]:
        """'HHMMSSmmm' → (hours, minutes, seconds, milliseconds)"""
        hours = int(time_string[:2])
        minutes = int(time_string[2:4])
        seconds = int(time_string[4:6])
        milliseconds = int(time_string[6:9])
        return hours, minutes, seconds, milliseconds

    def to_total_milliseconds(self, hours: int, minutes: int, seconds: int, milliseconds: int) -> int:
        """時間四元組 → 總毫秒"""
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds

    # ─────────────────────────────────────────────────────────────────────
    # 聚合與驅動（每當 TolMatchQty 成長）
    # ─────────────────────────────────────────────────────────────────────
    def calculate_time(
        self,
        database: Dict[str, float],
        RefPri: str, HighPri: str, LowPri: str,
        MatchQty: str, TolMatchQty: str, MatchTime: str, Is_simulation: bool
    ) -> None:
        """
        當某商品（TXF / MXF）的累計成交量成長：
        1) 累積 total_volume / current_total_volume / match_pri。
        2) 將 'HHMMSSmmm' 的 MatchTime 轉為毫秒並加總到 self.matchtime。
        3) 更新日內 high / low。
        4) 推進「交易時段總均價」並呼叫 calculate_tickbars() 以更新畫面與訊號。
        """
        if not database:
            database["current_total_volume"] = float(TolMatchQty)
            database["total_volume"] = float(MatchQty)
            database["match_pri"] = self.new_price
            h1, m1, s1, ms1 = self.parse_time_string(MatchTime)
            database["pre_matchtime"] = self.to_total_milliseconds(h1, m1, s1, ms1)

            if self.highest_price == 0 or self.lowest_price == 0:
                self.highest_price = int(HighPri)
                self.lowest_price = int(LowPri)
            else:
                if int(HighPri) > self.highest_price:
                    self.highest_price = int(HighPri)
                if int(LowPri) < self.lowest_price:
                    self.lowest_price = int(LowPri)

            self.calc_avg_price()
        elif database["current_total_volume"] < float(TolMatchQty):
            self.group_size += 1
            database["current_total_volume"] = float(TolMatchQty)
            database["total_volume"] += float(MatchQty)
            database["match_pri"] = self.new_price

            h1, m1, s1, ms1 = self.parse_time_string(MatchTime)
            temp_matchtime = self.to_total_milliseconds(h1, m1, s1, ms1)
            tol_matchtime = abs(temp_matchtime - database["pre_matchtime"])
            if tol_matchtime < 50000000:  # 過濾隔夜值 23:59:59.999 ~ 00:00:00.000
                self.matchtime += tol_matchtime
            database["pre_matchtime"] = temp_matchtime

            self.calc_avg_price()
            self.calculate_tickbars(MatchTime, Is_simulation)

    def calc_avg_price(self) -> None:
        """
        以「成交價值」除以「加權總量」得到交易時段總均價：
        - TR = new_price * tmp_qty
        - 加總到 self.TXF_MXF_tol_value
        - 分母 = TXF.total_volume*4 + MXF.total_volume*1
        """
        TR = self.new_price * self.tmp_qty
        self.TXF_MXF_tol_value += TR
        if self.TXF_database and self.MXF_database:
            self.TXF_MXF_avg_price = self.TXF_MXF_tol_value / (
                self.TXF_database["total_volume"] * 4 + self.MXF_database["total_volume"]
            )

    # ─────────────────────────────────────────────────────────────────────
    # 示範：手動設定進出（保留原印出行為）
    # ─────────────────────────────────────────────────────────────────────
    def handle_entry_signal(self, MatchTime: str, Is_simulation: bool) -> None:
        """
        當已跌破關鍵K低點 or 已突破關鍵K高點,是要等反彈或回檔或追價。

        參數：
        - MatchTime (str): 記錄當時的時間。

        注意：此函式沿用舊版的印出訊息與 self.short_signal 結構（示範用途）。
        """
        self.Index = -1
        self.short_signal["order_time"] = MatchTime
        self.short_signal["order_price"] = self.temp_big_value
        self.short_signal["profit_stop_price"] = 42-self.profit
        self.entry_price = self.new_price
        self.count += 1
        print(
            f'{Fore.CYAN}{Style.BRIGHT}第 {self.count} 筆  空   {self.short_signal["order_time"]}  出場價: {int(self.temp_big_value)}  進場價: {int(self.entry_price)} {Style.RESET_ALL}')

    def handle_short_exit(self, MatchTime: str) -> None:
        """示範性地結算一筆空單並印出損益（保留原字串）。"""
        self.entry_signal = False
        self.Index = 0
        self.profit += (self.entry_price-self.new_price-2)
        print(
            f'{Fore.YELLOW}{Style.BRIGHT}第 {self.count} 筆 出場  {MatchTime}  出場價: {self.new_price}  損益: {self.profit}{Style.RESET_ALL}')

    # ─────────────────────────────────────────────────────────────────────
    # 高低點追蹤（組內）
    # ─────────────────────────────────────────────────────────────────────
    def execute_compare(self, database: Dict, MatchTime: str, value: float) -> None:
        """
        在「本組」範圍內更新 big/small 值與其時間戳，並設定方向旗標 up/down。
        - 第一次見到 value：初始化 big=small=value。
        - 之後：只要創高就 up=True, down=False；創低則反之。
        """
        if not database and value != 0:
            database["big_value"] = value
            database["small_value"] = value
            database["big_value_time"] = float(MatchTime)
            database["small_value_time"] = float(MatchTime)
            database["up"] = False
            database["down"] = False
        elif database and value > database["big_value"]:
            database["big_value"] = value
            database["big_value_time"] = float(MatchTime)
            database["up"] = True
            database["down"] = False
        elif database and value < database["small_value"]:
            database["small_value"] = value
            database["small_value_time"] = float(MatchTime)
            database["up"] = False
            database["down"] = True

    # ─────────────────────────────────────────────────────────────────────
    # 盤中資訊刷新（費波那契、投資建議、最高/最低/價差等顯示）
    # ─────────────────────────────────────────────────────────────────────
    def calculate_and_update(self) -> None:
        """
        由外部定時呼叫以更新 GUI 顯示（最高、最低、壓力/支撐偏移、費波那契價位與操作建議）。
        - 當 self.temp_entry_price 有值時才推算費波那契價位，並同步到 fibonacciGrid。
        - 依 trending_up / trending_down 設定 infoDataGrid(0,5) 的操作傾向。
        """
        try:
            self.frame.infoDataGrid.SetCellValue(0, 0, str(int(self.highest_price)))
            self.frame.infoDataGrid.SetCellValue(0, 1, str(int(self.lowest_price)))
            self.frame.infoDataGrid.SetCellTextColour(0, 0, wx.RED)
            self.frame.infoDataGrid.SetCellTextColour(0, 1, wx.GREEN)

            if self.temp_entry_price > 0:
                if int(self.frame.avgPrice.GetValue()) > 0:
                    XF_avg_price = int(self.frame.avgPrice.GetValue())
                else:
                    XF_avg_price = int(self.TXF_MXF_avg_price)

                pressureNum = int(self.highest_price)
                supportNum = int(self.lowest_price)
                pressure_support_keypri = XF_avg_price
                pressure_diff = pressureNum - pressure_support_keypri  # 高 - 均
                self.frame.infoDataGrid.SetCellValue(0, 2, str(int(pressure_diff)))
                self.frame.infoDataGrid.SetCellTextColour(0, 2, wx.GREEN)
                support_diff = pressure_support_keypri - supportNum      # 均 - 低
                self.frame.infoDataGrid.SetCellValue(0, 3, str(int(support_diff)))
                self.frame.infoDataGrid.SetCellTextColour(0, 3, wx.RED)
                diffNum = pressureNum - supportNum
                self.frame.infoDataGrid.SetCellValue(0, 4, str(int(diffNum)))

                # —— 計算五個費波位（四捨五入到整數）——
                pressureNum_ratio_236 = round(pressure_support_keypri + pressure_diff * 0.236)
                pressureNum_ratio_382 = round(pressure_support_keypri + pressure_diff * 0.382)
                pressureNum_ratio_5   = round(pressure_support_keypri + pressure_diff * 0.5)
                pressureNum_ratio_618 = round(pressure_support_keypri + pressure_diff * 0.618)
                pressureNum_ratio_786 = round(pressure_support_keypri + pressure_diff * 0.786)

                supportNum_ratio_236 = round(pressure_support_keypri - (support_diff * 0.236))
                supportNum_ratio_382 = round(pressure_support_keypri - (support_diff * 0.382))
                supportNum_ratio_5   = round(pressure_support_keypri - (support_diff * 0.5))
                supportNum_ratio_618 = round(pressure_support_keypri - (support_diff * 0.618))
                supportNum_ratio_786 = round(pressure_support_keypri - (support_diff * 0.786))

                self.fibonacci_sell_str = f"{pressureNum_ratio_236} : {pressureNum_ratio_382} : {pressureNum_ratio_5} : {pressureNum_ratio_618} : {pressureNum_ratio_786}"
                self.fibonacci_buy_str  = f"{supportNum_ratio_236} : {supportNum_ratio_382} : {supportNum_ratio_5} : {supportNum_ratio_618} : {supportNum_ratio_786}"

                self.frame.fibonacciGrid.SetCellValue(0, 0, str(pressureNum_ratio_236))
                self.frame.fibonacciGrid.SetCellValue(0, 1, str(pressureNum_ratio_382))
                self.frame.fibonacciGrid.SetCellValue(0, 2, str(pressureNum_ratio_5))
                self.frame.fibonacciGrid.SetCellValue(0, 3, str(pressureNum_ratio_618))
                self.frame.fibonacciGrid.SetCellValue(0, 4, str(pressureNum_ratio_786))

                self.frame.fibonacciGrid.SetCellValue(1, 0, str(supportNum_ratio_236))
                self.frame.fibonacciGrid.SetCellValue(1, 1, str(supportNum_ratio_382))
                self.frame.fibonacciGrid.SetCellValue(1, 2, str(supportNum_ratio_5))
                self.frame.fibonacciGrid.SetCellValue(1, 3, str(supportNum_ratio_618))
                self.frame.fibonacciGrid.SetCellValue(1, 4, str(supportNum_ratio_786))

                # 操作建議
                if self.trending_down:
                    self.frame.infoDataGrid.SetCellTextColour(0, 5, wx.GREEN)
                    self.frame.infoDataGrid.SetCellValue(0, 5, "偏空操作")
                elif self.trending_up:
                    self.frame.infoDataGrid.SetCellTextColour(0, 5, wx.RED)
                    self.frame.infoDataGrid.SetCellValue(0, 5, "偏多操作")
                else:
                    self.frame.infoDataGrid.SetCellTextColour(0, 5, wx.WHITE)
                    self.frame.infoDataGrid.SetCellValue(0, 5, "觀望")

        except ValueError:
            pass
        except ZeroDivisionError:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # Telegram 推播
    # ─────────────────────────────────────────────────────────────────────
    def telegram_bot_sendtext(self, bot_message: str) -> None:
        """
        以 Telegram Bot 傳送文字訊息（保留原硬編 Token 與 chat_id；若需安全請自行改為環境變數）。
        """
        TOKEN = "8341950229:AAHw3h_p0Bnf_KcS5Mr4x3cOpIKHeFACiBs"
        chat_id = "8485648973"
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": bot_message}
        requests.post(url, data=payload)

    # ─────────────────────────────────────────────────────────────────────
    # （保留）外部觸發範例
    # ─────────────────────────────────────────────────────────────────────
    def trigger_short_signal(self) -> None:
        side = "S"
        symbol = "MXFK5"
        price = "31238"
        threading.Thread(
            target=self.bot.auto_send_order,
            args=(symbol, side, price),
            daemon=True
        ).start()

    def trigger_long_signal(self) -> None:
        bot_message = "進場多: TXF"
        print(bot_message)
        if self.frame.isSMS:
            print("發送Telegram通知...")
            side = "BUY"
            symbol = "TXF"
            lots = int(self.frame.lots_combo)
            threading.Thread(
                target=self.bot.auto_send_order,
                args=(self.frame.bot.Yuanta, symbol, side, lots),
                daemon=True
            ).start()


class RedirectText:
    """
    將 print() 文字（含 colorama 控制碼）繪製到 wx.TextCtrl：
    - 解析 ANSI-like 片段，對應前景/背景/粗體，再 AppendText。
    - 字體大小固定在 12（可依需求調整）。
    """
    def __init__(self, text_ctrl):
        self.out = text_ctrl  # 目標 wx.TextCtrl

    def write(self, message: str) -> None:
        tokens = re.split(r'(\x1b\[.*?m)', message)
        self._draw_segments(tokens)

    def _draw_segments(self, segments: List[str]) -> None:
        fg = wx.WHITE
        bg = wx.BLACK
        bold = False

        for seg in segments:
            # 偵測 colorama 控制碼
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

            # 設定字型與樣式（字體大小可在此調整）
            style = wx.TextAttr(fg, bg)
            style.SetFont(wx.Font(
                12,  # 字體大小（維持與原版一致）
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
            ))

            self.out.SetDefaultStyle(style)
            self.out.AppendText(seg)

        self.out.ShowPosition(self.out.GetLastPosition())

    def flush(self) -> None:
        pass
