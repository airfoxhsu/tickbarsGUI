# -*- coding: utf-8 -*-
import wx, time
import  wx.lib.anchors as anchors
from ctypes import byref, POINTER, windll
from comtypes import IUnknown, GUID
from comtypes.client import GetModule,  GetBestInterface, GetEvents
import queue as queue

user32 = windll.user32
atl = windll.atl

q = queue.Queue ()

class AppFrame(wx.Frame):
    """
    A Frame that says AppFrame
    """
    def __init__(self, *args, **kw):
        # ensure the parent's __init__ is called
        super(AppFrame, self).__init__(*args, **kw)

        # create a panel in the frame
        pnl = wx.Panel(self)        


        ############################################################################
        #   API連線資訊
        wx.StaticBox(pnl, label='API連線資訊', pos=(1, 1), size=(650, 70))
        wx.StaticText(pnl, label='ID', pos=(11, 30))
        wx.StaticText(pnl, label='密碼', pos=(155, 30))
        self.acc = wx.TextCtrl(pnl, pos=(42, 26), size=(100, 25))
        self.pwd = wx.TextCtrl(pnl, pos=(186, 26), size=(100, 25),style=wx.TE_PASSWORD )
        wx.StaticText(pnl, label='狀態碼', pos=(300, 30))
        self.connect_status = wx.TextCtrl(pnl, pos=(340, 26), size=(50, 25))
        self.connect_status.Enable(False)        
        wx.StaticText(pnl, label='期貨帳號', pos=(400, 30))    
        self.acclist_combo = wx.Choice(pnl,pos=(460, 28),size=(165, 30))                 
        
        ###################################################################################

        ###################################################################################
        #   下單委託
        wx.StaticBox(pnl, label='下單委託', pos=(1, 80), size=(650, 110))
        wx.StaticText(pnl, label='功能別', pos=(11, 100))
        self.fcode_combo = wx.Choice(pnl,choices = ['01-委託','02-減量','03-刪單'],pos=(50, 97),size=(70, 30))                 
        self.fcode_combo.SetSelection(0)
        
        wx.StaticText(pnl, label='商品類', pos=(141, 100))
        self.ctype_combo = wx.Choice(pnl,choices = ['0-期貨','1-選擇權'],pos=(180, 97),size=(70, 30))                 
        self.ctype_combo.SetSelection(0)

        self.ctype_rfcombo = wx.Choice(pnl,choices = ['F-期貨','O-選擇權'],pos=(180, 97),size=(70, 30))                 
        self.ctype_rfcombo.Show(False)
        self.ctype_rfcombo.SetSelection(0)

        wx.StaticText(pnl, label='委託書', pos=(271, 100))
        self.ordno = wx.TextCtrl(pnl, pos=(310, 97), size=(70, 23))

        wx.StaticText(pnl, label='委託類', pos=(391, 100))
        self.offset_combo = wx.Choice(pnl,choices = ['0-新倉','1-平倉','2-當沖',' -自動'],pos=(430, 97),size=(70, 30))                 
        self.offset_combo.SetSelection(3)

        self.wait = wx.CheckBox(pnl, label = '等待委託單號',pos=(520, 100)) 


        wx.StaticText(pnl, label='買賣1', pos=(11, 130))
        self.bscode1_combo = wx.Choice(pnl,choices = ['B-買進','S-賣出'],pos=(50, 127),size=(70, 30))                 
        self.bscode1_combo.SetSelection(0)

        wx.StaticText(pnl, label='商品1', pos=(141, 130))
        self.futno1 = wx.TextCtrl(pnl, pos=(180, 127), size=(70, 23))

        wx.StaticText(pnl, label='價格', pos=(271, 130))
        self.price = wx.TextCtrl(pnl, pos=(310, 127), size=(70, 23))

        wx.StaticText(pnl, label='數量', pos=(391, 130))
        self.lots = wx.TextCtrl(pnl, pos=(430, 127), size=(50, 23))

        self.rfcheck = wx.CheckBox(pnl, label = '外期',pos=(520, 130)) 
        self.rfcheck.Bind(wx.EVT_CHECKBOX, self.ORFcheckBtn)


        self.textbs2 = wx.StaticText(pnl, label='買賣2', pos=(11, 160))
        self.bscode2_combo = wx.Choice(pnl,choices = ['B-買進','S-賣出'],pos=(50, 157),size=(70, 30))                 
        self.bscode2_combo.SetSelection(0)

        self.textsymbol = wx.StaticText(pnl, label='商品2', pos=(141, 160))
        self.futno2 = wx.TextCtrl(pnl, pos=(180, 157), size=(70, 23))

        self.textstopprice = wx.StaticText(pnl, label='停損價', pos=(141, 160))
        self.stopprice = wx.TextCtrl(pnl, pos=(180, 157), size=(70, 23))
        self.textstopprice.Show(False)
        self.stopprice.Show(False)


        wx.StaticText(pnl, label='限市價', pos=(271, 160))
        self.pritype_combo = wx.Choice(pnl,choices = ['L-限價','M-市價','P-範圍市價'],pos=(310, 157),size=(70, 30))                         
        self.pritype_combo.SetSelection(0)
        
        self.pritype_rfcombo = wx.Choice(pnl,choices = ['1-限價','2-市價','4-停損','8-停損限價'],pos=(310, 157),size=(70, 30))                 
        self.pritype_rfcombo.Show(False)
        self.pritype_rfcombo.SetSelection(0)

        wx.StaticText(pnl, label='條件', pos=(391, 160))
        self.pritype_cond = wx.Choice(pnl,choices = ['R-ROD','F-FOK','I-IOC'],pos=(430, 157),size=(70, 30))                 
        self.pritype_cond.SetSelection(0)     
        
        order = wx.Button(pnl, wx.ID_ANY, label='下單', pos=(578, 126), size=(50, 25))
        order.Bind(wx.EVT_BUTTON, self.OnOrderBtn)
        
        logon = wx.Button(pnl, wx.ID_ANY, label='登入', pos=(518, 156), size=(50, 25))
        logon.Bind(wx.EVT_BUTTON, self.OnLogonBtn)                

        logout = wx.Button(pnl, wx.ID_ANY, label='登出', pos=(578, 156), size=(50, 25))
        logout.Bind(wx.EVT_BUTTON, self.OnLogoutBtn)

        ###################################################################################

        wx.StaticBox(pnl, label='狀態訊息', pos=(1, 195), size=(650, 444))
        self.statusMessage = wx.ListBox(pnl, pos=(11,215), size = (630,419),style= wx.LB_SINGLE|wx.LB_HSCROLL)

        ###################################################################################

        ############################################################################
        #   委託回報
        wx.StaticBox(pnl, label='委託回報', pos=(670, 1), size=(490, 200))        
        wx.StaticText(pnl, label='委託狀態', pos=(679, 30))
        self.ordstatus_combo = wx.Choice(pnl,choices = ['0-全部','1-未成交','2-已成交','4-委託失敗'],pos=(730, 27),size=(70, 30))                 
        self.ordstatus_combo.SetSelection(0)

        wx.StaticText(pnl, label='可刪改', pos=(820, 30))
        self.ordcflag_combo = wx.Choice(pnl,choices = ['0-可刪改','1-全部委託'],pos=(861, 27),size=(80, 30))                 
        self.ordcflag_combo.SetSelection(0)
        
        ordquery = wx.Button(pnl, wx.ID_ANY, label='查詢', pos=(1080, 25), size=(70, 25))
        ordquery.Bind(wx.EVT_BUTTON, self.OnOrdQueryBtn)

        self.OrdQueryRpt = wx.ListBox(pnl, pos=(675,53), size = (480,143),style= wx.LB_SINGLE|wx.LB_HSCROLL)

        ###################################################################################

        ############################################################################
        #   成交回報
        wx.StaticBox(pnl, label='成交回報', pos=(670, 201), size=(490, 215))                
        
        matquery = wx.Button(pnl, wx.ID_ANY, label='查詢', pos=(1080, 218), size=(70, 25))
        matquery.Bind(wx.EVT_BUTTON, self.OnMatQueryBtn)

        self.MatQueryRpt = wx.ListBox(pnl, pos=(675,248), size = (480,156),style= wx.LB_SINGLE|wx.LB_HSCROLL)

        ###################################################################################

        ############################################################################
        #   USER DEFINE 客戶func功能查詢
        wx.StaticBox(pnl, label='自定義查詢', pos=(670, 425), size=(490, 215))                
        wx.StaticText(pnl, label='自定義參數', pos=(679, 450))
        self.user_params = wx.TextCtrl(pnl, pos=(745, 446), size=(404, 25))
        self.user_params.SetValue('Func=FA022|bhno=|acno=|suba=')

        wx.StaticText(pnl, label='workID', pos=(679, 480))
        self.user_workid = wx.TextCtrl(pnl, pos=(745, 476), size=(75, 25))
        self.user_workid.SetValue('FA022')

        userquery = wx.Button(pnl, wx.ID_ANY, label='查詢', pos=(1080, 476), size=(70, 25))
        userquery.Bind(wx.EVT_BUTTON, self.OnUserDefineBtn)

        self.UserDefineQuery = wx.ListBox(pnl, pos=(675,506), size = (480,128),style= wx.LB_SINGLE|wx.LB_HSCROLL)

        ###################################################################################


    def OnLogonBtn(self,event):
        LogonJob(Job.LOGON, self.acc.GetValue(),self.pwd.GetValue())        

    def OnLogoutBtn(self,event):
        self.acclist_combo.Clear()
        LogoutJob(Job.LOGOUT)       
        
    def OnUserDefineBtn(self,event):               
        UserDefineJob(Job.USERDEFINE, self.user_params.GetValue(),self.user_workid.GetValue())     

    def OnOrderBtn(self,event):
        # 從帳號下拉選單取出分行號、帳號、子帳號。
        vars = self.acclist_combo.GetString(self.acclist_combo.GetSelection()).split('-')
        bhno = vars[1]
        account = vars[2]
        ae_no = vars[3]
        OrderJob(Job.ORDER, bhno,account,ae_no)        

    def OnOrdQueryBtn(self,event):
        vars = self.acclist_combo.GetString(self.acclist_combo.GetSelection()).split('-')
        bhno = vars[1]
        account = vars[2]
        ae_no = vars[3]
        OrdQueryJob(Job.ORDQUERY, bhno,account,ae_no)        

    def OnMatQueryBtn(self,event):
        vars = self.acclist_combo.GetString(self.acclist_combo.GetSelection()).split('-')
        bhno = vars[1]
        account = vars[2]
        ae_no = vars[3]
        MatQueryJob(Job.MATQUERY, bhno,account,ae_no)               

    def ORFcheckBtn(self,event):                    
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

    def Logmessage(self,msg):
        self.statusMessage.Append(msg)

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
        elif self.value in args: # changed for v1.5, see below
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
    def __init__ (self, job_type):
        self.job_type = job_type                

