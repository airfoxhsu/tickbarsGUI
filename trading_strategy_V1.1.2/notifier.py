"""
notifier.py
----------------
負責所有「輸出與通知」相關功能：

- RedirectText
    將標準輸出 (stdout / stderr) 導到 wx.TextCtrl，並解析 colorama 顏色碼，在 GUI 中保留彩色輸出。
- Notifier
    封裝 print / Telegram / 聲音播放邏輯，提供統一的通知介面。
"""

import re
import sys
import threading
import winsound
from typing import Optional

import requests
import wx
from colorama import Fore, Style, Back


class RedirectText:
    """
    將標準輸出導向到 wx.TextCtrl 的小工具。

    功能：
    - 接收原本寫到 stdout/stderr 的文字。
    - 解析其中的 ANSI / colorama 顏色碼。
    - 以對應的前景色 / 背景色 / 粗體字顯示在 GUI 的 TextCtrl 上。
    """
    def __init__(self, text_ctrl: wx.TextCtrl) -> None:
        """
        建構子。

        參數
        -----
        text_ctrl : wx.TextCtrl
            用來顯示輸出內容的文字輸入框（通常是 monitorTradeSignal）。
        """
        self.out = text_ctrl  # 真正用來顯示文字的 wx.TextCtrl 物件

    def write(self, message: str) -> None:
        """
        實作「檔案介面」的 write 方法，供 print 直接呼叫。

        邏輯：
        - 先用正則把字串切成「顏色控制碼片段」與「純文字片段」。
        - 再逐一交給 _draw_segments 做實際渲染。
        """
        tokens = re.split(r'(\x1b\[.*?m)', message)
        self._draw_segments(tokens)

    def _draw_segments(self, segments) -> None:
        """
        內部方法：依序處理每一個切好的片段。

        參數
        -----
        segments : list[str]
            由顏色碼與純文字交錯組成的字串列表。

        行為
        -----
        - 遇到顏色碼片段：更新目前的前景色 (fg)、背景色 (bg)、粗體 (bold) 狀態。
        - 遇到一般文字片段：套用目前顏色狀態後寫入 TextCtrl。
        """
        fg = wx.WHITE        # 目前前景色 (default: 白色)
        bg = wx.BLACK        # 目前背景色 (default: 黑色)
        bold = False         # 是否使用粗體字

        for seg in segments:
            # 若片段中包含任何 colorama 顏色碼，就只更新顏色狀態，不輸出文字
            if any(code in seg for code in [
                Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.CYAN, Fore.BLACK,
                Fore.MAGENTA, Fore.WHITE,
                Back.WHITE, Back.RED, Back.BLUE, Back.GREEN,
                Style.BRIGHT, Style.RESET_ALL
            ]):
                # 前景色判斷
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

                # 背景色判斷
                if Back.WHITE in seg:
                    bg = wx.Colour(255, 255, 255)
                elif Back.RED in seg:
                    bg = wx.Colour(128, 0, 0)
                elif Back.BLUE in seg:
                    bg = wx.Colour(0, 0, 128)
                elif Back.GREEN in seg:
                    bg = wx.Colour(0, 128, 0)

                # 粗體 / 重置
                if Style.BRIGHT in seg:
                    bold = True
                if Style.RESET_ALL in seg:
                    fg = wx.WHITE
                    bg = wx.BLACK
                    bold = False
                continue  # 處理顏色碼片段完畢，進入下一段

            # 純文字片段：依照目前 fg/bg/bold 狀態輸出
            style = wx.TextAttr(fg, bg)
            style.SetFont(wx.Font(
                12,
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
            ))
            self.out.SetDefaultStyle(style)
            self.out.AppendText(seg)

        # 把捲軸滾到最後一行，方便觀察最新訊息
        self.out.ShowPosition(self.out.GetLastPosition())

    def flush(self) -> None:
        """
        與檔案介面相容的 flush 函式。

        目前不需要做任何事，但保留介面實作避免錯誤。
        """
        pass


