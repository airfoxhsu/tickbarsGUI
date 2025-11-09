from encodings.punycode import T
from hmac import new
import re
import sys
import winsound
# import matplotlib.pyplot as plt
# import pandas as pd
from colorama import Fore, Style, init, Back
import tkinter as tk
import wx
import threading
import requests


class TradingStrategy:
    def __init__(self, frame) -> None:
        self.frame = frame
        sys.stdout = RedirectText(self.frame.monitorTradeSignal)
        sys.stderr = RedirectText(self.frame.monitorTradeSignal)
        print(Style.BRIGHT + Fore.GREEN + "✅ 成功訊息 (亮綠色)"
              + Fore.RED + Back.WHITE + "❌ 錯誤訊息 (紅字白底)"
              + Style.RESET_ALL)
        # print(Fore.CYAN + "🔷 額外測試：字體已放大、顏色可混用。")
        # print(Back.BLUE + Fore.YELLOW + Style.BRIGHT + "亮黃字 + 藍底測試" + Style.RESET_ALL)

        self.fibonacci_sell_str = ""
        self.fibonacci_buy_str = ""
        self.fibonacci_chkSell_str = "0"
        self.fibonacci_chkBuy_str = "0"
        self.profit_buy_str = ""
        self.profit_sell_str = ""
        self.total_spread = 0
        self.new_price = 0
        self.TXF_database = {}
        self.MXF_database = {}
        self.spread_compare_database = {}
        # self.price_compare_database = {}
        self.ohlc_database = {}
        self.long_signal = {}
        self.short_signal = {}
        self.Index = 0
        self.profit = 0
        self.is_dayhigh = True
        self.is_daylow = True

        self.TXF_MXF_tol_value = 0      # 大小台總價值
        self.TXF_MXF_avg_price = 0      # 大小台均價
        self.pre_TXF_MXF_avg_price = 0
        self.TRi = []
        self.ATR = 0
        self.trending_down = False
        self.trending_up = False
        self.pre_ATR = 0
        self.entry_signal = False
        self.entry_price_buy = 0     # 多單進場價
        self.entry_price_sell = 0    # 空單進場價
        # self.entry_price = 0
        self.temp_entry_price = 0
        self.temp_total_spread = 0
        self.warning_signal = False
        self.temp_ATR_up = False
        self.temp_ATR_down = False
        self.temp_price_compare_database = {}
        self.temp_big_value = 0
        self.temp_small_value = 0
        # self.temp_ATR_compare_database = {}
        self.highest_price = 0
        self.lowest_price = 0
        self.list_close_price = []                  # 每根tickbar的收盤價
        self.list_tickbars_tol_time = []            # 每根tickbar的總時間
        self.list_temp_tickbars_avg_price = []      # 每根tickbar的平均價
        self.list_temp_tickbars_big_price = []      # 每根tickbar的最高價
        self.list_temp_tickbars_small_price = []    # 每根tickbar的最低價
        self.list_temp_tickbars_total_volume = []   # 每根tickbar的總量
        self.previous_highest_price = 0      # 儲存上一根最高價
        self.previous_lowest_price = 0    # 儲存上一根最低價
        self.conform_total_volume = 0
        self.count = 0
        self.pre_matchtime = 0
        self.matchtime = 0
        self.group_size = 0
        self.time_diff = 0
        self.time_price_per = 0
        self.time_diff_str = "00:00:00.000"
        # self.up_down_str = ""
        self.list_signal_str = []
        self.trading_buy = False
        self.trading_sell = False
        self.stopLoss_sell = 0
        self.stopLoss_buy = 0
        # self.isPlaySound = True
        self.temp_tickbars_total_volume = 0
        self.temp_TXF_MXF_TR = 0
        self.temp_tickbars_avg_price = 0
        self.list_speedtime_big_price = []
        self.list_speedtime_small_price = []
        self.list_temp_up_down_str = []
        self.suspected_buy = False
        self.suspected_sell = False
        self.sell_signal = False
        self.buy_signal = False

        self.temp_howeverHighest_total_volume = 0
        self.temp_TXF_MXF_howeverHighest = 0
        self.temp_howeverHighest_avg_price = 0

        self.temp_howeverLowest_total_volume = 0
        self.temp_TXF_MXF_howeverLowest = 0
        self.temp_howeverLowest_avg_price = 0

    def execate_TXF_MXF(self, direction, symbol, RefPri, OpenPri, HighPri, LowPri, MatchTime, MatchPri, MatchQty, TolMatchQty, Is_simulation):
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

    def calculate_tickbars(self, MatchTime, Is_simulation):
        if self.highest_price < self.new_price:
            if self.trading_sell == True:
                if self.frame.acclist_combo.GetCount() != 0 and self.frame.chkSell.GetValue() == True:
                    val = self.frame.qtyLabel.GetLabel()
                    qty = int(val) if val.isdigit() else 0
                    if qty > 0:
                        self.frame.OnOrderBtn(
                            event=None, S_Buys="B", price=self.new_price, offset="1")
                        self.frame.qtyLabel.SetLabel("未連")
            if self.sell_signal == True:
                self.trading_sell = False
                self.sell_signal = False
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

            self.temp_howeverHighest_total_volume = 0
            self.temp_TXF_MXF_howeverHighest = 0
            self.temp_howeverHighest_avg_price = 0

        elif self.lowest_price > self.new_price:
            if self.trading_buy == True:
                if self.frame.acclist_combo.GetCount() != 0 and self.frame.chkBuy.GetValue() == True:
                    val = self.frame.qtyLabel.GetLabel()
                    qty = int(val) if val.isdigit() else 0
                    if qty > 0:
                        self.frame.OnOrderBtn(
                            event=None, S_Buys="S", price=self.new_price, offset="1")
                        self.frame.qtyLabel.SetLabel("未連")
            if self.buy_signal == True:
                self.trading_buy = False
                self.buy_signal = False
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
            
            self.temp_howeverLowest_total_volume = 0
            self.temp_TXF_MXF_howeverLowest = 0
            self.temp_howeverLowest_avg_price = 0

        up_down_str = ""
        # if self.price_compare_database and self.TXF_database:
        if self.TXF_database and self.MXF_database:
            if self.new_price > self.TXF_MXF_avg_price:
                up_down_str = "↑"
                self.frame.compareInfoGrid.SetCellTextColour(1, 5, wx.RED)
            elif self.new_price < self.TXF_MXF_avg_price:
                up_down_str = "↓"
                self.frame.compareInfoGrid.SetCellTextColour(1, 5, wx.GREEN)
            # self.real_atr_var.set(
            #     str(float(round(self.TXF_MXF_avg_price, 4)))+up_down_str)
            self.frame.compareInfoGrid.SetCellValue(
                0, 5, str(float(round(self.TXF_MXF_avg_price, 1))))
            self.frame.compareInfoGrid.SetCellValue(
                1, 5, str(int(self.new_price))+"  "+up_down_str)

            self.temp_entry_price = int(self.TXF_MXF_avg_price)

        # 趨勢原先向上,後轉為不明  #趨勢原先向下,後轉為不明
        if (self.trending_up and self.pre_ATR > self.TXF_MXF_avg_price) or (self.trending_down and self.pre_ATR < self.TXF_MXF_avg_price) and self.temp_price_compare_database:
            self.trending_up = False
            self.trending_down = False

        self.pre_ATR = self.TXF_MXF_avg_price
        if self.matchtime != 0:
            # 計算時間差
            diff_ms = abs(self.matchtime)
            tol_time = diff_ms
            # 將毫秒轉回時間格式
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
        # self.real_tickbars_tol_time_var.set(tol_time_str)
        self.frame.compareInfoGrid.SetCellValue(1, 2, tol_time_str)
        self.execute_compare(
            self.temp_price_compare_database, MatchTime, value=self.new_price)

        temp_up_down_str = ""
        if self.temp_price_compare_database['up']:
            temp_up_down_str = "↑"
        elif self.temp_price_compare_database['down']:
            temp_up_down_str = "↓"
        # self.a_var.set(str(int(self.temp_price_compare_database['big_value'])))
        # self.b_var.set(
        #     str(int(self.temp_price_compare_database['small_value']))+"  "+temp_up_down_str)
        self.frame.compareInfoGrid.SetCellTextColour(1, 0, wx.RED)
        self.frame.compareInfoGrid.SetCellTextColour(1, 1, wx.GREEN)
        self.frame.compareInfoGrid.SetCellValue(
            1, 0, str(int(self.temp_price_compare_database['big_value'])))
        self.frame.compareInfoGrid.SetCellValue(1, 1, str(
            int(self.temp_price_compare_database['small_value']))+"  "+temp_up_down_str)
        self.frame.compareInfoGrid.SetCellValue(1, 6, str(self.group_size))

        self.temp_tickbars_total_volume += self.tmp_qty
        self.temp_TXF_MXF_TR += (self.new_price * self.tmp_qty)
        self.temp_tickbars_avg_price = self.temp_TXF_MXF_TR / \
            (self.temp_tickbars_total_volume)
       
        if self.sell_signal == False:
            self.temp_howeverHighest_total_volume += self.tmp_qty
            self.temp_TXF_MXF_howeverHighest += (self.new_price * self.tmp_qty)
            self.temp_howeverHighest_avg_price = self.temp_TXF_MXF_howeverHighest / \
                (self.temp_howeverHighest_total_volume)

        if self.buy_signal == False:
            self.temp_howeverLowest_total_volume += self.tmp_qty
            self.temp_TXF_MXF_howeverLowest += (self.new_price * self.tmp_qty)
            self.temp_howeverLowest_avg_price = self.temp_TXF_MXF_howeverLowest / \
                (self.temp_howeverLowest_total_volume)

        self.frame.compareInfoGrid.SetCellValue(
            1, 3, str(int(self.temp_tickbars_total_volume)))
        self.frame.compareInfoGrid.SetCellValue(
            1, 4, str(int(self.temp_tickbars_avg_price)))

        value = int(self.frame.compareInfoGrid.GetCellValue(0, 6))

        if self.group_size >= value:
            self.show_tickbars(MatchTime, tol_time, tol_time_str)

            # === [新增] 即時停利判斷 ===
        # def _parse_profit_triplet(s):
        #     try:
        #         parts = [int(x.strip()) for x in s.split(":") if x.strip().isdigit()]
        #         if len(parts) >= 3:
        #             return parts[0], parts[1], parts[2]
        #     except Exception:
        #         pass
        #     return None, None, None

        # # 空單移動停利邏輯
        # if self.trading_sell:
        #     p1, p2, p3 = _parse_profit_triplet(self.profit_sell_str)
        #     if p1 and p2 and p3 and self.entry_price_sell:
        #         if self.new_price <= p1 and self.stopLoss_sell > self.entry_price_sell:
        #             self.stopLoss_sell = self.entry_price_sell
        #             print(Fore.CYAN + f"🟢 空單觸及 profit_1 → 停損改至進場價 {self.stopLoss_sell}" + Style.RESET_ALL)
        #         elif self.new_price <= p2 and self.stopLoss_sell > p1:
        #             self.stopLoss_sell = p1
        #             print(Fore.CYAN + f"🟢 空單觸及 profit_2 → 停損改至 {self.stopLoss_sell}" + Style.RESET_ALL)
        #         elif self.new_price <= p3:
        #             print(Fore.MAGENTA + f"🏁 空單觸及 profit_3 → 平倉 {self.new_price}" + Style.RESET_ALL)
        #             self.frame.OnOrderBtn(event=None, S_Buys="B", price=self.new_price, offset="1")
        #             self.trading_sell = False
        #             self.sell_signal = False

        # # 多單移動停利邏輯
        # elif self.trading_buy:
        #     p1, p2, p3 = _parse_profit_triplet(self.profit_buy_str)
        #     if p1 and p2 and p3 and self.entry_price_buy:
        #         if self.new_price >= p1 and self.stopLoss_buy < self.entry_price_buy:
        #             self.stopLoss_buy = self.entry_price_buy
        #             print(Fore.CYAN + f"🟢 多單觸及 profit_1 → 停損改至進場價 {self.stopLoss_buy}" + Style.RESET_ALL)
        #         elif self.new_price >= p2 and self.stopLoss_buy < p1:
        #             self.stopLoss_buy = p1
        #             print(Fore.CYAN + f"🟢 多單觸及 profit_2 → 停損改至 {self.stopLoss_buy}" + Style.RESET_ALL)
        #         elif self.new_price >= p3:
        #             print(Fore.MAGENTA + f"🏁 多單觸及 profit_3 → 平倉 {self.new_price}" + Style.RESET_ALL)
        #             self.frame.OnOrderBtn(event=None, S_Buys="S", price=self.new_price, offset="1")
        #             self.trading_buy = False
        #             self.buy_signal = False
        # 更新費波那契數
        self.calculate_and_update()
    def show_tickbars(self, MatchTime, tol_time, tol_time_str):
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
        # mark_temp_up_down_str_color = "Style.RESET_ALL"
        mark_temp_highest_arrow_color = "Style.RESET_ALL"
        mark_temp_lowest_arrow_color = "Style.RESET_ALL"
        mark_temp_big_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_small_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_close_price_color = "Fore.YELLOW + Style.BRIGHT"
        mark_temp_compare_avg_price_color = "Fore.YELLOW + Style.BRIGHT"

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
            # temp_avg_price = (
            #         self.temp_price_compare_database['big_value']+self.temp_price_compare_database['small_value'])/2
        else:
            self.list_temp_tickbars_big_price.append(self.new_price)
            self.list_temp_tickbars_small_price.append(self.new_price)
            # temp_avg_price = self.new_price

        # self.list_temp_tickbars_avg_price.append(self.time_price_per)
        # self.tickbars_tol_time_var.set(tol_time_str)
        # self.group_size_var.set(str(float(round(self.TXF_MXF_avg_price, 4))))
        self.frame.compareInfoGrid.SetCellValue(0, 2, tol_time_str)

        # temp_up_down_str = "．"
        temp_highest_arrow = "．"
        temp_lowest_arrow = "．"
        # if self.previous_highest_price == self.highest_price and self.previous_lowest_price == self.lowest_price:
        #     if self.temp_price_compare_database['up']:
        #         temp_up_down_str = "↑"
        #     elif self.temp_price_compare_database['down']:
        #         temp_up_down_str = "↓"

        if self.previous_highest_price == self.highest_price:
            if self.temp_price_compare_database['up']:
                temp_highest_arrow = "↑"
            elif self.temp_price_compare_database['down']:
                temp_highest_arrow = "↓"

        if self.previous_lowest_price == self.lowest_price:
            if self.temp_price_compare_database['up']:
                temp_lowest_arrow = "↑"
            elif self.temp_price_compare_database['down']:
                temp_lowest_arrow = "↓"

        self.previous_highest_price = self.highest_price
        self.previous_lowest_price = self.lowest_price

        self.frame.compareInfoGrid.SetCellTextColour(0, 0, wx.RED)
        self.frame.compareInfoGrid.SetCellTextColour(0, 1, wx.GREEN)
        self.frame.compareInfoGrid.SetCellValue(
            0, 0, str(int(self.list_temp_tickbars_big_price[-1]))+"  "+temp_highest_arrow)
        self.frame.compareInfoGrid.SetCellValue(
            0, 1, str(int(self.list_temp_tickbars_small_price[-1]))+"  "+temp_lowest_arrow)

        if len(self.list_temp_tickbars_big_price) > 1 and self.list_temp_tickbars_big_price[-1] == self.highest_price:
            self.is_dayhigh = True
        if len(self.list_temp_tickbars_small_price) > 1 and self.list_temp_tickbars_small_price[-1] == self.lowest_price:
            self.is_daylow = True

         # 1代表空 2代表多
        #  # 判斷收盤價的漲跌
        # if self.list_close_price[-1] < self.list_temp_tickbars_avg_price[-1]:
        #     mark_temp_close_avg_price_num = 1
        # elif self.list_close_price[-1] > self.list_temp_tickbars_avg_price[-1]:
        #     mark_temp_close_avg_price_num = 2

        # 判斷tickbars高價的漲跌
        if len(self.list_temp_tickbars_big_price) > 1 and self.list_temp_tickbars_big_price[-2] >= self.list_temp_tickbars_big_price[-1]:
            mark_temp_big_price_num = 1
        elif len(self.list_temp_tickbars_big_price) > 1 and self.list_temp_tickbars_big_price[-2] < self.list_temp_tickbars_big_price[-1]:
            mark_temp_big_price_num = 2

        # 判斷tickbars低價的漲跌
        if len(self.list_temp_tickbars_small_price) > 1 and self.list_temp_tickbars_small_price[-2] > self.list_temp_tickbars_small_price[-1]:
            mark_temp_small_price_num = 1
        elif len(self.list_temp_tickbars_small_price) > 1 and self.list_temp_tickbars_small_price[-2] <= self.list_temp_tickbars_small_price[-1]:
            mark_temp_small_price_num = 2

        # # 比較tickbars均價
        # if self.sell_signal and self.temp_tickbars_avg_price > self.temp_howeverHighest_avg_price:
        #     mark_temp_compare_avg_price_color = "Fore.BLACK + Back.WHITE"
        #     temp="空注意"
        # elif  self.buy_signal and self.temp_tickbars_avg_price < self.temp_howeverLowest_avg_price:
        #     mark_temp_compare_avg_price_color = "Fore.BLACK + Back.WHITE"
        #     temp="多注意"

        # 判斷tickbars總成交量的量增減
        if len(self.list_temp_tickbars_total_volume) > 1 and self.list_temp_tickbars_total_volume[-2] < self.list_temp_tickbars_total_volume[-1]:
            mark_temp_total_volume_num = 1

        # 判斷tickbars時間的快慢

        # if len(self.list_tickbars_tol_time) > 1 and self.list_tickbars_tol_time[-2] > self.list_tickbars_tol_time[-1] and mark_temp_total_volume_num == 1 and (temp_up_down_str == "↑" or temp_up_down_str == "↓"):
        #     mark_temp_up_down_str_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"
        #     mark_speedtime_num = 1

        if len(self.list_tickbars_tol_time) > 1 and (self.list_tickbars_tol_time[-2]/2) > self.list_tickbars_tol_time[-1] and mark_temp_total_volume_num == 1 and temp_highest_arrow == "↓":
            mark_tol_time_color = "Fore.BLACK + Back.WHITE"

        if len(self.list_tickbars_tol_time) > 1 and (self.list_tickbars_tol_time[-2]/2) > self.list_tickbars_tol_time[-1] and mark_temp_total_volume_num == 1 and temp_lowest_arrow == "↑":
            mark_tol_time_color = "Fore.BLACK + Back.WHITE"

        if len(self.list_tickbars_tol_time) > 1 and self.list_tickbars_tol_time[-2] > self.list_tickbars_tol_time[-1] and mark_temp_total_volume_num == 1 and temp_highest_arrow == "↓":
            mark_temp_highest_arrow_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"
            mark_speedtime_num = 1

        if len(self.list_tickbars_tol_time) > 1 and self.list_tickbars_tol_time[-2] > self.list_tickbars_tol_time[-1] and mark_temp_total_volume_num == 1 and temp_lowest_arrow == "↑":
            mark_temp_lowest_arrow_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"
            mark_speedtime_num = 1

        if mark_speedtime_num == 1:
            # if self.is_dayhigh and mark_temp_big_price_num == 1 and mark_temp_small_price_num == 1 and temp_up_down_str == "↓" and mark_temp_close_avg_price_num == 1:
            if self.is_dayhigh and temp_highest_arrow == "↓":
                self.is_dayhigh = False
                # self.conform_total_volume = self.list_temp_tickbars_total_volume[-1]
                # mark_temp_big_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
                # temp = "疑作頭"
                self.suspected_sell = True
            # elif self.is_daylow and mark_temp_big_price_num == 2 and mark_temp_small_price_num == 2 and temp_up_down_str == "↑" and mark_temp_close_avg_price_num == 2:
            elif self.is_daylow and temp_lowest_arrow == "↑":
                self.is_daylow = False
                # self.conform_total_volume = self.list_temp_tickbars_total_volume[-1]
                # mark_temp_small_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
                # temp = "疑打底"
                self.suspected_buy = True
            new_choices = [s.strip()
                               for s in self.fibonacci_sell_str.split(":")]
            if self.suspected_sell == True and temp_highest_arrow == "↓" and  int(new_choices[1])>self.temp_howeverHighest_avg_price:
                self.trading_sell = True
                # self.trading_buy = False
                mark_temp_close_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
                self.stopLoss_sell = self.highest_price+1
                profit_1 = self.list_close_price[-1] - \
                    (abs(self.stopLoss_sell-self.list_close_price[-1])+2)
                profit_2 = self.list_close_price[-1] - \
                    ((abs(self.stopLoss_sell-self.list_close_price[-1])+2)*2)
                profit_3 = self.list_close_price[-1] - \
                    ((abs(self.stopLoss_sell-self.list_close_price[-1])+2)*3)

                cols = self.frame.signalGrid.GetNumberCols()
                for c in range(cols):
                    self.frame.signalGrid.SetCellTextColour(0, c, wx.GREEN)
                self.frame.signalGrid.SetCellValue(
                    0, 0, str(int(self.list_close_price[-1])))
                self.frame.signalGrid.SetCellValue(
                    0, 1, str(int(self.stopLoss_sell)))
                self.frame.signalGrid.SetCellValue(0, 2, str(int(profit_1)))
                self.frame.signalGrid.SetCellValue(0, 3, str(int(profit_2)))
                self.frame.signalGrid.SetCellValue(0, 4, str(int(profit_3)))

                self.fibonacci_chkSell_str = self.fibonacci_sell_str
                self.profit_sell_str = f"{int(profit_1)} : {int(profit_2)} : {int(profit_3)}"

                if self.frame.chkSell.IsChecked():
                    new_choices = [s.strip()
                                for s in self.fibonacci_chkSell_str.split(":")]
                    self.frame.price_combo.SetItems(new_choices)
                    self.frame.price_combo.SetSelection(3)

                temp = "進場空"
                self.entry_price_sell = int(self.list_close_price[-1])  # 記錄空單進場價
                self.suspected_sell = False
                self.sell_signal = True
                if self.frame.chkSell.IsChecked() and self.frame.acclist_combo.GetCount() != 0:
                    val = self.frame.price_combo.GetString(
                        self.frame.price_combo.GetSelection())
                    price = int(val) if val.isdigit() else 0
                    self.frame.OnOrderBtn(
                        event=None, S_Buys="S", price=price, offset="0")

                if self.frame.isPlaySound.GetValue() == True:
                    threading.Thread(target=winsound.PlaySound, args=(
                        "woo.wav", winsound.SND_FILENAME), daemon=True).start()

                if self.frame.isSMS.GetValue() == True:
                    bot_message = f"{MatchTime}  放空進場: {int(self.list_close_price[-1])}  止損: {int(self.stopLoss_sell)}  停利: {int(profit_1)} : {int(profit_2)} : {int(profit_3)}"
                    threading.Thread(target=self.telegram_bot_sendtext, args=(
                        bot_message,), daemon=True).start()

            new_choices = [s.strip()
                               for s in self.fibonacci_buy_str.split(":")]
            if self.suspected_buy == True and temp_lowest_arrow == "↑" and  int(new_choices[1])<self.temp_howeverLowest_avg_price:
                self.trading_buy = True
                # self.trading_sell = False
                mark_temp_close_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
                self.stopLoss_buy = self.lowest_price-1
                profit_1 = self.list_close_price[-1] + \
                    (abs(self.stopLoss_buy-self.list_close_price[-1])+2)
                profit_2 = self.list_close_price[-1] + \
                    ((abs(self.stopLoss_buy-self.list_close_price[-1])+2)*2)
                profit_3 = self.list_close_price[-1] + \
                    ((abs(self.stopLoss_buy-self.list_close_price[-1])+2)*3)

                cols = self.frame.signalGrid.GetNumberCols()
                for c in range(cols):
                    self.frame.signalGrid.SetCellTextColour(1, c, wx.RED)
                self.frame.signalGrid.SetCellValue(
                    1, 0, str(int(self.list_close_price[-1])))
                self.frame.signalGrid.SetCellValue(
                    1, 1, str(int(self.stopLoss_buy)))
                self.frame.signalGrid.SetCellValue(1, 2, str(int(profit_1)))
                self.frame.signalGrid.SetCellValue(1, 3, str(int(profit_2)))
                self.frame.signalGrid.SetCellValue(1, 4, str(int(profit_3)))

                self.fibonacci_chkBuy_str = self.fibonacci_buy_str
                self.profit_buy_str = f"{int(profit_1)} : {int(profit_2)} : {int(profit_3)}"

                if self.frame.chkBuy.IsChecked():
                    new_choices = [s.strip()
                                for s in self.fibonacci_chkBuy_str.split(":")]
                    self.frame.price_combo.SetItems(new_choices)
                    self.frame.price_combo.SetSelection(3)

                temp = "進場多"
                self.entry_price_buy = int(self.list_close_price[-1])   # 記錄多單進場價
                self.suspected_buy = False
                self.buy_signal = True
                if self.frame.chkBuy.IsChecked() and self.frame.acclist_combo.GetCount() != 0:
                    val = self.frame.price_combo.GetString(
                        self.frame.price_combo.GetSelection())
                    price = int(val) if val.isdigit() else 0
                    # S_Buys = self.frame.bscode1_combo.GetString(
                    #     self.frame.bscode1_combo.GetSelection())[0:1]
                    self.frame.OnOrderBtn(
                        event=None, S_Buys="B", price=price, offset="0")

                if self.frame.isPlaySound.GetValue() == True:
                    threading.Thread(target=winsound.PlaySound, args=(
                        "woo.wav", winsound.SND_FILENAME), daemon=True).start()

                if self.frame.isSMS.GetValue() == True:
                    bot_message = f"{MatchTime}  作多進場: {int(self.list_close_price[-1])}  止損: {int(self.stopLoss_buy)}  停利: {int(profit_1)} : {int(profit_2)} : {int(profit_3)}"
                    threading.Thread(target=self.telegram_bot_sendtext, args=(
                        bot_message,), daemon=True).start()

        if self.pre_TXF_MXF_avg_price > self.TXF_MXF_avg_price and self.temp_price_compare_database:
            self.trending_up = False
            self.trending_down = True
            # print(Style.BRIGHT + Fore.GREEN + "✅ 成功訊息 (亮綠色)"
            #   + Fore.RED + Back.WHITE + "❌ 錯誤訊息 (紅字白底)"
            #   + Style.RESET_ALL)

            if temp == "進場空":
                print(
                    f"{Fore.GREEN}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_highest_arrow_color)}{temp_highest_arrow}{Style.RESET_ALL}  {eval(mark_temp_lowest_arrow_color)}{temp_lowest_arrow}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現:{Style.RESET_ALL}{eval(mark_temp_close_price_color)} {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {eval(mark_temp_compare_avg_price_color)}{int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_howeverHighest_avg_price):<5d} : {int(self.temp_howeverLowest_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.GREEN}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}放空 {int(self.list_close_price[-1])}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_sell_str}   止損: {int(self.stopLoss_sell)}   停利: {self.profit_sell_str}{Style.RESET_ALL}")

            elif temp == "進場多":
                print(
                    f"{Fore.GREEN}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_highest_arrow_color)}{temp_highest_arrow}{Style.RESET_ALL}  {eval(mark_temp_lowest_arrow_color)}{temp_lowest_arrow}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現:{Style.RESET_ALL}{eval(mark_temp_close_price_color)} {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {eval(mark_temp_compare_avg_price_color)}{int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_howeverHighest_avg_price):<5d} : {int(self.temp_howeverLowest_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.RED}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}買進 {int(self.list_close_price[-1])}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_buy_str}   止損: {int(self.stopLoss_buy)}   停利: {self.profit_buy_str}{Style.RESET_ALL}")
            else:
                print(
                    f"{Fore.GREEN}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_highest_arrow_color)}{temp_highest_arrow}{Style.RESET_ALL}  {eval(mark_temp_lowest_arrow_color)}{temp_lowest_arrow}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {eval(mark_temp_compare_avg_price_color)}{int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_howeverHighest_avg_price):<5d} : {int(self.temp_howeverLowest_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.YELLOW}{Style.BRIGHT}{temp}{Style.RESET_ALL}")

        elif self.pre_TXF_MXF_avg_price < self.TXF_MXF_avg_price and self.temp_price_compare_database:
            self.trending_up = True
            self.trending_down = False
            if temp == "進場多":
                print(
                    f"{Fore.RED}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_highest_arrow_color)}{temp_highest_arrow}{Style.RESET_ALL}  {eval(mark_temp_lowest_arrow_color)}{temp_lowest_arrow}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}現:{Style.RESET_ALL}{eval(mark_temp_close_price_color)} {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {eval(mark_temp_compare_avg_price_color)}{int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_howeverHighest_avg_price):<5d} : {int(self.temp_howeverLowest_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.RED}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}買進 {int(self.list_close_price[-1])}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_buy_str}   止損: {int(self.stopLoss_buy)}   停利: {self.profit_buy_str}{Style.RESET_ALL}")
            elif temp == "進場空":
                print(
                    f"{Fore.RED}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_highest_arrow_color)}{temp_highest_arrow}{Style.RESET_ALL}  {eval(mark_temp_lowest_arrow_color)}{temp_lowest_arrow}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}現:{Style.RESET_ALL}{eval(mark_temp_close_price_color)} {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {eval(mark_temp_compare_avg_price_color)}{int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_howeverHighest_avg_price):<5d} : {int(self.temp_howeverLowest_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.GREEN}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                print(
                    f"{Fore.YELLOW}{Style.BRIGHT}{MatchTime}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}放空 {int(self.list_close_price[-1])}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}費波: {self.fibonacci_sell_str}   止損: {int(self.stopLoss_sell)}   停利: {self.profit_sell_str}{Style.RESET_ALL}")

            else:
                print(
                    f"{Fore.RED}{Style.BRIGHT}{MatchTime}  {(self.TXF_MXF_avg_price):>9.4f}{Style.RESET_ALL}  {eval(mark_tol_time_color)}{tol_time_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_temp_tickbars_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_temp_tickbars_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_temp_highest_arrow_color)}{temp_highest_arrow}{Style.RESET_ALL}  {eval(mark_temp_lowest_arrow_color)}{temp_lowest_arrow}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_tickbars_total_volume):>5d} : {eval(mark_temp_compare_avg_price_color)}{int(self.temp_tickbars_avg_price):<5d}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_howeverHighest_avg_price):<5d} : {int(self.temp_howeverLowest_avg_price):<5d}{Style.RESET_ALL}  高: {int(self.highest_price)}  低: {int(self.lowest_price)}  {Fore.YELLOW}{Style.BRIGHT}{temp}{Style.RESET_ALL}")

        self.temp_price_compare_database = {}
        self.temp_tickbars_total_volume = 0
        self.temp_TXF_MXF_TR = 0
        self.temp_tickbars_avg_price = 0

        self.pre_TXF_MXF_avg_price = self.TXF_MXF_avg_price
        self.matchtime = 0
        self.group_size = 0

    # 提取時間的各部分
    def parse_time_string(self, time_string):
        hours = int(time_string[:2])
        minutes = int(time_string[2:4])
        seconds = int(time_string[4:6])
        milliseconds = int(time_string[6:9])
        return hours, minutes, seconds, milliseconds

    # 將時間轉換為總毫秒數
    def to_total_milliseconds(self, hours, minutes, seconds, milliseconds):
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds

    def calculate_time(self, database, RefPri, HighPri, LowPri,  MatchQty, TolMatchQty, MatchTime, Is_simulation):
        if not database:
            # database["match_pri"] = float(RefPri)
            database["current_total_volume"] = float(TolMatchQty)
            database["total_volume"] = float(MatchQty)
            database["match_pri"] = self.new_price
            # 提取時間的各部分
            h1, m1, s1, ms1 = self.parse_time_string(MatchTime)
            # 將時間轉換為總毫秒數
            database["pre_matchtime"] = self.to_total_milliseconds(
                h1, m1, s1, ms1)

            if self.highest_price == 0 or self.lowest_price == 0:
                self.highest_price = int(HighPri)
                self.lowest_price = int(LowPri)
            else:
                if int(HighPri) > self.highest_price:
                    self.highest_price = int(HighPri)
                if int(LowPri) < self.lowest_price:
                    self.lowest_price = int(LowPri)

             # 計算交易時段總均價
            self.calc_avg_price()
        elif database["current_total_volume"] < float(TolMatchQty):
            self.group_size += 1
            database["current_total_volume"] = float(
                TolMatchQty)
            database["total_volume"] += float(MatchQty)
            database["match_pri"] = self.new_price
            # 提取時間的各部分
            h1, m1, s1, ms1 = self.parse_time_string(MatchTime)
            # 將時間轉換為總毫秒數
            temp_matchtime = self.to_total_milliseconds(h1, m1, s1, ms1)
            tol_matchtime = abs(temp_matchtime - database["pre_matchtime"])
            if tol_matchtime < 50000000:  # 過濾隔夜值 23:59:59.999 ~ 00:00:00.000
                self.matchtime += tol_matchtime
            database["pre_matchtime"] = temp_matchtime

            # 計算交易時段總均價
            self.calc_avg_price()
            self.calculate_tickbars(MatchTime, Is_simulation)

    def calc_avg_price(self):
        TR = self.new_price * self.tmp_qty
        self.TXF_MXF_tol_value += TR
        if self.TXF_database and self.MXF_database:
            # 計算交易時段總均價
            self.TXF_MXF_avg_price = self.TXF_MXF_tol_value / \
                (self.TXF_database["total_volume"] *
                 4+self.MXF_database["total_volume"])

    def handle_entry_signal(self, MatchTime, Is_simulation):
        """
        當已跌破關鍵K低點 or 已突破關鍵K高點,是要等反彈或回檔或追價。

        參數：
        MatchTime (str): 記錄當時的時間。
        direction ("空" or "多"): 整個策略只作空或作多。

        注意事項：
        - self.ask_bid < 3 表示內外盤價差距要小,預防快市價位亂跳。
        - 。
        """
        self.Index = -1
        self.short_signal["order_time"] = MatchTime
        self.short_signal["order_price"] = self.temp_big_value
        self.short_signal["profit_stop_price"] = 42-self.profit
        self.entry_price = self.new_price
        self.count += 1
        print(
            f'{Fore.CYAN}{Style.BRIGHT}第 {self.count} 筆  空   {self.short_signal["order_time"]}  出場價: {int(self.temp_big_value)}  進場價: {int(self.entry_price)} {Style.RESET_ALL}')

    def handle_short_exit(self, MatchTime):
        self.entry_signal = False
        self.Index = 0
        self.profit += (self.entry_price-self.new_price-2)
        print(
            f'{Fore.YELLOW}{Style.BRIGHT}第 {self.count} 筆 出場  {MatchTime}  出場價: {self.new_price}  損益: {self.profit}{Style.RESET_ALL}')

    def execute_compare(self, database, MatchTime, value):
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

    def calculate_and_update(self):
        try:
            self.frame.infoDataGrid.SetCellValue(
                0, 0, str(int(self.highest_price)))
            self.frame.infoDataGrid.SetCellValue(
                0, 1, str(int(self.lowest_price)))
            self.frame.infoDataGrid.SetCellTextColour(0, 0, wx.RED)
            self.frame.infoDataGrid.SetCellTextColour(0, 1, wx.GREEN)

            #  f"  高低價差: {int(diffNum)}  \n"
            #                              f"  均價: {int(self.TXF_MXF_avg_price)}  現價: {int(self.new_price)}\n"

            if self.temp_entry_price > 0:
                if int(self.frame.avgPrice.GetValue()) > 0:
                    XF_avg_price = int(self.frame.avgPrice.GetValue())
                else:
                    XF_avg_price = int(self.TXF_MXF_avg_price)
                pressureNum = int(self.highest_price)
                supportNum = int(self.lowest_price)
                pressure_support_keypri = XF_avg_price
                pressure_diff = pressureNum - pressure_support_keypri  # 計算差子
                self.frame.infoDataGrid.SetCellValue(
                    0, 2, str(int(pressure_diff)))
                self.frame.infoDataGrid.SetCellTextColour(0, 2, wx.GREEN)
                support_diff = pressure_support_keypri - supportNum
                self.frame.infoDataGrid.SetCellValue(
                    0, 3, str(int(support_diff)))
                self.frame.infoDataGrid.SetCellTextColour(0, 3, wx.RED)
                diffNum = pressureNum-supportNum
                self.frame.infoDataGrid.SetCellValue(0, 4, str(int(diffNum)))
                # self.frame.infoDataGrid.SetCellTextColour(0, 4, wx.YELLOW)

                # 計算壓力的比率值（四捨五入到整數）

                pressure_support_keypri = XF_avg_price
                pressureNum_ratio_236 = round(
                    pressure_support_keypri + pressure_diff * 0.236)
                pressureNum_ratio_382 = round(
                    pressure_support_keypri + pressure_diff * 0.382)
                pressureNum_ratio_5 = round(
                    pressure_support_keypri + pressure_diff * 0.5)
                pressureNum_ratio_618 = round(
                    pressure_support_keypri + pressure_diff * 0.618)
                pressureNum_ratio_786 = round(
                    pressure_support_keypri + pressure_diff * 0.786)

                # 計算支撐的比率值（四捨五入到整數）
                supportNum_ratio_236 = round(
                    pressure_support_keypri - (support_diff * 0.236))
                supportNum_ratio_382 = round(
                    pressure_support_keypri - (support_diff * 0.382))
                supportNum_ratio_5 = round(
                    pressure_support_keypri - (support_diff * 0.5))
                supportNum_ratio_618 = round(
                    pressure_support_keypri - (support_diff * 0.618))
                supportNum_ratio_786 = round(
                    pressure_support_keypri - (support_diff * 0.786))

                # 計算反彈和回檔的0.382之差
                self.fibonacci_sell_str = f"{pressureNum_ratio_236} : {pressureNum_ratio_382} : {pressureNum_ratio_5} : {pressureNum_ratio_618} : {pressureNum_ratio_786}"
                self.fibonacci_buy_str = f"{supportNum_ratio_236} : {supportNum_ratio_382} : {supportNum_ratio_5} : {supportNum_ratio_618} : {supportNum_ratio_786}"

                # 費波那契數
                # cols = self.frame.fibonacciGrid.GetNumberCols()
                self.frame.fibonacciGrid.SetCellValue(
                    0, 0, str(pressureNum_ratio_236))
                self.frame.fibonacciGrid.SetCellValue(
                    0, 1, str(pressureNum_ratio_382))
                self.frame.fibonacciGrid.SetCellValue(
                    0, 2, str(pressureNum_ratio_5))
                self.frame.fibonacciGrid.SetCellValue(
                    0, 3, str(pressureNum_ratio_618))
                self.frame.fibonacciGrid.SetCellValue(
                    0, 4, str(pressureNum_ratio_786))
                # cols = self.frame.fibonacciGrid.GetNumberCols()
                # for c in range(cols):
                #     self.frame.fibonacciGrid.SetCellTextColour(0, c, wx.GREEN)

                self.frame.fibonacciGrid.SetCellValue(
                    1, 0, str(supportNum_ratio_236))
                self.frame.fibonacciGrid.SetCellValue(
                    1, 1, str(supportNum_ratio_382))
                self.frame.fibonacciGrid.SetCellValue(
                    1, 2, str(supportNum_ratio_5))
                self.frame.fibonacciGrid.SetCellValue(
                    1, 3, str(supportNum_ratio_618))
                self.frame.fibonacciGrid.SetCellValue(
                    1, 4, str(supportNum_ratio_786))
                # for c in range(cols):
                #     self.frame.fibonacciGrid.SetCellTextColour(1, c, wx.RED)

                # 投資建議
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
            # messagebox.showerror("錯誤", "請輸入有效的數字！")
            pass
        except ZeroDivisionError:
            pass  # 捕获 ZeroDivisionError，但什么都不做

    def telegram_bot_sendtext(self, bot_message):
        # Telegram Bot Token
        TOKEN = "8341950229:AAHw3h_p0Bnf_KcS5Mr4x3cOpIKHeFACiBs"

        # 目標 chat_id
        chat_id = "8485648973"

        # 要發送的訊息內容
        message = bot_message

        # Telegram API URL
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

        # API 請求參數
        payload = {
            "chat_id": chat_id,
            "text": message
        }

        # 發送請求
        response = requests.post(url, data=payload)

    def trigger_short_signal(self):
        # bot_message = "進場空: TXF"
        # print(bot_message)
        # if self.frame.isSMS:
        #     print("發送Telegram通知...")
        side = "S"
        symbol = "MXFK5"
        # lots = int(self.frame.lots_combo)
        price = "31238"
        threading.Thread(
            target=self.bot.auto_send_order,
            args=(symbol, side, price),
            daemon=True
        ).start()

    def trigger_long_signal(self):
        bot_message = "進場多: TXF"
        print(bot_message)
        if self.frame.isSMS:
            # 發送通知 (省略實際 telegram)
            print("發送Telegram通知...")
            # 🔧 自動下單
            side = "BUY"
            symbol = "TXF"
            lots = int(self.frame.lots_combo)
            threading.Thread(
                target=self.bot.auto_send_order,
                args=(self.frame.bot.Yuanta, symbol, side, lots),
                daemon=True
            ).start()


class RedirectText:
    def __init__(self, text_ctrl):
        self.out = text_ctrl

    def write(self, message):
        tokens = re.split(r'(\x1b\[.*?m)', message)
        self._draw_segments(tokens)

    def _draw_segments(self, segments):
        fg = wx.WHITE
        bg = wx.BLACK
        bold = False

        for seg in segments:
            # 檢查 colorama 控制碼
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
                12,  # 🔥 字體大小：改這裡就能放大或縮小
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
            ))

            self.out.SetDefaultStyle(style)
            self.out.AppendText(seg)

        self.out.ShowPosition(self.out.GetLastPosition())

    def flush(self):
        pass
