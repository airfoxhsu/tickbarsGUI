"""
order_manager.py
----------------
管理「進場 / 止損 / 停利 / 移動停損 / 自動收盤平倉」邏輯。
此檔案集中管理多空倉位狀態，並透過 frame.OnOrderBtn 與 GUI 互動。
"""

import datetime
import threading
import time

import wx
from colorama import Fore, Style

from .calculator import calc_profit_targets, parse_profit_triplet
from .ui_updater import UIUpdater
from .notifier import Notifier


class OrderManager:
    """
    多空倉位與停損 / 停利 / 自動平倉的集中管理類別。

    主要負責：
    - 接收策略層「進場訊號」並更新 GUI / 通知
    - 真實下單（透過 frame.OnOrderBtn）
    - 觸發「止損」、「停利」、「移動停損」
    - 盤中 / 收盤自動平倉（時間條件觸發）
    """

    def __init__(self, frame, ui: UIUpdater, notifier: Notifier) -> None:
        """
        建立 OrderManager。

        參數
        -----
        frame:
            主視窗物件，必須提供：
            - acclist_combo：帳號下拉選單（用來判斷是否已連線）
            - chkBuy / chkSell：是否允許自動下多 / 空單的 CheckBox
            - qtyLabel：顯示目前可用口數的 Label
            - infoDataGrid：報價 / 價格資訊表格，用於自動收盤平倉讀取市價
            - OnOrderBtn(...)：實際呼叫元大 API 下單的函數
        ui:
            UIUpdater 物件，負責更新 GUI 上的訊號列與價位選單。
        notifier:
            Notifier 物件，負責 log、Telegram 通知與音效。
        """
        # === 依賴物件 ===
        self.frame = frame          # 主 GUI 視窗，負責真正的下單與帳號資訊
        self.ui = ui                # UI 更新器（訊號列 / 價格選單）
        self.notifier = notifier    # 通知與 log 管理器

        # === 持倉狀態（True 代表目前有實際部位） ===
        self.trading_buy: bool = False   # 是否持有多單
        self.trading_sell: bool = False  # 是否持有空單

        # === 進場價格（實際進場價，用於計算移動停損） ===
        self.entry_price_buy: int = 0    # 多單進場價
        self.entry_price_sell: int = 0   # 空單進場價

        # === 止損價位 ===
        self.stopLoss_buy: int = 0       # 多單目前的止損價（可被移動停損邏輯修改）
        self.stopLoss_sell: int = 0      # 空單目前的止損價（可被移動停損邏輯修改）

        # === 停利目標字串（格式為 "p1:p2:p3"） ===
        self.profit_buy_str: str = ""    # 多單停利目標三段價位字串
        self.profit_sell_str: str = ""   # 空單停利目標三段價位字串

        # === 訊號標記（策略層用來判斷是否已有訊號） ===
        self.buy_signal: bool = False    # 是否目前有「多單進場訊號」
        self.sell_signal: bool = False   # 是否目前有「空單進場訊號」

        #給start_auto_liquidation加一個停止旗標    
        self._auto_thread_stop = threading.Event()
        self._auto_thread = None

        self.forbidden_warned = False   # 禁止時段是否警告過


    def _safe_order(self, side, price, offset):
        """安全封裝，確保所有傳入 OnOrderBtn 的參數都是字串。"""
        try:
            self.frame.OnOrderBtn(
                event=None,
                S_Buys=str(side),
                price=str(price),
                offset=str(offset),
            )
        except Exception as e:
            self.notifier.error(f"OnOrderBtn 失敗: {e}")    

    # ========= 進場 =========
    # 產生進場訊號（不送單）
    def signal_trade(
        self,
        direction: str,
        entry_price: int,
        trigger_price: int,
        stop_loss: int,
        fibonacci_str: str,
        match_time: str,
    ) -> str:
        """
        產生進場訊號，不執行真實下單。

        用途
        -----
        策略層「發現進場機會」時呼叫，
        - 設定進場 / 停損 / 停利價位
        - 更新 GUI 的訊號列
        - 更新 Fibonacci 價格選單
        - 發送通知與音效

        參數
        -----
        direction:
            方向字串，"多" 代表作多、"空" 代表放空。
        entry_price:
            策略計算的理論進場價（用於顯示在訊號列）。
        trigger_price:
            實際觸發價（通常用來填入真實下單價，也會灌入 entry_price_buy/sell）。
        stop_loss:
            初始止損價。
        fibonacci_str:
            費波那契價位字串，例如："27700:27800:27900:28000"。
        match_time:
            觸發訊號的時間（字串，HH:MM:SS）。

        回傳
        -----
        label:
            "進場多: xxx" 或 "進場空: xxx"，給呼叫者用來更新其他 UI。
        """
        # 計算三段停利價位（profit_1, profit_2, profit_3）
        p1, p2, p3 = calc_profit_targets(entry_price, stop_loss, direction)
        profits = [p1, p2, p3]
        # 將 Fibonacci 價格字串拆成清單，並去除空白與空字串
        levels = [s.strip() for s in fibonacci_str.split(":") if s.strip()]

        if direction == "多":
            row = 1                  # GUI 訊號列的「多單」所在列索引
            color = wx.RED           # 多單訊號顯示為紅色
            self.buy_signal = True   # ✅ 標記目前有多單訊號
            # 實際進場價使用 trigger_price（與策略計算價可能略有差異）
            self.entry_price_buy = trigger_price
            self.stopLoss_buy = stop_loss
            # 記錄多單的三段停利價位
            self.profit_buy_str = f"{p1}:{p2}:{p3}"
            # 使用第 4 段 Fibonacci 作為「主訊號價」顯示（呼叫者既有邏輯）
            # label = f"進場多: {levels[3] if len(levels) > 3 else entry_price}"
            label = f"進場多: {self.entry_price_buy}"
            if self.frame.chkBuy.IsChecked() and fibonacci_str and levels:
                self.ui.set_price_combo_items(levels, profits)
        else:
            row = 0                   # GUI 訊號列的「空單」所在列索引
            color = wx.GREEN          # 空單訊號顯示為綠色
            self.sell_signal = True   # ✅ 標記目前有空單訊號
            self.entry_price_sell = trigger_price
            self.stopLoss_sell = stop_loss
            self.profit_sell_str = f"{p1}:{p2}:{p3}"
            # label = f"進場空: {levels[3] if len(levels) > 3 else entry_price}"
            label = f"進場空: {self.entry_price_sell}"
            if self.frame.chkSell.IsChecked() and fibonacci_str and levels:
                self.ui.set_price_combo_items(levels, profits)

        # === UI 顯示更新 ===
        # 在 GUI 訊號列中顯示：進場價 / 止損 / 三段停利價位
        self.ui.update_signal_row(
            row, entry_price, stop_loss, p1, p2, p3, color)

        # === Fibonacci 價格設定 ===
        # 若有提供 Fibonacci 價格，更新 GUI 上的價格選單。
        # if fibonacci_str and levels:
        #     self.ui.set_price_combo_items(levels)

        # === 發出訊號通知 ===
        # 簡短版訊息（給 Telegram）
        level_text = self.entry_price_buy if direction == '多' else self.entry_price_sell
        # if len(levels) > 3:
        #     level_text = levels[3]
        # else:
        #     level_text = str(entry_price)

        msg_sms = (
            f"{match_time}  "
            f"{'作多訊號' if direction == '多' else '放空訊號'}: {level_text}  "
            f"止損: {stop_loss}  停利: {p1}"
        )
        # 詳細版訊息（包含完整 Fibonacci & 三段停利）
        msg = (
            f"{match_time}  "
            f"{'作多訊號' if direction == '多' else '放空訊號'}: {entry_price}  "
            f"費波: {fibonacci_str} 止損: {stop_loss}  停利: {p1} : {p2} : {p3}"
        )
        self.notifier.log(msg, Fore.CYAN + Style.BRIGHT)
        self.notifier.send_telegram_if_enabled(msg_sms)
        self.notifier.play_sound_if_enabled()

        return label

    # === 真實下單 ===
    def execute_trade(
        self,
        direction: str,
        trigger_price: int,
        match_time: str,
    ) -> None:
        """
        真實下單執行。

        須在已呼叫 :meth:`signal_trade` 並設定好
        entry_price_xxx / stopLoss_xxx / profit_xxx_str 後使用。

        參數
        -----
        direction:
            "多" 代表作多、"空" 代表放空。
        trigger_price:
            真實下單價（通常等於訊號觸發價）。
        match_time:
            下單時間（字串，HH:MM:SS），用於紀錄在 log / 通知中。

        邏輯
        -----
        1. 檢查是否已經有同方向部位（避免重複開倉）
        2. 檢查是否已連線（acclist_combo 有帳號）
        3. 檢查 GUI 上是否允許「自動下多 / 下空」
        4. 若允許，呼叫 frame.OnOrderBtn 實際送單
        5. 送單後標記 trading_buy/trading_sell = True
        """
        # === 禁止時段濾網 ===
        if self._is_forbidden_time(match_time):
            if not self.forbidden_warned:  
                self.notifier.warn(f"{match_time} 禁止時段，不執行真實下單。")
                self.forbidden_warned = True
            return

    
        # === 防重複開倉 ===
        if direction == "多" and self.trading_buy:
            self.notifier.log("⚠️ 已有多單，不重複開倉。", Fore.YELLOW)
            return
        if direction == "空" and self.trading_sell:
            self.notifier.log("⚠️ 已有空單，不重複開倉。", Fore.YELLOW)
            return

        # 將中文方向轉成 API 需要的買賣別（B=買進, S=賣出）
        side = "B" if direction == "多" else "S"
        offset = "0"  # 0: 開倉, 1: 平倉
        price = int(trigger_price)

        try:
            # 僅在已有帳號資料時才嘗試自動下單
            if self.frame.acclist_combo.GetCount() != 0:
                # 檢查 GUI 上「是否允許自動下單」
                if ((direction == "多" and self.frame.chkBuy.IsChecked()) or
                        (direction == "空" and self.frame.chkSell.IsChecked())):
                    # 實際呼叫 Yuanta API 下單                   
                    self._safe_order(
                        side=str(side),
                        price=str(price),
                        offset=str(offset),
                    )
                    # 下單後將口數標記為「未連」，等下一次更新
                    self.frame.qtyLabel.SetLabel("未連")

                    # === 成功訊息 ===
                    msg = f"{match_time}  實際{direction}下單成功: {price}"
                    self.notifier.log(msg, Fore.MAGENTA + Style.BRIGHT)
                    self.notifier.send_telegram_if_enabled(msg)

            # === 標記持倉狀態 ===
            if direction == "多":
                self.trading_buy = True
            else:
                self.trading_sell = True

        except Exception as e:  # noqa: BLE001 - 需確保任何錯誤都能被記錄
            self.notifier.error(f"自動下單失敗: {e}")

    # ========= 止損 =========
    def exit_stoploss(
        self,
        direction: str,
        price: int,
        match_time: str,
    ) -> None:
        """
        觸發止損出場（策略層主動呼叫）。

        參數
        -----
        direction:
            "多" 代表原本持有多單，止損時要賣出平倉；
            "空" 代表原本持有空單，止損時要買回平倉。
        price:
            止損觸發價（整數）。
        match_time:
            觸發止損的時間（字串）。

        邏輯
        -----
        - 依 direction 決定：
          - row：需重置的 GUI 訊號列索引
          - side：平倉方向（多單→賣出 S、空單→買回 B）
        - 若有允許自動下單，便以 offset="1" 呼叫 OnOrderBtn 平倉
        - 更新 trading_xxx / signal_xxx 與 GUI 顯示
        """
        if direction == "多":
            row = 1
            text = "作多止損"
            side = "S"  # 多單止損 → 賣出平倉
            self.trading_buy = False
            self.buy_signal = False
            self.profit_buy_str = ""
            self.entry_price_buy = 0
        else:
            row = 0
            text = "放空止損"
            side = "B"  # 空單止損 → 買回平倉
            self.trading_sell = False
            self.sell_signal = False
            self.profit_sell_str = ""
            self.entry_price_sell = 0

        # === 真正執行平倉委託 ===
        try:
            if self.frame.acclist_combo.GetCount() != 0:
                # 檢查 GUI 上「是否允許自動下單」
                if ((direction == "多" and self.frame.chkBuy.IsChecked()) or
                        (direction == "空" and self.frame.chkSell.IsChecked())):
                    val = self.frame.qtyLabel.GetLabel()
                    qty = int(val) if val.isdigit() else 0
                    if qty > 0:
                        self._safe_order(
                        side=str(side),
                        price=str(price),
                        offset=str("1"),
                          )
                        self.frame.qtyLabel.SetLabel("未連")

        except Exception:  # noqa: BLE001
            self.notifier.error("止損平倉下單失敗，請檢查 OnOrderBtn 或價位設定。")
        # 重置旗標，下次會再印一次
        self.forbidden_warned = False
        msg = f"{match_time}  {text}: {int(price)}  平倉不悔"
        self.notifier.log(msg, Fore.YELLOW + Style.BRIGHT)
        self.notifier.send_telegram_if_enabled(msg)

        # 重置 GUI 訊號列與價格選單狀態
        self.ui.reset_signal_row(row, text)
        self.ui.reset_price_select_state()

    # ========= 停利 =========
    def _exit_takeprofit_all(
        self,
        direction: str,
        price: int,
        match_time: str,
        profit_str: str,
    ) -> None:
        """
        第三段停利價達成時，全部平倉了結。

        參數
        -----
        direction:
            "多" 或 "空"，代表原本持有的方向。
        price:
            停利觸發價位。
        match_time:
            停利觸發時間，用於 log。
        """
        tag = "多單" if direction == "多" else "空單"
        msg = f"{match_time} 🏁 {tag}觸及 {profit_str} → 平倉 {int(price)}"
        self.notifier.log(msg, Fore.MAGENTA + Style.BRIGHT)

        side = "S" if direction == "多" else "B"

        try:
            if self.frame.acclist_combo.GetCount() != 0:
                # 檢查 GUI 上「是否允許自動下單」
                if ((direction == "多" and self.frame.chkBuy.IsChecked()) or
                        (direction == "空" and self.frame.chkSell.IsChecked())):
                    val = self.frame.qtyLabel.GetLabel()
                    qty = int(val) if val.isdigit() else 0
                    if qty > 0:
                        self._safe_order(
                        side=str(side),
                        price=str(price),
                        offset=str("1"),
                          )
                        self.frame.qtyLabel.SetLabel("未連")

        except Exception:  # noqa: BLE001
            self.notifier.error("停利平倉下單失敗，請檢查 OnOrderBtn。")

        # 平倉後重置持倉與訊號狀態
        if direction == "多":
            self.trading_buy = False
            self.buy_signal = False
            self.profit_buy_str = ""
            self.entry_price_buy = 0
        else:
            self.trading_sell = False
            self.sell_signal = False
            self.profit_sell_str = ""
            self.entry_price_sell = 0
            
        # 重置旗標，下次會再印一次
        self.forbidden_warned = False

    # ========= 移動停利 =========
    def update_trailing_profit(self, current_price: float, match_time: str) -> None:
        """
        每次價格更新時檢查是否觸及 profit_1 / profit_2 / profit_3，
        並依照「移動停損」規則調整 stopLoss_xxx 或全數出場。

        參數
        -----
        current_price:
            目前市價（可為 float，函式內會轉成 int）。
        match_time:
            當前時間字串（用於 log）。

        規則（空單）
        -----------
        - 價格 <= profit_1：
            若 stopLoss_sell > entry_price_sell，則將止損價移到進場價。
        - 價格 <= profit_2：
            若 stopLoss_sell > profit_1，則將止損價移到 profit_1。
        - 價格 <= profit_3：
            觸發 _exit_takeprofit_all("空") 全數平倉。

        規則（多單）
        -----------
        - 價格 >= profit_1：
            若 stopLoss_buy < entry_price_buy，則將止損價移到進場價。
        - 價格 >= profit_2：
            若 stopLoss_buy < profit_1，則將止損價移到 profit_1。
        - 價格 >= profit_3：
            觸發 _exit_takeprofit_all("多") 全數平倉。
        """
        price = int(current_price)

        # === 空單移動停損 ===
        if self.trading_sell and self.profit_sell_str:
            p1, p2, p3 = parse_profit_triplet(self.profit_sell_str)
            if p1 and p2 and p3 and self.entry_price_sell:
                if self.frame.chkProfit.IsChecked():
                    raw = self.frame.ktprice_combo.GetValue()
                    # === 保護 1：空白 → 不啟動此模式 ===
                    if not raw or not raw.strip():
                        return
                    # === 保護 2：必須是純數字 ===
                    if not raw.isdigit():
                        self.notifier.log(
                            f"{match_time} ⚠️ 警告：KT Price 不是合法數字 → 忽略單一停利模式",
                            Fore.YELLOW + Style.BRIGHT,
                        )
                        return
                    p = int(raw)
                    if price <= p and self.frame.chkSell.IsChecked():
                        self._exit_takeprofit_all(
                            "空", price, match_time, str(p))
                    # elif price <= p2:
                    #     self._exit_takeprofit_all("空", price, match_time,"profit_2")
                    # elif price <= p3:
                    #     self._exit_takeprofit_all("空", price, match_time,"profit_3")

                else:
                    if price <= p1 and self.stopLoss_sell > self.entry_price_sell:
                        self.stopLoss_sell = self.entry_price_sell
                        self.notifier.log(
                            f"{match_time} 🟢 空單觸及 profit_1 → 停損改至進場價 {self.stopLoss_sell}",
                            Fore.CYAN + Style.BRIGHT,
                        )
                    elif price <= p2 and self.stopLoss_sell > p1:
                        self.stopLoss_sell = p1
                        self.notifier.log(
                            f"{match_time} 🟢 空單觸及 profit_2 → 停損改至 {self.stopLoss_sell}",
                            Fore.CYAN + Style.BRIGHT,
                        )
                    elif price <= p3 and self.frame.chkSell.IsChecked():
                        self._exit_takeprofit_all(
                            "空", price, match_time, "profit_3")

        # === 多單移動停損 ===
        if self.trading_buy and self.profit_buy_str:
            p1, p2, p3 = parse_profit_triplet(self.profit_buy_str)
            if p1 and p2 and p3 and self.entry_price_buy:
                if self.frame.chkProfit.IsChecked():
                    raw = self.frame.ktprice_combo.GetValue()
                    # === 保護 1：空白 → 不啟動此模式 ===
                    if not raw or not raw.strip():
                        return
                    # === 保護 2：必須是純數字 ===
                    if not raw.isdigit():
                        self.notifier.log(
                            f"{match_time} ⚠️ 警告：KT Price 不是合法數字 → 忽略單一停利模式",
                            Fore.YELLOW + Style.BRIGHT,
                        )
                        return
                    p = int(raw)
                    if price >= p and self.frame.chkBuy.IsChecked():
                        # BUG 修正：原本少傳 match_time，會造成 TypeError
                        self._exit_takeprofit_all(
                            "多", price, match_time, str(p))
                    # elif price >= p2:
                    #     # BUG 修正：原本少傳 match_time，會造成 TypeError
                    #     self._exit_takeprofit_all("多", price, match_time,"profit_2")
                    # elif price >= p3:
                    #     # BUG 修正：原本少傳 match_time，會造成 TypeError
                    #     self._exit_takeprofit_all("多", price, match_time,"profit_3")
                else:
                    if price >= p1 and self.stopLoss_buy < self.entry_price_buy:
                        self.stopLoss_buy = self.entry_price_buy
                        self.notifier.log(
                            f"{match_time} 🟢 多單觸及 profit_1 → 停損改至進場價 {self.stopLoss_buy}",
                            Fore.CYAN + Style.BRIGHT,
                        )
                    elif price >= p2 and self.stopLoss_buy < p1:
                        self.stopLoss_buy = p1
                        self.notifier.log(
                            f"{match_time} 🟢 多單觸及 profit_2 → 停損改至 {self.stopLoss_buy}",
                            Fore.CYAN + Style.BRIGHT,
                        )
                    elif price >= p3 and self.frame.chkBuy.IsChecked():
                        # BUG 修正：原本少傳 match_time，會造成 TypeError
                        self._exit_takeprofit_all(
                            "多", price, match_time, "profit_3")

    def check_stoploss_triggered(self, price: int, match_time: str) -> None:
        """
        檢查是否觸及「硬性止損價」，若觸發則立刻執行平倉委託。

        通常在每筆 tick 更新時呼叫：
        - 放空：若價格 >= stopLoss_sell 則觸發止損，買回平倉。
        - 作多：若價格 <= stopLoss_buy 則觸發止損，賣出平倉。

        參數
        -----
        price:
            目前價格（整數）。
        match_time:
            觸發檢查時間字串，用於 log。
        """
        # ---- 放空止損 ----
        if getattr(self, "trading_sell", False) and getattr(self, "stopLoss_sell", 0):
            if price >= self.stopLoss_sell:
                msg = f"{match_time} 🟥 空單觸發止損價 {self.stopLoss_sell}，執行平倉"
                self.notifier.log(msg, Fore.YELLOW + Style.BRIGHT)
                self.trading_sell = False
                self.sell_signal = False
                try:
                    if self.frame.acclist_combo.GetCount() != 0 and self.frame.chkSell.IsChecked():
                        val = self.frame.qtyLabel.GetLabel()
                        qty = int(val) if val.isdigit() else 0
                        if qty > 0:
                            # 檢查 GUI 上「是否允許自動下單」
                            self._safe_order(
                            side=str("B"),
                            price=str(price),
                            offset=str("1"),
                            )
                            self.frame.qtyLabel.SetLabel("未連")
                except Exception:  # noqa: BLE001
                    self.notifier.error("⚠️ 放空止損平倉下單失敗，請檢查 OnOrderBtn。")

        # ---- 作多止損 ----
        if getattr(self, "trading_buy", False) and getattr(self, "stopLoss_buy", 0):
            if price <= self.stopLoss_buy:
                msg = f"{match_time} 🟥 多單觸發止損價 {self.stopLoss_buy}，執行平倉"
                self.notifier.log(msg, Fore.YELLOW + Style.BRIGHT)
                self.trading_buy = False
                self.buy_signal = False
                try:
                    if self.frame.acclist_combo.GetCount() != 0 and self.frame.chkBuy.IsChecked():
                        val = self.frame.qtyLabel.GetLabel()
                        qty = int(val) if val.isdigit() else 0
                        if qty > 0:
                            # 檢查 GUI 上「是否允許自動下單」
                            self._safe_order(
                            side=str("S"),
                            price=str(price),
                            offset=str("1"),
                            )
                            self.frame.qtyLabel.SetLabel("未連")
                except Exception:  # noqa: BLE001
                    self.notifier.error("⚠️ 多單止損平倉下單失敗，請檢查 OnOrderBtn。")

    # ========= 自動收盤平倉 =========

    def start_auto_liquidation(self) -> None:
        """
        啟動「自動收盤平倉」監控（背景執行緒）。

        行為
        -----
        - 每 30 秒檢查一次現在時間是否為「收盤前幾分鐘」
        - 若時間符合且仍有持倉，則呼叫 :meth:`_force_liquidation` 強制平倉。
        """
        # 若舊 thread 還在，先停掉
        if self._auto_thread and self._auto_thread.is_alive():
            self._auto_thread_stop.set()
            self._auto_thread.join(timeout=1)

        self._auto_thread_stop.clear()
        self._auto_thread = threading.Thread(
            target=self._auto_liquidation_loop,
            daemon=True
        )
        self._auto_thread.start()
        # t = threading.Thread(target=self._auto_liquidation_loop, daemon=True)
        # t.start()
        self.notifier.log("✅ 自動收盤平倉監控已啟動", Fore.CYAN + Style.BRIGHT)

    def _auto_liquidation_loop(self) -> None:
        """
        自動收盤平倉的背景迴圈。

        每 30 秒：
        - 取得目前時間（HH:MM）
        - 若時間為 close_times 之一，則呼叫 :meth:`_force_liquidation`。
        """
        while not self._auto_thread_stop.is_set():
            try:
                now = datetime.datetime.now()
                current = now.strftime("%H:%M")

                # 台指期日盤 / 夜盤收盤時間（可依需求調整）
                close_times = ["13:42", "04:57"]

                if current in close_times:
                    self._force_liquidation(now)

                # 每次 sleep 時也要能被停止
                for _ in range(30):
                    if self._auto_thread_stop.is_set():
                        break
                    time.sleep(1)

            except Exception as e:  # noqa: BLE001
                # 使用 print 是為了在 notifier 發生問題時仍能看到錯誤訊息
                print(f"自動平倉監控錯誤: {e}")
                time.sleep(1)

    def _force_liquidation(self, now: datetime.datetime) -> None:
        """
        在指定的收盤時間強制平倉。

        參數
        -----
        now:
            目前的 datetime 物件，用於格式化時間字串。
        """
        match_time = now.strftime("%H:%M:%S")

        # 若仍有空單
        if getattr(self, "trading_sell", False):
            msg = f"{match_time} ⚠️ 收盤自動平倉觸發：空單強制平倉"
            self.notifier.log(msg, Fore.YELLOW + Style.BRIGHT)
            self._execute_force_exit("空", now)

        # 若仍有多單
        if getattr(self, "trading_buy", False):
            msg = f"{match_time} ⚠️ 收盤自動平倉觸發：多單強制平倉"
            self.notifier.log(msg, Fore.YELLOW + Style.BRIGHT)
            self._execute_force_exit("多", now)

    def _execute_force_exit(self, direction: str, now: datetime.datetime) -> None:
        """
        在收盤時間執行實際平倉委託。

        此邏輯與一般停損 / 停利平倉完全一致，
        差別只有「觸發來源為時間」。

        參數
        -----
        direction:
            "多" 或 "空"，代表目前持倉方向。
        now:
            當前時間，用於 log 顯示。

        邏輯
        -----
        - direction == "空"：以市價買回（side="B"）
        - direction == "多"：以市價賣出（side="S"）
        - 市價由 frame.infoDataGrid 第 0 列的欄位讀取（符合你既有 GUI 設計）
        - 若允許自動下單且口數 > 0，則呼叫 OnOrderBtn 實際平倉。
        """
        try:
            # 空單要買回；多單要賣出
            side = "B" if direction == "空" else "S"
            offset = "1"

            # 從 infoDataGrid 取得目前市價
            if direction == "空":
                price = int(self.frame.infoDataGrid.GetCellValue(0, 0))
            else:
                price = int(self.frame.infoDataGrid.GetCellValue(0, 1))

            msg = f"{now.strftime('%H:%M:%S')} ⏰ 自動平倉觸發：{direction}單 → {price}平倉"
            self.notifier.log(msg, Fore.YELLOW + Style.BRIGHT)

            if self.frame.acclist_combo.GetCount() != 0:
                if ((direction == "多" and self.frame.chkBuy.IsChecked()) or
                        (direction == "空" and self.frame.chkSell.IsChecked())):
                    val = self.frame.qtyLabel.GetLabel()
                    qty = int(val) if val.isdigit() else 0
                    if qty > 0:
                        # 呼叫原生下單介面
                        self._safe_order(
                        side=str(side),
                        price=str(price),
                        offset=str(offset),
                          )
                        self.frame.qtyLabel.SetLabel("未連")

                    msg_done = f"{now.strftime('%H:%M:%S')} ✅ 自動平倉成功：{direction}單"
                    self.notifier.log(msg_done, Fore.GREEN + Style.BRIGHT)
                    self.notifier.send_telegram_if_enabled(msg_done)

            # 更新持倉狀態
            if direction == "多":
                self.trading_buy = False
                self.buy_signal = False
                self.profit_buy_str = ""
            else:
                self.trading_sell = False
                self.sell_signal = False
                self.profit_sell_str = ""

        except Exception as e:  # noqa: BLE001
            self.notifier.error(f"⚠️ 自動收盤平倉失敗: {e}")

    def stop_all_threads(self):
        # 停止自動收盤平倉 thread
        if self._auto_thread and self._auto_thread.is_alive():
            self._auto_thread_stop.set()
            self._auto_thread.join(timeout=1)

    def _is_forbidden_time(self, match_time: str) -> bool:
        """判斷是否為禁止進場時間區段。match_time 格式預期為 HH:MM:SS"""

        try:
            hh = int(match_time[:2])
            mm = int(match_time[3:5])
        except:
            return False  # 若時間格式怪怪的，先不阻擋以避免誤殺

        # 13:00 ~ 13:45 禁止
        if hh == 13 and 0 <= mm <= 45:
            return True

        # 04:00 ~ 05:00 禁止
        if hh == 4:
            return True
        if hh == 5 and mm == 0:
            return True

        return False

