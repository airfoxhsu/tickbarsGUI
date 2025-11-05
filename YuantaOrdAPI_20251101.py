# -*- coding: utf-8 -*-
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
import trading_strategy_calc
from colorama import Fore, Back, Style, init
from functools import partial

user32 = windll.user32
atl = windll.atl
q = queue.Queue()


class AppFrame(wx.Frame):
    """
    A Frame that says AppFrame
    """

    def __init__(self, *args, **kw):
        # ensure the parent's __init__ is called
        super(AppFrame, self).__init__(*args, **kw)

        # ts = trading_strategy_calc.RedirectText(None)

        # create a panel in the frame
        pnl = wx.Panel(self)
        # ts = trading_strategy_calc.TradingStrategy(pnl)

        ############################################################################
        #   API連線資訊
        wx.StaticBox(pnl, label='API連線資訊', pos=(1, 1), size=(650, 70))
        wx.StaticText(pnl, label='ID', pos=(11, 30))
        wx.StaticText(pnl, label='密碼', pos=(155, 30))
        config = load_json("./config.json")
        self.acc = wx.TextCtrl(
            pnl, value=config["username"], pos=(42, 26), size=(100, 25))
        self.pwd = wx.TextCtrl(pnl, value=config["password"], pos=(
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

        self.ctype_rfcombo = wx.Choice(
            pnl, choices=['F-期貨', 'O-選擇權'], pos=(180, 97), size=(70, 30))
        self.ctype_rfcombo.Show(False)
        self.ctype_rfcombo.SetSelection(0)

        wx.StaticText(pnl, label='委託書', pos=(271, 100))
        self.ordno = wx.TextCtrl(pnl, pos=(310, 97), size=(70, 23))

        wx.StaticText(pnl, label='委託類', pos=(391, 100))
        self.offset_combo = wx.Choice(
            pnl, choices=['0-新倉', '1-平倉', '2-當沖', ' -自動'], pos=(430, 97), size=(70, 30))
        self.offset_combo.SetSelection(3)

        self.wait = wx.CheckBox(pnl, label='等待委託單號', pos=(520, 100))

        wx.StaticText(pnl, label='買賣1', pos=(11, 130))
        self.bscode1_combo = wx.Choice(
            pnl, choices=['B-買進', 'S-賣出'], pos=(50, 127), size=(70, 30))
        self.bscode1_combo.SetSelection(1)

        wx.StaticText(pnl, label='商品1', pos=(141, 130))
        data = load_json("./code.json")
        choice_symbols = data["stock"]
        self.futno1_combo = wx.Choice(
            pnl, choices=choice_symbols, pos=(180, 127), size=(70, 23))
        self.futno1_combo.SetSelection(1)

        wx.StaticText(pnl, label='價格', pos=(271, 130))
        self.price = wx.TextCtrl(pnl, pos=(310, 127), size=(70, 23))
        self.price.SetValue("31273")

        wx.StaticText(pnl, label='數量', pos=(391, 130))
        self.lots_combo = wx.Choice(
            pnl, choices=['1', '2', '3', '4', '5'], pos=(430, 127), size=(50, 23))
        self.lots_combo.SetSelection(0)

        self.rfcheck = wx.CheckBox(pnl, label='外期', pos=(520, 130))
        self.rfcheck.Bind(wx.EVT_CHECKBOX, self.ORFcheckBtn)

        self.textbs2 = wx.StaticText(pnl, label='買賣2', pos=(11, 160))
        self.bscode2_combo = wx.Choice(
            pnl, choices=['B-買進', 'S-賣出'], pos=(50, 157), size=(70, 30))
        self.bscode2_combo.SetSelection(0)

        self.textsymbol = wx.StaticText(pnl, label='商品2', pos=(141, 160))
        self.futno2 = wx.TextCtrl(pnl, pos=(180, 157), size=(70, 23))

        self.textstopprice = wx.StaticText(pnl, label='停損價', pos=(141, 160))
        self.stopprice = wx.TextCtrl(pnl, pos=(180, 157), size=(70, 23))
        self.textstopprice.Show(False)
        self.stopprice.Show(False)

        wx.StaticText(pnl, label='限市價', pos=(271, 160))
        self.pritype_combo = wx.Choice(
            pnl, choices=['L-限價', 'M-市價', 'P-範圍市價'], pos=(310, 157), size=(70, 30))
        self.pritype_combo.SetSelection(0)

        self.pritype_rfcombo = wx.Choice(
            pnl, choices=['1-限價', '2-市價', '4-停損', '8-停損限價'], pos=(310, 157), size=(70, 30))
        self.pritype_rfcombo.Show(False)
        self.pritype_rfcombo.SetSelection(0)

        wx.StaticText(pnl, label='條件', pos=(391, 160))
        self.pritype_cond = wx.Choice(
            pnl, choices=['R-ROD', 'F-FOK', 'I-IOC'], pos=(430, 157), size=(70, 30))
        self.pritype_cond.SetSelection(0)

        order = wx.Button(pnl, wx.ID_ANY, label='下單',
                          pos=(578, 126), size=(50, 25))
        order.Bind(wx.EVT_BUTTON, self.OnOrderBtn)

        logon = wx.Button(pnl, wx.ID_ANY, label='登入',
                          pos=(518, 156), size=(50, 25))
        logon.Bind(wx.EVT_BUTTON, self.OnLogonBtn)
        logout = wx.Button(pnl, wx.ID_ANY, label='登出',
                           pos=(578, 156), size=(50, 25))
        logout.Bind(wx.EVT_BUTTON, self.OnLogoutBtn)

        ###################################################################################

        ############################################################################
        #   狀態訊息
        wx.StaticBox(pnl, label='狀態訊息', pos=(1, 195), size=(550, 175))
        self.statusMessage = wx.ListBox(pnl, pos=(10, 215), size=(
            530, 143), style=wx.LB_SINGLE | wx.LB_HSCROLL)

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

        ###################################################################################

        ############################################################################
        #   成交回報
        wx.StaticBox(pnl, label='成交回報', pos=(670, 405), size=(550, 153))
        self.isPlaySound = wx.CheckBox(pnl, label='音效提示', pos=(680, 425))
        self.isPlaySound.SetValue(False)
        self.isSMS = wx.CheckBox(pnl, label='簡訊提示', pos=(760, 425))
        self.isSMS.SetValue(False)

        self.isAutoPosition = wx.CheckBox(pnl, label="定期查倉", pos=(840, 425))
        self.isAutoPosition.SetValue(False)
        self.isAutoPosition.Bind(wx.EVT_CHECKBOX, self.OnAutoPositionCheck)
        self.position_watcher = PositionWatcher(interval=30)

        matquery = wx.Button(pnl, wx.ID_ANY, label='查詢',
                             pos=(1130, 420), size=(70, 25))
        matquery.Bind(wx.EVT_BUTTON, self.OnMatQueryBtn)  #手動查詢成交回報

        self.MatQueryRpt = wx.ListBox(pnl, pos=(680, 450), size=(
            530, 90), style=wx.LB_SINGLE | wx.LB_HSCROLL)

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

        self.rbAm = wx.RadioButton(
            pnl, 1, label='T', pos=(870, 30), style=wx.RB_GROUP)
        self.rbPm = wx.RadioButton(pnl, 2, label='T+1', pos=(910, 30))

        register = wx.Button(pnl, wx.ID_ANY, label='註冊',
                             pos=(1100, 22), size=(40, 30))
        # register.Bind(wx.EVT_BUTTON, self.OnRegisterBtn)

        unregister = wx.Button(pnl, wx.ID_ANY, label='取消註冊',
                               pos=(1150, 22), size=(70, 30))
        # unregister.Bind(wx.EVT_BUTTON, self.OnUnRegisterBtn)

        # self.quote_status = wx.TextCtrl(pnl, pos=(680, 118), size=(150, 25))
        # self.quote_status.Enable(False)

        UpdateMode = ["1-Snapshot", "2-Update", "4-SnapshotUpd"]
        self.modle = wx.Choice(pnl, choices=UpdateMode,
                               pos=(960, 25), size=(130, 10))
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
        self.compareInfoGrid.SetColLabelValue(4, "當時均價")
        self.compareInfoGrid.SetColLabelValue(5, "比較均價")
        self.compareInfoGrid.SetColLabelValue(6, "筆數")

        self.compareInfoGrid.SetCellValue(0, 0, "空倉不急")
        self.compareInfoGrid.SetCellValue(0, 1, "開倉不畏")
        self.compareInfoGrid.SetCellValue(0, 2, " 00:00:00.000 ")
        self.compareInfoGrid.SetCellValue(0, 3, "持不慌 ")
        self.compareInfoGrid.SetCellValue(0, 4, "猶豫不決 ")
        self.compareInfoGrid.SetCellValue(0, 5, "平倉不悔")
        self.compareInfoGrid.SetCellValue(0, 6, "10")
        self.compareInfoGrid.SetCellValue(1, 0, "學會放棄")
        self.compareInfoGrid.SetCellValue(1, 1, "學會等待")
        self.compareInfoGrid.SetCellValue(1, 2, " 00:00:00.000 ")
        self.compareInfoGrid.SetCellValue(1, 3, "學坦然")
        self.compareInfoGrid.SetCellValue(1, 4, "猶豫不決")
        self.compareInfoGrid.SetCellValue(1, 5, "學會果斷")
        self.compareInfoGrid.SetCellValue(1, 6, "老無成")
        # self.compareInfoGrid.EnableScrolling(False, False)

        self.compareInfoGrid.SetDefaultCellBackgroundColour('BLACK')
        self.compareInfoGrid.EnableEditing(False)
        self.compareInfoGrid.AutoSizeColumns()

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
        #   USER DEFINE 客戶func功能查詢
        # wx.StaticBox(pnl, label='自定義查詢', pos=(670, 425), size=(490, 215))
        # wx.StaticText(pnl, label='自定義參數', pos=(679, 450))
        # self.user_params = wx.TextCtrl(pnl, pos=(745, 446), size=(404, 25))
        # self.user_params.SetValue('Func=FA022|bhno=|acno=|suba=')

        wx.StaticText(pnl, label='        通用查詢', pos=(560, 405))
        # self.user_workid = wx.TextCtrl(pnl, pos=(560, 425), size=(100, 20))部位狀況
        # self.user_workid.SetValue('FA022')
        self.user_workid_combo = wx.Choice(pnl, choices=[
                                           'FA001-未平倉合計', 'FA002-未平倉明細', 'FA003-財務查詢', 'RA003-部位狀況'], pos=(560, 425), size=(100, 25))
        self.user_workid_combo.SetSelection(0)

        userquery = wx.Button(pnl, wx.ID_ANY, label='查詢',
                              pos=(580, 455), size=(70, 25))
        userquery.Bind(wx.EVT_BUTTON, partial(self.OnUserDefineBtn,"通用"))

        wx.StaticText(pnl, label='未平倉口數：', pos=(560, 500))
        self.qtyLabel=wx.StaticText(pnl, label='未連', pos=(635, 500))

        self.chkSell = wx.CheckBox(pnl, label='作空', pos=(560, 525))
        self.chkBuy = wx.CheckBox(pnl, label='作多', pos=(620, 525))
         # 綁定事件
        self.chkSell.Bind(wx.EVT_CHECKBOX, self.OnChkDealClick)
        self.chkBuy.Bind(wx.EVT_CHECKBOX, self.OnChkDealClick)
        self.chkSell.SetValue(False)
        self.chkBuy.SetValue(False)
        ###################################################################################
    
    def OnAutoPositionCheck(self, event):
        if self.acclist_combo.GetCount() == 0:
            self.isAutoPosition.SetValue(False)
            self.Logmessage('請先登入並選擇期貨帳號')
            return
        if self.isAutoPosition.GetValue():
            self.position_watcher.start()
        else:
            self.position_watcher.stop()

    def OnChkDealClick(self, event):
        cb = event.GetEventObject()        
        if cb == self.chkSell and self.chkSell.IsChecked():
            self.chkBuy.SetValue(False)
        elif cb == self.chkBuy and self.chkBuy.IsChecked():
            self.chkSell.SetValue(False)

            
    def OnLogonBtn(self, event):
        LogonJob(Job.LOGON, self.acc.GetValue(), self.pwd.GetValue())

    def OnLogoutBtn(self, event):
        self.acclist_combo.Clear()
        self.isAutoPosition.SetValue(False)
        self.qtyLabel.SetLabel("未連")
        self.position_watcher.stop()
        LogoutJob(Job.LOGOUT)

    def OnUserDefineBtn(self,method, event):
        # self.user_params.SetValue('Func=FA022|bhno=|acno=|suba=')
        # self.user_workid.SetValue('FA022')
        if self.acclist_combo.GetCount() == 0:
            self.Logmessage('請先登入並選擇期貨帳號')
            return
        vars = self.acclist_combo.GetString(
            self.acclist_combo.GetSelection()).split('-')
        func = self.user_workid_combo.GetString(
            self.user_workid_combo.GetSelection()).split('-')
        bhno = vars[1]
        ae_no = vars[2]
        if method=="庫存":
            user_params = f'Func=FA001|bhno={bhno}|acno={ae_no}|suba=|kind=A|FC=N'
        else:
            user_params = f'Func={func[0]}|bhno={bhno}|acno={ae_no}|suba=|type=1|currency=TWD'
            if func[0] == "FA001" or func[0] == "FA002" or func[0] == "FA009":
                user_params = f'Func={func[0]}|bhno={bhno}|acno={ae_no}|suba=|kind=A|FC=N'
            elif func[0] == "RA003":
                user_params = f'Func={func[0]}|bhno={bhno}|acno={ae_no}|suba=|FC=N'

        UserDefineJob(Job.USERDEFINE, user_params, func[0])

    def OnOrderBtn(self, event):
        if self.acclist_combo.GetCount() == 0:
            # wx.MessageBox('請先登入並選擇期貨帳號','錯誤',wx.OK | wx.ICON_ERROR)
            self.Logmessage('請先登入並選擇期貨帳號')
            return
        vars = self.acclist_combo.GetString(
            self.acclist_combo.GetSelection()).split('-')
        bhno = vars[1]
        account = vars[2]
        ae_no = vars[3]
        OrderJob(Job.ORDER, bhno, account, ae_no)

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

    def ORFcheckBtn(self, event):
        if self.rfcheck.GetValue() == True:
            self.pritype_rfcombo.Show(True)
            self.pritype_combo.Show(False)
            self.ctype_rfcombo.Show(True)
            self.ctype_combo.Show(False)
            self.offset_combo.SetSelection(3)
            self.pritype_cond.SetSelection(0)
            self.textstopprice.Show(True)
            self.stopprice.Show(True)
            self.textsymbol.Show(False)
            self.futno2.Show(False)
            self.textbs2.Show(False)
            self.bscode2_combo.Show(False)
        else:
            self.pritype_rfcombo.Show(False)
            self.pritype_combo.Show(True)
            self.ctype_rfcombo.Show(False)
            self.ctype_combo.Show(True)
            self.textstopprice.Show(False)
            self.stopprice.Show(False)
            self.textsymbol.Show(True)
            self.futno2.Show(True)
            self.textbs2.Show(True)
            self.bscode2_combo.Show(True)

    def Logmessage(self, msg):
        self.statusMessage.Append(msg)
        item_count = self.statusMessage.GetCount()
        if item_count > 0:
            self.statusMessage.EnsureVisible(self.statusMessage.GetCount()-1)



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

    def __init__(self, job_type):
        self.job_type = job_type
#########################################
#########     Quote define      #########
#########################################


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
            -2: "Connection failed.",
            -1: "Connection broken.",
            0: "Connection idled.",
            1: "Connection ready.",
            2: "Connection success.",
        }

        if Status < 0:
            msg = f"{link_status.get(Status)}: Try to login again."
            frame.Logmessage(msg)
            if Bot.is_trade_time():
                msg = "Reconnection in trade time will be wait for 1 second"
                frame.Logmessage(msg)
                time.sleep(1)
            else:
                msg = "Reconnection beyond trade time will wait for 1 minutes"
                frame.Logmessage(msg)
                time.sleep(60)
            Bot.UpdateDayNight()
            # Bot.Logon()

        if Status != 2:
            return

        code_list = load_json("./code.json")
        for code in code_list["stock"]:
            result = Bot.YuantaQ.YuantaQuote.AddMktReg(
                code, 2, ReqType, 0)
            msg = f"Registered {code}, result: {result}"
            frame.Logmessage(msg)
        msg = "Stock registration done."
        frame.Logmessage(msg)

        for code in code_list["future"]:
            code = Bot.XF(code)
            result = Bot.YuantaQ.YuantaQuote.AddMktReg(
                code, 2, ReqType, 0)
            msg = f"Registered {code}, result: {result}"
            frame.Logmessage(msg)
        msg = "Future registration done."
        frame.Logmessage(msg)

    def OnRegError(self, this, symbol, updmode, ErrCode, ReqType):
        frame.Logmessage('OnRegError {},{},{},{}'.format(
            ReqType, ErrCode, symbol, updmode))

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
        strReqType = '日盤' if ReqType == 1 else '夜盤'
        print(f'{Back.BLUE}{Fore.YELLOW}{Style.BRIGHT}開始接受資料  {strTradeType} {ReqType} {strTime}{Style.RESET_ALL}')

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
    def __init__(self, job_type, bhno, account, ae_no):
        super(OrderJob, self).__init__(job_type)
        self.bhno = bhno
        self.account = account
        self.ae_no = ae_no
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


class StockBot:
    def __init__(self, botuid):
        self.Yuanta = YuantaOrdWapper(botuid, self)
        self.YuantaQ = YuantaQuoteWapper(botuid, self)
        self.YuantaAccount = []
        self.YuantaSN = []

    def UpdateDayNight(self):
        config = load_json("./config.json")
        self.Username = config["username"]
        self.Password = config["password"]
        self.Host = "203.66.93.84"
        if self.is_day() and not self.is_day_port():
            self.Port = 443
            msg = "Change connection port to 443."
            frame.Logmessage(msg)
            self.Logon()
        elif not self.is_day() and self.is_day_port():
            self.Port = 442
            msg = "Change connection port to 442."
            frame.Logmessage(msg)
            self.Logon()

        time.sleep(1)

    def ConnectionConfiguration(self, username, password):
        self.Username = username
        self.Password = password
        self.Host = "203.66.93.84"
        self.Port = 442 if not self.is_day() else 443
        self.Logon()
        time.sleep(1)
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
        now = get_time()
        day_begin = now.replace(hour=7, minute=0, second=0)
        day_end = now.replace(hour=14, minute=30, second=0)

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
        now = get_time()
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

    def Config(self, host, port, username, password):
        self.Host = host
        self.Port = port
        self.Username = username
        self.Password = password
    # 計算選擇權商品代碼

    def XXF(self):
        """計算期貨商品代碼"""
        today = datetime.date.today()
        day = datetime.date.today().replace(day=1)

        while day.weekday() != 2:
            day = day + datetime.timedelta(days=1)
        day = day + dateutil.relativedelta.relativedelta(days=14)

        if day < today:
            day = day + dateutil.relativedelta.relativedelta(months=1)

        codes = "ABCDEFGHIJKL"
        y = day.year % 10
        m = codes[day.month - 1]

        return f"{m}{y}"
    # 計算期貨商品代碼

    def XF(self, code):
        return f"{code}{self.XXF()}"
    # 登入

    def Logon(self):
        msg = f"連接報價行情主機 {self.Host}:{self.Port}"
        frame.Logmessage(msg)
        self.YuantaQ.YuantaQuote.SetMktLogon(self.Username, self.Password,
                                             self.Host, self.Port, 1, 0)

    def loginq(self, account, password):
        # T port 80/443 , T+1 port 82/442 ,  reqType=1 T盤 , reqType=2  T+1盤
        self.YuantaQ.YuantaQuote.SetMktLogon(
            account, password, 'apiquote.yuantafutures.com.tw', '80', 1, 0)  # 正式環境
        self.YuantaQ.YuantaQuote.SetMktLogon(
            account, password, 'apiquote.yuantafutures.com.tw', '82', 2, 0)
        print('login')

    def RegisterQuoteSymbol(self, QuoteSymbol, modle, ret_type):
        ret = self.YuantaQ.YuantaQuote.AddMktReg(
            QuoteSymbol, modle[0], ret_type, 0)
        print("AddMktReg {}".format(ret))  # 正常ret = 0
        frame.SetQuoteStatusValue(str(ret))
        if ret == 0:
            InsertSymbol(Job.INSERTSYMBOL, QuoteSymbol)

    def UnRegisterQuoteSymbol(self, QuoteSymbol, ret_type):
        ret = self.YuantaQ.YuantaQuote.DelMktReg(QuoteSymbol, ret_type)
        print("DelMktReg {}".format(ret))  # 正常ret = 0
        frame.SetQuoteStatusValue(str(ret))
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
        ret = self.Yuanta.YuantaOrd.UserDefinsFunc(params, workid)
        frame.Logmessage('user define ret = {}'.format(ret))

    def send_order(self, bhon, account, ae_no):
        ## 同步、非同步##
        if frame.wait.GetValue() == True:
            self.Yuanta.YuantaOrd.SetWaitOrdResult(1)
        else:
            self.Yuanta.YuantaOrd.SetWaitOrdResult(0)

        ## 國外、國內##
        if frame.rfcheck.GetValue() == True:
            frame.Logmessage("RfSendOrder() {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}".format(
                frame.fcode_combo.GetString(
                    frame.fcode_combo.GetSelection())[0:2],
                frame.ctype_rfcombo.GetString(
                    frame.ctype_rfcombo.GetSelection())[0:1],
                bhon,
                account,
                ae_no,
                frame.ordno.GetValue(),
                frame.bscode1_combo.GetString(
                    frame.bscode1_combo.GetSelection())[0:1],
                frame.futno1_combo.GetString(
                    frame.futno1_combo.GetSelection())[0:5],
                frame.pritype_rfcombo.GetString(
                    frame.pritype_rfcombo.GetSelection())[0:1],
                frame.price.GetValue(),
                frame.stopprice.GetValue(),
                frame.lots_combo.GetString(
                    frame.lots_combo.GetSelection())[0:1],
                frame.offset_combo.GetString(frame.offset_combo.GetSelection())[0:1]))

            ret_no = self.Yuanta.YuantaOrd.RfSendOrder(frame.fcode_combo.GetString(frame.fcode_combo.GetSelection())[0:2],
                                                       frame.ctype_rfcombo.GetString(
                                                           frame.ctype_rfcombo.GetSelection())[0:1],
                                                       bhon,
                                                       account,
                                                       ae_no,
                                                       frame.ordno.GetValue(),
                                                       frame.bscode1_combo.GetString(
                                                           frame.bscode1_combo.GetSelection())[0:1],
                                                       frame.futno1_combo.GetString(
                                                           frame.futno1_combo.GetSelection())[0:5],
                                                       frame.pritype_rfcombo.GetString(
                                                           frame.pritype_rfcombo.GetSelection())[0:1],
                                                       frame.price.GetValue(),
                                                       frame.stopprice.GetValue(),
                                                       frame.lots_combo.GetString(
                                                           frame.lots_combo.GetSelection())[0:1],
                                                       frame.offset_combo.GetString(frame.offset_combo.GetSelection())[0:1])

            frame.Logmessage("RfSendOrder() return = {}".format(ret_no))

        else:
            frame.Logmessage("SendOrderF() {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}".format(
                frame.fcode_combo.GetString(
                    frame.fcode_combo.GetSelection())[0:2],
                frame.ctype_combo.GetString(
                    frame.ctype_combo.GetSelection())[0:1],
                bhon,
                account,
                ae_no,
                frame.ordno.GetValue(),
                frame.bscode1_combo.GetString(
                    frame.bscode1_combo.GetSelection())[0:1],
                frame.futno1_combo.GetString(
                    frame.futno1_combo.GetSelection())[0:5],
                frame.price.GetValue(),
                frame.lots_combo.GetString(
                    frame.lots_combo.GetSelection())[0:1],
                frame.offset_combo.GetString(
                    frame.offset_combo.GetSelection())[0:1],
                frame.pritype_combo.GetString(
                    frame.pritype_combo.GetSelection())[0:1],
                frame.pritype_cond.GetString(
                    frame.pritype_cond.GetSelection())[0:1],
                frame.bscode2_combo.GetString(
                    frame.bscode2_combo.GetSelection())[0:1],
                frame.futno2.GetValue()))

            if frame.futno2.GetValue().strip() == '':
                bs2 = ''
            else:
                bs2 = frame.bscode2_combo.GetString(
                    frame.bscode2_combo.GetSelection())[0:1]

            ret_no = self.Yuanta.YuantaOrd.SendOrderF(frame.fcode_combo.GetString(frame.fcode_combo.GetSelection())[0:2],
                                                      frame.ctype_combo.GetString(
                                                          frame.ctype_combo.GetSelection())[0:1],
                                                      bhon,
                                                      account,
                                                      ae_no,
                                                      frame.ordno.GetValue(),
                                                      frame.bscode1_combo.GetString(
                                                          frame.bscode1_combo.GetSelection())[0:1],
                                                      frame.futno1_combo.GetString(
                                                          frame.futno1_combo.GetSelection())[0:5],
                                                      frame.price.GetValue(),
                                                      frame.lots_combo.GetString(
                                                          frame.lots_combo.GetSelection())[0:1],
                                                      frame.offset_combo.GetString(
                                                          frame.offset_combo.GetSelection())[0:1],
                                                      frame.pritype_combo.GetString(
                                                          frame.pritype_combo.GetSelection())[0:1],
                                                      frame.pritype_cond.GetString(
                                                          frame.pritype_cond.GetSelection())[0:1],
                                                      bs2,
                                                      frame.futno2.GetValue().strip())

            frame.Logmessage("SendOrderF() return = {}".format(ret_no))

    def send_ordQuery(self, bhon, account, ae_no):
        if frame.rfcheck.GetValue() == True:  # 查國外
            ret_code = self.Yuanta.YuantaOrd.RfReportQuery(bhon, account, ae_no,
                                                           frame.ordstatus_combo.GetString(
                                                               frame.ordstatus_combo.GetSelection())[0:1],
                                                           frame.ordcflag_combo.GetString(
                                                               frame.ordcflag_combo.GetSelection())[0:1],
                                                           '*')
            frame.Logmessage("RfReportQuery() return = {}".format(ret_code))
        else:  # 查國內
            ret_code = self.Yuanta.YuantaOrd.ReportQuery("F", bhon, account, ae_no,
                                                         frame.ordstatus_combo.GetString(
                                                             frame.ordstatus_combo.GetSelection())[0:1],
                                                         '*',
                                                         frame.ordcflag_combo.GetString(frame.ordcflag_combo.GetSelection())[0:1])
            frame.Logmessage("ReportQuery() return = {}".format(ret_code))

    def send_matQuery(self, bhon, account, ae_no):
        if frame.rfcheck.GetValue() == True:  # 查國外
            ret_code = self.Yuanta.YuantaOrd.RfDealQuery(
                bhon, account, ae_no, '*')
            frame.Logmessage("RfDealQuery() return = {}".format(ret_code))
        else:  # 查國內
            ret_code = self.Yuanta.YuantaOrd.DealQuery(
                "F", bhon, account, ae_no, '*')
            frame.Logmessage("DealQuery() return = {}".format(ret_code))
    
    # --- 自動下單與監控模組 ---
    def auto_send_order(self, symbol, side, price):
        bhon="P05"
        account="2427191"                                              
        ae_no=""        
        bs2=""                                      
        ret_no = self.Yuanta.YuantaOrd.SendOrderF(frame.fcode_combo.GetString(frame.fcode_combo.GetSelection())[0:2],
                                                      frame.ctype_combo.GetString(
                                                          frame.ctype_combo.GetSelection())[0:1],
                                                      bhon,
                                                      account,
                                                      ae_no,
                                                      frame.ordno.GetValue(),
                                                    #   frame.bscode1_combo.GetString(
                                                    #       frame.bscode1_combo.GetSelection())[0:1],
                                                    #   frame.futno1_combo.GetString(
                                                    #       frame.futno1_combo.GetSelection())[0:5],
                                                    #   frame.price.GetValue(),
                                                      side,
                                                      symbol,
                                                      price,
                                                      frame.lots_combo.GetString(
                                                          frame.lots_combo.GetSelection())[0:1],
                                                      frame.offset_combo.GetString(
                                                          frame.offset_combo.GetSelection())[0:1],
                                                      frame.pritype_combo.GetString(
                                                          frame.pritype_combo.GetSelection())[0:1],
                                                      frame.pritype_cond.GetString(
                                                          frame.pritype_cond.GetSelection())[0:1],
                                                      bs2,
                                                      frame.futno2.GetValue().strip())
        # order_id = api.send_order(symbol=symbol, side=side, lots=lots)
        # print(f"🔹已送出{side}單 {symbol} {lots}口, order_id={order_id}")

        # t = threading.Thread(target=self.auto_monitor_order_status, args=(ret_no))
        # t.daemon = True
        # t.start()
        # return ret_no

    def auto_monitor_order_status(self,api, order_id, symbol, lots):
        timeout = 60
        elapsed = 0
        while elapsed < timeout:
            status = api.query_order_status(order_id)
            print(f"查詢委託 {order_id} 狀態：{status}")
            if status in ["Filled", "Rejected", "Cancelled"]:
                break
            time.sleep(2)
            elapsed += 2
        print(f"委託完成，最終狀態：{status}")
        self.auto_monitor_position(api, symbol, lots)

    def auto_monitor_position(api, symbol, expected_qty):
        pos = api.query_position(symbol)
        if pos == expected_qty:
            print(f"✅ {symbol} 持倉正確 ({pos})")
        else:
            print(f"⚠️ {symbol} 持倉異常，實際:{pos} 預期:{expected_qty}")
    
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
            #登入查庫存
            # vars = frame.acclist_combo.GetString(
            # frame.acclist_combo.GetSelection()).split('-')            
            # bhno = vars[1]
            # ae_no = vars[2]            
            # user_params = f'Func=FA001|bhno={bhno}|acno={ae_no}|suba=|kind=A|FC=N'
            # UserDefineJob(Job.USERDEFINE, user_params, "FA001")    
            frame.OnUserDefineBtn("庫存",wx.EVT_BUTTON)

    def OnReportQuery(self, this, RowCount, Results):
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
        item_count = frame.OrdQueryRpt.GetCount()
        if item_count > 0:
            frame.OrdQueryRpt.EnsureVisible(frame.OrdQueryRpt.GetCount()-1)

    def OnDealQuery(self, this, RowCount, Results):
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

    def OnUserDefinsFuncResult(self, this, RowCount, Results, WorkID):
        data=dict(p.split("=") for p in Results.split("|"))  
        if (WorkID=="FA001" or WorkID=="FA002") and data["RETC"]=="00000":
            frame.qtyLabel.SetLabel(data["TOTAL_OFF_POSITION"])  
        frame.Logmessage(Results) 
        # frame.statusMessage.Append(RowCount)

    def OnOrdRptF(self, this, Omkt, Mktt, Cmbf, Statusc, Ts_Code, Ts_Msg, Bhno, AcNo,
                  Suba, Symb, Scnam, O_Kind, O_Type, Buys, S_Buys, O_Prc, O_Qty, Work_Qty, Kill_Qty,
                  Deal_Qty, Order_No, T_Date, O_Date, O_Time,
                  O_Src, O_Lin, A_Prc, Oseq_No, Err_Code,
                  Err_Msg, R_Time, D_Flag):
        msg = 'Omkt={},Mktt={},Cmbf={},Statusc={},Ts_Code={},Ts_Msg={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},O_Type={},Buys={},S_Buys={},O_Prc={},O_Qty={},Work_Qty={},Kill_Qty={},Deal_Qty={},Order_No={},T_Date={},O_Date={},O_Time={},O_Src={},O_Lin={},A_Prc={},Oseq_No={},Err_Code={},Err_Msg={},R_Time={},D_Flag={}'.format(Omkt.strip(), Mktt.strip(), Cmbf.strip(), Statusc.strip(), Ts_Code.strip(), Ts_Msg.strip(
        ), Bhno.strip(), AcNo.strip(), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), O_Type.strip(), Buys.strip(), S_Buys.strip(), O_Prc.strip(), O_Qty.strip(), Work_Qty.strip(), Kill_Qty.strip(), Deal_Qty.strip(), Order_No.strip(), T_Date.strip(), O_Date.strip(), O_Time.strip(), O_Src.strip(), O_Lin.strip(), A_Prc.strip(), Oseq_No.strip(), Err_Code.strip(), Err_Msg.strip(), R_Time.strip(), D_Flag.strip())
        frame.OrdQueryRpt.Append(msg)
        item_count = frame.OrdQueryRpt.GetCount()
        if item_count > 0:
            frame.OrdQueryRpt.EnsureVisible(frame.OrdQueryRpt.GetCount()-1)

    def OnOrdMatF(self, this, Omkt, Buys, Cmbf, Bhno,
                  AcNo, Suba, Symb, Scnam, O_Kind,
                  S_Buys, O_Prc, A_Prc, O_Qty, Deal_Qty,
                  T_Date, D_Time, Order_No, O_Src, O_Lin,
                  Oseq_No):
        #檢查庫存
        frame.OnUserDefineBtn("庫存",wx.EVT_BUTTON)
        msg = 'Omkt={},Buys={},Cmbf={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},S_Buys={},O_Prc={},A_Prc={},O_Qty={},Deal_Qty={},T_Date={},D_Time={},Order_No={},O_Src={},O_Lin={},Oseq_No={}'.format(Omkt.strip(), Buys.strip(), Cmbf.strip(), Bhno.strip(
        ), AcNo.strip(), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), S_Buys.strip(), O_Prc.strip(), A_Prc.strip(), O_Qty.strip(), Deal_Qty.strip(), T_Date.strip(), D_Time.strip(), Order_No.strip(), O_Src.strip(), O_Lin.strip(), Oseq_No.strip())
        frame.MatQueryRpt.Append(msg)

    def OnOrdResult(self, this, ID, result):
        msg = 'OnOrdResult:ID={},result={}'.format(ID, result)
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

        # Create an event loop and make it active.  If you are
        # only going to temporarily have a nested event loop then
        # you should get a reference to the old one and set it as
        # the active event loop when you are done with this one...
        evtloop = wx.GUIEventLoop()
        old = wx.EventLoop.GetActive()
        wx.EventLoop.SetActive(evtloop)

        # This outer loop determines when to exit the application,
        # for this example we let the main frame reset this flag
        # when it closes.
        while self.keepGoing:
            # At this point in the outer loop you could do
            # whatever you implemented your own MainLoop for.  It
            # should be quick and non-blocking, otherwise your GUI
            # will freeze.

            # call_your_code_here()
            run_func()
            while not q.empty():
                next_job = q.get()
                DoJob(Bot, next_job)

            # This inner loop will process any GUI events
            # until there are no more waiting.
            while evtloop.Pending():
                evtloop.Dispatch()

            # Send idle events to idle handlers.  You may want to
            # throttle this back a bit somehow so there is not too
            # much CPU time spent in the idle handlers.  For this
            # example, I'll just snooze a little...
            time.sleep(0.10)
            evtloop.ProcessIdle()

        wx.EventLoop.SetActive(old)

    def OnInit(self):
        self.keepGoing = True
        return True

