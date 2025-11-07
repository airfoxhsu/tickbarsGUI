from re import M
import winsound
import matplotlib.pyplot as plt
import pandas as pd
from colorama import Fore, Style, init, Back
import tkinter as tk
from tkinter import messagebox


class TradingStrategy:
    def __init__(self) -> None:
        # self.frame=frame
        # # 建立結果顯示標籤
        # self.result_label = tk.Label(frame, text="請輸入數值後點擊計算", justify="left")
        # self.result_label.grid(row=5, column=0, columnspan=4, padx=10, pady=10)
        # # self.result_label.pack()
        
        # # 使用 StringVar 綁定輸入框
        # self.big_value_var=tk.StringVar()
        # self.small_value_var=tk.StringVar()
        # self.a_var=tk.StringVar()
        # self.b_var=tk.StringVar()
        # self.c_var=tk.StringVar()
        
        # # 自動設定初始值
        # self.big_value_var.set("0")
        # self.small_value_var.set("0")
        # self.a_var.set("0")
        # self.b_var.set("0")
        # self.c_var.set("0")
        
        self.volumes_per_price = {}
        self.spreads_per_price = {}
        self.total_spread = 0
        self.new_price = 0
        self.TXF_database = {}
        self.MXF_database = {}
        self.spread_compare_database = {}
        self.price_compare_database = {}
        self.ohlc_database = {}
        self.long_signal = {}
        self.short_signal = {}
        self.Index = 0
        self.profit = 0
        # self.first_step_price = 0
        self.second_step_price = 0
        self.third_step_price = 0
        self.TXF_MXF_TR = 0
        self.TXF_MXF_ATR = 0
        self.pre_TXF_MXF_ATR = 0
        self.TRi = []
        self.ATR = 0
        self.trending_down = False
        self.trending_up = False
        self.pre_ATR = 0
        self.entry_signal = False
        self.trailing_stop = False
        self.entry_price = 0
        self.temp_trend_advice=""
        self.temp_entry_price = 0
        self.temp_total_spread = 0
        self.warning_signal = False
        self.temp_ATR_up = False
        self.temp_ATR_down = False
        self.temp_price_compare_database = {}
        self.temp_big_value = 0
        self.temp_small_value = 0
        self.temp_ATR_compare_database = {}
        self.temp_ATR_big_then_value = 0
        self.temp_ATR_small_then_value = 0
        self.temp_ATR_big_value = 0
        self.temp_ATR_small_value = 0
        self.key_signal = False
        self.list_ATR_price = []
        self.list_ATR_timediff = []
        self.list_ATR_timediff_price_per = []
        self.list_ATR_temp_big_price= []
        self.list_ATR_temp_small_price =[]
        self.conform_big_price= 0
        self.conform_small_price = 0
        self.conform_close_price=0
        self.count = 0
        self.pre_matchtime=0
        self.matchtime=0
        self.num=0
        self.rolling_back=False
        self.list_signal_str=[]
        self.temp_TXF_MXF_total_volume = 0
        self.temp_TXF_MXF_TR = 0
        self.temp_TXF_MXF_ATR = 0
        self.list_speedtime_big_price = []
        self.list_speedtime_small_price = []
        self.is_dayhigh = False
        self.is_daylow = False

    def execate_TXF_MXF(self, direction, symbol, RefPri, OpenPri, MatchTime, MatchPri, MatchQty, TolMatchQty, Is_simulation):
        # if "-1" not in TolMatchQty and OpenPri != "0" and Bid != "0":
        if "XF" in symbol:
            self.tmp_qty = 0
            self.tmp_qty_spread = 0
            self.new_price = float(MatchPri)
        if "TXF" in symbol:
            self.tmp_qty = 4 * float(MatchQty)
            self.calculate_XF(self.TXF_database, RefPri,
                              MatchQty, TolMatchQty, MatchTime, Is_simulation)
        elif "MXF" in symbol:
            self.tmp_qty = float(MatchQty)
            self.calculate_XF(self.MXF_database, RefPri,
                              MatchQty, TolMatchQty, MatchTime, Is_simulation)

        self.total_spread += self.tmp_qty_spread
        if self.warning_signal:
            self.temp_total_spread += self.tmp_qty_spread

    def calculate_ATR(self, MatchTime, Is_simulation):
        key_price = 0
        # TR = (abs(self.new_price-self.price_compare_database['small_value'])-abs(
        #     self.price_compare_database['big_value']-self.new_price))*self.tmp_qty
        # self.TXF_MXF_TR += TR
        temp_up_down_str=""
    
        # 趨勢原先向上,後轉為不明  #趨勢原先向下,後轉為不明
        if (self.trending_up and self.pre_ATR > self.TXF_MXF_ATR) or (self.trending_down and self.pre_ATR < self.TXF_MXF_ATR) and self.temp_price_compare_database:
            if self.pre_TXF_MXF_ATR < self.TXF_MXF_ATR:
                self.temp_ATR_compare_database['big_value'] = self.pre_ATR
                self.temp_ATR_compare_database['small_value'] = self.TXF_MXF_ATR
                self.rolling_back=True
                # if  130000000000 >= int(MatchTime) > 85500000000:   
                # # if 250000>self.num>15000:                 
                #     self.temp_big_value = self.temp_price_compare_database['big_value']
                #     self.temp_small_value = self.temp_price_compare_database['small_value']
                #     self.entry_signal = True
                # print(
                #     # f"{Fore.RED}{Style.BRIGHT}{MatchTime}  ATR: {(self.TXF_MXF_ATR):>9.4f} < Pre_ATR: {(self.pre_ATR):>9.4f}  {Fore.YELLOW}回檔中...進入多空交戰  {Fore.RED}關鍵價: {int(self.new_price)}{Style.RESET_ALL}  {int(max((self.peaks))):<5d} : {int(min((self.peaks))):<5d}")
                #     f"{self.num} {Fore.GREEN}{Style.BRIGHT}{MatchTime}  ATR: {(self.TXF_MXF_ATR):>9.4f} < Pre_ATR: {(self.pre_ATR):>9.4f}  {Fore.YELLOW}回檔中...進入多空交戰  {int(self.temp_price_compare_database['big_value']):<5d} : {int(self.temp_price_compare_database['small_value']):<5d}  {Fore.GREEN}關鍵價: {int(self.new_price)}{Style.RESET_ALL}")
                # if Is_simulation:
                #     # self.show_bar()
                #     winsound.PlaySound("woo.wav", winsound.SND_FILENAME)
            elif self.pre_TXF_MXF_ATR > self.TXF_MXF_ATR:
                self.temp_ATR_compare_database['big_value'] = self.TXF_MXF_ATR
                self.temp_ATR_compare_database['small_value'] = self.pre_ATR
                self.rolling_back=False
                # if self.entry_signal:
                #   self.handle_short_exit(MatchTime)
                # print(
                #     # f"{Fore.GREEN}{Style.BRIGHT}{MatchTime}  ATR: {(self.TXF_MXF_ATR):>9.4f} > Pre_ATR: {(self.pre_ATR):>9.4f}  {Fore.YELLOW}反彈中...進入多空交戰  {Fore.GREEN}關鍵價: {int(self.new_price)}{Style.RESET_ALL}  {int(max((self.peaks))):<5d} : {int(min((self.peaks))):<5d}")
                #     f"{self.num} {Fore.RED}{Style.BRIGHT}{MatchTime}  ATR: {(self.TXF_MXF_ATR):>9.4f} > Pre_ATR: {(self.pre_ATR):>9.4f}  {Fore.YELLOW}反彈中...進入多空交戰  {int(self.temp_price_compare_database['big_value']):<5d} : {int(self.temp_price_compare_database['small_value']):<5d}  {Fore.RED}關鍵價: {int(self.new_price)}{Style.RESET_ALL}")
                # if Is_simulation:
                #     # self.show_bar()                    
                #     winsound.PlaySound("woo.wav", winsound.SND_FILENAME)

            self.trending_up = False
            self.trending_down = False
            self.key_signal = True
            self.warning_signal = False
            self.temp_entry_price = self.new_price
            self.temp_trend_advice= ""
            # self.temp_price_compare_database = {}
            self.temp_ATR_compare_database["big_then_value"] = self.new_price
            self.temp_ATR_compare_database["small_then_value"] = self.new_price
        elif self.price_compare_database['big_value']<self.new_price:
            self.temp_entry_price=0
            self.temp_trend_advice = "股價創高-做多"
        elif self.price_compare_database['small_value']>self.new_price:
            self.temp_entry_price=0
            self.temp_trend_advice = "股價創低-做空"
                
        self.pre_ATR = self.TXF_MXF_ATR
        self.execute_compare(
            self.temp_price_compare_database, MatchTime, value=self.new_price, then_value=self.temp_total_spread)
        if self.temp_price_compare_database['up'] :
            temp_up_down_str = "↑"
        elif self.temp_price_compare_database['down']:
            temp_up_down_str = "↓"
        self.execute_per_price()
        self.temp_TXF_MXF_total_volume += self.tmp_qty
        self.temp_TXF_MXF_TR += (self.new_price * self.tmp_qty)
        self.temp_TXF_MXF_ATR = self.temp_TXF_MXF_TR / (self.temp_TXF_MXF_total_volume)
            
        if self.warning_signal:  # 進入多空交戰區
            if self.temp_ATR_compare_database['big_value'] < self.TXF_MXF_ATR:
                if not self.temp_ATR_up:
                    self.temp_ATR_up = True
                    self.temp_ATR_down = False
                    self.temp_ATR_small_value = self.temp_ATR_compare_database['small_value']
                    self.temp_ATR_small_then_value = self.temp_ATR_compare_database[
                        "small_then_value"]
                    self.pre_TXF_MXF_ATR = self.temp_ATR_small_value
                    if self.entry_signal:
                        self.handle_short_exit(MatchTime)
                    print(
                        f"{MatchTime}  ATR: {(self.TXF_MXF_ATR):>9.4f}          {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_ATR_small_then_value)}  低: {(self.temp_ATR_small_value):>9.4f}  {Fore.RED}現價: {int(self.new_price)}{Style.RESET_ALL}  {int(self.temp_price_compare_database['big_value']):<5d} : {int(self.temp_price_compare_database['small_value']):<5d}")
                    
            elif self.temp_ATR_compare_database['small_value'] > self.TXF_MXF_ATR:
                if not self.temp_ATR_down:
                    self.temp_ATR_up = False
                    self.temp_ATR_down = True
                    self.temp_ATR_big_value = self.temp_ATR_compare_database['big_value']
                    self.temp_ATR_big_then_value = self.temp_ATR_compare_database["big_then_value"]
                    self.pre_TXF_MXF_ATR = self.temp_ATR_big_value
                    if  130000000000 >= int(MatchTime) > 85500000000 and self.rolling_back:   
                        self.temp_big_value = self.temp_price_compare_database['big_value']
                        self.temp_small_value = self.temp_price_compare_database['small_value']
                        self.entry_signal = True
                    print(
                        f"{MatchTime}  ATR: {(self.TXF_MXF_ATR):>9.4f}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_ATR_big_then_value)}          高: {(self.temp_ATR_big_value):>9.4f}  {Fore.GREEN}現價: {int(self.new_price)}{Style.RESET_ALL}  {int(self.temp_price_compare_database['big_value']):<5d} : {int(self.temp_price_compare_database['small_value']):<5d}")

        self.execute_compare(
            self.temp_ATR_compare_database, MatchTime, value=self.TXF_MXF_ATR, then_value=self.new_price)

        if abs(self.pre_TXF_MXF_ATR - self.TXF_MXF_ATR) >= 1:
            temp = ""
            mark_timediff_num=0
            mark_timediff_price_per_num = 0
            mark_temp_big_price_num = 0
            mark_temp_small_price_num = 0 
            mark_temp_close_price_num = 0 
            temp_avg_price=0
            
            mark_timediff_color="Style.RESET_ALL"
            mark_timediff_price_per_color = "Style.RESET_ALL" 
            mark_temp_big_price_color = "Fore.YELLOW + Style.BRIGHT" 
            mark_temp_small_price_color = "Fore.YELLOW + Style.BRIGHT" 
            self.list_ATR_price.append(self.new_price)
            # 提取時間的各部分
            h1, m1, s1, ms1 = self.parse_time_string(MatchTime)
            # 將時間轉換為總毫秒數
            self.matchtime=self.to_total_milliseconds(h1, m1, s1, ms1)
            
            if self.pre_matchtime!=0 and self.matchtime!=0 :
                # 計算時間差
                # self.list_ATR_timediff_price_per.append(abs(self.matchtime-self.pre_matchtime))
                diff_ms = abs(self.matchtime-self.pre_matchtime)
                time_diff=diff_ms
                # 將毫秒轉回時間格式
                hours = diff_ms // (3600 * 1000)
                diff_ms %= 3600 * 1000
                minutes = diff_ms // (60 * 1000)
                diff_ms %= 60 * 1000
                seconds = diff_ms // 1000
                milliseconds = diff_ms % 1000
                time_diff_str = f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"
            else:
                time_diff_str="00:00:00.000"
                time_diff = 0
            
            self.list_ATR_timediff.append(time_diff)

            if self.temp_price_compare_database:
                    self.list_ATR_temp_big_price.append(self.temp_price_compare_database['big_value'])
                    self.list_ATR_temp_small_price.append(self.temp_price_compare_database['small_value'])
                    temp_avg_price = (self.temp_price_compare_database['big_value']+self.temp_price_compare_database['small_value'])/2
                   
            else:
                self.list_ATR_temp_big_price.append(self.new_price)
                self.list_ATR_temp_small_price.append(self.new_price)
                temp_avg_price = self.new_price
                
            if len(self.list_ATR_temp_big_price) > 1 and self.list_ATR_temp_big_price[-1] == self.price_compare_database['big_value']:
                self.is_dayhigh = True
            if len(self.list_ATR_temp_small_price) > 1 and self.list_ATR_temp_small_price[-1] == self.price_compare_database['small_value']:
                self.is_daylow = True

            if (self.list_ATR_temp_big_price[-1]-self.list_ATR_temp_small_price[-1])>0:
                time_price_per=abs(self.matchtime-self.pre_matchtime)/(self.list_ATR_temp_big_price[-1]-self.list_ATR_temp_small_price[-1])
            else:
                time_price_per=0
            
            self.list_ATR_timediff_price_per.append(time_price_per)
            self.conform_big_price = self.list_ATR_temp_big_price[-1]
            self.conform_small_price = self.list_ATR_temp_small_price[-1]
            
            if self.warning_signal:
                self.temp_total_spread = 0
                self.warning_signal = False
                self.temp_ATR_up = False
                self.temp_ATR_down = False
                # self.temp_price_compare_database = {}
            
            if len(self.list_ATR_price) > 2 and self.list_ATR_price[-2] > self.list_ATR_price[-1]:
                    mark_temp_close_price_num = 1
            elif len(self.list_ATR_price) > 2 and self.list_ATR_price[-2] < self.list_ATR_price[-1]:
                    mark_temp_close_price_num = 2
            
            # 1代表空 2代表多
            if len(self.list_ATR_temp_big_price) > 2 and self.list_ATR_temp_big_price[-2] >= self.list_ATR_temp_big_price[-1]:
                mark_temp_big_price_num=1
            elif len(self.list_ATR_temp_big_price) > 2 and self.list_ATR_temp_big_price[-2] < self.list_ATR_temp_big_price[-1]:
                mark_temp_big_price_num=2
                
            if len(self.list_ATR_temp_small_price) > 2 and self.list_ATR_temp_small_price[-2] > self.list_ATR_temp_small_price[-1]:
                mark_temp_small_price_num = 1
            elif len(self.list_ATR_temp_small_price) > 2 and self.list_ATR_temp_small_price[-2] <= self.list_ATR_temp_small_price[-1]:
                mark_temp_small_price_num = 2
                
            # if len(self.list_ATR_temp_big_price) > 3 and ((self.list_ATR_temp_big_price[-3] < self.list_ATR_temp_big_price[-2] > self.list_ATR_temp_big_price[-1]) or (self.list_ATR_temp_big_price[-4] < self.list_ATR_temp_big_price[-3] == self.list_ATR_temp_big_price[-2] > self.list_ATR_temp_big_price[-1])):
            #     mark_temp_big_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"  
                
            # if len(self.list_ATR_temp_small_price) > 3 and ((self.list_ATR_temp_small_price[-3] > self.list_ATR_temp_small_price[-2] < self.list_ATR_temp_small_price[-1]) or (self.list_ATR_temp_small_price[-4] > self.list_ATR_temp_small_price[-3] == self.list_ATR_temp_small_price[-2] < self.list_ATR_temp_small_price[-1])):
            #     mark_temp_small_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED" 
                        
            if len(self.list_ATR_timediff) > 1 and self.list_ATR_timediff[-2] > self.list_ATR_timediff[-1] and len(self.list_ATR_timediff_price_per) > 1 and self.list_ATR_timediff_price_per[-2] > self.list_ATR_timediff_price_per[-1]:
                mark_timediff_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"   
                mark_timediff_num=1
                mark_timediff_price_per_color = "Fore.BLACK + Style.BRIGHT + Back.WHITE"    
                mark_timediff_price_per_num=1 
                self.list_speedtime_big_price.append(self.conform_big_price)
                self.list_speedtime_small_price.append(self.conform_small_price)
                # if self.conform_big_price != 0 and self.conform_small_price != 0 and self.conform_close_price !=0 :
                #     if self.conform_big_price > self.list_ATR_temp_big_price[-1] and self.conform_small_price > self.list_ATR_temp_small_price[-1] and self.conform_close_price > self.list_ATR_price[-1]:
                #         temp = "空增速"   
                #     elif self.conform_big_price < self.list_ATR_temp_big_price[-1] and self.conform_small_price < self.list_ATR_temp_small_price[-1] and self.conform_close_price < self.list_ATR_price[-1]:
                #         temp = "多增速"
                # self.conform_big_price = self.list_ATR_temp_big_price[-1]
                # self.conform_small_price = self.list_ATR_temp_small_price[-1]
                # self.conform_close_price=self.list_ATR_price[-1]
            #     if temp_avg_price  > self.temp_TXF_MXF_ATR and mark_temp_close_price_num == 1 and mark_temp_big_price_num == 1 and mark_temp_small_price_num == 1:
            #         temp = "空增速"   
            #     elif  temp_avg_price < self.temp_TXF_MXF_ATR and mark_temp_close_price_num == 2 and mark_temp_big_price_num == 2 and mark_temp_small_price_num == 2:
            #         temp = "多增速"
            #     else:
            #         temp = "整理"
            # else:
            #     if temp_avg_price  > self.temp_TXF_MXF_ATR and mark_temp_close_price_num == 1 and mark_temp_big_price_num == 1 and mark_temp_small_price_num == 1:
            #         temp = "疑空"   
            #     elif  temp_avg_price < self.temp_TXF_MXF_ATR and mark_temp_close_price_num == 2 and mark_temp_big_price_num == 2 and mark_temp_small_price_num == 2:
            #         temp = "疑多"
            #     else:
            #         temp = "整理"
                    
            self.list_signal_str.append(temp) 
                
            # if len(self.list_signal_str) > 1 and temp_avg_price  > self.temp_TXF_MXF_ATR and mark_temp_big_price_num==2 and self.list_signal_str[-1]== "整理" and (self.list_signal_str[-2]== "多增速" or self.list_signal_str[-2]== "多" ):
            #        temp = "疑作頭"  
            #        self.list_signal_str.append(temp)
            # elif  len(self.list_signal_str) > 1 and temp_avg_price  < self.temp_TXF_MXF_ATR and mark_temp_small_price_num == 1 and self.list_signal_str[-1]== "整理" and (self.list_signal_str[-2]== "空增速" or self.list_signal_str[-2]== "空" ):
            #        temp = "疑打底"  
            #        self.list_signal_str.append(temp)  
            if mark_timediff_num == 1:   
                if self.is_dayhigh and temp_up_down_str == "↓" :
                    self.is_dayhigh = False
                    # self.conform_small_price = self.list_temp_tickbars_small_price[-1]
                    # self.conform_total_volume = self.list_temp_tickbars_total_volume[-1]
                    mark_temp_big_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
                    # temp = "疑作頭"
                    temp = "空:"+str(int(self.new_price))+" 損:"+str(int(self.list_ATR_temp_big_price[-1])+1)
                if self.is_daylow and temp_up_down_str == "↑" :
                    self.is_daylow = False
                    # self.conform_big_price = self.list_temp_tickbars_big_price[-1]
                    # self.conform_total_volume = self.list_temp_tickbars_total_volume[-1]
                    mark_temp_small_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
                    # temp = "疑打底" 
                    temp = "多:"+str(int(self.new_price))+" 損:"+str(int(self.list_ATR_temp_small_price[-1])-1)

            max_key = max(self.volumes_per_price, key=self.volumes_per_price.get)

            if self.pre_TXF_MXF_ATR > self.TXF_MXF_ATR and self.temp_price_compare_database:
                self.trending_up = False
                self.trending_down = True
                # if len(self.list_speedtime_big_price) > 2 and (self.list_speedtime_big_price[-3] < self.list_speedtime_big_price[-2] > self.list_speedtime_big_price[-1] and mark_timediff_num == 1):
                #     mark_temp_big_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
                # if len(self.list_speedtime_small_price) > 1 and (self.list_speedtime_small_price[-2] < self.list_speedtime_small_price[-1]) and mark_timediff_num == 1:
                #   mark_temp_small_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
                
                if temp == "疑空" or temp == "空增速":
                    print(
                        f"{Fore.GREEN}{Style.BRIGHT}{MatchTime} {(self.TXF_MXF_ATR):>9.4f}{Style.RESET_ALL}  {eval(mark_timediff_color)}{time_diff_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_ATR_temp_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_ATR_temp_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_timediff_price_per_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_TXF_MXF_total_volume ):<5d}:{int(self.temp_TXF_MXF_ATR):<5d}{Style.RESET_ALL}  高: {int(self.price_compare_database['big_value'])}  低: {int(self.price_compare_database['small_value'])}  {Fore.GREEN}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                elif temp == "疑多" or temp == "多增速":
                    print(
                        f"{Fore.GREEN}{Style.BRIGHT}{MatchTime} {(self.TXF_MXF_ATR):>9.4f}{Style.RESET_ALL}  {eval(mark_timediff_color)}{time_diff_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_ATR_temp_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_ATR_temp_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_timediff_price_per_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_TXF_MXF_total_volume):<5d}:{int(self.temp_TXF_MXF_ATR):<5d}{Style.RESET_ALL}  高: {int(self.price_compare_database['big_value'])}  低: {int(self.price_compare_database['small_value'])}  {Fore.RED}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                else:
                    print(
                        f"{Fore.GREEN}{Style.BRIGHT}{MatchTime} {(self.TXF_MXF_ATR):>9.4f}{Style.RESET_ALL}  {eval(mark_timediff_color)}{time_diff_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_ATR_temp_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_ATR_temp_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_timediff_price_per_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.GREEN}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_TXF_MXF_total_volume):<5d}:{int(self.temp_TXF_MXF_ATR):<5d}{Style.RESET_ALL}  高: {int(self.price_compare_database['big_value'])}  低: {int(self.price_compare_database['small_value'])}  {Fore.YELLOW}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                
                self.temp_price_compare_database = {}
                self.volumes_per_price = {}
                self.temp_TXF_MXF_total_volume = 0
                self.temp_TXF_MXF_TR = 0
                self.temp_TXF_MXF_ATR = 0
            elif self.pre_TXF_MXF_ATR < self.TXF_MXF_ATR:
                self.trending_up = True
                self.trending_down = False
                # if len(self.list_speedtime_small_price) > 2 and (self.list_speedtime_small_price[-3] > self.list_speedtime_small_price[-2] < self.list_speedtime_small_price[-1]) and mark_timediff_num == 1:
                #     mark_temp_small_price_color = "Fore.WHITE + Style.BRIGHT + Back.RED"
                # if len(self.list_speedtime_big_price) > 1 and (self.list_speedtime_big_price[-2] > self.list_speedtime_big_price[-1] and mark_timediff_num == 1):
                #     mark_temp_big_price_color = "Fore.WHITE + Style.BRIGHT + Back.GREEN"
                
                if temp == "疑多" or temp == "多增速":   
                    print(
                        f"{Fore.RED}{Style.BRIGHT}{MatchTime} {(self.TXF_MXF_ATR):>9.4f}{Style.RESET_ALL}  {eval(mark_timediff_color)}{time_diff_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_ATR_temp_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_ATR_temp_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_timediff_price_per_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_TXF_MXF_total_volume):<5d}:{int(self.temp_TXF_MXF_ATR):<5d}{Style.RESET_ALL}  高: {int(self.price_compare_database['big_value'])}  低: {int(self.price_compare_database['small_value'])}  {Fore.RED}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                elif temp == "疑空" or temp == "空增速":   
                    print(
                        f"{Fore.RED}{Style.BRIGHT}{MatchTime} {(self.TXF_MXF_ATR):>9.4f}{Style.RESET_ALL}  {eval(mark_timediff_color)}{time_diff_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_ATR_temp_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_ATR_temp_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_timediff_price_per_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_TXF_MXF_total_volume):<5d}:{int(self.temp_TXF_MXF_ATR):<5d}{Style.RESET_ALL}  高: {int(self.price_compare_database['big_value'])}  低: {int(self.price_compare_database['small_value'])}  {Fore.GREEN}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                else :   
                    print(
                        f"{Fore.RED}{Style.BRIGHT}{MatchTime} {(self.TXF_MXF_ATR):>9.4f}{Style.RESET_ALL}  {eval(mark_timediff_color)}{time_diff_str}{Style.RESET_ALL}  {eval(mark_temp_big_price_color)}{int(self.list_ATR_temp_big_price[-1]):<5d}{Style.RESET_ALL} : {eval(mark_temp_small_price_color)}{int(self.list_ATR_temp_small_price[-1]):<5d}{Style.RESET_ALL}  {eval(mark_timediff_price_per_color)}{temp_up_down_str}{Style.RESET_ALL}  {Fore.RED}{Style.BRIGHT}現: {int(self.new_price)}{Style.RESET_ALL}  {Fore.YELLOW}{Style.BRIGHT}{int(self.temp_TXF_MXF_total_volume):<5d}:{int(self.temp_TXF_MXF_ATR):<5d}{Style.RESET_ALL}  高: {int(self.price_compare_database['big_value'])}  低: {int(self.price_compare_database['small_value'])}  {Fore.YELLOW}{Style.BRIGHT}{temp}{Style.RESET_ALL}")
                
                self.temp_price_compare_database = {}
                self.volumes_per_price = {}
                self.temp_TXF_MXF_total_volume = 0
                self.temp_TXF_MXF_TR = 0
                self.temp_TXF_MXF_ATR = 0
            self.pre_TXF_MXF_ATR = self.TXF_MXF_ATR
            self.pre_matchtime=self.matchtime

    # 提取時間的各部分
    def parse_time_string(self,time_string):
        hours = int(time_string[:2])
        minutes = int(time_string[2:4])
        seconds = int(time_string[4:6])
        milliseconds = int(time_string[6:9])
        return hours, minutes, seconds, milliseconds

    # 將時間轉換為總毫秒數
    def to_total_milliseconds(self,hours, minutes, seconds, milliseconds):
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds

    def short_peak(self, MatchTime, direction, Is_simulation):
        """
        當已跌破關鍵K低點 or 已突破關鍵K高點,是要等反彈或回檔或追價。

        參數：
        MatchTime (str): 記錄當時的時間。
        direction ("空" or "多"): 整個策略只進場空或進場多。

        注意事項：
        - self.ask_bid < 3 表示內外盤價差距要小,預防快市價位亂跳。
        - 。
        """
        self.short_signal["signal"] = False
        self.third_step_price = self.new_price
        # TR = abs(self.price_compare_database['small_value']-self.third_step_price)-abs(
        #     self.price_compare_database['big_value']-self.third_step_price)
        # self.TRi.append(TR)
        # self.ATR = round(sum(self.TRi)/len(self.TRi))
        if self.third_step_price:
            if self.temp_price_compare_database:
                temp_big_value = self.temp_price_compare_database['big_value']
                temp_small_value = self.temp_price_compare_database['small_value']
            else:
                temp_big_value = 0
                temp_small_value = 0
            # print(
            #     f"{MatchTime}  ATR: {(self.TXF_MXF_ATR):>9.4f}  暫高價: {int(temp_big_value):<5d}  暫低價: {int(temp_small_value):<5d}  高平均: {int(self.third_step_price)}  最高價: {int(self.price_compare_database['big_value'])}  最低價: {int(self.price_compare_database['small_value'])}")


    def handle_entry_signal(self, MatchTime, Is_simulation):
        """
        當已跌破關鍵K低點 or 已突破關鍵K高點,是要等反彈或回檔或追價。

        參數：
        MatchTime (str): 記錄當時的時間。
        direction ("空" or "多"): 整個策略只進場空或進場多。

        注意事項：
        - self.ask_bid < 3 表示內外盤價差距要小,預防快市價位亂跳。
        - 。
        """
        self.Index = -1
        self.short_signal["order_time"] = MatchTime
        self.short_signal["order_price"] = self.temp_big_value  #self.temp_price_compare_database['big_value']
        self.short_signal["profit_stop_price"] = 42-self.profit
        self.entry_price = self.new_price
        self.count += 1
        print(
            f'{MatchTime} {Fore.CYAN}{Style.BRIGHT}第 {self.count} 筆  空   {self.short_signal["order_time"]}  出場價: {int(self.temp_big_value)}  進場價: {int(self.entry_price)} {Style.RESET_ALL}')

    def handle_short_exit(self, MatchTime):
        self.entry_signal = False
        self.Index = 0
        self.profit += (self.entry_price-self.new_price-2)
        print(
            f'{Fore.YELLOW}{Style.BRIGHT}第 {self.count} 筆 出場  {MatchTime}  出場價: {self.new_price}  損益: {self.profit}{Style.RESET_ALL}')

    def calculate_XF(self, database, RefPri,  MatchQty, TolMatchQty, MatchTime, Is_simulation):
        if not database:
            self.tmp_qty_spread = self.init_database(database, RefPri, TolMatchQty, MatchQty,
                                                     self.new_price, self.tmp_qty)
            # self.execute_per_price()
        elif database["current_total_volume"] < float(TolMatchQty):            
            self.num=self.num+1
            database["current_total_volume"] = float(
                TolMatchQty)
            database["total_volume"] += float(MatchQty)
            self.tmp_qty_spread = self.execute_bidask_spread(database,
                                                             self.new_price, self.tmp_qty)
            # self.execute_per_price()
            self.calculate_ATR(MatchTime, Is_simulation)

    def execute_per_price(self):
        if self.new_price in self.volumes_per_price:
            self.volumes_per_price[self.new_price] += self.tmp_qty
            self.spreads_per_price[self.new_price] += self.tmp_qty_spread
        else:
            self.volumes_per_price[self.new_price] = self.tmp_qty
            self.spreads_per_price[self.new_price] = self.tmp_qty_spread
            sorted_keys = reversed(
                sorted(self.spreads_per_price.keys()))  # 從高到低
            for key in sorted_keys:
                if self.spreads_per_price[key] < 0:
                    self.key_price = key
                    break
            else:
                self.key_price = 0
            # 1. dict.items返回可遍历的(键, 值) 元组list。 2. 將dict按key排序返回list內含(键, 值)
            # 3. 轉換成dict後,取其所有值values,再將轉換成list
            # self.sorted_spreads_per_price = list(
            #     dict(sorted(self.spreads_per_price.items())).values())

    def init_database(self, database, RefPri, TolMatchQty, MatchQty,  new_price, tmp_qty):
        database["match_pri"] = float(RefPri)
        database["current_total_volume"] = float(TolMatchQty)
        database["total_volume"] = float(MatchQty)
        return self.execute_bidask_spread(database, new_price, tmp_qty)

    def execute_bidask_spread(self, database, new_price, tmp_qty):
        if new_price > database["match_pri"]:
            tmp = tmp_qty
            database["up"] = True
            database["down"] = False
        elif new_price < database["match_pri"]:
            tmp = -tmp_qty
            database["up"] = False
            database["down"] = True
        elif database.get("up"):  # 這裡使用get()取值,如找不到鍵,會回傳None,而不會報錯
            tmp = tmp_qty
        elif database.get("down"):
            tmp = -tmp_qty
        elif new_price == database["match_pri"]:  # 預防開盤價等於昨收價
            tmp = tmp_qty
            database["up"] = True
            database["down"] = False

        database["match_pri"] = new_price
        TR = self.new_price * self.tmp_qty
        self.TXF_MXF_TR += TR
        self.TXF_MXF_ATR = self.TXF_MXF_TR / \
            (self.TXF_database["total_volume"] *
             4+self.MXF_database["total_volume"])
        return tmp

    def execute_compare(self, database, MatchTime, value, then_value):  # then_value 當時的變量
        if not database and value != 0:
            database["big_value"] = value
            database["small_value"] = value
            database["big_then_value"] = then_value
            database["small_then_value"] = then_value
            database["big_value_time"] = float(MatchTime)
            database["small_value_time"] = float(MatchTime)
            database["big_array"] = [MatchTime,
                                     database["big_value"], then_value]
            database["small_array"] = [MatchTime,
                                       database["small_value"], then_value]
            database["up"] = False
            database["down"] = False
        elif database and value > database["big_value"]:
            # database["first_step_signal"] = True
            database["big_value"] = value
            database["big_then_value"] = then_value
            database["big_value_time"] = float(MatchTime)
            database["big_array"] = [MatchTime,
                                     database["big_value"], then_value]
            database["up"] = True
            database["down"] = False
        elif database and value < database["small_value"]:
            database["small_value"] = value
            database["small_then_value"] = then_value
            database["small_value_time"] = float(MatchTime)
            database["down"] = True
            database["small_array"] = [MatchTime,
                                       database["small_value"], then_value]
            database["up"] = False
            database["down"] = True

    def find_peaks(self, bars: dict):
        # 找到柱状图的平均值
        average_height = (sum(bars.values()) / len(bars))

        # 找到所有高于平均值的柱状設為True,低於平均值設為False
        above_average = {key: True if value >
                         average_height else False for key, value in bars.items()}
        keys = sorted(bars, reverse=True)
        # 找到所有的骆驼峰
        self.peaks = []
        temp_peak = []
        for key in keys:
            if above_average[key]:
                self.peaks.append(key)
        return self.peaks

    


    def calculate_and_update(self):
        try:
            # {int():<5d} : {int(self.temp_price_compare_database['small_value']):<5d}
            if  self.temp_entry_price>0:
                font_color="black"
                self.big_value_var.set(str(int(self.price_compare_database['big_value'])))
                self.small_value_var.set(str(int(self.price_compare_database['small_value'])))
                self.a_var.set(str(int(max((self.peaks)))))
                self.b_var.set(str(int(min((self.peaks)))))
                self.c_var.set(str(int(self.temp_entry_price)))
                # 計算支撐和壓力數值
                pressureAvg = float(self.a_var.get())
                supportAvg = float(self.b_var.get())
                pressureNum = float(self.big_value_var.get())
                supportNum = float(self.small_value_var.get())
                pressure_support_keypri = float(self.c_var.get())
                
                pressure_diff = pressureNum - pressure_support_keypri  # 計算差子
                support_diff = pressure_support_keypri - supportNum
                sum_diff = pressure_diff + support_diff
                
                # 計算反彈和回檔差價的比率
                # if pressure_diff >= support_diff:
                #     pressure_ratio = round((support_diff/sum_diff), 3)
                #     support_raito = round((1-pressure_ratio), 3)
                # else:
                #     support_raito = round((pressure_diff/sum_diff), 3)
                #     pressure_ratio = round((1-support_raito), 3)

                # 計算壓力的比率值（四捨五入到整數）
                # pressureNum_ratio = round(
                #     pressure_support_keypri + pressure_diff * pressure_ratio)
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
                # supportNum_ratio = round(
                #     pressure_support_keypri - (support_diff * support_raito))
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
                diffNum = pressureNum-supportNum

                # 投資建議
                # if pressure_diff < diffNum and support_diff > diffNum:
                #     trend_advice = "趨勢向上-做多"
                #     expectation_value = round(
                #         (pressureNum-self.new_price)/(self.new_price-supportNum), 3)
                #     font_color = "red"
                # elif pressure_diff > diffNum and support_diff < diffNum:
                #     trend_advice = "趨勢向下-做空"
                #     expectation_value = round(
                #         (self.new_price-supportNum)/(pressureNum-self.new_price), 3)
                #     font_color = "#006400"
                if pressure_diff > support_diff:
                    trend_advice = "偏空操作"
                    expectation_value = round(
                        (self.new_price-supportNum)/(pressureNum-self.new_price), 3)
                    font_color = "#006400"
                elif pressure_diff < support_diff:
                    trend_advice = "偏多操作"
                    expectation_value = round(
                        (pressureNum-self.new_price)/(self.new_price-supportNum), 3)
                    font_color = "red"
                else:
                    trend_advice = "整理"
                    expectation_value = 0
                    font_color = "black"
                    
                # 更新結果標籤
                self.result_label.config(font=("Arial", 16, "bold"),
                                    text=f"壓力: 反彈0.786價: {pressureNum_ratio_786}\n"
                                    f"壓力: 反彈0.618價: {pressureNum_ratio_618}\n"
                                    f"壓力: 反彈  0.5  價: {pressureNum_ratio_5}\n"
                                    f"壓力: 反彈0.382價: {pressureNum_ratio_382}\n"
                                    f"壓力: 反彈0.236價: {pressureNum_ratio_236}\n\n"
                                    # f"壓力差: {int(pressure_diff)} 反彈{pressure_ratio}價: {pressureNum_ratio}\n\n"
                                    f"壓力差: {int(pressure_diff)}\n"
                                    f"高低價差: {int(diffNum)}  {trend_advice}\n"
                                    f"期望值: {expectation_value:>6.3f}  現價: {int(self.new_price)}\n"
                                    # f"支撐差: {int(support_diff)} 回檔{support_raito}價: {supportNum_ratio}\n"
                                    f"支撐差: {int(support_diff)}\n\n"
                                    f"支撐: 回檔0.236價: {supportNum_ratio_236}\n"
                                    f"支撐: 回檔0.382價: {supportNum_ratio_382}\n"
                                    f"支撐: 回檔  0.5  價: {supportNum_ratio_5}\n"
                                    f"支撐: 回檔0.618價: {supportNum_ratio_618}\n"
                                    f"支撐: 回檔0.786價: {supportNum_ratio_786}",fg=font_color
                                    )
                
            elif self.temp_trend_advice=="股價創高-做多":
                self.big_value_var.set(str(int(self.price_compare_database['big_value'])))
                self.a_var.set(str(int(max((self.peaks)))))
                # self.b_var.set(str(int(min((self.peaks)))))
                trend_advice = "股價持續創新高..."
                self.result_label.config(font=("Arial", 22, "bold"),
                                    text=f"\n\n    {trend_advice}\n"
                                         f"        現價: {int(self.new_price)}\n",fg="red")
            elif self.temp_trend_advice=="股價創低-做空":
                # self.a_var.set(str(int(max((self.peaks)))))
                self.b_var.set(str(int(min((self.peaks)))))
                self.small_value_var.set(str(int(self.price_compare_database['small_value'])))
                trend_advice = "股價持續創新低..."
                self.result_label.config(font=("Arial", 22, "bold"),
                                     text=f"\n\n    {trend_advice}\n"
                                          f"        現價: {int(self.new_price)}\n",fg="#006400")
                    
        except ValueError:
            # messagebox.showerror("錯誤", "請輸入有效的數字！")
            pass
        except ZeroDivisionError:
            pass  # 捕获 ZeroDivisionError，但什么都不做