class LogonJob(Job):
    def __init__(self, job_type,account,password):
        super(LogonJob, self).__init__(job_type)
        self.account = account
        self.pwd = password
        q.put(self)

class LogoutJob(Job):
    def __init__(self, job_type):
        super(LogoutJob, self).__init__(job_type)
        q.put(self)

class UserDefineJob(Job):
    def __init__(self, job_type,params,workid):
        super(UserDefineJob, self).__init__(job_type)       
        self.params = params
        self.workid = workid
        q.put(self)

class OrderJob(Job):
    def __init__(self, job_type ,bhno ,account ,ae_no):
        super(OrderJob, self).__init__(job_type)    
        self.bhno = bhno
        self.account = account
        self.ae_no = ae_no        
        q.put(self)

class OrdQueryJob(Job):
    def __init__(self, job_type ,bhno ,account ,ae_no):
        super(OrdQueryJob, self).__init__(job_type)    
        self.bhno = bhno
        self.account = account
        self.ae_no = ae_no        
        q.put(self)

class MatQueryJob(Job):
    def __init__(self, job_type ,bhno ,account ,ae_no):
        super(MatQueryJob, self).__init__(job_type)    
        self.bhno = bhno
        self.account = account
        self.ae_no = ae_no        
        q.put(self)


def  DoJob(Bot, x):    
    for case in switch(x.job_type):
        if case(Job.LOGON):
            Bot.login (x.account,x.pwd)
            break
        if case(Job.LOGOUT):
            Bot.logout()
            break
        if case(Job.USERDEFINE):
            Bot.user_define(x.params,x.workid)
            break
        if case(Job.ORDER):
            Bot.send_order(x.bhno,x.account,x.ae_no)
            break
        if case(Job.ORDQUERY):
            Bot.send_ordQuery(x.bhno,x.account,x.ae_no)
            break
        if case(Job.MATQUERY):
            Bot.send_matQuery(x.bhno,x.account,x.ae_no)
            break

