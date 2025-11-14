"""
ui_updater.py
----------------
集中管理與 wx GUI 相關的更新行為。

目的：
- 把所有「直接操作 Grid / ComboBox」的程式碼集中在這裡，
  讓交易策略 (TradingStrategy) 與下單邏輯 (OrderManager) 可以保持乾淨的純邏輯。
"""

from typing import List, Dict

import wx


class UIUpdater:
    """
    包裝對 frame 的所有畫面更新操作。

    以 composition 的方式持有 frame，避免在策略邏輯中直接碰觸 GUI 控制項。
    """
    def __init__(self, frame) -> None:
        """
        建構子。

        參數
        -----
        frame :
            主視窗物件 (AppFrame)，包含所有需要更新的 Grid、ComboBox 等控制項。
        """
        self.frame = frame  # GUI 主視窗參考

    def update_signal_row(
        self,
        row: int,
        entry: int,
        stop_loss: int,
        p1: int,
        p2: int,
        p3: int,
        color: wx.Colour,
    ) -> None:
        """
        更新「多 / 空訊號 Grid」中的一整列（進場 / 停損 / 三段停利）。

        參數
        -----
        row : int
            要更新的列索引：0=放空列、1=買進列。
        entry : int
            進場價。
        stop_loss : int
            止損價。
        p1, p2, p3 : int
            三段停利價位。
        color : wx.Colour
            此列整行文字的顏色（多單通常為紅色，空單為綠色）。
        """
        grid = self.frame.signalGrid
        cols = grid.GetNumberCols()
        # 把整列字體顏色改成指定顏色
        for c in range(cols):
            grid.SetCellTextColour(row, c, color)
        # 寫入數值
        grid.SetCellValue(row, 0, str(int(entry)))
        grid.SetCellValue(row, 1, str(int(stop_loss)))
        grid.SetCellValue(row, 2, str(int(p1)))
        grid.SetCellValue(row, 3, str(int(p2)))
        grid.SetCellValue(row, 4, str(int(p3)))

    def reset_signal_row(self, row: int, label: str) -> None:
        """
        將訊號列恢復成「文字提示」狀態，用在平倉或止損後。

        參數
        -----
        row : int
            要重置的列索引：0=放空列、1=買進列。
        label : str
            重置後第 0 欄顯示的說明文字（例如："作多止損", "放空止損"）。
        """
        grid = self.frame.signalGrid
        grid.SetCellValue(row, 0, label)
        grid.SetCellValue(row, 1, "       ")
        grid.SetCellValue(row, 2, "猶豫不決")
        grid.SetCellValue(row, 3, "老而無成")
        grid.SetCellValue(row, 4, "平倉不悔")

    def update_fibonacci_grid(
        self,
        sell_levels: List[int],
        buy_levels: List[int],
    ) -> None:
        """
        更新費波那契 Grid 的上下兩列數值。

        參數
        -----
        sell_levels : list[int]
            上方「壓力」列的五個價位（0.236 ~ 0.786）。
        buy_levels : list[int]
            下方「支撐」列的五個價位。
        """
        g = self.frame.fibonacciGrid
        for i, v in enumerate(sell_levels[:5]):
            g.SetCellValue(0, i, str(int(v)))
        for i, v in enumerate(buy_levels[:5]):
            g.SetCellValue(1, i, str(int(v)))

    def update_info_grid_basic(
        self,
        high_price: int,
        low_price: int,
        diff_up: int,
        diff_down: int,
        diff_total: int,
    ) -> None:
        """
        更新 infoDataGrid 內「最高價 / 最低價 / 壓力差 / 支撐差 / 價差」五個欄位。

        參數
        -----
        high_price : int
            日內最高價。
        low_price : int
            日內最低價。
        diff_up : int
            日高 - 關鍵價 (keypri)，視為壓力差。
        diff_down : int
            關鍵價 - 日低，視為支撐差。
        diff_total : int
            日高 - 日低，總價差。
        """
        g = self.frame.infoDataGrid
        # 日高 / 日低
        g.SetCellValue(0, 0, str(int(high_price)))
        g.SetCellValue(0, 1, str(int(low_price)))
        g.SetCellTextColour(0, 0, wx.RED)
        g.SetCellTextColour(0, 1, wx.GREEN)

        # 壓力差 / 支撐差
        g.SetCellValue(0, 2, str(int(diff_up)))
        g.SetCellTextColour(0, 2, wx.GREEN)

        g.SetCellValue(0, 3, str(int(diff_down)))
        g.SetCellTextColour(0, 3, wx.RED)

        # 價差
        g.SetCellValue(0, 4, str(int(diff_total)))

    def update_trend_suggestion(self, trend: str) -> None:
        """
        更新 infoDataGrid 右側「方向」欄位。

        參數
        -----
        trend : str
            "空" → 顯示「偏空操作」並以綠色顯示。
            "多" → 顯示「偏多操作」並以紅色顯示。
            其他 → 顯示「觀望」並以白色顯示。
        """
        g = self.frame.infoDataGrid
        if trend == "空":
            g.SetCellTextColour(0, 5, wx.GREEN)
            g.SetCellValue(0, 5, "偏空操作")
        elif trend == "多":
            g.SetCellTextColour(0, 5, wx.RED)
            g.SetCellValue(0, 5, "偏多操作")
        else:
            g.SetCellTextColour(0, 5, wx.WHITE)
            g.SetCellValue(0, 5, "觀望")

    def update_compare_on_tick(
        self,
        avg_price: float,
        new_price: float,
        up_down: str,
        tol_time_str: str,
        group_size: int,
        temp_db: Dict,
        temp_total_volume: float,
        temp_avg_price: float,
    ) -> None:
        """
        每筆 tick 來時，更新 compareInfoGrid 的顯示。

        參數
        -----
        avg_price : float
            合併均價 (TXF+MXF)。
        new_price : float
            最新成交價。
        up_down : str
            現價相對均價的方向箭頭："↑" / "↓" 或空字串。
        tol_time_str : str
            目前區間累積時間的字串，例如 "00:01:23.456"。
        group_size : int
            本區間累積的 tick 數，用來顯示在「筆數」欄位。
        temp_db : dict
            當前區間比較資料（big_value / small_value / up / down 等欄位）。
        temp_total_volume : float
            目前區間累積成交量。
        temp_avg_price : float
            目前區間加權平均價。
        """
        g = self.frame.compareInfoGrid
        # 總平均價 / 現價 + 箭頭
        g.SetCellValue(0, 5, f"{avg_price:.1f}")
        g.SetCellValue(1, 5, f"{int(new_price)}  {up_down}")

        # 若有高低價暫存資料，顯示在第 1 列前兩格
        if temp_db:
            g.SetCellTextColour(1, 0, wx.RED)
            g.SetCellTextColour(1, 1, wx.GREEN)
            g.SetCellValue(1, 0, str(int(temp_db["big_value"])))
            arrow = ""
            if temp_db.get("up"):
                arrow = "  ↑"
            elif temp_db.get("down"):
                arrow = "  ↓"
            g.SetCellValue(1, 1, str(int(temp_db["small_value"])) + arrow)

        # 區間時間 / 量 / 均價 / 筆數
        g.SetCellValue(1, 2, tol_time_str)
        g.SetCellValue(1, 3, str(int(temp_total_volume)))
        g.SetCellValue(1, 4, str(int(temp_avg_price)))
        g.SetCellValue(1, 6, str(group_size))

    def set_price_combo_items(self, items: List[int] ,profits= List[int]) -> None:
        """
        將價格選單 (price_combo) 設定為指定價位列表。

        通常由 Fibonacci 計算結果呼叫，用來提供「預設進場 / 停利價」。

        參數
        -----
        items : list[int]
            欲顯示在下拉選單中的價位列表。
        """
        combo = self.frame.price_combo
        combo.SetItems([str(i) for i in items])
        if items:
            # 預設選第 4 個價位（若不足 4 個，就選最後一個）
            combo.SetSelection(min(3, len(items) - 1))

        combo = self.frame.ktprice_combo
        combo.SetItems([str(i) for i in profits])
        if profits:
            # 預設選第 3 個價位（若不足 3 個，就選最後一個）
            combo.SetSelection(min(2, len(profits) - 1))

    def reset_price_select_state(self) -> None:
        """
        重置價格選單與相關 CheckBox 狀態。

        用於：
        - 止損 / 停利出場後，清除 price_combo 的內容，並關閉自動下單訊號。
        """
        self.frame.price_combo.SetItems(["0"])
        self.frame.price_combo.SetSelection(0)

        self.frame.ktprice_combo.SetItems(["0"])
        self.frame.ktprice_combo.SetSelection(0)

        # 關閉「錯失訊號」勾選
        if hasattr(self.frame, "chkSignal"):
            self.frame.chkSignal.SetValue(False)
        # 將錯失訊號選單回到預設「無」
        if hasattr(self.frame, "missedSignal_combo"):
            self.frame.missedSignal_combo.SetSelection(0)
