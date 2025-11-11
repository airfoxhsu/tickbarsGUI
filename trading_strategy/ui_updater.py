"""
ui_updater.py
----------------
集中管理 wx GUI 更新，讓策略邏輯保持乾淨。
"""

import wx
from typing import List, Dict


class UIUpdater:
    """包裝對 frame 的所有畫面更新操作。"""
    def __init__(self, frame):
        self.frame = frame

    def update_signal_row(self,
                          row: int,
                          entry: int,
                          stop_loss: int,
                          p1: int,
                          p2: int,
                          p3: int,
                          color: wx.Colour):
        grid = self.frame.signalGrid
        cols = grid.GetNumberCols()
        for c in range(cols):
            grid.SetCellTextColour(row, c, color)
        grid.SetCellValue(row, 0, str(int(entry)))
        grid.SetCellValue(row, 1, str(int(stop_loss)))
        grid.SetCellValue(row, 2, str(int(p1)))
        grid.SetCellValue(row, 3, str(int(p2)))
        grid.SetCellValue(row, 4, str(int(p3)))

    def reset_signal_row(self, row: int, label: str):
        grid = self.frame.signalGrid
        grid.SetCellValue(row, 0, label)
        grid.SetCellValue(row, 1, "       ")
        grid.SetCellValue(row, 2, "猶豫不決")
        grid.SetCellValue(row, 3, "老而無成")
        grid.SetCellValue(row, 4, "平倉不悔")

    def update_fibonacci_grid(self,
                              sell_levels: List[int],
                              buy_levels: List[int]):
        g = self.frame.fibonacciGrid
        for i, v in enumerate(sell_levels[:5]):
            g.SetCellValue(0, i, str(int(v)))
        for i, v in enumerate(buy_levels[:5]):
            g.SetCellValue(1, i, str(int(v)))

    def update_info_grid_basic(self,
                               high_price: int,
                               low_price: int,
                               diff_up: int,
                               diff_down: int,
                               diff_total: int):
        g = self.frame.infoDataGrid
        g.SetCellValue(0, 0, str(int(high_price)))
        g.SetCellValue(0, 1, str(int(low_price)))
        g.SetCellTextColour(0, 0, wx.RED)
        g.SetCellTextColour(0, 1, wx.GREEN)

        g.SetCellValue(0, 2, str(int(diff_up)))
        g.SetCellTextColour(0, 2, wx.GREEN)

        g.SetCellValue(0, 3, str(int(diff_down)))
        g.SetCellTextColour(0, 3, wx.RED)

        g.SetCellValue(0, 4, str(int(diff_total)))

    def update_trend_suggestion(self, trend: str):
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

    def update_compare_on_tick(self,
                               avg_price: float,
                               new_price: float,
                               up_down: str,
                               tol_time_str: str,
                               group_size: int,
                               temp_db: Dict,
                               temp_total_volume:float,
                               temp_avg_price:float):
        g = self.frame.compareInfoGrid
        g.SetCellValue(0, 5, f"{avg_price:.1f}")
        g.SetCellValue(1, 5, f"{int(new_price)}  {up_down}")
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
        g.SetCellValue(1, 2, tol_time_str)
        g.SetCellValue(1, 3, str(int(temp_total_volume)))
        g.SetCellValue(1, 4, str(int(temp_avg_price)))
        g.SetCellValue(1, 6, str(group_size))

    def set_price_combo_items(self, items):
        combo = self.frame.price_combo
        combo.SetItems([str(i) for i in items])
        if items:
            combo.SetSelection(min(3, len(items) - 1))

    def reset_price_select_state(self):
        self.frame.price_combo.SetItems(["0"])
        self.frame.price_combo.SetSelection(0)
        if hasattr(self.frame, "chkSignal"):
            self.frame.chkSignal.SetValue(False)
        if hasattr(self.frame, "missedSignal_combo"):
            self.frame.missedSignal_combo.SetSelection(0)
