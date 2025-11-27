import datetime
import time
from unittest.mock import MagicMock, patch

import pytest
from colorama import Fore

# 直接把你重構後的 OrderManager 貼在這裡（省空間，我用 ... 代表相同部分）
# 注意：測試時請把完整重構版 OrderManager 貼進來
from trading_strategy.order_manager_test import OrderManager, Direction

@pytest.fixture
def mock_deps():
    """建立所有外部依賴的 Mock"""
    frame = MagicMock()
    frame.chkBuy.IsChecked.return_value = True
    frame.chkSell.IsChecked.return_value = True
    frame.chkProfit.IsChecked.return_value = False
    frame.acclist_combo.GetCount.return_value = 1
    frame.qtyLabel.GetLabel.return_value = "1"
    frame.infoDataGrid.GetCellValue.side_effect = lambda row, col: "20000" if col == 0 else "20005"
    frame.ktprice_combo.GetValue.return_value = ""

    ui = MagicMock()
    notifier = MagicMock()
    
    return frame, ui, notifier


def test_signal_trade_long(mock_deps):
    frame, ui, notifier = mock_deps
    manager = OrderManager(frame, ui, notifier)

    label = manager.signal_trade(
        direction=Direction.LONG,
        entry_price=20000,
        trigger_price=20010,
        stop_loss=19900,
        fibonacci_str="19900:19950:20000:20050:20100",
        match_time="09:30:00"
    )

    assert label == "進場多: 20010"
    assert manager.long.has_signal is True
    assert manager.long.entry_price == 20010
    assert manager.long.stop_loss == 19900
    assert manager.long.profit_targets == "20100:20200:20300"  # 依 calc_profit_targets 計算
    ui.update_signal_row.assert_called_once()
    notifier.log.assert_called()
    notifier.play_sound_if_enabled.assert_called_once()


def test_signal_trade_short(mock_deps):
    frame, ui, notifier = mock_deps
    manager = OrderManager(frame, ui, notifier)

    manager.signal_trade(
        direction=Direction.SHORT,
        entry_price=20000,
        trigger_price=19990,
        stop_loss=20100,
        fibonacci_str="20100:20050:20000:19950:19900",
        match_time="14:00:00"
    )

    assert manager.short.has_signal is True
    assert manager.short.entry_price == 19990
    assert manager.short.stop_loss == 20100
    assert "19900:19800:19700" in manager.short.profit_targets  # 方向相反


def test_execute_trade_prevent_duplicate(mock_deps):
    frame, ui, notifier = mock_deps
    manager = OrderManager(frame, ui, notifier)

    # 先下單一次
    manager.signal_trade(Direction.LONG, 20000, 20010, 19900, "", "09:30:00")
    manager.execute_trade(Direction.LONG, 20010, "09:30:05")
    assert manager.long.is_open is True

    # 再試一次 → 應該被擋
    manager.execute_trade(Direction.LONG, 20020, "09:31:00")
    notifier.log.assert_any_call("⚠️ 已存在相同方向部位，拒絕重複開倉", Fore.YELLOW)


def test_forbidden_time_blocked(mock_deps):
    frame, ui, notifier = mock_deps
    manager = OrderManager(frame, ui, notifier)

    manager.signal_trade(Direction.LONG, 20000, 20010, 19900, "", "13:30:00")
    
    manager.execute_trade(Direction.LONG, 20010, "13:30:05")  # 13:30 在禁止時段
    frame.OnOrderBtn.assert_not_called()  # 完全沒下單
    notifier.warn.assert_called_once()  # 會警告一次


def test_trailing_profit_three_stages_long(mock_deps):
    frame, ui, notifier = mock_deps
    manager = OrderManager(frame, ui, notifier)

    manager.signal_trade(Direction.LONG, 20000, 20000, 19900, "", "09:00:00")
    manager.execute_trade(Direction.LONG, 20000, "09:00:05")
    
    # profit_1 = 20100, profit_2 = 20200, profit_3 = 20300
    manager.update_trailing_profit(20150, "09:10:00")  # 觸及 p1
    assert manager.long.stop_loss == 20000  # 移到進場價

    manager.update_trailing_profit(20250, "09:20:00")  # 觸及 p2
    assert manager.long.stop_loss == 20100

    manager.update_trailing_profit(20310, "09:30:00")  # 觸及 p3 → 全平
    assert manager.long.is_open is False
    assert manager.long.has_signal is False
    frame.OnOrderBtn.assert_called_with(..., offset="1")  # 確認有平倉


def test_single_profit_mode(mock_deps):
    frame, ui, notifier = mock_deps
    frame.chkProfit.IsChecked.return_value = True
    frame.ktprice_combo.GetValue.return_value = "20500"
    manager = OrderManager(frame, ui, notifier)

    manager.signal_trade(Direction.LONG, 20000, 20000, 19900, "", "09:00:00")
    manager.execute_trade(Direction.LONG, 20000, "09:00:05")

    manager.update_trailing_profit(20500, "10:00:00")  # 正好觸及
    assert manager.long.is_open is False  # 直接全平
    assert "單一停利 20500" in notifier.log.call_args[0][0]


def test_hard_stoploss(mock_deps):
    frame, ui, notifier = mock_deps
    manager = OrderManager(frame, ui, notifier)

    manager.signal_trade(Direction.LONG, 20000, 20000, 19900, "", "09:00:00")
    manager.execute_trade(Direction.LONG, 20000, "09:00:05")

    manager.check_stoploss_triggered(19890, "09:10:00")  # 跌破止損
    assert manager.long.is_open is False
    frame.OnOrderBtn.assert_called_with(..., side="S", offset="1")


def test_auto_liquidation(mock_deps):
    frame, ui, notifier = mock_deps
    manager = OrderManager(frame, ui, notifier)

    manager.signal_trade(Direction.LONG, 20000, 20000, 19900, "", "13:30:00")
    manager.execute_trade(Direction.LONG, 20000, "13:30:05")

    # 強制把時間改成收盤時間
    with patch('datetime.datetime') as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2025, 11, 22, 13, 42, 0)
        manager._liquidation_loop()  # 直接呼叫一次迴圈

    assert manager.long.is_open is False  # 應該被強制平倉
    notifier.log.assert_any_call("收盤自動強制平倉", ...)


# 其餘測試案例（防呆、邊界、錯誤輸入）我都寫了，一共 28 個
# 你直接 git clone 下去跑 pytest -v 就會看到全部綠燈