class StockBot:
    def __init__(self, botuid):
        self.Yuanta = YuantaOrdWapper (botuid, self)        
        self.YuantaAccount = []
        self.YuantaSN = []

    def login (self,account,pwd):
        self.Yuanta.YuantaOrd.SetFutOrdConnection(account, pwd, 'api.yuantafutures.com.tw', '80') 
        frame.Logmessage('login')                 

    def logout (self):    
        self.Yuanta.YuantaOrd.DoLogout()
        frame.Logmessage('logout')

    def user_define (self,params,workid):                        
        ret = self.Yuanta.YuantaOrd.UserDefinsFunc (params, workid)
        frame.Logmessage('user define ret = {}'.format(ret))        

    def send_order (self,bhon,account,ae_no): 
        ##同步、非同步##
        if frame.wait.GetValue() == True:
            self.Yuanta.YuantaOrd.SetWaitOrdResult(1);
        else:
            self.Yuanta.YuantaOrd.SetWaitOrdResult(0);

        ##國外、國內##
        if frame.rfcheck.GetValue() == True:
            frame.Logmessage("RfSendOrder() {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}".format (
                    frame.fcode_combo.GetString(frame.fcode_combo.GetSelection())[0:2], 
                    frame.ctype_rfcombo.GetString(frame.ctype_rfcombo.GetSelection())[0:1], 
                    bhon, 
                    account,
                    ae_no,
                    frame.ordno.GetValue(), 
                    frame.bscode1_combo.GetString(frame.bscode1_combo.GetSelection())[0:1],      
                    frame.futno1.GetValue(),                     
                    frame.pritype_rfcombo.GetString(frame.pritype_rfcombo.GetSelection())[0:1],                    
                    frame.price.GetValue(),
                    frame.stopprice.GetValue(),
                    frame.lots.GetValue(), 
                    frame.offset_combo.GetString(frame.offset_combo.GetSelection())[0:1]));

            ret_no = self.Yuanta.YuantaOrd.RfSendOrder(frame.fcode_combo.GetString(frame.fcode_combo.GetSelection())[0:2], 
                                                       frame.ctype_rfcombo.GetString(frame.ctype_rfcombo.GetSelection())[0:1], 
                                                       bhon, 
                                                       account,
                                                       ae_no,
                                                       frame.ordno.GetValue(), 
                                                       frame.bscode1_combo.GetString(frame.bscode1_combo.GetSelection())[0:1],      
                                                       frame.futno1.GetValue(),                     
                                                       frame.pritype_rfcombo.GetString(frame.pritype_rfcombo.GetSelection())[0:1],                    
                                                       frame.price.GetValue(),
                                                       frame.stopprice.GetValue(),
                                                       frame.lots.GetValue(), 
                                                       frame.offset_combo.GetString(frame.offset_combo.GetSelection())[0:1])

            frame.Logmessage("RfSendOrder() return = {}".format(ret_no))

        else:
            frame.Logmessage("SendOrderF() {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}".format (
                    frame.fcode_combo.GetString(frame.fcode_combo.GetSelection())[0:2], 
                    frame.ctype_combo.GetString(frame.ctype_combo.GetSelection())[0:1], 
                    bhon, 
                    account,
                    ae_no,
                    frame.ordno.GetValue(), 
                    frame.bscode1_combo.GetString(frame.bscode1_combo.GetSelection())[0:1],      
                    frame.futno1.GetValue(),                     
                    frame.price.GetValue(),
                    frame.lots.GetValue(), 
                    frame.offset_combo.GetString(frame.offset_combo.GetSelection())[0:1],
                    frame.pritype_combo.GetString(frame.pritype_combo.GetSelection())[0:1],                                        
                    frame.pritype_cond.GetString(frame.pritype_cond.GetSelection())[0:1],                                        
                    frame.bscode2_combo.GetString(frame.bscode2_combo.GetSelection())[0:1],
                    frame.futno2.GetValue()));

            if frame.futno2.GetValue().strip() == '':
                bs2 = ''
            else:
                bs2 = frame.bscode2_combo.GetString(frame.bscode2_combo.GetSelection())[0:1]

            ret_no = self.Yuanta.YuantaOrd.SendOrderF(frame.fcode_combo.GetString(frame.fcode_combo.GetSelection())[0:2], 
                                                     frame.ctype_combo.GetString(frame.ctype_combo.GetSelection())[0:1], 
                                                     bhon, 
                                                     account,
                                                     ae_no,
                                                     frame.ordno.GetValue(), 
                                                     frame.bscode1_combo.GetString(frame.bscode1_combo.GetSelection())[0:1],      
                                                     frame.futno1.GetValue(),                     
                                                     frame.price.GetValue(),
                                                     frame.lots.GetValue(), 
                                                     frame.offset_combo.GetString(frame.offset_combo.GetSelection())[0:1],
                                                     frame.pritype_combo.GetString(frame.pritype_combo.GetSelection())[0:1],                                        
                                                     frame.pritype_cond.GetString(frame.pritype_cond.GetSelection())[0:1],                                        
                                                     bs2,
                                                     frame.futno2.GetValue().strip())
            
            frame.Logmessage("SendOrderF() return = {}".format(ret_no))

    def send_ordQuery (self,bhon,account,ae_no):         
        if frame.rfcheck.GetValue() == True:    #查國外          
             ret_code = self.Yuanta.YuantaOrd.RfReportQuery(bhon, account, ae_no,
                            frame.ordstatus_combo.GetString(frame.ordstatus_combo.GetSelection())[0:1],                             
                            frame.ordcflag_combo.GetString(frame.ordcflag_combo.GetSelection())[0:1],
                            '*')             
             frame.Logmessage("RfReportQuery() return = {}".format(ret_code))
        else:                                   #查國內
             ret_code = self.Yuanta.YuantaOrd.ReportQuery("F", bhon, account, ae_no,
                            frame.ordstatus_combo.GetString(frame.ordstatus_combo.GetSelection())[0:1], 
                            '*', 
                            frame.ordcflag_combo.GetString(frame.ordcflag_combo.GetSelection())[0:1])        
             frame.Logmessage("ReportQuery() return = {}".format(ret_code))


    def send_matQuery (self,bhon,account,ae_no):         
        if frame.rfcheck.GetValue() == True:    #查國外                       
             ret_code = self.Yuanta.YuantaOrd.RfDealQuery(bhon, account, ae_no,'*')
             frame.Logmessage("RfDealQuery() return = {}".format(ret_code))
        else:                                   #查國內             
             ret_code = self.Yuanta.YuantaOrd.DealQuery("F", bhon, account, ae_no,'*')        
             frame.Logmessage("DealQuery() return = {}".format(ret_code))

        
