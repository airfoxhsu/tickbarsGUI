import wx
import sys
import re
from colorama import Fore, Back, Style, init

init(autoreset=True)

class RedirectText:
    def __init__(self, text_ctrl):
        self.out = text_ctrl

    def write(self, message):
        tokens = re.split(r'(\x1b\[.*?m)', message)
        self._draw_segments(tokens)

    def _draw_segments(self, segments):
        fg = wx.WHITE
        bg = wx.BLACK
        bold = False

        for seg in segments:
            # 檢查 colorama 控制碼
            if any(code in seg for code in [
                Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.CYAN,
                Back.WHITE, Back.RED, Back.BLUE,
                Style.BRIGHT, Style.RESET_ALL
            ]):
                if Fore.RED in seg: fg = wx.RED
                elif Fore.GREEN in seg: fg = wx.Colour(0, 255, 0)
                elif Fore.YELLOW in seg: fg = wx.Colour(255, 255, 0)
                elif Fore.CYAN in seg: fg = wx.Colour(0, 255, 255)

                if Back.WHITE in seg: bg = wx.Colour(255, 255, 255)
                elif Back.RED in seg: bg = wx.Colour(128, 0, 0)
                elif Back.BLUE in seg: bg = wx.Colour(0, 0, 128)

                if Style.BRIGHT in seg: bold = True
                if Style.RESET_ALL in seg:
                    fg = wx.WHITE
                    bg = wx.BLACK
                    bold = False
                continue

            # 設定樣式（含字體大小）
            style = wx.TextAttr(fg, bg)
            style.SetFont(wx.Font(
                18,  # 🔥 字體大小：改這裡就能放大或縮小
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
            ))

            self.out.SetDefaultStyle(style)
            self.out.AppendText(seg)

        self.out.ShowPosition(self.out.GetLastPosition())

    def flush(self):
        pass


class MyFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="wxPython 終端 + 放大字體 + colorama", size=(900, 500))
        panel = wx.Panel(self)

        self.text = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL
        )
        self.text.SetBackgroundColour("black")

        # sizer = wx.BoxSizer(wx.VERTICAL)
        # sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 5)
        # panel.SetSizer(sizer)

        sys.stdout = RedirectText(self.text)
        sys.stderr = RedirectText(self.text)

        # 🔥 測試輸出
        print(Style.BRIGHT + Fore.GREEN + "✅ 成功訊息 (亮綠色)"
              + Fore.RED + Back.WHITE + "❌ 錯誤訊息 (紅字白底)"
              + Style.RESET_ALL)
        print(Fore.CYAN + "🔷 額外測試：字體已放大、顏色可混用。")
        print(Back.BLUE + Fore.YELLOW + Style.BRIGHT + "亮黃字 + 藍底測試" + Style.RESET_ALL)

class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    app = MyApp(False)
    app.MainLoop()
