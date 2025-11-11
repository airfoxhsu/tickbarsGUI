"""
order_manager.py
----------------
管理「進場 / 止損 / 停利 / 移動停損」。
"""

from typing import Optional

import wx
from colorama import Fore, Style

from .calculator import calc_profit_targets, parse_profit_triplet
from .ui_updater import UIUpdater
from .notifier import Notifier


class OrderManager:
    """
    多空倉位與停利停損的集中管理。
    """
    def __init__(self, frame, ui: UIUpdater, notifier: Notifier):
        self.frame = frame
        self.ui = ui
        self.notifier = notifier

        self.trading_buy = False     # 真實成交
        self.trading_sell = False    # 真實成交

        self.entry_price_buy: int = 0
        self.entry_price_sell: int = 0

        self.stopLoss_buy: int = 0
        self.stopLoss_sell: int = 0

        self.profit_buy_str: str = ""
        self.profit_sell_str: str = ""

        self.buy_signal: bool = False
        self.sell_signal: bool = False

    # ========= 進場 =========
    # 產生進場訊號（不送單）
    def signal_trade(self,
                 direction: str,
                 entry_price: int,
                 trigger_price: int,
                 stop_loss: int,
                 fibonacci_str: str,
                 match_time: str) -> str:
        """
        產生進場訊號，不執行真實下單。
        用於策略層「發現進場機會」時呼叫。
        回傳: "進場多" 或 "進場空"
        """
        p1, p2, p3 = calc_profit_targets(entry_price, stop_loss, direction)

        if direction == "多":
            row = 1
            color = wx.RED
            self.buy_signal = True        # ✅ 訊號層標記
            self.entry_price_buy = trigger_price
            self.stopLoss_buy = stop_loss
            self.profit_buy_str = f"{p1}:{p2}:{p3}"
            label = "進場多"
        else:
            row = 0
            color = wx.GREEN
            self.sell_signal = True       # ✅ 訊號層標記
            self.entry_price_sell = trigger_price
            self.stopLoss_sell = stop_loss
            self.profit_sell_str = f"{p1}:{p2}:{p3}"
            label = "進場空"

        # === UI 顯示更新 ===
        self.ui.update_signal_row(row, entry_price, stop_loss, p1, p2, p3, color)

        # === Fibonacci 價格設定 ===
        if fibonacci_str:
            levels = [s.strip() for s in fibonacci_str.split(":") if s.strip()]
            if levels:
                self.ui.set_price_combo_items(levels)

        # === 發出訊號通知 ===
        msg = (
            f"{match_time}  "
            f"{'作多訊號' if direction == '多' else '放空訊號'}: {entry_price}  "
            f"費波: {fibonacci_str} 止損: {stop_loss}  停利: {p1} : {p2} : {p3}"
        )
        self.notifier.log(msg, Fore.CYAN + Style.BRIGHT)
        self.notifier.send_telegram_if_enabled(msg)
        self.notifier.play_sound_if_enabled()

        return label


    def execute_trade(self,
                    direction: str,
                    entry_price: int,
                    match_time: str):
        """
        真實下單執行。
        須確保 signal_trade() 已被呼叫並設置相關變數。
        """
        # === 防重複開倉 ===
        if direction == "多" and self.trading_buy:
            self.notifier.log("⚠️ 已有多單，不重複開倉。", Fore.YELLOW)
            return
        if direction == "空" and self.trading_sell:
            self.notifier.log("⚠️ 已有空單，不重複開倉。", Fore.YELLOW)
            return

        # === 真實下單 ===
        side = "B" if direction == "多" else "S"
        offset = "0"  # 0: 開倉, 1: 平倉

        try:
            if self.frame.acclist_combo.GetCount() != 0:
                # 檢查 GUI 上「是否允許自動下單」
                if ((direction == "多" and self.frame.chkBuy.IsChecked()) or
                        (direction == "空" and self.frame.chkSell.IsChecked())):
                    val = self.frame.price_combo.GetString(
                        self.frame.price_combo.GetSelection()
                    )
                    price = int(val) if val.isdigit() else entry_price

                    # 進場  實際呼叫 Yuanta API 下單
                    self.frame.OnOrderBtn(
                        event=None,
                        S_Buys=side,
                        price=price,
                        offset=offset
                    )

                   

                    # === 成功訊息 ===
                    msg = f"{match_time}  實際{direction}下單成功: {price}"
                    self.notifier.log(msg, Fore.MAGENTA + Style.BRIGHT)
                    self.notifier.send_telegram_if_enabled(msg)
             # === 標記持倉狀態 ===
            if direction == "多":
                self.trading_buy = True
            else:
                self.trading_sell = True
        except Exception as e:
            self.notifier.error(f"自動下單失敗: {e}")


    # ========= 止損 =========

    def exit_stoploss(self,
                      direction: str,
                      price: int,
                      match_time: str):
        """觸發止損出場。"""
        if direction == "多":
            row = 1
            text = "作多止損"
            side = "S"  # 多單止損 → 賣出平倉
            self.trading_buy = False
            self.buy_signal = False
            self.profit_buy_str = ""
        else:
            row = 0
            text = "放空止損"
            side = "B"  # 空單止損 → 買回平倉
            self.trading_sell = False
            self.sell_signal = False
            self.profit_sell_str = ""

        # === 真正執行平倉委託 ===
        try:
            # offset="1" 表示平倉
            self.frame.OnOrderBtn(
                event=None,
                S_Buys=side,
                price=int(price),
                offset="1"
            )
        except Exception:
            self.notifier.error("止損平倉下單失敗，請檢查 OnOrderBtn 或價位設定。")

        msg = f"{match_time}  {text}: {int(price)}  平倉不悔"
        self.notifier.log(msg, Fore.YELLOW + Style.BRIGHT)
        self.notifier.send_telegram_if_enabled(msg)

        self.ui.reset_signal_row(row, text)
        self.ui.reset_price_select_state()

    # ========= 停利 =========

    def _exit_takeprofit_all(self, direction: str, price: int):
        """第三段停利價達成，平倉了結。"""
        tag = "多單" if direction == "多" else "空單"
        msg = f"🏁 {tag}觸及 profit_3 → 平倉 {int(price)}"
        self.notifier.log(msg, Fore.MAGENTA + Style.BRIGHT)

        side = "S" if direction == "多" else "B"
        try:
            self.frame.OnOrderBtn(
                event=None,
                S_Buys=side,
                price=price,
                offset="1"
            )
        except Exception:
            self.notifier.error("停利平倉下單失敗，請檢查 OnOrderBtn。")

        if direction == "多":
            self.trading_buy = False
            self.buy_signal = False
            self.profit_buy_str = ""
        else:
            self.trading_sell = False
            self.sell_signal = False
            self.profit_sell_str = ""

    # ========= 移動停利 =========

    def update_trailing_profit(self, current_price: float):
        """
        每次價格更新時檢查是否觸及 profit_1/2/3，並移動止損或全數出場。
        """
        price = int(current_price)

        # 空單
        if self.trading_sell and self.profit_sell_str:
            p1, p2, p3 = parse_profit_triplet(self.profit_sell_str)
            if p1 and p2 and p3 and self.entry_price_sell:
                if price <= p1 and self.stopLoss_sell > self.entry_price_sell:
                    self.stopLoss_sell = self.entry_price_sell
                    self.notifier.log(
                        f"🟢 空單觸及 profit_1 → 停損改至進場價 {self.stopLoss_sell}",
                        Fore.CYAN + Style.BRIGHT
                    )
                elif price <= p2 and self.stopLoss_sell > p1:
                    self.stopLoss_sell = p1
                    self.notifier.log(
                        f"🟢 空單觸及 profit_2 → 停損改至 {self.stopLoss_sell}",
                        Fore.CYAN + Style.BRIGHT
                    )
                elif price <= p3:
                    self._exit_takeprofit_all("空", price)

        # 多單
        if self.trading_buy and self.profit_buy_str:
            p1, p2, p3 = parse_profit_triplet(self.profit_buy_str)
            if p1 and p2 and p3 and self.entry_price_buy:
                if price >= p1 and self.stopLoss_buy < self.entry_price_buy:
                    self.stopLoss_buy = self.entry_price_buy
                    self.notifier.log(
                        f"🟢 多單觸及 profit_1 → 停損改至進場價 {self.stopLoss_buy}",
                        Fore.CYAN + Style.BRIGHT
                    )
                elif price >= p2 and self.stopLoss_buy < p1:
                    self.stopLoss_buy = p1
                    self.notifier.log(
                        f"🟢 多單觸及 profit_2 → 停損改至 {self.stopLoss_buy}",
                        Fore.CYAN + Style.BRIGHT
                    )
                elif price >= p3:
                    self._exit_takeprofit_all("多", price)