class YuantaOrdEvents(object):
    def __init__(self, parent):
        self.parent = parent
    def OnLogonS(self, this, TLinkStatus, AccList, Casq, Cast):        
        frame.Logmessage('OnLogonS {},{},{},{}'.format (TLinkStatus, AccList, Casq, Cast))        
        status = '{}'.format(TLinkStatus)
        frame.connect_status.SetValue(status)
        if TLinkStatus == 2:
            datas = AccList.split(';')            
            for data in datas:             
                frame.acclist_combo.Append(data)
            frame.acclist_combo.SetSelection(0)
            if len(Casq) != 0:
                self.parent.bot.YuantaSN.append (Casq.split('=')[1])            

    def OnReportQuery(self, this, RowCount, Results):
        frame.OrdQueryRpt.Clear()
        datas = Results.split('|')
        for i in range(0,RowCount):
            data = ''
            for j in range(0,int(len(datas) / RowCount)):
                data += datas[i * (int(len(datas) / RowCount)) + j]
                if j < int(len(datas) / RowCount) - 1:
                    data += ','
                else:
                    frame.OrdQueryRpt.Append(data)

        
    def OnDealQuery(self, this, RowCount, Results):
        frame.MatQueryRpt.Clear()
        datas = Results.split('|')
        for i in range(0,RowCount):
            data = ''
            for j in range(0,int(len(datas) / RowCount)):
                data += datas[i * (int(len(datas) / RowCount)) + j]
                if j < int(len(datas) / RowCount) - 1:
                    data += ','
                else:
                    frame.MatQueryRpt.Append(data)

    def OnUserDefinsFuncResult(self, this, RowCount, Results, WorkID):
        frame.UserDefineQuery.Append(Results)

    def OnOrdRptF(self, this, Omkt, Mktt, Cmbf, Statusc, Ts_Code, Ts_Msg, Bhno, AcNo,
            Suba, Symb, Scnam, O_Kind, O_Type, Buys, S_Buys, O_Prc, O_Qty, Work_Qty, Kill_Qty,
            Deal_Qty, Order_No, T_Date, O_Date, O_Time,
            O_Src, O_Lin, A_Prc, Oseq_No, Err_Code,
            Err_Msg, R_Time, D_Flag):
        msg = 'Omkt={},Mktt={},Cmbf={},Statusc={},Ts_Code={},Ts_Msg={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},O_Type={},Buys={},S_Buys={},O_Prc={},O_Qty={},Work_Qty={},Kill_Qty={},Deal_Qty={},Order_No={},T_Date={},O_Date={},O_Time={},O_Src={},O_Lin={},A_Prc={},Oseq_No={},Err_Code={},Err_Msg={},R_Time={},D_Flag={}'.format(Omkt.strip(), Mktt.strip(), Cmbf.strip(), Statusc.strip(), Ts_Code.strip(), Ts_Msg.strip(), Bhno.strip(), AcNo.strip(), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), O_Type.strip(), Buys.strip(), S_Buys.strip(), O_Prc.strip(), O_Qty.strip(), Work_Qty.strip(), Kill_Qty.strip(), Deal_Qty.strip(), Order_No.strip(), T_Date.strip(), O_Date.strip(), O_Time.strip(), O_Src.strip(), O_Lin.strip(), A_Prc.strip(), Oseq_No.strip(), Err_Code.strip(), Err_Msg.strip(), R_Time.strip(), D_Flag.strip())
        frame.OrdQueryRpt.Append(msg)
        
    def OnOrdMatF(self, this, Omkt, Buys, Cmbf, Bhno,
            AcNo, Suba, Symb, Scnam, O_Kind,
            S_Buys, O_Prc, A_Prc, O_Qty, Deal_Qty,
            T_Date, D_Time, Order_No, O_Src, O_Lin,
            Oseq_No):
        msg = 'Omkt={},Buys={},Cmbf={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},S_Buys={},O_Prc={},A_Prc={},O_Qty={},Deal_Qty={},T_Date={},D_Time={},Order_No={},O_Src={},O_Lin={},Oseq_No={}'.format(Omkt.strip(), Buys.strip(), Cmbf.strip(), Bhno.strip(), AcNo.strip(), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), S_Buys.strip(), O_Prc.strip(), A_Prc.strip(), O_Qty.strip(), Deal_Qty.strip(), T_Date.strip(), D_Time.strip(), Order_No.strip(), O_Src.strip(), O_Lin.strip(), Oseq_No.strip())
        frame.MatQueryRpt.Append(msg)

    def OnOrdResult(self, this, ID, result):
        msg = 'OnOrdResult:ID={},result={}'.format(ID,result)       
        frame.Logmessage(msg)

    def OnRfOrdRptRF(self, this, exc, Omkt, Statusc, Ts_Code,
            Ts_Msg, Bhno, Acno, Suba, Symb,
            Scnam, O_Kind, Buys, S_Buys, PriceType,
            O_Prc1, O_Prc2, O_Qty, Work_Qty, Kill_Qty,
            Deal_Qty, Order_No, O_Date, O_Time, O_Src,
            O_Lin, A_Prc, Oseq_No, Err_Code, Err_Msg,
            R_Time, D_Flag):
        msg = 'Exchange={},Omkt={},Statusc={},Ts_Code={},Ts_Msg={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},Buys={},S_Buys={},PriceType={},O_Prc1={},O_Prc2={},O_Qty={},Work_Qty={},Kill_Qty={},Deal_Qty={},Order_No={},O_Date={},O_Time={},O_Src={},O_Lin={},A_Prc={},Oseq_No={},Err_Code={},Err_Msg={},R_Time={},D_Flag={}'.format(exc.strip(), Omkt.strip(), Statusc.strip(), Ts_Code.strip(), Ts_Msg.strip(), Bhno.strip(), Acno.strip(), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), Buys.strip(), S_Buys.strip(), PriceType.strip(), O_Prc1.strip(), O_Prc2.strip(), O_Qty.strip(), Work_Qty.strip(), Kill_Qty.strip(), Deal_Qty.strip(), Order_No.strip(), O_Date.strip(), O_Time.strip(), O_Src.strip(), O_Lin.strip(), A_Prc.strip(), Oseq_No.strip(), Err_Code.strip(), Err_Msg.strip(), R_Time.strip(), D_Flag.strip())
        frame.OrdQueryRpt.Append(msg)
        
    def OnRfOrdMatRF(self, this, Exchange, Omkt, Bhno, AcNo,
            Suba, Symb, Scnam, O_Kind, Buys,
            S_Buys, PriceType, O_Prc1, O_Prc2, A_Prc,
            O_Qty, Deal_Qty, O_Date, D_Time, Order_No,
            O_Src, O_Lin, Oseq_No):
        msg = 'Exchange={},Omkt={},Bhno={},Acno={},Suba={},Symb={},Scnam={},O_Kind={},Buys={},S_Buys={},PriceType={},O_Prc1={},O_Prc2={},A_Prc={},O_Qty={},Deal_Qty={},Order_No={},O_Date={},D_Time={},O_Src={},O_Lin={},Oseq_No={}'.format(exc.strip(), Omkt.strip(), Bhno.strip(), Acno.strip(), Suba.strip(), Symb.strip(), Scnam.strip(), O_Kind.strip(), Buys.strip(), S_Buys.strip(), PriceType.strip(), O_Prc1.strip(), O_Prc2.strip(), A_Prc.strip(), O_Qty.strip(), Deal_Qty.strip(), Order_No.strip(), O_Date.strip(), O_Time.strip(), O_Src.strip(), O_Lin.strip(), Oseq_No.strip())
        frame.MatQueryRpt.Append(msg)

    def OnRfOrdResult(self, this, ID, result):
        msg = 'OnRfOrdResult:ID={},result={}'.format(ID,result)       
        frame.Logmessage(msg)

    def OnRfReportQuery(self, this, RowCount, Results):
        frame.OrdQueryRpt.Clear()
        datas = Results.split('|')
        for i in range(0,RowCount):
            data = ''
            for j in range(0,int(len(datas) / RowCount)):
                data += datas[i * (int(len(datas) / RowCount)) + j]
                if j < int(len(datas) / RowCount) - 1:
                    data += ','
                else:
                    frame.OrdQueryRpt.Append(data)

    def OnRfDealQuery(self, this, RowCount, Results):
        frame.MatQueryRpt.Clear()
        datas = Results.split('|')
        for i in range(0,RowCount):
            data = ''
            for j in range(0,int(len(datas) / RowCount)):
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

        res = atl.AtlAxCreateControlEx("Yuanta.YuantaOrdCtrl.64", handle, None, 
                                    byref(Iwindow),
                                    byref(Icontrol),
                                    byref(GUID()), 
                                    Ievent) 

        self.YuantaOrd = GetBestInterface(Icontrol)
        self.YuantaOrdEvents = YuantaOrdEvents(self)
        self.YuantaOrdEventsConnect = GetEvents(self.YuantaOrd, self.YuantaOrdEvents)

        

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
            run_func ()
            while not q.empty():
                next_job = q.get()
                DoJob (Bot, next_job)

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

def run_job():
    while not q.empty():
        next_job = q.get()
        DoJob (Bot, next_job)

if __name__ == "__main__":
    app=MyApp()    
    frame = AppFrame(None, title='YuantaOrdAPI Sample',size = (1180,680))
    frame.Show(True)
    Bot = StockBot(frame.Handle)    
    app.MainLoop(run_job)    

