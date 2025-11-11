"""
strategy_core.py
----------------
TradingStrategy 主體：接收 tick、計算均價、產生訊號，並呼叫 OrderManager/Notifier/UIUpdater。
"""

import sys
import threading
import datetime
from typing import Dict

import wx
from colorama import Fore, Style , Back

from .calculator import parse_time_string, to_ms, calc_fibonacci_levels
from .notifier import Notifier, RedirectText
from .ui_updater import UIUpdater
from .order_manager import OrderManager


class TradingStrategy:
    """
    策略核心類別：
    - execate_TXF_MXF(): 外部丟 tick 進來的入口
    - calculate_time(): 管理成交量與時間累積
    - calculate_tickbars(): 控制 tickbars 與訊號產生
    - show_tickbars(): 依原始邏輯判斷疑似頭部/底部並呼叫 enter_trade()
    """
    def __init__(self, frame):
        self.frame = frame

        # 將 stdout/stderr 導入 GUI 終端視窗
        sys.stdout = RedirectText(self.frame.monitorTradeSignal)
        sys.stderr = RedirectText(self.frame.monitorTradeSignal)

        # 通知/畫面/下單管理物件
        self.notifier = Notifier(
            frame=self.frame,
            telegram_token="8341950229:AAHw3h_p0Bnf_KcS5Mr4x3cOpIKHeFACiBs",
            telegram_chat_id="8485648973",
        )
        self.ui = UIUpdater(self.frame)
        self.order = OrderManager(self.frame, self.ui, self.notifier)

        self.notifier.log(
            "✅ TradingStrategy 初始化完成",
            Fore.GREEN + Style.BRIGHT
        )

        # ===== 狀態變數 =====

        # 商品資料庫（累積量與時間）
        self.TXF_database: Dict = {}
        self.MXF_database: Dict = {}

        # 合併均價
        self.TXF_MXF_tol_value: float = 0.0
        self.TXF_MXF_avg_price: float = 0.0
        self.pre_TXF_MXF_avg_price: float = 0.0

        # 日內高低價
        self.highest_price: int = 0
        self.lowest_price: int = 0
        self.previous_highest_price: int = 0
        self.previous_lowest_price: int = 0
        self.is_dayhigh: bool = True
        self.is_daylow: bool = True

        # group 與時間
        self.matchtime: int = 0           # 累積毫秒
        self.group_size: int = 0          # 當前區間內 tick 數
        self.tmp_qty: float = 0.0         # 本筆口數(含TXF*4)
        self.new_price: float = 0.0       # 本筆價格

        # tickbars 暫存
        self.list_close_price = []
        self.list_tickbars_tol_time = []
        self.list_temp_tickbars_total_volume = []
        self.list_temp_tickbars_big_price = []
        self.list_temp_tickbars_small_price = []
        self.list_temp_tickbars_avg_price = []

        # 區間比較資料
        self.temp_price_compare_database: Dict = {}
        self.temp_tickbars_total_volume: float = 0.0
        self.temp_TXF_MXF_TR: float = 0.0
        self.temp_tickbars_avg_price: float = 0.0

        # 然而平均（高/低）
        self.temp_howeverHighest_total_volume: float = 0.0
        self.temp_TXF_MXF_howeverHighest: float = 0.0
        self.temp_howeverHighest_avg_price: float = 0.0

        self.temp_howeverLowest_total_volume: float = 0.0
        self.temp_TXF_MXF_howeverLowest: float = 0.0
        self.temp_howeverLowest_avg_price: float = 0.0

        # 趨勢
        self.trending_up: bool = False
        self.trending_down: bool = False
        self.pre_ATR: float = 0.0  # 這裡當作均價前值使用

        # Fibonacci 文字
        self.fibonacci_sell_str: str = ""
        self.fibonacci_buy_str: str = ""

        # 疑似頭部/底部旗標
        self.suspected_sell: bool = False
        self.suspected_buy: bool = False

        # 舊版相容：給 YuantaOrdAPI.OnChkDeal 用的費波字串
        # 代表「當前多單/空單採用的那組 fibonacci 價格」
        self.fibonacci_chkBuy_str: str = "0"
        self.fibonacci_chkSell_str: str = "0"

    # ===== 舊版相容屬性 =====
    @property
    def trading_buy(self):
        return self.order.trading_buy

    @trading_buy.setter
    def trading_buy(self, v):
        self.order.trading_buy = v

    @property
    def trading_sell(self):
        return self.order.trading_sell

    @trading_sell.setter
    def trading_sell(self, v):
        self.order.trading_sell = v

    # ===== 舊版相容方法 =====
    def telegram_bot_sendtext(self, msg: str):
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
                        Is_simulation):
        """
        外部呼叫：逐筆 TXF/MXF tick 進來。
        """
        if "XF" in symbol:
            self.tmp_qty = 0
            self.new_price = float(MatchPri)

        if "TXF" in symbol:
            self.tmp_qty = 4 * float(MatchQty)
            self.calculate_time(
                self.TXF_database,
                RefPri, HighPri, LowPri,
                MatchQty, TolMatchQty, MatchTime, Is_simulation
            )
        elif "MXF" in symbol:
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
                       Is_simulation):
        """
        管理 TXF/MXF 個別商品的成交量與時間累積，並在有新量時觸發 calculate_tickbars。
        """
        if not database:
            database["current_total_volume"] = float(TolMatchQty)
            database["total_volume"] = float(MatchQty)
            database["match_pri"] = self.new_price

            h, m, s, ms = parse_time_string(MatchTime)
            database["pre_matchtime"] = to_ms(h, m, s, ms)

            hp = int(HighPri)
            lp = int(LowPri)
            if self.highest_price == 0 or hp > self.highest_price:
                self.highest_price = hp
            if self.lowest_price == 0 or lp < self.lowest_price:
                self.lowest_price = lp

            self.calc_avg_price()

        elif database["current_total_volume"] < float(TolMatchQty):
            self.group_size += 1
            database["current_total_volume"] = float(TolMatchQty)
            database["total_volume"] += float(MatchQty)
            database["match_pri"] = self.new_price

            h, m, s, ms = parse_time_string(MatchTime)
            now_ms = to_ms(h, m, s, ms)
            diff = abs(now_ms - database["pre_matchtime"])
            if diff < 50000000:
                self.matchtime += diff
            database["pre_matchtime"] = now_ms

            self.calc_avg_price()
            self.calculate_tickbars(MatchTime, Is_simulation)

    def calc_avg_price(self):
        """計算 TXF+MXF 加權均價。"""
        TR = self.new_price * self.tmp_qty
        self.TXF_MXF_tol_value += TR
        if self.TXF_database and self.MXF_database:
            total = (self.TXF_database["total_volume"] * 4 +
                     self.MXF_database["total_volume"])
            if total > 0:
                self.TXF_MXF_avg_price = self.TXF_MXF_tol_value / total

    # =========================================================
    # Tickbars 控制
    # =========================================================

    def calculate_tickbars(self, MatchTime: str, Is_simulation):
        """
        每有新成交量時呼叫：更新高低、方向、區間資訊，決定是否產生 tickbar。
        """
        # 日高創新高 → 處理空方止損 / 重置區間
        if self.highest_price < self.new_price:
            if self.order.sell_signal:
                self.order.exit_stoploss("空", int(self.new_price), MatchTime)
            self.highest_price = int(self.new_price)
            self.trending_up = True
            self.trending_down = False
            self._reset_temp_zone(high=True)

        # 日低創新低 → 處理多方止損 / 重置區間
        elif self.lowest_price > self.new_price:
            if self.order.buy_signal:
                self.order.exit_stoploss("多", int(self.new_price), MatchTime)
            self.lowest_price = int(self.new_price)
            self.trending_up = False
            self.trending_down = True
            self._reset_temp_zone(high=False)

        # 均價 vs 現價箭頭
        up_down_str = ""
        if self.TXF_database and self.MXF_database:
            if self.new_price > self.TXF_MXF_avg_price:
                up_down_str = "↑"
                self.frame.compareInfoGrid.SetCellTextColour(1, 5, wx.RED)
            elif self.new_price < self.TXF_MXF_avg_price:
                up_down_str = "↓"
                self.frame.compareInfoGrid.SetCellTextColour(1, 5, wx.GREEN)

        # 趨勢轉折判斷
        if (
            (self.trending_up and self.pre_ATR > self.TXF_MXF_avg_price) or
            (self.trending_down and self.pre_ATR < self.TXF_MXF_avg_price)
        ) and self.temp_price_compare_database:
            self.trending_up = False
            self.trending_down = False

        self.pre_ATR = self.TXF_MXF_avg_price

        # 組時間字串
        if self.matchtime != 0:
            diff_ms = abs(self.matchtime)
            tol_time = diff_ms
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

        # 更新區間高低資料
        self.execute_compare(self.temp_price_compare_database,
                             MatchTime,
                             self.new_price)
       
        # 累積區間成交量
        self.temp_tickbars_total_volume += self.tmp_qty
        self.temp_TXF_MXF_TR += (self.new_price * self.tmp_qty)
        if self.temp_tickbars_total_volume > 0:
            self.temp_tickbars_avg_price = (
                self.temp_TXF_MXF_TR / self.temp_tickbars_total_volume
            )
        
        self.ui.update_compare_on_tick(
                    avg_price=self.TXF_MXF_avg_price,
                    new_price=self.new_price,
                    up_down=up_down_str,
                    tol_time_str=tol_time_str,
                    group_size=self.group_size,
                    temp_db=self.temp_price_compare_database,
                    temp_total_volume=self.temp_tickbars_total_volume ,
                    temp_avg_price= self.temp_tickbars_avg_price
                )


        # 累積「然而平均」
        if not self.order.sell_signal:
            self._accumulate_however_high()
        if not self.order.buy_signal:
            self._accumulate_however_low()

        # group 門檻檢查
        try:
            threshold = int(self.frame.compareInfoGrid.GetCellValue(0, 6))
        except ValueError:
            threshold = 1000

        if self.group_size >= threshold:
            self.show_tickbars(MatchTime, tol_time, tol_time_str)

        # 檢查移動停利
        self.order.update_trailing_profit(self.new_price)

        # 更新 Fibonacci 與建議
        self.calculate_and_update()

        # ✅ 每筆 tick 都檢查是否觸發真實進場（依據先前 1000 筆產生的訊號）
        self.check_entry_on_tick(MatchTime)

    # =========================================================
    # 每筆 tick 依據訊號檢查是否觸發真實進場
    # =========================================================
    def check_entry_on_tick(self, MatchTime: str):
        """
        每筆 tick 檢查是否達到先前 signal_trade 設定的進場價，決定是否執行 execute_trade。
        - 放空：價格 >= entry_price_sell 且尚未有空單部位
        - 作多：價格 <= entry_price_buy 且尚未有多單部位
        """
        price = int(self.new_price)

        # 放空：等反彈到預設放空價（含）以上
        # 「如果當前有放空訊號 (sell_signal == True)，並且目前沒有放空持倉 (trading_sell == False)，那就執行下面的放空邏輯。」
        if getattr(self.order, "sell_signal", False) and not getattr(self.order, "trading_sell", False):
            entry = int(getattr(self.order, "entry_price_sell", 0) or 0)
            if entry > 0 and price >= entry:
                self.notifier.log(
                    f"{MatchTime}  放空觸價成交 現價:{price}  觸發價:{entry}",
                    Fore.GREEN + Style.BRIGHT
                )
                if hasattr(self.order, "execute_trade"):
                    self.order.execute_trade(
                        direction="空",
                        entry_price=entry,
                        match_time=MatchTime,
                    )

        # 作多：等回檔到預設作多價（含）以下
        if getattr(self.order, "buy_signal", False) and not getattr(self.order, "trading_buy", False):
            entry = int(getattr(self.order, "entry_price_buy", 0) or 0)
            if entry > 0 and price <= entry:
                self.notifier.log(
                    f"{MatchTime}  作多觸價成交 現價:{price}  觸發價:{entry}",
                    Fore.RED + Style.BRIGHT
                )
                if hasattr(self.order, "execute_trade"):
                    self.order.execute_trade(
                        direction="多",
                        entry_price=entry,
                        match_time=MatchTime,
                    )

    # =========================================================
    # show_tickbars：每根 tickbar(如 1000 筆) 完成時產生進場訊號
    # =========================================================

    def show_tickbars(self, MatchTime, tol_time, tol_time_str):
        """
        一根 tickbar 成形時的邏輯（原始版移植）：
        - 更新列表
        - 判斷速度、量能、日高日低
        - 符合條件時設定 suspected_sell/buy
        - 符合更嚴格條件時呼叫 OrderManager.enter_trade() 進場
        - 最後呼叫 print_trade_info() 印出結果
        """
        temp = ""
        mark_temp_big_price_num = 0
        mark_temp_small_price_num = 0
        mark_temp_total_volume_num = 0
        mark_speedtime_num = 0

        mark_tol_time_color = "Style.RESET_ALL"
        mark_temp_highest_arrow_color = "Style.RESET_ALL"
        mark_temp_lowest_arrow_color = "Style.RESET_ALL"
        mark_temp_big_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_small_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_close_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_compare_avg_price_color = "Fore.YELLOW + Style.BRIGHT"

        # 收盤 / 量 / 均價列表更新
        self.list_close_price.append(self.new_price)
        self.list_temp_tickbars_total_volume.append(self.temp_tickbars_total_volume)
        self.list_temp_tickbars_avg_price.append(int(self.temp_tickbars_avg_price))

        self.frame.compareInfoGrid.SetCellValue(0, 3, str(int(self.temp_tickbars_total_volume)))
        self.frame.compareInfoGrid.SetCellValue(0, 4, str(int(self.temp_tickbars_avg_price)))

        self.list_tickbars_tol_time.append(tol_time)
        self.frame.compareInfoGrid.SetCellValue(0, 2, tol_time_str)

        # 高低價來源：有區間資料用區間，否則用現價
        if self.temp_price_compare_database:
            self.list_temp_tickbars_big_price.append(self.temp_price_compare_database['big_value'])
            self.list_temp_tickbars_small_price.append(self.temp_price_compare_database['small_value'])
        else:
            self.list_temp_tickbars_big_price.append(self.new_price)
            self.list_temp_tickbars_small_price.append(self.new_price)

        # 箭頭判斷
        temp_highest_arrow = "．"
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

        self.previous_highest_price = self.highest_price
        self.previous_lowest_price = self.lowest_price

        # 更新 compare 高低列
        self.frame.compareInfoGrid.SetCellTextColour(0, 0, wx.RED)
        self.frame.compareInfoGrid.SetCellTextColour(0, 1, wx.GREEN)
        self.frame.compareInfoGrid.SetCellValue(
            0, 0, f"{int(self.list_temp_tickbars_big_price[-1])}  {temp_highest_arrow}"
        )
        self.frame.compareInfoGrid.SetCellValue(
            0, 1, f"{int(self.list_temp_tickbars_small_price[-1])}  {temp_lowest_arrow}"
        )

        # 更新日高日低旗標
        if (len(self.list_temp_tickbars_big_price) > 1 and
                self.list_temp_tickbars_big_price[-1] == self.highest_price):
            self.is_dayhigh = True
        if (len(self.list_temp_tickbars_small_price) > 1 and
                self.list_temp_tickbars_small_price[-1] == self.lowest_price):
            self.is_daylow = True

        # tickbar 高價漲跌
        if len(self.list_temp_tickbars_big_price) > 1:
            if self.list_temp_tickbars_big_price[-2] >= self.list_temp_tickbars_big_price[-1]:
                mark_temp_big_price_num = 1
            elif self.list_temp_tickbars_big_price[-2] < self.list_temp_tickbars_big_price[-1]:
                mark_temp_big_price_num = 2

        # tickbar 低價漲跌
        if len(self.list_temp_tickbars_small_price) > 1:
            if self.list_temp_tickbars_small_price[-2] > self.list_temp_tickbars_small_price[-1]:
                mark_temp_small_price_num = 1
            elif self.list_temp_tickbars_small_price[-2] <= self.list_temp_tickbars_small_price[-1]:
                mark_temp_small_price_num = 2

        # tickbar 成交量增減
        if len(self.list_temp_tickbars_total_volume) > 1 and self.list_temp_tickbars_total_volume[-2] < self.list_temp_tickbars_total_volume[-1]:
            mark_temp_total_volume_num = 1

        # 時間快慢 + 量增 + 箭頭 → 速度判斷
        if len(self.list_tickbars_tol_time) > 1:
            prev_t = self.list_tickbars_tol_time[-2]
            curr_t = self.list_tickbars_tol_time[-1]

            if prev_t / 2 > curr_t and mark_temp_total_volume_num == 1 and temp_highest_arrow == "↓":
                mark_tol_time_color = "Fore.BLACK + Back.WHITE"
            if prev_t / 2 > curr_t and mark_temp_total_volume_num == 1 and temp_lowest_arrow == "↑":
                mark_tol_time_color = "Fore.BLACK + Back.WHITE"

            if prev_t > curr_t and mark_temp_total_volume_num == 1 and temp_highest_arrow == "↓":
                mark_temp_highest_arrow_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"
                mark_speedtime_num = 1

            if prev_t > curr_t and mark_temp_total_volume_num == 1 and temp_lowest_arrow == "↑":
                mark_temp_lowest_arrow_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"
                mark_speedtime_num = 1

        # 若速度條件成立 → 設定疑似頭部/底部
        if mark_speedtime_num == 1:
            if self.is_dayhigh and temp_highest_arrow == "↓":
                self.is_dayhigh = False
                self.suspected_sell = True
            elif self.is_daylow and temp_lowest_arrow == "↑":
                self.is_daylow = False
                self.suspected_buy = True

            # 放空進場訊號：作空等反彈，使用 Fibonacci 第四階 (sell_levels[3]) 作為預設進場價
            sell_levels = [s.strip() for s in self.fibonacci_sell_str.split(":") if s.strip().isdigit()]
            if (
                self.suspected_sell
                and temp_highest_arrow == "↓"
                and len(sell_levels) > 3
                and int(sell_levels[1]) > self.temp_howeverHighest_avg_price
                and not getattr(self.order, "trading_sell", False)
            ):
                mark_temp_close_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
                mark_temp_big_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
                entry_price =  int(self.list_close_price[-1])
                trigger_price = int(sell_levels[3])
                if hasattr(self.order, "signal_trade"):
                    temp = self.order.signal_trade(
                        direction="空",
                        entry_price=entry_price,
                        trigger_price= trigger_price,
                        stop_loss=self.highest_price + 1,
                        fibonacci_str=self.fibonacci_sell_str,
                        match_time=MatchTime,
                    )
                self.fibonacci_chkSell_str = self.fibonacci_sell_str
                self.suspected_sell = False

            # 作多進場訊號：作多等回檔，使用 Fibonacci 第四階 (buy_levels[3]) 作為預設進場價
            buy_levels = [s.strip() for s in self.fibonacci_buy_str.split(":") if s.strip().isdigit()]
            if (
                self.suspected_buy
                and temp_lowest_arrow == "↑"
                and len(buy_levels) > 3
                and int(buy_levels[1]) < self.temp_howeverLowest_avg_price
                and not getattr(self.order, "trading_buy", False)
            ):
                mark_temp_close_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
                mark_temp_small_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
                entry_price =  int(self.list_close_price[-1])
                trigger_price = int(buy_levels[3])
                if hasattr(self.order, "signal_trade"):
                    temp = self.order.signal_trade(
                        direction="多",
                        entry_price=entry_price,
                        trigger_price= trigger_price,
                        stop_loss=self.lowest_price - 1,
                        fibonacci_str=self.fibonacci_buy_str,
                        match_time=MatchTime,
                    )
                self.fibonacci_chkBuy_str = self.fibonacci_buy_str
                self.suspected_buy = False

        # 依均價方向輸出完整資訊
        if self.pre_TXF_MXF_avg_price > self.TXF_MXF_avg_price and self.temp_price_compare_database:
            self.trending_up = False
            self.trending_down = True
            color_main = Fore.GREEN
            if temp in ["進場多", "進場空"]:
                trend_color = Fore.GREEN if temp == "進場空" else Fore.RED
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
            self.trending_up = True
            self.trending_down = False
            color_main = Fore.RED
            if temp in ["進場多", "進場空"]:
                trend_color = Fore.RED if temp == "進場多" else Fore.GREEN
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

        # reset 區間暫存
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

    def _reset_temp_zone(self, high: bool):
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
        else:
            self.temp_howeverLowest_total_volume = 0
            self.temp_TXF_MXF_howeverLowest = 0
            self.temp_howeverLowest_avg_price = 0

    def _accumulate_however_high(self):
        self.temp_howeverHighest_total_volume += self.tmp_qty
        self.temp_TXF_MXF_howeverHighest += (self.new_price * self.tmp_qty)
        if self.temp_howeverHighest_total_volume > 0:
            self.temp_howeverHighest_avg_price = (
                self.temp_TXF_MXF_howeverHighest /
                self.temp_howeverHighest_total_volume
            )

    def _accumulate_however_low(self):
        self.temp_howeverLowest_total_volume += self.tmp_qty
        self.temp_TXF_MXF_howeverLowest += (self.new_price * self.tmp_qty)
        if self.temp_howeverLowest_total_volume > 0:
            self.temp_howeverLowest_avg_price = (
                self.temp_TXF_MXF_howeverLowest /
                self.temp_howeverLowest_total_volume
            )

    def execute_compare(self, database: Dict, MatchTime: str, value: float):
        if not value:
            return
        if not database:
            database["big_value"] = value
            database["small_value"] = value
            database["big_value_time"] = float(MatchTime)
            database["small_value_time"] = float(MatchTime)
            database["up"] = False
            database["down"] = False
        elif value > database["big_value"]:
            database["big_value"] = value
            database["big_value_time"] = float(MatchTime)
            database["up"] = True
            database["down"] = False
        elif value < database["small_value"]:
            database["small_value"] = value
            database["small_value_time"] = float(MatchTime)
            database["up"] = False
            database["down"] = True

    def calculate_and_update(self):
        """更新 Fibonacci、infoDataGrid 與趨勢建議。"""
        try:
            if self.highest_price == 0 or self.lowest_price == 0:
                return
            if int(self.frame.avgPrice.GetValue()) > 0:
                keypri = int(self.frame.avgPrice.GetValue())
            else:
                keypri = int(self.TXF_MXF_avg_price)

            levels = calc_fibonacci_levels(
                high_price=self.highest_price,
                low_price=self.lowest_price,
                key_price=keypri
            )
            self.fibonacci_sell_str = " : ".join(str(v) for v in levels["sell"])
            self.fibonacci_buy_str = " : ".join(str(v) for v in levels["buy"])
            self.ui.update_fibonacci_grid(levels["sell"], levels["buy"])

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

            if self.trending_down:
                self.ui.update_trend_suggestion("空")
            elif self.trending_up:
                self.ui.update_trend_suggestion("多")
            else:
                self.ui.update_trend_suggestion("無")
        except Exception:
            pass

    # =========================================================
    # 統一輸出函式（沿用原始 print_trade_info 邏輯）
    # =========================================================

    def print_trade_info(self, MatchTime, temp, color_main, trend_color,
                         mark_tol_time_color, tol_time_str,
                         mark_temp_big_price_color, mark_temp_small_price_color,
                         mark_temp_highest_arrow_color, mark_temp_lowest_arrow_color,
                         mark_temp_close_price_color, mark_temp_compare_avg_price_color,
                         temp_highest_arrow, temp_lowest_arrow):
        """
        將 tickbar 資訊、價差、訊號等以彩色格式印出。
        完全保留原本輸出風格，以方便你觀察市場行為。
        """
        if not self.list_temp_tickbars_big_price or not self.list_temp_tickbars_small_price:
            return

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

        print((
            f"{color_main}{Style.BRIGHT}{MatchTime}  {avg_price}{Style.RESET_ALL}  "
            f"{eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  "
            f"{Fore.YELLOW}{Style.BRIGHT}{big:<5d}{Style.RESET_ALL} : "
            f"{Fore.YELLOW}{Style.BRIGHT}{small:<5d}{Style.RESET_ALL}  "
            f"{eval(mark_temp_highest_arrow_color)}{temp_highest_arrow}{Style.RESET_ALL}  "
            f"{eval(mark_temp_lowest_arrow_color)}{temp_lowest_arrow}{Style.RESET_ALL}  "
            f"{trend_color}{Style.BRIGHT}現:{Style.RESET_ALL}"
            f"{eval(mark_temp_close_price_color)} {newp}{Style.RESET_ALL}  "
            f"{Fore.YELLOW}{Style.BRIGHT}{vol:>5d} : "
            f"{eval(mark_temp_compare_avg_price_color)}{avg:<5d}{Style.RESET_ALL}  "
            f"{eval(mark_temp_big_price_color)}{hi_avg:<5d}{Style.RESET_ALL} : "
            f"{eval(mark_temp_small_price_color)}{lo_avg:<5d}{Style.RESET_ALL}  "
            f"高: {high}  低: {low}  {trend_color}{Style.BRIGHT}{temp}{Style.RESET_ALL}"
        ))

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
