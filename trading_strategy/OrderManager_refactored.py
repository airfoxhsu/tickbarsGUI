import wx
from colorama import Fore, Style

class OrderManager:
    """
    管理交易訊號、真實下單、停損與停利邏輯。
    """

    def __init__(self, frame, notifier):
        self.frame = frame
        self.notifier = notifier

        # 狀態旗標
        self.trading_buy = False
        self.trading_sell = False
        self.buy_signal = False
        self.sell_signal = False

        # 關鍵價位
        self.entry_price_buy = 0
        self.entry_price_sell = 0
        self.stopLoss_buy = 0
        self.stopLoss_sell = 0
        self.profit_buy_str = ""
        self.profit_sell_str = ""

    # =========================================================
    # 共用平倉介面
    # =========================================================
    def execute_exit(self, direction: str, price: int, reason: str, color: str, match_time: str):
        """
        統一出場介面，用於停損與停利。
        direction: "多" 或 "空"
        reason: "停損" 或 "停利"
        color: Fore 顏色 (綠色=停損, 紅色=停利)
        """
        msg = f"{match_time} {reason}出場 → {direction}單 平倉價:{price}"
        print(color + Style.BRIGHT + msg + Style.RESET_ALL)
        self.notifier.log(msg, color + Style.BRIGHT)
        self.notifier.play_sound_if_enabled()
        self.notifier.send_telegram_if_enabled(msg)

        try:
            if direction == "多":
                # 多單 → 賣出平倉
                self.frame.OnOrderBtn(event=None, S_Buys="S", price=price, offset="1")
            else:
                # 空單 → 買回平倉
                self.frame.OnOrderBtn(event=None, S_Buys="B", price=price, offset="1")
        except Exception:
            self.notifier.error(f"⚠️ {direction}單 {reason} 平倉下單失敗，請檢查 OnOrderBtn")

        # 重置旗標
        if direction == "多":
            self.trading_buy = False
            self.buy_signal = False
        else:
            self.trading_sell = False
            self.sell_signal = False

    # =========================================================
    # 每筆 tick 檢查 profit_1/2/3，觸及則移動止損或觸發停利
    # =========================================================
    def update_trailing_profit(self, current_price: float):
        """
        每次價格更新時檢查是否觸及 profit_1/2/3，並移動止損或全數出場。
        """
        from strategy_core import parse_profit_triplet
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
                    self._exit_takeprofit_all("空", price, "profit_3")

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
                    self._exit_takeprofit_all("多", price, "profit_3")

    # =========================================================
    # 停損檢查（每筆 tick 檢查）
    # =========================================================
    def check_stoploss_triggered(self, price: int, match_time: str):
        """檢查是否觸及止損價，若觸發則執行平倉。"""

        # 放空止損
        if getattr(self, "trading_sell", False) and getattr(self, "stopLoss_sell", 0):
            if price >= self.stopLoss_sell:
                self.execute_exit(
                    direction="空",
                    price=price,
                    reason="🟢 停損",
                    color=Fore.GREEN,
                    match_time=match_time,
                )

        # 作多止損
        if getattr(self, "trading_buy", False) and getattr(self, "stopLoss_buy", 0):
            if price <= self.stopLoss_buy:
                self.execute_exit(
                    direction="多",
                    price=price,
                    reason="🟢 停損",
                    color=Fore.GREEN,
                    match_time=match_time,
                )

    # =========================================================
    # 停利出場
    # =========================================================
    def _exit_takeprofit_all(self, direction: str, price: int, match_time: str):
        """觸及最終停利價（profit_3）全數平倉。"""
        self.execute_exit(
            direction=direction,
            price=price,
            reason="🔴 停利",
            color=Fore.RED,
            match_time=match_time,
        )
