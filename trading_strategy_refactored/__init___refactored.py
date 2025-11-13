from .strategy_core import TradingStrategy

__all__ = ["TradingStrategy"]

# rading_strategy/
#  ├── __init__.py          # 對外只輸出 TradingStrategy
#  ├── calculator.py        # 純計算：時間, 停利價, Fibonacci
#  ├── notifier.py          # RedirectText + Notifier(Telegram/聲音/顏色輸出)
#  ├── ui_updater.py        # 所有 wx Grid / Combo 更新封裝
#  ├── order_manager.py     # 多空進出場、停損、三段停利、移動停損
#  └── strategy_core.py     # TradingStrategy 主策略：tick → 訊號 → 呼叫 OrderManager/UI/Notifier
