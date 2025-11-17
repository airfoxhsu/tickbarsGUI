# -*- coding: utf-8 -*-
# from math import e
# from turtle import st
import wx
import time
import wx.grid
import wx.lib.anchors as anchors
import threading
from ctypes import byref, POINTER, windll
from comtypes import IUnknown, GUID
from comtypes.client import GetModule,  GetBestInterface, GetEvents
import queue as queue
import json
import datetime
import dateutil.relativedelta
# import trading_strategy_calc
from trading_strategy import TradingStrategy
from colorama import Fore, Back, Style, init
from functools import partial


user32 = windll.user32
atl = windll.atl
q = queue.Queue()
ts = None


class AppFrame(wx.Frame):
    """
    A Frame that says AppFrame
    """

    def __init__(self, *args, **kw):
        # Integrated TradingStrategy initialization
        # self.TELEGRAM_TOKEN = "8341950229:AAHw3h_p0Bnf_KcS5Mr4x3cOpIKHeFACiBs"
        # self.TELEGRAM_CHAT_ID = "8485648973"

        # ensure the parent's __init__ is called
        super(AppFrame, self).__init__(*args, **kw)
        # create a panel in the frame
        pnl = wx.Panel(self)

        config = load_json("./config.json")
        self.Username = config["username"]
        self.Password = config["password"]
        self.Host = "203.66.93.84"
        self.Port = 443

        self.waitMinuteToSMS = True   # 等待分鐘數重置簡訊發送
        self.last_userdefine_source = None  # 紀錄最後一次通用查詢的來源

        ############################################################################
        #   API連線資訊
        wx.StaticBox(pnl, label='API連線資訊', pos=(1, 1), size=(650, 70))
        wx.StaticText(pnl, label='ID', pos=(11, 30))
        wx.StaticText(pnl, label='密碼', pos=(155, 30))
        # config = load_json("./config.json")
        self.acc = wx.TextCtrl(
            pnl, value=self.Username, pos=(42, 26), size=(100, 25))
        self.pwd = wx.TextCtrl(pnl, value=self.Password, pos=(
            186, 26), size=(100, 25), style=wx.TE_PASSWORD)

        wx.StaticText(pnl, label='狀態碼', pos=(300, 30))
        self.connect_status = wx.TextCtrl(pnl, pos=(340, 26), size=(50, 25))
        self.connect_status.Enable(False)
        wx.StaticText(pnl, label='期貨帳號', pos=(400, 30))
        self.acclist_combo = wx.Choice(pnl, pos=(460, 28), size=(165, 30))

        ###################################################################################

        ###################################################################################
        #   下單委託
        wx.StaticBox(pnl, label='下單委託', pos=(1, 80), size=(650, 110))
        wx.StaticText(pnl, label='功能別', pos=(11, 100))
        self.fcode_combo = wx.Choice(
            pnl, choices=['01-委託', '02-減量', '03-刪單'], pos=(50, 97), size=(70, 30))
        self.fcode_combo.SetSelection(0)

        wx.StaticText(pnl, label='商品類', pos=(141, 100))
        self.ctype_combo = wx.Choice(
            pnl, choices=['0-期貨', '1-選擇權'], pos=(180, 97), size=(70, 30))
        self.ctype_combo.SetSelection(0)

        # self.ctype_rfcombo = wx.Choice(
        #     pnl, choices=['F-期貨', 'O-選擇權'], pos=(180, 97), size=(70, 30))
        # self.ctype_rfcombo.Show(False)
        # self.ctype_rfcombo.SetSelection(0)

        wx.StaticText(pnl, label='委託書', pos=(271, 100))
        self.ordno = wx.TextCtrl(pnl, pos=(310, 97), size=(70, 23))

        wx.StaticText(pnl, label='委託類', pos=(391, 100))
        self.offset_combo = wx.Choice(
            pnl, choices=['0-新倉', '1-平倉', '2-當沖', ' -自動'], pos=(430, 97), size=(70, 30))
        self.offset_combo.SetSelection(3)

        self.wait = wx.CheckBox(pnl, label='等待委託單號', pos=(520, 100))

        wx.StaticText(pnl, label='進場', pos=(11, 130))
        self.bscode1_combo = wx.Choice(
            pnl, choices=['B-買進', 'S-賣出'], pos=(50, 127), size=(70, 30))
        self.bscode1_combo.SetSelection(1)

        wx.StaticText(pnl, label='商品', pos=(141, 130))
        # data = load_json("./code.json")
        # choice_symbols = data["future"]
        self.futno1_combo = wx.Choice(
            pnl, choices=["無"], pos=(180, 127), size=(70, 23))
        # self.futno1_combo.SetSelection(1)

        wx.StaticText(pnl, label='價格', pos=(271, 130))
        self.price_combo = wx.ComboBox(
            pnl, choices=['0'], pos=(310, 127), size=(70, 23),
            style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER
        )
        self.price_combo.SetSelection(0)
        # 限制鍵盤輸入（只能按數字、Backspace、方向鍵）
        self.price_combo.Bind(wx.EVT_CHAR, self.OnComboNumberOnly)
        # Enter 觸發驗證（最多五位，轉成有效數字）
        self.price_combo.Bind(wx.EVT_TEXT_ENTER, self.OnComboEnterValidate)

        wx.StaticText(pnl, label='數量', pos=(391, 130))
        self.lots_combo = wx.Choice(
            pnl, choices=['1', '2', '3', '4', '5'], pos=(430, 127), size=(50, 23))
        self.lots_combo.SetSelection(0)

        self.chkProfit = wx.CheckBox(pnl, label='停利', pos=(520, 130))
        self.chkProfit.Bind(wx.EVT_CHECKBOX, self.OnChkProfit)

        self.textbs2 = wx.StaticText(pnl, label='停利', pos=(11, 160))
        self.bscode2_combo = wx.Choice(
            pnl, choices=['B-買進', 'S-賣出'], pos=(50, 157), size=(70, 30))
        self.bscode2_combo.SetSelection(0)
        # self.textbs2.Show(False)
        # self.bscode2_combo.Show(False)

        # self.textsymbol = wx.StaticText(pnl, label='商品2', pos=(141, 160))
        # self.futno2 = wx.TextCtrl(pnl, pos=(180, 157), size=(70, 23))

        self.textktprice = wx.StaticText(pnl, label='停利價', pos=(141, 160))
        self.ktprice_combo = wx.ComboBox(
            pnl,
            choices=['0'],
            pos=(180, 157),   # ❗座標你自己調整
            size=(70, 23),
            style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER
        )
        self.ktprice_combo.SetSelection(0)
        # 綁定輸入限制 & Enter 驗證
        self.ktprice_combo.Bind(wx.EVT_CHAR, self.OnComboNumberOnly)
        self.ktprice_combo.Bind(wx.EVT_TEXT_ENTER, self.OnComboEnterValidate)
        # self.textktprice.Show(False)
        # self.ktprice_combo.Show(False)

        wx.StaticText(pnl, label='限市價', pos=(271, 160))
        self.pritype_combo = wx.Choice(
            pnl, choices=['L-限價', 'M-市價', 'P-範圍市價'], pos=(310, 157), size=(70, 30))
        self.pritype_combo.SetSelection(0)

        # self.pritype_rfcombo = wx.Choice(
        #     pnl, choices=['1-限價', '2-市價', '4-停損', '8-停損限價'], pos=(310, 157), size=(70, 30))
        # self.pritype_rfcombo.Show(False)
        # self.pritype_rfcombo.SetSelection(0)

        wx.StaticText(pnl, label='條件', pos=(391, 160))
        self.pritype_cond = wx.Choice(
            pnl, choices=['R-ROD', 'F-FOK', 'I-IOC'], pos=(430, 157), size=(70, 30))
        self.pritype_cond.SetSelection(0)

        order = wx.Button(pnl, wx.ID_ANY, label='下單',
                          pos=(578, 126), size=(50, 25))
        order.Bind(wx.EVT_BUTTON, partial(
            self.OnOrderBtn, S_Buys=None, price=None, offset=None))

        logon = wx.Button(pnl, wx.ID_ANY, label='登入',
                          pos=(518, 156), size=(50, 25))
        logon.Bind(wx.EVT_BUTTON, self.OnLogonBtn)
        logout = wx.Button(pnl, wx.ID_ANY, label='登出',
                           pos=(578, 156), size=(50, 25))
        logout.Bind(wx.EVT_BUTTON, self.OnLogoutBtn)

        ###################################################################################

        ############################################################################
        #   狀態訊息
        wx.StaticBox(pnl, label='狀態訊息', pos=(1, 195), size=(550, 207))
        self.statusMessage = wx.ListBox(pnl, pos=(10, 215), size=(
            530, 180), style=wx.LB_SINGLE | wx.LB_HSCROLL)
        self.statusMessage.Bind(wx.EVT_KEY_DOWN, self.OnCtrlC)
        ###################################################################################

        ############################################################################
        #   委託回報
        wx.StaticBox(pnl, label='委託回報', pos=(1, 405), size=(550, 153))
        wx.StaticText(pnl, label='委託狀態', pos=(10, 425))
        self.ordstatus_combo = wx.Choice(
            pnl, choices=['0-全部', '1-未成交', '2-已成交', '4-委託失敗'], pos=(90, 423), size=(90, 30))
        self.ordstatus_combo.SetSelection(0)

        wx.StaticText(pnl, label='可刪改', pos=(192, 425))
        self.ordcflag_combo = wx.Choice(
            pnl, choices=['0-可刪改', '1-全部委託'], pos=(233, 423), size=(80, 30))
        self.ordcflag_combo.SetSelection(0)

        ordquery = wx.Button(pnl, wx.ID_ANY, label='查詢',
                             pos=(452, 423), size=(70, 25))
        ordquery.Bind(wx.EVT_BUTTON, self.OnOrdQueryBtn)

        self.OrdQueryRpt = wx.ListBox(pnl, pos=(10, 450), size=(
            530, 90), style=wx.LB_SINGLE | wx.LB_HSCROLL)
        self.OrdQueryRpt.Bind(wx.EVT_KEY_DOWN, self.OnCtrlC)

        ###################################################################################

        ############################################################################
        #   成交回報
        wx.StaticBox(pnl, label='成交回報', pos=(670, 405), size=(550, 153))
        self.isPlaySound = wx.CheckBox(pnl, label='音效提示', pos=(680, 425))
        self.isPlaySound.SetValue(False)
        self.isSMS = wx.CheckBox(pnl, label='簡訊提示', pos=(760, 425))
        self.isSMS.SetValue(False)

        self.isAutoPosition = wx.CheckBox(pnl, label="定時查倉", pos=(840, 425))
        self.isAutoPosition.SetValue(False)
        self.isAutoPosition.Bind(wx.EVT_CHECKBOX, self.OnAutoPositionCheck)
        self.position_watcher = PositionWatcher(interval=1)

        qtyquery = wx.Button(pnl, wx.ID_ANY, label='庫存',
                             pos=(910, 420), size=(70, 25))
        qtyquery.Bind(wx.EVT_BUTTON, self.OnQtyBtn)

        qtyquery = wx.Button(pnl, wx.ID_ANY, label='回測',
                             pos=(1060, 420), size=(70, 25))
        qtyquery.Bind(wx.EVT_BUTTON, self.OnBacktestData)

        matquery = wx.Button(pnl, wx.ID_ANY, label='查詢',
                             pos=(1140, 420), size=(70, 25))
        matquery.Bind(wx.EVT_BUTTON, self.OnMatQueryBtn)  # 手動查詢成交回報

        self.MatQueryRpt = wx.ListBox(pnl, pos=(680, 450), size=(
            530, 90), style=wx.LB_SINGLE | wx.LB_HSCROLL)
        self.MatQueryRpt.Bind(wx.EVT_KEY_DOWN, self.OnCtrlC)

        ###################################################################################
        #   交易狀態訊息
        wx.StaticBox(pnl, label='交易訊號', pos=(1, 540), size=(1230, 444))
        # self.monitorTradeSignal = wx.ListBox(pnl, pos=(10,660), size = (1350,290),style= wx.LB_SINGLE|wx.LB_HSCROLL)
        self.monitorTradeSignal = wx.TextCtrl(pnl, pos=(10, 565), size=(
            1220, 240), style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.monitorTradeSignal.SetBackgroundColour("black")
        ###################################################################################

        ############################################################################
        #   API商品資訊
        wx.StaticBox(pnl, label='API商品資訊', pos=(670, 1), size=(565, 60))
        wx.StaticText(pnl, label='商品代碼', pos=(680, 30))
        self.symbol = wx.TextCtrl(pnl, pos=(740, 26), size=(120, 25))
        # code_list = ",".join(load_json("./code.json")["future"])
        # self.symbol.SetValue(code_list)

        self.rbAm = wx.RadioButton(
            pnl, 1, label='日盤', pos=(870, 30), style=wx.RB_GROUP)
        self.rbPm = wx.RadioButton(pnl, 2, label='夜盤', pos=(915, 30))
        self.rbAm.SetValue(True) if self.is_day() else self.rbPm.SetValue(True)

        logonQuote = wx.Button(pnl, wx.ID_ANY, label='登入',
                               pos=(1080, 22), size=(40, 30))
        logonQuote.Bind(wx.EVT_BUTTON, self.ConnectionQuote)

        register = wx.Button(pnl, wx.ID_ANY, label='註冊',
                             pos=(1120, 22), size=(40, 30))
        register.Bind(wx.EVT_BUTTON, self.OnRegisterBtn)

        unregister = wx.Button(pnl, wx.ID_ANY, label='取消註冊',
                               pos=(1160, 22), size=(70, 30))
        unregister.Bind(wx.EVT_BUTTON, self.OnUnRegisterBtn)

        UpdateMode = ["1-Snapshot", "2-Update", "4-SnapshotUpd"]
        self.modle = wx.Choice(pnl, choices=UpdateMode,
                               pos=(965, 25), size=(110, 10))
        self.modle.SetSelection(2)
        ###################################################################################

        font = wx.Font(
            14,                      # 字體大小
            wx.FONTFAMILY_SWISS,     # 無襯線字型（清晰）
            wx.FONTSTYLE_NORMAL,     # 標準樣式
            wx.FONTWEIGHT_BOLD       # 加粗
        )

        ###################################################################################
        #   各項期貨資訊
        self.infoDataGrid = wx.grid.Grid(pnl, pos=(680, 65))
        self.infoDataGrid.SetDefaultCellFont(font)

        self.infoDataGrid.CreateGrid(1, 6)
        # 不顯示列名稱（左邊的數字標籤）
        self.infoDataGrid.SetRowLabelSize(0)
        # 禁止使用者改變欄寬與列高
        self.infoDataGrid.DisableDragColSize()
        self.infoDataGrid.DisableDragRowSize()
        rows = self.infoDataGrid.GetNumberRows()
        cols = self.infoDataGrid.GetNumberCols()
        # self.infoDataGrid.SetRowLabelValue(0, "放空")
        # self.infoDataGrid.SetRowLabelValue(1, "買進")

        self.infoDataGrid.SetColLabelValue(0, "最高價")
        self.infoDataGrid.SetColLabelValue(1, "最低價")
        self.infoDataGrid.SetColLabelValue(2, "壓力差")
        self.infoDataGrid.SetColLabelValue(3, "支撐差")
        self.infoDataGrid.SetColLabelValue(4, "價差")
        self.infoDataGrid.SetColLabelValue(5, "方向")

        self.infoDataGrid.SetCellValue(0, 0, "空倉不急")
        self.infoDataGrid.SetCellValue(0, 1, "開倉不畏")
        self.infoDataGrid.SetCellValue(0, 2, "持倉不慌")
        self.infoDataGrid.SetCellValue(0, 3, "平倉不悔")
        self.infoDataGrid.SetCellValue(0, 4, "猶不決  ")
        self.infoDataGrid.SetCellValue(0, 5, "老而無成")
        # self.infoDataGrid.EnableScrolling(False, False)

        self.infoDataGrid.SetDefaultCellBackgroundColour('BLACK')
        self.infoDataGrid.EnableEditing(False)
        self.infoDataGrid.AutoSizeColumns()

        attr_yellow = wx.grid.GridCellAttr()
        attr_yellow.SetTextColour(wx.YELLOW)
        self.infoDataGrid.SetRowAttr(0, attr_yellow)
        # self.infoDataGrid.SetRowAttr(1, attr_yellow)

        # attr_red = wx.grid.GridCellAttr()
        # attr_red.SetTextColour(wx.RED)
        # self.infoDataGrid.SetRowAttr(1, attr_red)

        for r in range(rows):
            for c in range(cols):
                self.infoDataGrid.SetCellAlignment(
                    r, c, wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        # 自動調整每欄與每列大小
        # self.infoDataGrid.AutoSizeColumns()
        self.infoDataGrid.AutoSizeRows()
        # 根據自動調整後的實際大小，更新 grid 控制項的尺寸
        grid_size = self.infoDataGrid.GetBestSize()
        self.infoDataGrid.SetSize(grid_size)
        ###################################################################################

        ###################################################################################
        #   買賣訊號
        # Create a wxGrid object  ,size=(643, 185)
        self.signalGrid = wx.grid.Grid(pnl, pos=(680, 130))
        self.signalGrid.SetDefaultCellFont(font)
        # Then we call CreateGrid to set the dimensions of the grid
        # (10 rows and 10 columns in this example)
        self.signalGrid.CreateGrid(2, 5)
        # 禁止使用者改變欄寬與列高
        self.signalGrid.DisableDragColSize()
        self.signalGrid.DisableDragRowSize()
        rows = self.signalGrid.GetNumberRows()
        cols = self.signalGrid.GetNumberCols()
        self.signalGrid.SetRowLabelValue(0, "放空")
        self.signalGrid.SetRowLabelValue(1, "買進")

        self.signalGrid.SetColLabelValue(0, "進場價")
        self.signalGrid.SetColLabelValue(1, "停損價")
        self.signalGrid.SetColLabelValue(2, "停利一")
        self.signalGrid.SetColLabelValue(3, "停利二")
        self.signalGrid.SetColLabelValue(4, "停利三")

        self.signalGrid.SetCellValue(0, 0, "空倉不急")
        self.signalGrid.SetCellValue(0, 1, "開倉不畏")
        self.signalGrid.SetCellValue(0, 2, "持倉不慌")
        self.signalGrid.SetCellValue(0, 3, "平倉不悔")
        self.signalGrid.SetCellValue(0, 4, "猶豫不決")
        self.signalGrid.SetCellValue(1, 0, "學會放棄")
        self.signalGrid.SetCellValue(1, 1, "學會等待")
        self.signalGrid.SetCellValue(1, 2, "學會坦然")
        self.signalGrid.SetCellValue(1, 3, "學會果斷")
        self.signalGrid.SetCellValue(1, 4, "老而無成")
        # self.signalGrid.EnableScrolling(False, False)

        self.signalGrid.SetDefaultCellBackgroundColour('BLACK')
        self.signalGrid.EnableEditing(False)
        self.signalGrid.AutoSizeColumns()

        attr_yellow = wx.grid.GridCellAttr()
        attr_yellow.SetTextColour(wx.YELLOW)
        self.signalGrid.SetRowAttr(0, attr_yellow)
        self.signalGrid.SetRowAttr(1, attr_yellow)

        # attr_red = wx.grid.GridCellAttr()
        # attr_red.SetTextColour(wx.RED)
        # self.signalGrid.SetRowAttr(1, attr_red)

        for r in range(rows):
            for c in range(cols):
                self.signalGrid.SetCellAlignment(
                    r, c, wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        # 自動調整每欄與每列大小
        # self.signalGrid.AutoSizeColumns()
        self.signalGrid.AutoSizeRows()
        # 根據自動調整後的實際大小，更新 grid 控制項的尺寸
        grid_size = self.signalGrid.GetBestSize()
        self.signalGrid.SetSize(grid_size)
        ###################################################################################

        ###################################################################################
        #   費波那契數
        # Create a wxGrid object  ,size=(643, 185)
        self.fibonacciGrid = wx.grid.Grid(pnl, pos=(680, 220))
        self.fibonacciGrid.SetDefaultCellFont(font)
        # Then we call CreateGrid to set the dimensions of the grid
        # (10 rows and 10 columns in this example)
        self.fibonacciGrid.CreateGrid(2, 5)
        # 禁止使用者改變欄寬與列高
        self.fibonacciGrid.DisableDragColSize()
        self.fibonacciGrid.DisableDragRowSize()

        self.fibonacciGrid.SetRowLabelValue(0, "壓力")
        self.fibonacciGrid.SetRowLabelValue(1, "支撐")

        self.fibonacciGrid.SetColLabelValue(0, "0.236")
        self.fibonacciGrid.SetColLabelValue(1, "0.382")
        self.fibonacciGrid.SetColLabelValue(2, "0.5")
        self.fibonacciGrid.SetColLabelValue(3, "0.618")
        self.fibonacciGrid.SetColLabelValue(4, "0.786")

        self.fibonacciGrid.SetCellValue(0, 0, "空倉不急")
        self.fibonacciGrid.SetCellValue(0, 1, "開倉不畏")
        self.fibonacciGrid.SetCellValue(0, 2, "持倉不慌")
        self.fibonacciGrid.SetCellValue(0, 3, "平倉不悔")
        self.fibonacciGrid.SetCellValue(0, 4, "猶豫不決")
        self.fibonacciGrid.SetCellValue(1, 0, "學會放棄")
        self.fibonacciGrid.SetCellValue(1, 1, "學會等待")
        self.fibonacciGrid.SetCellValue(1, 2, "學會坦然")
        self.fibonacciGrid.SetCellValue(1, 3, "學會果斷")
        self.fibonacciGrid.SetCellValue(1, 4, "老而無成")
        # self.signalGrid.EnableScrolling(False, False)

        self.fibonacciGrid.SetDefaultCellBackgroundColour('BLACK')
        self.fibonacciGrid.EnableEditing(False)
        self.fibonacciGrid.AutoSizeColumns()

        attr_green = wx.grid.GridCellAttr()
        attr_green.SetTextColour(wx.GREEN)
        self.fibonacciGrid.SetRowAttr(0, attr_green)

        attr_red = wx.grid.GridCellAttr()
        attr_red.SetTextColour(wx.RED)
        self.fibonacciGrid.SetRowAttr(1, attr_red)

        for r in range(rows):
            for c in range(cols):
                self.fibonacciGrid.SetCellAlignment(
                    r, c, wx.ALIGN_CENTER, wx.ALIGN_CENTER)

        # 自動調整每欄與每列大小
        # self.fibonacciGrid.AutoSizeColumns()
        self.fibonacciGrid.AutoSizeRows()
        # 根據自動調整後的實際大小，更新 grid 控制項的尺寸
        grid_size = self.fibonacciGrid.GetBestSize()
        self.fibonacciGrid.SetSize(grid_size)
        ###################################################################################

        ###################################################################################
        #   比較各項資訊
        # Create a wxGrid object  ,size=(643, 185)
        self.compareInfoGrid = wx.grid.Grid(pnl, pos=(560, 310))
        self.compareInfoGrid.SetDefaultCellFont(font)
        # Then we call CreateGrid to set the dimensions of the grid
        # (10 rows and 10 columns in this example)
        self.compareInfoGrid.CreateGrid(2, 7)
        # 不顯示列名稱（左邊的數字標籤）
        self.compareInfoGrid.SetRowLabelSize(0)
        # 禁止使用者改變欄寬與列高
        self.compareInfoGrid.DisableDragColSize()
        self.compareInfoGrid.DisableDragRowSize()
        rows = self.compareInfoGrid.GetNumberRows()
        cols = self.compareInfoGrid.GetNumberCols()

        self.compareInfoGrid.SetColLabelValue(0, "比較高")
        self.compareInfoGrid.SetColLabelValue(1, "比較低")
        self.compareInfoGrid.SetColLabelValue(2, "比較時間")
        self.compareInfoGrid.SetColLabelValue(3, "比較量")
        self.compareInfoGrid.SetColLabelValue(4, "比較均價")
        self.compareInfoGrid.SetColLabelValue(5, "總平均價")
        self.compareInfoGrid.SetColLabelValue(6, "筆數")

        self.compareInfoGrid.SetCellValue(0, 0, "空倉不急")
        self.compareInfoGrid.SetCellValue(0, 1, "開倉不畏")
        self.compareInfoGrid.SetCellValue(0, 2, " 00:00:00.000 ")
        self.compareInfoGrid.SetCellValue(0, 3, "持不慌 ")
        self.compareInfoGrid.SetCellValue(0, 4, "猶豫不決 ")
        self.compareInfoGrid.SetCellValue(0, 5, "平倉不悔")
        self.compareInfoGrid.SetCellValue(0, 6, "1000")
        self.compareInfoGrid.SetCellValue(1, 0, "學會放棄")
        self.compareInfoGrid.SetCellValue(1, 1, "學會等待")
        self.compareInfoGrid.SetCellValue(1, 2, " 00:00:00.000 ")
        self.compareInfoGrid.SetCellValue(1, 3, "學坦然")
        self.compareInfoGrid.SetCellValue(1, 4, "猶豫不決")
        self.compareInfoGrid.SetCellValue(1, 5, "學會果斷")
        self.compareInfoGrid.SetCellValue(1, 6, "老無成")

        self.compareInfoGrid.SetDefaultCellBackgroundColour('BLACK')
        self.compareInfoGrid.AutoSizeColumns()
        self.compareInfoGrid.EnableEditing(True)  # 整張表格可編輯
        for r in range(self.compareInfoGrid.GetNumberRows()):  # 再把其他表格鎖起來
            for c in range(self.compareInfoGrid.GetNumberCols()):
                self.compareInfoGrid.SetReadOnly(r, c, True)
        self.compareInfoGrid.SetReadOnly(0, 6, False)  # 最後開放你要輸入的這一格

        attr_yellow = wx.grid.GridCellAttr()
        attr_yellow.SetTextColour(wx.YELLOW)
        self.compareInfoGrid.SetRowAttr(0, attr_yellow)
        self.compareInfoGrid.SetRowAttr(1, attr_yellow)

        # attr_red = wx.grid.GridCellAttr()
        # attr_red.SetTextColour(wx.RED)
        # self.compareInfoGrid.SetRowAttr(1, attr_red)

        for r in range(rows):
            for c in range(cols):
                self.compareInfoGrid.SetCellAlignment(
                    r, c, wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        # 自動調整每欄與每列大小
        # self.compareInfoGrid.AutoSizeColumns()
        self.compareInfoGrid.AutoSizeRows()
        # 根據自動調整後的實際大小，更新 grid 控制項的尺寸
        grid_size = self.compareInfoGrid.GetBestSize()
        self.compareInfoGrid.SetSize(grid_size)
        ###################################################################################

        ############################################################################

        # wx.StaticText(pnl, label='        通用查詢', pos=(560, 405))
        self.user_workid_combo = wx.Choice(pnl, choices=[
                                           'FA001-未平倉合計', 'FA002-未平倉明細', 'FA003-財務查詢', 'RA003-部位狀況'], pos=(560, 425), size=(100, 25))
        self.user_workid_combo.SetSelection(0)

        userquery = wx.Button(pnl, wx.ID_ANY, label='查詢',
                              pos=(580, 455), size=(70, 25))
        userquery.Bind(wx.EVT_BUTTON, partial(
            self.OnUserDefineBtn, method="通用"))

        wx.StaticText(pnl, label='未平倉口數：', pos=(560, 500))
        self.qtyLabel = wx.StaticText(pnl, label='未連', pos=(635, 500))

        self.chkSell = wx.CheckBox(pnl, label='作空', pos=(560, 525))
        self.chkBuy = wx.CheckBox(pnl, label='作多', pos=(620, 525))
        # 綁定事件
        self.chkSell.Bind(wx.EVT_CHECKBOX, self.OnChkDeal)
        self.chkBuy.Bind(wx.EVT_CHECKBOX, self.OnChkDeal)
        self.chkSell.SetValue(False)
        self.chkBuy.SetValue(False)
        ###################################################################################

        ###################################################################################
        wx.StaticText(pnl, label='錯失訊號', pos=(580, 200))
        self.missedSignal_combo = wx.Choice(
            pnl, choices=['無', '進場空', '進場多'], pos=(560, 220), size=(70, 25))
        self.missedSignal_combo.SetSelection(0)
        self.chkSignal = wx.CheckBox(pnl, pos=(635, 223))
        self.chkSignal.Bind(wx.EVT_CHECKBOX, self.OnMissedSignal)
        # self.chkSignal.SetValue(False)

        ###################################################################################

        ###################################################################################
        wx.StaticText(pnl, label='真實均價', pos=(580, 260))
        self.avgPrice = wx.TextCtrl(pnl, value="0", pos=(
            560, 280), size=(90, 25), style=wx.TE_CENTER)
        ###################################################################################

        # 連線行情
        self.ConnectionQuote(None)
        ###################################################################################
        global ts
        ts = TradingStrategy(self)  # 用 GUI Frame 傳給策略模組

        # 所有 UI 初始化完成後加這行
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnComboNumberOnly(self, event):
        key = event.GetKeyCode()

        # 允許 Backspace
        if key == wx.WXK_BACK:
            event.Skip()
            return

        # 允許 Enter
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            event.Skip()
            return

        # 允許方向鍵
        if key in (wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN):
            event.Skip()
            return

        # 允許 0–9（主鍵盤 + 小鍵盤）
        if (48 <= key <= 57) or (wx.WXK_NUMPAD0 <= key <= wx.WXK_NUMPAD9):
            event.Skip()
            return

        # ❌ 阻擋其他按鍵
        return

    def OnComboEnterValidate(self, event):
        combo = event.GetEventObject()   # ⭐ 自動抓到 price_combo 或 ktprice_combo
        # 🔥 判斷是哪一個 ComboBox
        if combo is self.price_combo:
            combo_name = "進場"
        elif combo is self.ktprice_combo:
            combo_name = "停利"
        else:
            combo_name = "未知 ComboBox"

        val = combo.GetValue()
        # 只保留數字
        filtered = ''.join([ch for ch in val if ch.isdigit()])

        # ❌ 錯誤：不是 5 位數
        if len(filtered) != 5:
            wx.Bell()  # 發出錯誤提示聲

            self.Logmessage(f"{combo_name}價格必須是 5 位數！")
            combo.SetValue("0")
            combo.SetSelection(-1, -1)  # 全選
            return  # ❗ 不 Skip → 不會產生系統 beep

        # ✔ 正確 → 生效
        combo.SetValue(str(filtered))
        self.Logmessage(f"{combo_name}價格生效：{filtered}")

        return  # 不 Skip → 不會 beep

    def OnClose(self, event):
        app = wx.GetApp()
        if hasattr(app, "keepGoing"):
            app.keepGoing = False
        self.Destroy()

    def OnBacktestData(self, event):
        # 1. 選檔案（只管 UI）
        with wx.FileDialog(
            self,
            "選擇檔案",
            wildcard="回測檔案 (event.log)|event.log",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return  # 使用者取消就乾淨離開
            filename = dlg.GetPath()

        direction = "空"      # 未來可做成參數
        is_simulation = 0     # 命名小寫，易讀

        # 狀態：記住目前是哪一個交易時段
        current_session = None      # "day" / "night" / None
        need_reset = False          # 用來標記下一個有效時段要重置

        def get_session(t):
            """
            用 tick[15] 的時間數字判斷屬於哪個交易時段：
            - 日盤: 08:45:00 ~ 13:45:00
            - 夜盤: 15:00:00 ~ 次日 05:00:00
            其他時間 (13:45~15:00、05:00~08:45) 回傳 None
            """
            # 這裡假設 t 是類似 84500000000, 134500000000 這種 HHMMSSxxxxxx 格式
            DAY_START = 84500000000
            DAY_END = 134500000000
            NIGHT_START = 150000000000
            NIGHT_END = 50000000000    # 凌晨 05:00:00 以前

            if DAY_START <= t <= DAY_END:
                return "day"
            # 夜盤是「下午三點以後」或「凌晨五點以前」（跨日）
            if t >= NIGHT_START or t <= NIGHT_END:
                return "night"
            return None  # 午休或非交易時間

        # 2. 執行回測主流程（用 try，但不要吃光）
        try:
            self.monitorTradeSignal.Clear()

            # ts.__init__(frame)

            print(f"你選擇的回測檔案是: {filename}")

            with open(filename, "r") as f:
                for raw in f:
                    # 先過濾不需要的行
                    if "全" not in raw or "tmatqty=-1" in raw or "open=0" in raw:
                        continue

                    # 字串轉 tick list
                    line = (
                        raw.replace("  [全] MDS=1 Symbol=", ",")
                        .replace("=", ",")
                        .strip("\n")
                    )
                    tick = line.split(",")

                    # 防呆：長度不夠就跳過
                    if len(tick) <= 29:
                        print(f"格式異常，略過: {raw.strip()}")
                        continue

                    try:
                        try:
                            tick_time = int(tick[15])
                            session = get_session(tick_time)
                        except ValueError:
                            continue  # 跳過不是數字的欄位

                         # 不在交易時間：標記需要重置，然後略過
                        if session is None:
                            if current_session is not None:
                                # 離開一個時段 → 等下一個合法時段出現時重置
                                need_reset = True
                            continue

                        # 進入新時段：重置策略狀態（清空原始數據）
                        if need_reset or session != current_session:
                            ts.__init__(frame)
                            print(f"=== 新開 {session} 盤，重置策略狀態 ===")
                            current_session = session
                            need_reset = False

                        # 時間 + bid 檢查
                        # if int(tick[15]) <= 134500000000 and tick[29] != "0":
                         # 這筆 tick 要不要進策略
                        if tick[29] != "0":
                            ts.execate_TXF_MXF(
                                direction,
                                tick[1],  # 股票代號
                                tick[3],  # 參考價
                                tick[5],  # 開盤價
                                tick[7],  # 最高價
                                tick[9],  # 最低價
                                tick[15],  # 成交時間
                                tick[17],  # 成交價
                                tick[19],  # 單量
                                tick[21],  # 總成交量
                                is_simulation
                            )
                    except Exception as e:
                        # 單筆 tick 的錯誤，要看得到
                        print(f"處理單筆 tick 發生錯誤: {e} | 原始資料: {raw.strip()}")

        except Exception as e:
            # 外層錯誤也要印出來，不要 pass
            print(f"回測執行錯誤: {e}")

    def OnQtyBtn(self, event):
        self.qtyLabel.SetLabel("QQ")

    def OnRegisterBtn(self, event):
        updatemodle = self.modle.GetString(self.modle.GetSelection())
        datas = self.symbol.GetValue().split(',')
        for data in datas:
            if self.rbAm.GetValue() == True:
                RegisterJob(Job.REGISTER, data, 1, updatemodle)
            else:
                RegisterJob(Job.REGISTER, data, 2, updatemodle)

    def OnUnRegisterBtn(self, event):
        datas = self.symbol.GetValue().split(',')
        for data in datas:
            if "XF" in data:
                self.Logmessage(f"{data}此為必須商品不能移除")
                continue
            if self.rbAm.GetValue() == True:
                UnRegisterJob(Job.UNREGISTER, data, 1)
            else:
                UnRegisterJob(Job.UNREGISTER, data, 2)

    def OnCtrlC(self, event):
        # Ctrl+C 複製
        cb = event.GetEventObject()
        if event.ControlDown() and event.GetKeyCode() == ord('C'):
            sel = cb.GetSelection()
            if sel != wx.NOT_FOUND:
                text = cb.GetString(sel)
                if wx.TheClipboard.Open():
                    wx.TheClipboard.SetData(wx.TextDataObject(text))
                    wx.TheClipboard.Close()
                    # print(f"已複製：{text}")
        else:
            event.Skip()  # 讓其他鍵仍可正常使用

    def OnAutoPositionCheck(self, event):
        if self.acclist_combo.GetCount() == 0:
            self.isAutoPosition.SetValue(False)
            self.Logmessage('請先登入並選擇期貨帳號')
            return
        if self.isAutoPosition.GetValue():
            self.position_watcher.start()
        else:
            self.position_watcher.stop()

    def OnMissedSignal(self, event):
        cb = event.GetEventObject()
        if self.chkSignal.IsChecked():
            val = self.missedSignal_combo.GetString(
                self.missedSignal_combo.GetSelection())
            if val == "進場空" and self.chkSell.IsChecked():
                ts.trading_sell = True
                self.Logmessage(f"錯失訊號: {val} trading_sell = True")
            elif val == "進場多" and self.chkBuy.IsChecked():
                ts.trading_buy = True
                self.Logmessage(f"錯失訊號: {val} trading_buy = True")
            else:
                # wx.MessageBox('錯失訊號與選擇下單方向不符','錯誤',wx.OK | wx.ICON_ERROR)
                self.Logmessage('錯失訊號與選擇下單方向不符')
                self.chkSignal.SetValue(False)
                return
        # else:
        #     ts.missed_signal = "無"

    def OnChkDeal(self, event):
        cb = event.GetEventObject()
        if cb == self.chkSell and self.chkSell.IsChecked():
            self.chkBuy.SetValue(False)
            self.bscode1_combo.SetSelection(1)  # S-賣出
            self.bscode2_combo.SetSelection(0)  # B-買進
            if ts.fibonacci_chkSell_str and ts.fibonacci_chkSell_str.strip() != "0":
                new_choices = [s.strip()
                               for s in ts.fibonacci_chkSell_str.split(":")]
                self.price_combo.SetItems(new_choices)
                self.price_combo.SetSelection(3)
            else:
                new_choices = ["0"]  # 或給預設選單
                self.price_combo.SetItems(new_choices)
                self.price_combo.SetSelection(0)
            if self.chkProfit.IsChecked():
                self.OnChkProfit(None)
        elif cb == self.chkBuy and self.chkBuy.IsChecked():
            self.chkSell.SetValue(False)
            self.bscode1_combo.SetSelection(0)  # B-買進
            self.bscode2_combo.SetSelection(1)  # S-賣出
            if ts.fibonacci_chkBuy_str and ts.fibonacci_chkBuy_str.strip() != "0":
                new_choices = [s.strip()
                               for s in ts.fibonacci_chkBuy_str.split(":")]
                self.price_combo.SetItems(new_choices)
                self.price_combo.SetSelection(3)
            else:
                new_choices = ["0"]  # 或給預設選單
                self.price_combo.SetItems(new_choices)
                self.price_combo.SetSelection(0)
            if self.chkProfit.IsChecked():
                self.OnChkProfit(None)
        else:
            new_choices = ["0"]  # 或給預設選單
            self.price_combo.SetItems(new_choices)
            self.price_combo.SetSelection(0)
            if self.chkProfit.IsChecked():
                self.chkProfit.SetValue(False)
                new_choices = ["0"]  # 或給預設選單
                self.ktprice_combo.SetItems(new_choices)
                self.ktprice_combo.SetSelection(0)

    def OnLogonBtn(self, event):
        LogonJob(Job.LOGON, self.acc.GetValue(), self.pwd.GetValue())

    def OnLogoutBtn(self, event):
        self.acclist_combo.Clear()
        self.isAutoPosition.SetValue(False)
        self.qtyLabel.SetLabel("未連")
        self.position_watcher.stop()
        self.chkSignal.SetValue(False)
        self.missedSignal_combo.SetSelection(0)
        self.chkSell.SetValue(False)
        self.chkBuy.SetValue(False)
        self.chkProfit.SetValue(False)
        LogoutJob(Job.LOGOUT)

    def OnUserDefineBtn(self, event=None, method=None):
        if self.acclist_combo.GetCount() == 0:
            self.Logmessage('請先登入並選擇期貨帳號')
            return
        vars = self.acclist_combo.GetString(
            self.acclist_combo.GetSelection()).split('-')
        func = "FA001"
        bhno = vars[1]
        ae_no = vars[2]
        if method == "庫存":
            user_params = f'Func=FA001|bhno={bhno}|acno={ae_no}|suba=|kind=A|FC=N'
        else:
            func = self.user_workid_combo.GetString(
                self.user_workid_combo.GetSelection()).split('-')[0]
            if func == "FA001" or func == "FA002" or func == "FA009":
                user_params = f'Func={func}|bhno={bhno}|acno={ae_no}|suba=|kind=A|FC=N'
            elif func == "RA003":
                user_params = f'Func={func}|bhno={bhno}|acno={ae_no}|suba=|FC=N'
            elif func == "FA003":
                user_params = f'Func={func}|bhno={bhno}|acno={ae_no}|suba=|type=1|currency=TWD'

        self.last_userdefine_source = "userquery"
        UserDefineJob(Job.USERDEFINE, user_params, func)

    def OnOrderBtn(self, event=None, S_Buys=None, price=None, offset=None):
        if self.acclist_combo.GetCount() == 0:
            # wx.MessageBox('請先登入並選擇期貨帳號','錯誤',wx.OK | wx.ICON_ERROR)
            self.Logmessage('請先登入並選擇期貨帳號')
            return
        if event:
            # val = self.price_combo.GetString(self.price_combo.GetSelection())
            price = self.price_combo.GetValue()
            # price = int(val) if val.isdigit() and val != "0" else "0"
            S_Buys = self.bscode1_combo.GetString(
                self.bscode1_combo.GetSelection())[0:1]
            offset = self.offset_combo.GetString(
                self.offset_combo.GetSelection())[0:1]
        vars = self.acclist_combo.GetString(
            self.acclist_combo.GetSelection()).split('-')
        bhno = vars[1]
        account = vars[2]
        ae_no = vars[3]
        OrderJob(Job.ORDER, bhno, account, ae_no, S_Buys, price, offset)

    def OnOrdQueryBtn(self, event):
        if self.acclist_combo.GetCount() == 0:
            # wx.MessageBox('請先登入並選擇期貨帳號','錯誤',wx.OK | wx.ICON_ERROR)
            self.Logmessage('請先登入並選擇期貨帳號')
            return
        vars = self.acclist_combo.GetString(
            self.acclist_combo.GetSelection()).split('-')
        bhno = vars[1]
        account = vars[2]
        ae_no = vars[3]
        OrdQueryJob(Job.ORDQUERY, bhno, account, ae_no)

    def OnMatQueryBtn(self, event):
        if self.acclist_combo.GetCount() == 0:
            # wx.MessageBox('請先登入並選擇期貨帳號','錯誤',wx.OK | wx.ICON_ERROR)
            self.Logmessage('請先登入並選擇期貨帳號')
            return
        vars = self.acclist_combo.GetString(
            self.acclist_combo.GetSelection()).split('-')
        bhno = vars[1]
        account = vars[2]
        ae_no = vars[3]
        MatQueryJob(Job.MATQUERY, bhno, account, ae_no)

    def OnChkProfit(self, event):
        if self.chkProfit.GetValue() == True and self.chkSell.IsChecked():
            # self.textktprice.Show(True)
            # self.ktprice_combo.Show(True)
            # self.textbs2.Show(True)
            # self.bscode2_combo.Show(True)
            self.chkBuy.SetValue(False)
            self.bscode1_combo.SetSelection(1)  # S-賣出
            self.bscode2_combo.SetSelection(0)  # B-買進
            # 空單停利目標三段價位字串
            if ts.order.profit_sell_str and ts.order.profit_sell_str.strip() != "0":
                new_choices = [s.strip()
                               for s in ts.order.profit_sell_str.split(":")]
                self.ktprice_combo.SetItems(new_choices)
                self.ktprice_combo.SetSelection(2)
            else:
                new_choices = ["0"]  # 或給預設選單
                self.ktprice_combo.SetItems(new_choices)
                self.ktprice_combo.SetSelection(0)
        elif self.chkProfit.GetValue() == True and self.chkBuy.IsChecked():
            # self.textktprice.Show(True)
            # self.ktprice_combo.Show(True)
            # self.textbs2.Show(True)
            # self.bscode2_combo.Show(True)
            self.chkSell.SetValue(False)
            self.bscode1_combo.SetSelection(0)  # B-買進
            self.bscode2_combo.SetSelection(1)  # S-賣出
            # 多單停利目標三段價位字串
            if ts.order.profit_buy_str and ts.order.profit_buy_str.strip() != "0":
                new_choices = [s.strip()
                               for s in ts.order.profit_buy_str.split(":")]
                self.ktprice_combo.SetItems(new_choices)
                self.ktprice_combo.SetSelection(2)
            else:
                new_choices = ["0"]  # 或給預設選單
                self.ktprice_combo.SetItems(new_choices)
                self.ktprice_combo.SetSelection(0)
        # else:
        #     new_choices = ["0"]  # 或給預設選單
        #     self.ktprice_combo.SetItems(new_choices)
        #     self.ktprice_combo.SetSelection(0)
        elif self.chkProfit.IsChecked():
            self.chkProfit.SetValue(False)
            new_choices = ["0"]  # 或給預設選單
            self.ktprice_combo.SetItems(new_choices)
            self.ktprice_combo.SetSelection(0)
            # self.textktprice.Show(False)
            # self.ktprice_combo.Show(False)
            # self.textbs2.Show(False)
            # self.bscode2_combo.Show(False)
            self.Logmessage("未勾選作空或作多")
        else:
            self.chkProfit.SetValue(False)
            new_choices = ["0"]  # 或給預設選單
            self.ktprice_combo.SetItems(new_choices)
            self.ktprice_combo.SetSelection(0)
            # self.textktprice.Show(False)
            # self.ktprice_combo.Show(False)
            # self.textbs2.Show(False)
            # self.bscode2_combo.Show(False)
            # self.Logmessage("未勾選作空或作多")

    def Logmessage(self, msg):
        # 如果是 Exception，就轉成字串
        if isinstance(msg, Exception):
            msg = f"[錯誤] {msg}"

        # 確保是字串
        msg = str(msg)
        try:
            self.statusMessage.Append(msg)
            item_count = self.statusMessage.GetCount()
            if item_count > 0:
                self.statusMessage.EnsureVisible(
                    self.statusMessage.GetCount()-1)
        except Exception as e:
            # 最後防線：避免 logging 再丟例外導致整個系統死掉
            print("Logmessage 失敗:", e, "| 原始訊息:", msg)

    def UpdateDayNight(self):
        # config = load_json("./config.json")
        # self.Username = config["username"]
        # self.Password = config["password"]
        # self.Host = "203.66.93.84"
        while True:
            if self.is_day() and not self.is_day_port():
                self.Port = 443
                # msg = "Change connection port to 443."
                msg = f"{datetime.datetime.now().strftime('%H:%M:%S')}  切換日盤port to 443並初始化數據."
                ts.__init__(frame)
                self.Logmessage(msg)
                self.ConnectionQuote(None)
            elif not self.is_day() and self.is_day_port():
                self.Port = 442
                msg = f"{datetime.datetime.now().strftime('%H:%M:%S')}  切換夜盤port to 442並初始化數據."
                ts.__init__(frame)
                self.Logmessage(msg)
                self.ConnectionQuote(None)
            time.sleep(60)

    def ConnectionQuote(self, event=None):
        # config = load_json("./config.json")
        # self.Username = config["username"]
        # self.Password = config["password"]
        # self.Host = "203.66.93.84"
        self.Port = 443 if self.is_day() else 442        
        self.rbAm.SetValue(True) if self.Port == 443 else self.rbPm.SetValue(True)
        LogonQuoteJob(Job.LOGONQUOTE, self.Username,
                      self.Password, self.Host, self.Port)
        # time.sleep(1)
    # 判斷是否為日盤連線埠

    def is_day_port(self):
        if self.Port == 443:
            return True
        if self.Port == 80:
            return True
        return False

    # 判斷是否為日盤時間
    def is_day(self):
        """
        07:00~14:45 - Day
        14:45~07:00 - Night
        """
        now = self.get_time()
        # now = datetime.datetime.now()
        day_begin = now.replace(hour=7, minute=50, second=0)
        day_end = now.replace(hour=14, minute=50, second=0)

        if now < day_begin:
            return False
        if now > day_end:
            return False
        return True

    # 判斷是否為交易時間(day+night)
    def is_trade_time(self):
        """
        08:45~13:45 - Day
        15:00~05:00 - Night
        """
        now = self.get_time()
        day_begin = now.replace(hour=8, minute=45, second=0)
        day_end = now.replace(hour=13, minute=45, second=0)
        night_begin = now.replace(hour=15, minute=00, second=0)
        night_end = now.replace(hour=5, minute=0, second=0)

        if now >= day_begin and now <= day_end:
            return True
        if now <= night_end:
            return True
        if now >= night_begin:
            return True

        return False

    def get_time(self):
        """Get the absolute time of UTC+8.「中原標準時間」"""
        d = datetime.timedelta(hours=8)
        t = datetime.datetime.utcnow()
        # t = datetime.datetime.now()
        t += d
        return t

    # 計算選擇權商品代碼
    def get_month_code(self):
        """計算期貨商品代碼"""
        # today = datetime.date.today()
        # day = datetime.date.today().replace(day=1)
        """計算期貨商品代碼（本月第三個星期三 14:00 後 → 切換到下個月合約）"""
        # 現在時間（含時分秒）
        now = datetime.datetime.now()
        # 本月 1 號的 datetime
        day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # 找到本月第一個星期三（weekday=2）
        while day.weekday() != 2:
            day = day + datetime.timedelta(days=1)
        # 第一個星期三 + 14 天 = 第三個星期三
        day = day + dateutil.relativedelta.relativedelta(days=14)
        # if day < today:
        #     day = day + dateutil.relativedelta.relativedelta(months=1)
        # 將時間設成 14:00
        third_wed_14 = day.replace(hour=14, minute=0, second=0, microsecond=0)
        # 若現在時間 >= 第三個星期三 14:00 → 使用下個月合約
        if now >= third_wed_14:
            third_wed_14 += dateutil.relativedelta(months=1)
        # Month code mapping（依你的券商規則 A～L)
        codes = "ABCDEFGHIJKL"
        # 年份最後一碼
        y = day.year % 10
        # 月份代碼字母
        m = codes[day.month - 1]

        return f"{m}{y}"
    # 計算期貨商品代碼

    def generate_codes_and_save(self):
        """
        自動產生 TXF、MXF 商品代碼，並寫入 code.json。

        JSON 格式：
        {
            "future": ["TXFK5", "MXFK5"]
        }
        """
        month_code = self.get_month_code()   # 取得像 K5、M4 這種月碼

        txf_code = f"TXF{month_code}"
        mxf_code = f"MXF{month_code}"

        data = {
            "future": [txf_code, mxf_code]
        }

        # 寫入 JSON
        with open("code.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        self.Logmessage(f"{datetime.datetime.now().strftime('%H:%M:%S')}  已產生並寫入 code.json：{data}")
        return data

    # def XF(self, code):
    #     return f"{code}{self.XXF()}"

    def reset_waitMinuteToSMS(self):
        self.waitMinuteToSMS = True


class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration

    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args:  # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False
#########################################
#########      Job define       #########
#########################################


class Job:
    LOGON = 1
    LOGOUT = 2
    USERDEFINE = 3
    ORDER = 4
    ORDQUERY = 5
    MATQUERY = 6
    REGISTER = 7
    UNREGISTER = 8
    QUOTE = 9
    INSERTSYMBOL = 10
    DELETESYMBOL = 11
    LOGONQUOTE = 12

    def __init__(self, job_type):
        self.job_type = job_type
#########################################
#########     Quote define      #########
#########################################


class LogonQuoteJob(Job):
    def __init__(self, job_type, account, password, host, port):
        super().__init__(job_type)
        self.account = account
        self.pwd = password
        self.host = host
        self.port = port
        q.put(self)


class RegisterJob(Job):
    def __init__(self, job_type, regSymbol, AmPm, modle):
        super(RegisterJob, self).__init__(job_type)
        self.regSymbol = regSymbol
        self.AmPm = AmPm
        self.modle = modle
        q.put(self)


class UnRegisterJob(Job):
    def __init__(self, job_type, unSymbol, AmPm):
        super(UnRegisterJob, self).__init__(job_type)
        self.unSymbol = unSymbol
        self.AmPm = AmPm
        q.put(self)


class QuoteJob(Job):
    def __init__(self, job_type, symbol, RefPri, OpenPri, HighPri, LowPri,  MatchTime, MatchPri, MatchQty, BestBuyPri, BestBuyQty, BestSellPri, BestSellQty, TolMatchQty):
        super(QuoteJob, self).__init__(job_type)
        self.symbol = symbol
        self.RefPri = RefPri
        self.OpenPri = OpenPri
        self.HighPri = HighPri
        self.LowPri = LowPri
        self.MatchTime = MatchTime
        self.MatchPri = MatchPri
        self.MatchQty = MatchQty
        self.BestBuyPri = BestBuyPri
        self.BestBuyQty = BestBuyQty
        self.BestSellPri = BestSellPri
        self.BestSellQty = BestSellQty
        self.TolMatchQty = TolMatchQty
        q.put(self)


class InsertSymbol(Job):
    def __init__(self, job_type, insertSymbol):
        super(InsertSymbol, self).__init__(job_type)
        self.symbol = insertSymbol
        q.put(self)


class DeleteSymbol(Job):
    def __init__(self, job_type, deleteSymbol):
        super(DeleteSymbol, self).__init__(job_type)
        self.symbol = deleteSymbol
        q.put(self)


class YuantaQuoteEvents(object):
    def __init__(self, parent):
        self.parent = parent

    def OnMktStatusChange(self, this, Status, Msg, ReqType):
        # print ('OnMktStatusChange {},{},{}'.format (ReqType, Msg, Status))
        # frame.SetConnectStatusValue(Msg)
        link_status = {
            -2: "網路連線失敗",
            -1: "網路連線中斷",
            0: "未進行連線",
            1: "準備連線",
            2: "登入成功",
        }

        if Status < 0:
            msg = f"{datetime.datetime.now().strftime('%H:%M:%S')}  {link_status.get(Status)}: Try to login again."
            frame.Logmessage(msg)
            if frame.is_trade_time():
                msg = f"{datetime.datetime.now().strftime('%H:%M:%S')}  Reconnection in trade time will be wait for 1 second"
                if frame.waitMinuteToSMS:
                    frame.waitMinuteToSMS = False
                    bot_message = f"{datetime.datetime.now().strftime('%H:%M:%S')}  網路中斷,目前在交易時間內請檢查連線狀況"
                    threading.Thread(target=ts.telegram_bot_sendtext, args=(
                        bot_message,), daemon=True).start()
                    threading.Timer(60, frame.reset_waitMinuteToSMS).start()
                frame.Logmessage(msg)
                time.sleep(1)
            else:
                msg = f"{datetime.datetime.now().strftime('%H:%M:%S')}  Reconnection beyond trade time will wait for 1 minutes"
                frame.Logmessage(msg)
                time.sleep(60)
            if Status == -1:
                frame.ConnectionQuote(None)

        if Status != 2:
            return

        # code_list = load_json("./code.json")
        # for code in code_list["stock"]:
        #     result = Bot.YuantaQ.YuantaQuote.AddMktReg(
        #         code, 2, ReqType, 0)
        #     msg = f"Registered {code}, result: {result}"
        #     frame.Logmessage(msg)
        # msg = "Stock registration done."
        # frame.Logmessage(msg)

        code_list = frame.generate_codes_and_save()
        choice_symbols = code_list["future"]
        frame.futno1_combo.SetItems(choice_symbols)
        frame.futno1_combo.SetSelection(1)

        data = ",".join(choice_symbols)
        frame.symbol.SetValue(data)

        for code in code_list["future"]:
            # code = frame.XF(code)
            result = Bot.YuantaQ.YuantaQuote.AddMktReg(
                code, 2, ReqType, 0)
            msg = f"Registered {code}, result: {result}"
            frame.Logmessage(msg)
        msg = f"{datetime.datetime.now().strftime('%H:%M:%S')}  Future registration done."
        frame.Logmessage(msg)

    def OnRegError(self, this, symbol, updmode, ErrCode, ReqType):
        link_status = {
            0: "註冊成功",
            1: "註冊商品錯誤(長度<4 或 >13)",
            2: "註冊方式錯誤",
            3: "連線未完成",
        }
        frame.Logmessage(f'OnRegError {link_status.get(ErrCode)},{symbol}')

    def OnGetMktData(self, this, PriType, symbol, Qty, Pri, ReqType):
        frame.Logmessage('OnGetMktData')

    def OnGetMktQuote(self, this, symbol, DisClosure, Duration, ReqType):
        frame.Logmessage('OnGetMktQuote')

    def OnGetMktAll(self, this, symbol, RefPri, OpenPri, HighPri, LowPri, UpPri, DnPri, MatchTime, MatchPri, MatchQty, TolMatchQty,
                    BestBuyQty, BestBuyPri, BestSellQty, BestSellPri, FDBPri, FDBQty, FDSPri, FDSQty, ReqType):
        # print ('OnGetMktAll')
        # print ('buy{} buyQty{} sell{} sellQty{}'.format (BestBuyPri,BestBuyQty,BestSellPri,BestSellQty))

        # 開盤
        if "-1" not in TolMatchQty and OpenPri != "0":
            QuoteJob(Job.QUOTE, symbol, RefPri, OpenPri, HighPri, LowPri, MatchTime, MatchPri,
                     MatchQty, BestBuyPri, BestBuyQty, BestSellPri, BestSellQty, TolMatchQty)

    def OnGetDelayClose(self, this, symbol, DelayClose, ReqType):
        frame.Logmessage('OnGetDelayClose')

    def OnGetBreakResume(self, this, symbol, BreakTime, ResumeTime, ReqType):
        frame.Logmessage('OnGetBreakResume')

    def OnGetTradeStatus(self, this, symbol, TradeStatus, ReqType):
        frame.Logmessage('OnGetTradeStatus')

    def OnTickRegError(self, this, strSymbol, lMode, lErrCode, ReqType):
        frame.Logmessage('OnTickRegError')

    def OnGetTickData(self, this, strSymbol, strTickSn, strMatchTime, strBuyPri, strSellPri, strMatchPri, strMatchQty, strTolMatQty,
                      strMatchAmt, strTolMatAmt, ReqType):
        frame.Logmessage('OnGetTickData')

    def OnTickRangeDataError(self, this, strSymbol, lErrCode, ReqType):
        frame.Logmessage('OnTickRangeDataError')

    def OnGetTickRangeData(self, this, strSymbol, strStartTime, strEndTime, strTolMatQty, strTolMatAmt, ReqType):
        frame.Logmessage('OnGetTickRangeData')

    def OnGetTimePack(self, this, strTradeType, strTime, ReqType):
        # print ('OnGetTimePack {},{}'.format (strTradeType, strTime))
        # T port 80/443 , T+1 port 82/442 ,  reqType=1 T盤 , reqType=2  T+1盤
        # strReqType = '日盤' if ReqType == 1 else '夜盤'
        print(f'{Back.BLUE}{Fore.YELLOW}{Style.BRIGHT}開始接受資料  {strTradeType}  {ReqType}  {strTime}{Style.RESET_ALL}')

    def OnGetDelayOpen(self, this, symbol, DelayOpen, ReqType):
        frame.Logmessage('OnGetDelayOpen')

    def OnGetFutStatus(self, this, symbol, FunctionCode, BreakTime, StartTime, ReopenTime, ReqType):
        frame.Logmessage('OnGetFutStatus')

    def OnGetLimitChange(self, this, symbol, FunctionCode, StatusTime, Level, ExpandType, ReqType):
        frame.Logmessage('OnGetLimitChange')


class YuantaQuoteWapper:
    def __init__(self, handle, bot):
        self.bot = bot

        Iwindow = POINTER(IUnknown)()
        Icontrol = POINTER(IUnknown)()
        Ievent = POINTER(IUnknown)()

        res = atl.AtlAxCreateControlEx("YUANTAQUOTE.YuantaQuoteCtrl.1", handle, None,
                                       byref(Iwindow),
                                       byref(Icontrol),
                                       byref(GUID()),
                                       Ievent)

        self.YuantaQuote = GetBestInterface(Icontrol)
        self.YuantaQuoteEvents = YuantaQuoteEvents(self)
        self.YuantaQuoteEventsConnect = GetEvents(
            self.YuantaQuote, self.YuantaQuoteEvents)

#########################################
#########     Order define      #########
#########################################


class LogonJob(Job):
    def __init__(self, job_type, account, password):
        super(LogonJob, self).__init__(job_type)
        self.account = account
        self.pwd = password
        q.put(self)


class LogoutJob(Job):
    def __init__(self, job_type):
        super(LogoutJob, self).__init__(job_type)
        q.put(self)


class UserDefineJob(Job):
    def __init__(self, job_type, params, workid):
        super(UserDefineJob, self).__init__(job_type)
        self.params = params
        self.workid = workid
        q.put(self)


class OrderJob(Job):
    def __init__(self, job_type, bhno, account, ae_no, S_Buys, price, offset):
        super(OrderJob, self).__init__(job_type)
        self.bhno = bhno
        self.account = account
        self.ae_no = ae_no
        self.S_Buys = S_Buys
        self.price = str(price)
        self.offset = str(offset)
        q.put(self)


class OrdQueryJob(Job):
    def __init__(self, job_type, bhno, account, ae_no):
        super(OrdQueryJob, self).__init__(job_type)
        self.bhno = bhno
        self.account = account
        self.ae_no = ae_no
        q.put(self)


class MatQueryJob(Job):
    def __init__(self, job_type, bhno, account, ae_no):
        super(MatQueryJob, self).__init__(job_type)
        self.bhno = bhno
        self.account = account
        self.ae_no = ae_no
        q.put(self)

# 元大API元件 能和元大主機溝通


class StockBot:
    def __init__(self, botuid):
        self.Yuanta = YuantaOrdWapper(botuid, self)
        self.YuantaQ = YuantaQuoteWapper(botuid, self)
        self.YuantaAccount = []
        self.YuantaSN = []

    def logon_quote(self, Username, Password, Host, Port):
        # T port 80/443 , T+1 port 82/442 ,  reqType=1 T盤 , reqType=2  T+1盤
        reqType = "日盤" if Port == 443 or Port == 80 else "夜盤"
        msg = f"{datetime.datetime.now().strftime('%H:%M:%S')}  連接報價行情主機  {Host}:{Port}  {reqType}"
        frame.Logmessage(msg)
        self.YuantaQ.YuantaQuote.SetMktLogon(Username, Password,
                                             Host, Port, 1, 0)

    def RegisterQuoteSymbol(self, QuoteSymbol, modle, ret_type):
        ret = self.YuantaQ.YuantaQuote.AddMktReg(
            QuoteSymbol, modle[0], ret_type, 0)
        link_status = {
            0: "註冊成功",
            1: "註冊商品錯誤(長度<4 或 >13)",
            2: "註冊方式錯誤",
            3: "連線未完成",
        }
        frame.Logmessage(f'{QuoteSymbol}  {link_status.get(ret)}')
        # frame.Logmessage(str(ret))   # 正常ret = 0
        # if ret == 0:
        #     InsertSymbol(Job.INSERTSYMBOL, QuoteSymbol)

    def UnRegisterQuoteSymbol(self, QuoteSymbol, ret_type):
        ret = self.YuantaQ.YuantaQuote.DelMktReg(QuoteSymbol, ret_type)
        link_status = {
            0: "取消註冊成功",
            1: "尚未登入",
            2: "該商品不存在",
            3: "連線未完成",
        }
        frame.Logmessage(f'{QuoteSymbol}  {link_status.get(ret)}')
        # if ret == 0:
        #    DeleteSymbol(Job.DELETESYMBOL,QuoteSymbol)
        #

    def login(self, account, pwd):
        self.Yuanta.YuantaOrd.SetFutOrdConnection(
            account, pwd, 'api.yuantafutures.com.tw', '80')
        frame.Logmessage('登入中...')

    def logout(self):
        self.Yuanta.YuantaOrd.DoLogout()
        frame.Logmessage('登出')

    def user_define(self, params, workid):
        # self.Yuanta.YuantaOrd.UserDefinsFunc(params, workid)
        ret = self.Yuanta.YuantaOrd.UserDefinsFunc(params, workid)
        # frame.Logmessage('user define ret = {}'.format(ret))

    def send_order(self, bhon, account, ae_no, S_Buys, price, offset):
        ## 同步、非同步##
        if frame.wait.GetValue() == True:
            self.Yuanta.YuantaOrd.SetWaitOrdResult(1)
        else:
            self.Yuanta.YuantaOrd.SetWaitOrdResult(0)
      
        frame.Logmessage("{}  SendOrderF() {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}".format(
            datetime.datetime.now().strftime('%H:%M:%S'),
            frame.fcode_combo.GetString(
                frame.fcode_combo.GetSelection())[0:2],
            frame.ctype_combo.GetString(
                frame.ctype_combo.GetSelection())[0:1],
            bhon,
            account,
            ae_no,
            frame.ordno.GetValue(),
            # frame.bscode1_combo.GetString(
            #     frame.bscode1_combo.GetSelection())[0:1],
            S_Buys,
            frame.futno1_combo.GetString(
                frame.futno1_combo.GetSelection())[0:5],
            # frame.price.GetValue(),
            price,
            frame.lots_combo.GetString(
                frame.lots_combo.GetSelection())[0:1],
            # frame.offset_combo.GetString(
            #     frame.offset_combo.GetSelection())[0:1],
            offset,
            frame.pritype_combo.GetString(
                frame.pritype_combo.GetSelection())[0:1],
            frame.pritype_cond.GetString(
                frame.pritype_cond.GetSelection())[0:1],
            # frame.bscode2_combo.GetString(
            #     frame.bscode2_combo.GetSelection())[0:1],
            '',
            ''))
        ret_no = self.Yuanta.YuantaOrd.SendOrderF(frame.fcode_combo.GetString(frame.fcode_combo.GetSelection())[0:2],
                                                  frame.ctype_combo.GetString(
            frame.ctype_combo.GetSelection())[0:1],
            bhon,
            account,
            ae_no,
            frame.ordno.GetValue(),
            # frame.bscode1_combo.GetString(
            # frame.bscode1_combo.GetSelection())[0:1],
            S_Buys,
            frame.futno1_combo.GetString(
            frame.futno1_combo.GetSelection())[0:5],
            # frame.price.GetValue(),
            price,
            frame.lots_combo.GetString(
            frame.lots_combo.GetSelection())[0:1],
            # frame.offset_combo.GetString(
            # frame.offset_combo.GetSelection())[0:1],
            offset,
            frame.pritype_combo.GetString(
            frame.pritype_combo.GetSelection())[0:1],
            frame.pritype_cond.GetString(
            frame.pritype_cond.GetSelection())[0:1],
            # bs2,
            # frame.futno2.GetValue().strip())
            '',
            '')
        frame.Logmessage(f"{datetime.datetime.now().strftime('%H:%M:%S')}  SendOrderF() return = {ret_no}")

    def send_ordQuery(self, bhon, account, ae_no):
        # if frame.chkProfit.GetValue() == True:  # 查國外
        #     ret_code = self.Yuanta.YuantaOrd.RfReportQuery(bhon, account, ae_no,
        #                                                    frame.ordstatus_combo.GetString(
        #                                                        frame.ordstatus_combo.GetSelection())[0:1],
        #                                                    frame.ordcflag_combo.GetString(
        #                                                        frame.ordcflag_combo.GetSelection())[0:1],
        #                                                    '*')
        #     frame.Logmessage("RfReportQuery() return = {}".format(ret_code))
        # else:  # 查國內
        ret_code = self.Yuanta.YuantaOrd.ReportQuery("F", bhon, account, ae_no,
                                                     frame.ordstatus_combo.GetString(
                                                         frame.ordstatus_combo.GetSelection())[0:1],
                                                     '*',
                                                     frame.ordcflag_combo.GetString(frame.ordcflag_combo.GetSelection())[0:1])
        frame.Logmessage("ReportQuery() return = {}".format(ret_code))

    def send_matQuery(self, bhon, account, ae_no):
        # if frame.chkProfit.GetValue() == True:  # 查國外
        #     ret_code = self.Yuanta.YuantaOrd.RfDealQuery(
        #         bhon, account, ae_no, '*')
        #     frame.Logmessage("RfDealQuery() return = {}".format(ret_code))
        # else:  # 查國內
        ret_code = self.Yuanta.YuantaOrd.DealQuery(
            "F", bhon, account, ae_no, '*')
        frame.Logmessage("DealQuery() return = {}".format(ret_code))


class YuantaOrdEvents(object):
    def __init__(self, parent):
        self.parent = parent

    def OnLogonS(self, this, TLinkStatus, AccList, Casq, Cast):
        frame.Logmessage('OnLogonS {},{},{},{}'.format(
            TLinkStatus, AccList, Casq, Cast))
        status = '{}'.format(TLinkStatus)
        frame.connect_status.SetValue(status)
        if TLinkStatus == 2:
            datas = AccList.split(';')
            for data in datas:
                frame.acclist_combo.Append(data)
            frame.acclist_combo.SetSelection(0)
            if len(Casq) != 0:
                Bot.YuantaSN.append(Casq.split('=')[1])
            # # 登入查庫存
            # if frame.isAutoPosition.GetValue()==False:
            #     frame.isAutoPosition.SetValue(True)
            #     frame.OnAutoPositionCheck(None)
            frame.OnUserDefineBtn(event=None, method="庫存")

    # 手動委託回報查詢
    def OnReportQuery(self, this, RowCount, Results):
        """
        將 Yuanta 回報 Results 拆成 RowCount 筆，
        每筆以 '|' 分割、以 '=' 拆成 key/value，
        最終整理成 row_dict，並依 O_TIME 升冪排序。
        """

        frame.OrdQueryRpt.Clear()

        raw_fields = Results.split('|')
        fields = [f.strip() for f in raw_fields if f.strip()]

        total = len(fields)

        if RowCount <= 0 or total % RowCount != 0:
            frame.OrdQueryRpt.Append(f"RowCount={RowCount} 或欄位數不符，資料無法解析")
            return

        columns = total // RowCount

        all_rows = []

        # 1. 拆成每筆資料
        for row_idx in range(RowCount):
            start = row_idx * columns
            end = start + columns

            row_items = fields[start:end]
            row_dict = {}

            for item in row_items:
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                row_dict[key.strip()] = value.strip()

            all_rows.append(row_dict)

        # 2. 依 O_TIME 排序 (由小到大)
        sorted_rows = sorted(
            all_rows,
            key=lambda x: x.get('O_TIME', '000000')  # 避免 O_TIME 缺失
        )

        # 3. 顯示排序後結果
        for row in sorted_rows:
            msg = (
                f"{row.get('O_TIME', '')}  手查  {row.get('TS_MSG', '')}  {row.get('SYMB', '')}  "
                f"{row.get('O_KIND', '')}  {row.get('BUYS', '')}  {row.get('S_BUYS', '')}  "
                f"{row.get('O_QYT', '')}  {row.get('O_PRC', '')}  {row.get('ORDER_NO', '')}  "
                f"{row.get('ERR_MSG', '')}"
            )
            frame.OrdQueryRpt.Append(msg)

    # 手動成交回報查詢
    def OnDealQuery(self, this, RowCount, Results):
        frame.MatQueryRpt.Clear()
        """
        將 Yuanta 回報 Results 拆成 RowCount 筆，
        每筆以 '|' 分割、以 '=' 拆成 key/value，
        最終整理成 row_dict，並依 O_TIME 升冪排序。
        """

        frame.MatQueryRpt.Clear()

        raw_fields = Results.split('|')
        fields = [f.strip() for f in raw_fields if f.strip()]

        total = len(fields)

        if RowCount <= 0 or total % RowCount != 0:
            frame.MatQueryRpt.Append(f"RowCount={RowCount} 或欄位數不符，資料無法解析")
            return

        columns = total // RowCount

        all_rows = []

        # 1. 拆成每筆資料
        for row_idx in range(RowCount):
            start = row_idx * columns
            end = start + columns

            row_items = fields[start:end]
            row_dict = {}

            for item in row_items:
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                row_dict[key.strip()] = value.strip()

            all_rows.append(row_dict)

        # 2. 依 O_TIME 排序 (由小到大)
        sorted_rows = sorted(
            all_rows,
            key=lambda x: x.get('D_TIME', '000000')  # 避免 O_TIME 缺失
        )

        # 3. 顯示排序後結果
        for row in sorted_rows:
            msg = (
                f"{row.get('D_TIME', '')}  手查  {row.get('SYMB', '')}  "
                f"{row.get('O_KIND', '')}  {row.get('BUYS', '')}  {row.get('S_BUYS', '')}  "
                f"{row.get('O_QTY', '')}  {row.get('A_PRC', '')}  {row.get('ORDER_NO', '')}  "
            )
            frame.MatQueryRpt.Append(msg)

    # 通用查詢 Event
    def OnUserDefinsFuncResult(self, this, RowCount, Results, WorkID):
        try:
            # data = dict(p.split("=") for p in Results.split("|"))
            # parts = [p.split("=") for p in Results.split("|") if "=" in p]
            # data = dict((k, v) for k, v in parts if len((k, v)) == 2)
            data = {}
            for seg in Results.split("|"):
                if "=" in seg:  # 只處理有等號的
                    k, v = seg.split("=", 1)  # 最多分割一次，避免 value 裡也有 "="
                    data[k] = v

            if frame.last_userdefine_source == "autoposition":
                if frame.qtyLabel.GetLabel() != data["TOTAL_OFF_POSITION"]:
                    frame.qtyLabel.SetLabel(data["TOTAL_OFF_POSITION"])
                    frame.Logmessage(Results)
            elif frame.last_userdefine_source == "userquery":
                if WorkID == "FA001" or WorkID == "FA002":
                    frame.qtyLabel.SetLabel(data["TOTAL_OFF_POSITION"])
                    frame.Logmessage(Results)
                elif WorkID == "FA003":
                    result = f'權益數:{data["EQUITY"]}  浮動損益:{data["FLOAT_MARGIN"]}  本日損益:{data["GRANTAL"]}'
                    frame.Logmessage(result)
                # elif WorkID == "RA003":
                else:
                    frame.Logmessage(Results)
        except Exception as e:
            frame.Logmessage(f"OnUserDefinsFuncResult error: {e}")
        finally:
            frame.last_userdefine_source = None

    # 自動委託回報 Event
    def OnOrdRptF(self, this, Omkt, Mktt, Cmbf, Statusc, Ts_Code, Ts_Msg, Bhno, AcNo,
                  Suba, Symb, Scnam, O_Kind, O_Type, Buys, S_Buys, O_Prc, O_Qty, Work_Qty, Kill_Qty,
                  Deal_Qty, Order_No, T_Date, O_Date, O_Time,
                  O_Src, O_Lin, A_Prc, Oseq_No, Err_Code,
                  Err_Msg, R_Time, D_Flag):
        
        # msg = 'Omkt={},Mktt={},Cmbf={},Statusc={},Ts_Code={},Ts_Msg={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},O_Type={},Buys={},S_Buys={},O_Prc={},O_Qty={},Work_Qty={},Kill_Qty={},Deal_Qty={},Order_No={},T_Date={},O_Date={},O_Time={},O_Src={},O_Lin={},A_Prc={},Oseq_No={},Err_Code={},Err_Msg={},R_Time={},D_Flag={}'.format(Omkt.strip(), Mktt.strip(), Cmbf.strip(), Statusc.strip(), Ts_Code.strip(), Ts_Msg.strip(
        # ), Bhno.strip(), AcNo.strip(), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), O_Type.strip(), Buys.strip(), S_Buys.strip(), O_Prc.strip(), O_Qty.strip(), Work_Qty.strip(), Kill_Qty.strip(), Deal_Qty.strip(), Order_No.strip(), T_Date.strip(), O_Date.strip(), O_Time.strip(), O_Src.strip(), O_Lin.strip(), A_Prc.strip(), Oseq_No.strip(), Err_Code.strip(), Err_Msg.strip(), R_Time.strip(), D_Flag.strip())
        
        msg = f"{O_Time.strip()}  自查  {Ts_Msg.strip()}  {Symb.strip()}  {O_Kind.strip()}  {Buys.strip()}  {S_Buys.strip()}  {O_Qty.strip()}  {O_Prc.strip()}  {Order_No.strip()}  {Err_Msg.strip()}"
        frame.OrdQueryRpt.Append(msg)
        item_count = frame.OrdQueryRpt.GetCount()
        if item_count > 0:
            frame.OrdQueryRpt.EnsureVisible(frame.OrdQueryRpt.GetCount()-1)

    # 自動成交回報 Event
    def OnOrdMatF(self, this, Omkt, Buys, Cmbf, Bhno,
                  AcNo, Suba, Symb, Scnam, O_Kind,
                  S_Buys, O_Prc, A_Prc, O_Qty, Deal_Qty,
                  T_Date, D_Time, Order_No, O_Src, O_Lin,
                  Oseq_No):
        # 檢查庫存
        # frame.OnUserDefineBtn(event=None, method="庫存")
        # # 檢查庫存  手動呼叫事件函式
        if frame.isAutoPosition.GetValue() == False:
            frame.isAutoPosition.SetValue(True)
            frame.OnAutoPositionCheck(None)

        # msg = 'Omkt={},Buys={},Cmbf={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},S_Buys={},O_Prc={},A_Prc={},O_Qty={},Deal_Qty={},T_Date={},D_Time={},Order_No={},O_Src={},O_Lin={},Oseq_No={}'.format(Omkt.strip(), Buys.strip(), Cmbf.strip(), Bhno.strip(
        # ), AcNo.strip(), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), S_Buys.strip(), O_Prc.strip(), A_Prc.strip(), O_Qty.strip(), Deal_Qty.strip(), T_Date.strip(), D_Time.strip(), Order_No.strip(), O_Src.strip(), O_Lin.strip(), Oseq_No.strip())
        msg = f"{D_Time.strip()}  自查  {Symb.strip()}  {O_Kind.strip()}  {Buys.strip()}  {S_Buys.strip()}  {O_Qty.strip()}  {O_Prc.strip()}  {Order_No.strip()}"

        frame.MatQueryRpt.Append(msg)
        item_count = frame.MatQueryRpt.GetCount()
        if item_count > 0:
            frame.MatQueryRpt.EnsureVisible(frame.MatQueryRpt.GetCount()-1)
    # 委託結果 當委託後產生Event

    def OnOrdResult(self, this, ID, result):
        msg = f"{datetime.datetime.now().strftime('%H:%M:%S')}  OnOrdResult:ID={ID},result={result}"
        frame.Logmessage(msg)

    def OnRfOrdRptRF(self, this, exc, Omkt, Statusc, Ts_Code,
                     Ts_Msg, Bhno, Acno, Suba, Symb,
                     Scnam, O_Kind, Buys, S_Buys, PriceType,
                     O_Prc1, O_Prc2, O_Qty, Work_Qty, Kill_Qty,
                     Deal_Qty, Order_No, O_Date, O_Time, O_Src,
                     O_Lin, A_Prc, Oseq_No, Err_Code, Err_Msg,
                     R_Time, D_Flag):
        msg = 'Exchange={},Omkt={},Statusc={},Ts_Code={},Ts_Msg={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},Buys={},S_Buys={},PriceType={},O_Prc1={},O_Prc2={},O_Qty={},Work_Qty={},Kill_Qty={},Deal_Qty={},Order_No={},O_Date={},O_Time={},O_Src={},O_Lin={},A_Prc={},Oseq_No={},Err_Code={},Err_Msg={},R_Time={},D_Flag={}'.format(exc.strip(), Omkt.strip(), Statusc.strip(), Ts_Code.strip(), Ts_Msg.strip(), Bhno.strip(
        ), Acno.strip(), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), Buys.strip(), S_Buys.strip(), PriceType.strip(), O_Prc1.strip(), O_Prc2.strip(), O_Qty.strip(), Work_Qty.strip(), Kill_Qty.strip(), Deal_Qty.strip(), Order_No.strip(), O_Date.strip(), O_Time.strip(), O_Src.strip(), O_Lin.strip(), A_Prc.strip(), Oseq_No.strip(), Err_Code.strip(), Err_Msg.strip(), R_Time.strip(), D_Flag.strip())
        frame.OrdQueryRpt.Append(msg)

    def OnRfOrdMatRF(self, this, Exchange, Omkt, Bhno, AcNo,
                     Suba, Symb, Scnam, O_Kind, Buys,
                     S_Buys, PriceType, O_Prc1, O_Prc2, A_Prc,
                     O_Qty, Deal_Qty, O_Date, D_Time, Order_No,
                     O_Src, O_Lin, Oseq_No):
        msg = 'Exchange={},Omkt={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},Buys={},S_Buys={},PriceType={},O_Prc1={},O_Prc2={},A_Prc={},O_Qty={},Deal_Qty={},Order_No={},O_Date={},D_Time={},O_Src={},O_Lin={},Oseq_No={}'.format(Exchange.strip(), Omkt.strip(), Bhno.strip(), AcNo.strip(
        ), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), Buys.strip(), S_Buys.strip(), PriceType.strip(), O_Prc1.strip(), O_Prc2.strip(), A_Prc.strip(), O_Qty.strip(), Deal_Qty.strip(), Order_No.strip(), O_Date.strip(), D_Time.strip(), O_Src.strip(), O_Lin.strip(), Oseq_No.strip())
        frame.MatQueryRpt.Append(msg)

    def OnRfOrdResult(self, this, ID, result):
        msg = 'OnRfOrdResult:ID={},result={}'.format(ID, result)
        frame.Logmessage(msg)

    def OnRfReportQuery(self, this, RowCount, Results):
        frame.OrdQueryRpt.Clear()
        datas = Results.split('|')
        for i in range(0, RowCount):
            data = ''
            for j in range(0, int(len(datas) / RowCount)):
                data += datas[i * (int(len(datas) / RowCount)) + j]
                if j < int(len(datas) / RowCount) - 1:
                    data += ','
                else:
                    frame.OrdQueryRpt.Append(data)

    def OnRfDealQuery(self, this, RowCount, Results):
        frame.MatQueryRpt.Clear()
        datas = Results.split('|')
        for i in range(0, RowCount):
            data = ''
            for j in range(0, int(len(datas) / RowCount)):
                data += datas[i * (int(len(datas) / RowCount)) + j]
                if j < int(len(datas) / RowCount) - 1:
                    data += ','
                else:
                    frame.MatQueryRpt.Append(data)


class YuantaOrdWapper:
    def __init__(self, handle, bot):
        self.bot = bot

        Iwindow = POINTER(IUnknown)()
        Icontrol = POINTER(IUnknown)()
        Ievent = POINTER(IUnknown)()

        res = atl.AtlAxCreateControlEx("Yuanta.YuantaOrdCtrl.1", handle, None,
                                       byref(Iwindow),
                                       byref(Icontrol),
                                       byref(GUID()),
                                       Ievent)

        self.YuantaOrd = GetBestInterface(Icontrol)
        self.YuantaOrdEvents = YuantaOrdEvents(self)
        self.YuantaOrdEventsConnect = GetEvents(
            self.YuantaOrd, self.YuantaOrdEvents)


class MyApp(wx.App):
    def MainLoop(self, run_func):
        """
        改良版主事件迴圈 (完整保留原設計)
        - 外層: 控制程式生命週期
        - 中層: 處理交易工作佇列
        - 內層: 處理 GUI 事件與 idle
        - 新增: Frame 存活檢查 + idle 安全防護
        """
        evtloop = wx.GUIEventLoop()
        old = wx.EventLoop.GetActive()
        wx.EventLoop.SetActive(evtloop)

        frame = wx.GetTopLevelWindows()[0] if wx.GetTopLevelWindows() else None

        while getattr(self, "keepGoing", True):
            # 1️⃣ 檢查 GUI 是否仍存在
            if frame is None or not frame.IsShown():
                print("⚠️ Frame 已關閉，結束 MainLoop。")
                break

            # 2️⃣ 主任務邏輯 (策略、行情更新)
            try:
                run_func()
            except Exception as e:
                print(f"MainLoop 執行 run_func 發生錯誤: {e}")

            # 3️⃣ 核心佇列任務 (交易訊息)
            try:
                while not q.empty():
                    next_job = q.get()
                    DoJob(Bot, next_job)
            except Exception as e:
                print(f"DoJob 執行錯誤: {e}")

            # 4️⃣ GUI 事件處理
            try:
                while evtloop.Pending():
                    evtloop.Dispatch()
            except Exception as e:
                print(f"事件 Dispatch 錯誤: {e}")

            # 5️⃣ Idle 與節流 time.sleep(防止 CPU 滿載)
            try:
                # time.sleep(0.1)
                # if wx.GetApp() and wx.GetApp().IsMainLoopRunning():
                evtloop.ProcessIdle()
            except (wx._core.wxAssertionError, RuntimeError):
                # GUI 已經關閉 / 控制項被刪除，直接跳出，不再 print，避免觸發 RedirectText
                break
            except Exception:
                # 其他錯誤一樣直接跳出，避免再寫入已死掉的 TextCtrl
                break

        wx.EventLoop.SetActive(old)
        # print("✅ MainLoop 已正常結束。")   # 這裡也不要 print，因為 sys.stdout 可能還是被導向 TextCtrl

    def OnInit(self):
        self.keepGoing = True
        return True


class PositionWatcher:
    def __init__(self, interval=30):
        self.interval = interval
        self.stop_flag = threading.Event()
        self.thread = None
        self.user_params = None

    def start(self):
        """啟動背景查倉執行緒"""
        if self.thread and self.thread.is_alive():
            frame.Logmessage("⚠️ 查倉執行緒已在運行中")
            return
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        vars = frame.acclist_combo.GetString(
            frame.acclist_combo.GetSelection()).split('-')
        bhno = vars[1]
        ae_no = vars[2]
        self.user_params = f'Func=FA001|bhno={bhno}|acno={ae_no}|suba=|kind=A|FC=N'
        frame.Logmessage("✅ 已啟動自動查倉")

    def stop(self):
        """停止背景查倉執行緒"""
        if self.thread:
            self.stop_flag.set()
            frame.qtyLabel.SetLabel("未連")
            frame.Logmessage("🛑 已停止自動查倉（執行緒將自行結束）")
            wx.CallLater(500, self._check_thread_done)

    def _check_thread_done(self):
        if self.thread and not self.thread.is_alive():
            frame.Logmessage("✅ 查倉執行緒已安全結束")
            self.thread = None
        else:
            wx.CallLater(500, self._check_thread_done)

    def _loop(self):
        """執行緒主迴圈"""
        while not self.stop_flag.is_set() and frame.acclist_combo.GetCount() != 0:  # and not frame.last_userdefine_source:
            frame.last_userdefine_source = "autoposition"
            # frame.OnUserDefineBtn(event=None, method="庫存")
            UserDefineJob(Job.USERDEFINE, self.user_params, "FA001")
            time.sleep(self.interval)
        frame.Logmessage("查倉執行緒結束 (正常退出或條件不符)")
        # self.thread = None


def DoJob(Bot, x):    # x表示各類Job
    for case in switch(x.job_type):
        if case(Job.LOGON):
            Bot.login(x.account, x.pwd)
            break
        if case(Job.LOGOUT):
            Bot.logout()
            break
        if case(Job.USERDEFINE):
            Bot.user_define(x.params, x.workid)
            break
        if case(Job.ORDER):
            Bot.send_order(x.bhno, x.account, x.ae_no,
                           x.S_Buys, x.price, x.offset)
            break
        if case(Job.ORDQUERY):
            Bot.send_ordQuery(x.bhno, x.account, x.ae_no)
            break
        if case(Job.MATQUERY):
            Bot.send_matQuery(x.bhno, x.account, x.ae_no)
            break
        if case(Job.REGISTER):
            frame.Logmessage(f"註冊報價: {x.regSymbol}, {x.modle[0]}")
            Bot.RegisterQuoteSymbol(x.regSymbol, x.modle, x.AmPm)
            break
        if case(Job.UNREGISTER):
            frame.Logmessage(f"取消註冊: {x.unSymbol}")
            Bot.UnRegisterQuoteSymbol(x.unSymbol, x.AmPm)
            break
        if case(Job.QUOTE):
            # frame.UpdateSymbol(x.symbol,x.RefPri, x.OpenPri, x.HighPri, x.LowPri, x.MatchTime, x.MatchPri, x.MatchQty, x.BestBuyPri, x.BestBuyQty, x.BestSellPri, x.BestSellQty)
            direction = "空"  # "多" #
            Is_simulation = 1
            try:
                ts.execate_TXF_MXF(direction, x.symbol, x.RefPri, x.OpenPri, x.HighPri, x.LowPri, x.MatchTime,
                                   x.MatchPri, x.MatchQty, x.TolMatchQty, Is_simulation)
                # 更新費波那契數
                # ts.calculate_and_update()
            except Exception as e:
                frame.Logmessage(e)
            break
        if case(Job.INSERTSYMBOL):
            frame.InsertSymbol(x.symbol)
            break
        if case(Job.DELETESYMBOL):
            frame.DeleteSymbol(x.symbol)
            break
        if case(Job.LOGONQUOTE):
            Bot.logon_quote(x.account, x.pwd, x.host, x.port)
            break


def run_job():
    while not q.empty():
        next_job = q.get()
        DoJob(Bot, next_job)


def load_json(fpath):
    with open(fpath, "r", encoding="UTF-8") as f:
        return json.load(f)


if __name__ == "__main__":
    APP_VERSION = "v1.1.0"
    today = datetime.date.today().strftime("%Y-%m-%d")
    app = MyApp()
    frame = AppFrame(None, title=f'千金交易系統  {APP_VERSION}  ({today})', size=(1260, 850))
    frame.SetPosition((10, 10))
    frame.Show(True)
    Bot = StockBot(frame.Handle)
    # ts = trading_strategy_calc.TradingStrategy(frame)
    threading.Thread(target=frame.UpdateDayNight, daemon=True).start()
    app.MainLoop(run_job)

"""
Host IP: 203.66.93.84
Host Domain: apiquote.yuantafutures.com.tw
T Port: 80 or 443
T+1 Port: 82 or 442
"""
