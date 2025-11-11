"""
notifier.py
----------------
負責輸出與通知：
- RedirectText: print 導入 wx.TextCtrl，保留 colorama 顏色
- Notifier: 統一管理 print / Telegram / 聲音
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
    """將標準輸出導到 wx.TextCtrl，並解析 colorama 顏色碼。"""
    def __init__(self, text_ctrl: wx.TextCtrl):
        self.out = text_ctrl

    def write(self, message: str):
        tokens = re.split(r'(\x1b\[.*?m)', message)
        self._draw_segments(tokens)

    def _draw_segments(self, segments):
        fg = wx.WHITE
        bg = wx.BLACK
        bold = False

        for seg in segments:
            if any(code in seg for code in [
                Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.CYAN, Fore.BLACK,
                Fore.MAGENTA, Fore.WHITE,
                Back.WHITE, Back.RED, Back.BLUE, Back.GREEN,
                Style.BRIGHT, Style.RESET_ALL
            ]):
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

                if Back.WHITE in seg:
                    bg = wx.Colour(255, 255, 255)
                elif Back.RED in seg:
                    bg = wx.Colour(128, 0, 0)
                elif Back.BLUE in seg:
                    bg = wx.Colour(0, 0, 128)
                elif Back.GREEN in seg:
                    bg = wx.Colour(0, 128, 0)

                if Style.BRIGHT in seg:
                    bold = True
                if Style.RESET_ALL in seg:
                    fg = wx.WHITE
                    bg = wx.BLACK
                    bold = False
                continue

            style = wx.TextAttr(fg, bg)
            style.SetFont(wx.Font(
                12,
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
            ))
            self.out.SetDefaultStyle(style)
            self.out.AppendText(seg)

        self.out.ShowPosition(self.out.GetLastPosition())

    def flush(self):
        pass


class Notifier:
    """
    統一處理訊息輸出與通知。
    需要 frame 具備:
        - isSMS: 是否啟用 Telegram
        - isPlaySound: 是否播放音效
    """
    def __init__(self,
                 frame,
                 telegram_token: Optional[str] = None,
                 telegram_chat_id: Optional[str] = None):
        self.frame = frame
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id

    def log(self, msg: str, color: Optional[str] = None):
        if color:
            print(color + msg + Style.RESET_ALL)
        else:
            print(msg)

    def info(self, msg: str):
        self.log(msg, Fore.GREEN + Style.BRIGHT)

    def warn(self, msg: str):
        self.log(msg, Fore.YELLOW + Style.BRIGHT)

    def error(self, msg: str):
        self.log(msg, Fore.RED + Style.BRIGHT + Back.WHITE)

    def play_sound_if_enabled(self):
        try:
            if hasattr(self.frame, "isPlaySound") and self.frame.isPlaySound.GetValue():
                threading.Thread(
                    target=winsound.PlaySound,
                    args=("woo.wav", winsound.SND_FILENAME),
                    daemon=True
                ).start()
        except Exception:
            pass

    def send_telegram_if_enabled(self, msg: str):
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
            pass

    def _send_telegram(self, msg: str):
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {"chat_id": self.telegram_chat_id, "text": msg}
        try:
            requests.post(url, data=payload, timeout=3)
        except Exception as e:
            print(Fore.RED + f"Telegram 發送失敗: {e}" + Style.RESET_ALL)