class PositionWatcher:
    def __init__(self,interval=30):
        self.interval = interval
        self.stop_flag = threading.Event()
        self.thread = None

    def start(self):
        """啟動背景查倉執行緒"""
        if self.thread and self.thread.is_alive():
            frame.Logmessage("⚠️ 查倉執行緒已在運行中")
            return
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
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
        while not self.stop_flag.is_set() and frame.acclist_combo.GetCount() != 0:
            # vars = frame.acclist_combo.GetString(
            # frame.acclist_combo.GetSelection()).split('-')            
            # bhno = vars[1]
            # ae_no = vars[2]            
            # user_params = f'Func=FA001|bhno={bhno}|acno={ae_no}|suba=|kind=A|FC=N'
            # UserDefineJob(Job.USERDEFINE, user_params, "FA001")
            frame.OnUserDefineBtn("庫存",wx.EVT_BUTTON)
            time.sleep(self.interval)

def DoJob(Bot, x):
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
            Bot.send_order(x.bhno, x.account, x.ae_no)
            break
        if case(Job.ORDQUERY):
            Bot.send_ordQuery(x.bhno, x.account, x.ae_no)
            break
        if case(Job.MATQUERY):
            Bot.send_matQuery(x.bhno, x.account, x.ae_no)
            break
        if case(Job.REGISTER):
            print(x.job_type, x.regSymbol, x.modle[0])
            Bot.RegisterQuoteSymbol(x.regSymbol, x.modle, x.AmPm)
            break
        if case(Job.UNREGISTER):
            print(x.job_type, x.unSymbol)
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
                ts.calculate_and_update()
            except Exception as e:
                frame.Logmessage(e)
            break
        if case(Job.INSERTSYMBOL):
            frame.InsertSymbol(x.symbol)
            break
        if case(Job.DELETESYMBOL):
            frame.DeleteSymbol(x.symbol)
            break


def run_job():
    while not q.empty():
        next_job = q.get()
        DoJob(Bot, next_job)


def load_json(fpath):
    with open(fpath, "r", encoding="UTF-8") as f:
        return json.load(f)


def get_time():
    """Get the absolute time of UTC+8.「中原標準時間」"""
    d = datetime.timedelta(hours=8)
    t = datetime.datetime.utcnow()
    t += d
    return t


if __name__ == "__main__":
    app = MyApp()
    frame = AppFrame(None, title='千金交易系統', size=(1260, 850))
    frame.SetPosition((10, 10))
    frame.Show(True)
    Bot = StockBot(frame.Handle)
    ts = trading_strategy_calc.TradingStrategy(frame)
    config = load_json("./config.json")
    # Bot.login(config["username"], config["password"])
    Bot.ConnectionConfiguration(config["username"], config["password"])
    app.MainLoop(run_job)

"""
Host IP: 203.66.93.84
Host Domain: apiquote.yuantafutures.com.tw
T Port: 80 or 443
T+1 Port: 82 or 442
"""