class Notifier:
    """
    統一處理訊息輸出與通知。

    需要 frame 具備以下屬性：
    - isSMS: wx.CheckBox，控制是否啟用 Telegram 推播。
    - isPlaySound: wx.CheckBox，控制是否播放音效。
    """
    def __init__(
        self,
        frame,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ) -> None:
        """
        建構子。

        參數
        -----
        frame :
            主視窗 (wx.Frame)，用來讀取 isSMS / isPlaySound 等控制元件狀態。
        telegram_token : str | None
            Telegram Bot 的 token（若為 None 則不啟用 Telegram 功能）。
        telegram_chat_id : str | None
            接收訊息的 chat_id（若為 None 則不啟用 Telegram 功能）。
        """
        self.frame = frame                              # GUI 主視窗，用來存取 CheckBox 狀態
        self.telegram_token = telegram_token            # Telegram Bot token
        self.telegram_chat_id = telegram_chat_id        # Telegram chat id

    def log(self, msg: str, color: Optional[str] = None) -> None:
        """
        封裝 print，支援 colorama 顏色。

        參數
        -----
        msg : str
            要輸出的訊息內容。
        color : str | None
            若提供，預期是一段 colorama 組合字串，例如 `Fore.RED + Style.BRIGHT`。
        """
        if color:
            print(color + msg + Style.RESET_ALL)
        else:
            print(msg)

    def info(self, msg: str) -> None:
        """
        輸出一般提示訊息（綠色亮字）。
        """
        self.log(msg, Fore.GREEN + Style.BRIGHT)

    def warn(self, msg: str) -> None:
        """
        輸出警告訊息（黃色亮字）。
        """
        self.log(msg, Fore.YELLOW + Style.BRIGHT)

    def error(self, msg: str) -> None:
        """
        輸出錯誤訊息（紅字白底），用來強調嚴重問題。

        例如：下單失敗、自動平倉異常等。
        """
        self.log(msg, Fore.RED + Style.BRIGHT + Back.WHITE)

    def play_sound_if_enabled(self) -> None:
        """
        若 frame.isPlaySound 被勾選，則在背景執行緒播放提示音。

        - 使用 winsound.PlaySound 播放 "woo.wav" 檔案。
        - 以 daemon thread 執行，避免阻塞主執行緒。
        - 若播放過程發生錯誤，會被吃掉以避免影響流程。
        """
        try:
            if hasattr(self.frame, "isPlaySound") and self.frame.isPlaySound.GetValue():
                threading.Thread(
                    target=winsound.PlaySound,
                    args=("woo.wav", winsound.SND_FILENAME),
                    daemon=True
                ).start()
        except Exception:
            # 播放音效失敗不視為致命錯誤，因此靜默忽略
            pass

    def send_telegram_if_enabled(self, msg: str) -> None:
        """
        若 Telegram 設定齊全且 frame.isSMS 被勾選，則以背景執行緒發送訊息。

        參數
        -----
        msg : str
            要送出的文字內容。
        """
        if not (self.telegram_token and self.telegram_chat_id):
            return
        try:
            if hasattr(self.frame, "isSMS") and self.frame.isSMS.GetValue():
                threading.Thread(
                    target=self._send_telegram,
                    args=(msg,),
                    daemon=True
                ).start()
        except Exception:
            # Telegram 發送錯誤不應影響主策略運作，因此靜默忽略
            pass

    def _send_telegram(self, msg: str) -> None:
        """
        實際呼叫 Telegram HTTP API 發送訊息的底層方法。

        使用 POST 請求呼叫：
        https://api.telegram.org/bot<token>/sendMessage

        若發送失敗，會在終端輸出錯誤訊息（紅色字）。
        """
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {"chat_id": self.telegram_chat_id, "text": msg}
        try:
            requests.post(url, data=payload, timeout=3)
        except Exception as e:
            print(Fore.RED + f"Telegram 發送失敗: {e}" + Style.RESET_ALL)
