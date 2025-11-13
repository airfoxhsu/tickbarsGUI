"""trading_strategy 套件
對外僅暴露 TradingStrategy 供主程式使用。
"""

from .strategy_core import TradingStrategy

__all__ = ["TradingStrategy"]  # 套件公開介面：外部只能直接看到 TradingStrategy
