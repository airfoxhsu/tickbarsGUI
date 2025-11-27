import os
import re
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt
import glob

plt.rcParams.update({'figure.autolayout': True})

class FuturesBatchProcessorGUI:
    def __init__(self, window_size=1000):
        self.WINDOW_SIZE = window_size
        self.BIG_FUTURES_TAG = "TXF"
        self.SMALL_FUTURES_TAG = "MXF"
        # session definition
        self.day_start = (8,45)
        self.day_end = (13,45)
        self.night_start = (15,0)
        self.night_end = (5,0)

    def format_time(self, raw_time):
        try:
            s = str(raw_time)
            if len(s) >= 6:
                return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"
            return s
        except:
            return raw_time

    def parse_line(self, line):
        try:
            if "Symbol=" not in line or "tmatqty=" not in line:
                return None
            d = {}
            m = re.search(r"Symbol=([A-Z0-9]+)", line)
            if not m: return None
            d['symbol'] = m.group(1)

            m = re.search(r"tmatqty=(\d+)", line)
            if not m: return None
            d['tqty'] = int(m.group(1))

            m = re.search(r"matpri=(\d+)", line)
            d['price'] = float(m.group(1)) if m else None

            m = re.search(r"mattime=(\d+)", line)
            d['mattime'] = m.group(1) if m else ''

            m = re.search(r"high=(\d+)", line)
            d['high'] = float(m.group(1)) if m else None

            m = re.search(r"low=(\d+)", line)
            d['low'] = float(m.group(1)) if m else None

            m = re.search(r"bestbp=([\d]+)", line)
            d['bid1'] = float(m.group(1)) if m else None

            m = re.search(r"bestsp=([\d]+)", line)
            d['ask1'] = float(m.group(1)) if m else None

            date_m = re.search(r"(\d{8})", line)
            if date_m:
                d['logdate'] = date_m.group(1)
            return d
        except:
            return None

    def determine_bs(self, price, bid1, ask1, qty):
        if price is None or bid1 is None or ask1 is None:
            return 0
        if price >= ask1:
            return qty
        if price <= bid1:
            return -qty
        return 0

    def time_to_minutes(self, hhmmss):
        s = str(hhmmss)
        if len(s) < 6:
            return None
        hh = int(s[0:2]); mm = int(s[2:4]); ss = int(s[4:6])
        return hh*60 + mm

    def classify_session(self, mattime):
        mins = self.time_to_minutes(mattime)
        if mins is None:
            return 'unknown'
        day_start = self.day_start[0]*60 + self.day_start[1]
        day_end = self.day_end[0]*60 + self.day_end[1]
        night_start = self.night_start[0]*60 + self.night_start[1]
        night_end = self.night_end[0]*60 + self.night_end[1]
        if day_start <= mins <= day_end:
            return 'day'
        if mins >= night_start or mins <= night_end:
            return 'night'
        return 'other'

    def choose_root_and_range(self):
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("說明", "請選取 TickBarsGUI 的 Logs 根目錄（例如 H:\\Coding\\python\\TickBarsGUI\\Logs）")
        root_dir = filedialog.askdirectory(title="選擇 Logs 根目錄")
        if not root_dir:
            raise ValueError("未選擇目錄")
        dr = simpledialog.askstring("輸入日期區間", "請輸入日期區間（格式：YYYYMMDD-YYYYMMDD），例如：20250101-20251124")
        if not dr:
            raise ValueError("未輸入日期區間")
        try:
            start_s, end_s = dr.split('-')
            start_dt = datetime.strptime(start_s.strip(), "%Y%m%d")
            end_dt = datetime.strptime(end_s.strip(), "%Y%m%d")
            if end_dt < start_dt:
                raise ValueError("結束日不可早於開始日")
        except Exception as e:
            raise ValueError("日期格式錯誤，請使用 YYYYMMDD-YYYYMMDD") from e
        return root_dir, start_dt, end_dt

    def gather_files(self, root_dir, start_dt, end_dt):
        files = []
        dt = start_dt
        while dt <= end_dt:
            folder = os.path.join(root_dir, dt.strftime("%Y%m%d"))
            print(f"檢查目錄: {folder}")
            if os.path.isdir(folder):
                found = glob.glob(os.path.join(folder, "Event.Log"))
                print(f"  -> 找到 {len(found)} 個 Log 檔")
                for fp in found:
                    files.append(fp)
            else:
                print("  -> 目錄不存在")
            dt += timedelta(days=1)
        if not files:
            raise ValueError("在指定日期區間未找到任何 .Log 檔")
        return sorted(files)

    def process(self, root_dir, files, output_dir=None):
        if output_dir is None:
            output_dir = root_dir
        all_ticks = []
        last_tqty = {}
        for fp in files:
            # Extract date from folder name (parent directory of the log file)
            file_date = os.path.basename(os.path.dirname(fp))
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parsed = self.parse_line(line)
                    if not parsed:
                        continue
                    parsed['logdate'] = file_date
                    sym = parsed['symbol']
                    ct = parsed['tqty']
                    last = last_tqty.get(sym, -1)
                    if last == -1:
                        last_tqty[sym] = ct
                        continue
                    delta = ct - last
                    if delta > 0:
                        last_tqty[sym] = ct
                        parsed['qty'] = delta
                        parsed['bs_val'] = self.determine_bs(parsed.get('price'), parsed.get('bid1'), parsed.get('ask1'), delta)
                        parsed['source_file'] = os.path.basename(fp)
                        all_ticks.append(parsed)
        if not all_ticks:
            raise ValueError("沒有從所選檔案抽出任何成交記錄。")

        df = pd.DataFrame(all_ticks).reset_index(drop=True)
        for c in ['price','high','low','mattime','logdate','symbol','bs_val','qty','source_file']:
            if c not in df.columns:
                df[c] = None

        trades = []
        equity = []
        equity_sum = 0.0
        position = 0
        entry_price = None
        entry_time = None
        entry_date = None
        entry_day_high = None
        entry_day_low = None
        window_buffer = []
        last_window_signal = 0
        last_window_signal_str = ""
        consec_loss = 0
        max_consec_loss = 0
        current_day_high = None
        current_day_high = None
        current_day_low = None
        current_print_date = None

        for idx, row in df.iterrows():
            if row['logdate'] != current_print_date:
                current_print_date = row['logdate']
                print(f"\n========= {current_print_date} =========")

            curr_price = row['price']
            tick_high = row['high']
            tick_low = row['low']
            mattime = row['mattime']
            session = self.classify_session(mattime)

            # Session-end forced closing (intraday trading) - look ahead to next tick
            if position != 0 and session in ['day', 'night']:
                session_end_reason = None
                # Check if next tick exists and is in a different session
                if idx + 1 < len(df):
                    next_mattime = df.iloc[idx + 1]['mattime']
                    next_session = self.classify_session(next_mattime)
                    if next_session != session:
                        # Current tick is last tick of this session
                        if session == 'day':
                            session_end_reason = 'session_end_day'
                        elif session == 'night':
                            session_end_reason = 'session_end_night'
                
                if session_end_reason:
                    pnl_points = (curr_price - entry_price) * position
                    exit_time = mattime
                    holding_secs = None
                    try:
                        et = datetime.strptime(entry_time[:6], "%H%M%S")
                        xt = datetime.strptime(mattime[:6], "%H%M%S")
                        holding_secs = (xt - et).total_seconds()
                        if holding_secs < 0:
                            holding_secs += 24*3600
                    except:
                        holding_secs = None
                    
                    trades.append({
                        'entry_time': entry_time, 'exit_time': exit_time,
                        'entry_price': entry_price, 'exit_price': curr_price,
                        'position': position, 'pnl_points': pnl_points,
                        'holding_secs': holding_secs, 'exit_reason': session_end_reason,
                        'session': session, 'index_when_exited': idx
                    })
                    print(f"[Trade] {entry_date} {self.format_time(entry_time)} @ {entry_price:.0f} ({'Long' if position==1 else 'Short'}) -> {row['logdate']} {self.format_time(mattime)} @ {curr_price:.0f} | PnL: {pnl_points:+.0f} | Reason: {session_end_reason}")
                    equity_sum += pnl_points
                    equity.append({'idx': idx, 'equity': equity_sum})
                    if pnl_points < 0:
                        consec_loss += 1
                        if consec_loss > max_consec_loss:
                            max_consec_loss = consec_loss
                    else:
                        consec_loss = 0
                    
                    position = 0
                    entry_price = None
                    entry_time = None
                    entry_date = None
                    entry_day_high = None
                    entry_day_low = None

            if tick_high is not None:
                current_day_high = tick_high if current_day_high is None else max(current_day_high, tick_high)
            if tick_low is not None:
                current_day_low = tick_low if current_day_low is None else min(current_day_low, tick_low)

            stop_reason = None
            if position == 1 and entry_day_low is not None and current_day_low < entry_day_low:
                stop_reason = 'day_low_broken'
            if position == -1 and entry_day_high is not None and current_day_high > entry_day_high:
                stop_reason = 'day_high_broken'

            if stop_reason:
                pnl_points = (curr_price - entry_price) * position
                exit_time = mattime
                holding_secs = None
                try:
                    et = datetime.strptime(entry_time[:6], "%H%M%S")
                    xt = datetime.strptime(mattime[:6], "%H%M%S")
                    holding_secs = (xt - et).total_seconds()
                    if holding_secs < 0:
                        holding_secs += 24*3600
                except:
                    holding_secs = None

                trades.append({
                    'entry_time': entry_time, 'exit_time': exit_time,
                    'entry_price': entry_price, 'exit_price': curr_price,
                    'position': position, 'pnl_points': pnl_points,
                    'holding_secs': holding_secs, 'exit_reason': stop_reason,
                    'session': session, 'index_when_exited': idx
                })
                print(f"[Trade] {entry_date} {self.format_time(entry_time)} @ {entry_price:.0f} ({'Long' if position==1 else 'Short'}) -> {row['logdate']} {self.format_time(mattime)} @ {curr_price:.0f} | PnL: {pnl_points:+.0f} | Reason: {stop_reason}")
                equity_sum += pnl_points
                equity.append({'idx': idx, 'equity': equity_sum})
                if pnl_points < 0:
                    consec_loss += 1
                    if consec_loss > max_consec_loss:
                        max_consec_loss = consec_loss
                else:
                    consec_loss = 0

                prev_pos = position
                position = 0
                entry_price = None
                entry_time = None
                entry_day_high = None
                entry_day_low = None

                if last_window_signal != 0 and last_window_signal != prev_pos:
                    position = last_window_signal
                    entry_price = curr_price
                    entry_time = mattime
                    entry_date = row['logdate']
                    entry_day_high = current_day_high
                    entry_day_low = current_day_low
                continue

            window_buffer.append(row)
            if len(window_buffer) >= self.WINDOW_SIZE:
                window_df = pd.DataFrame(window_buffer)
                big_rows = window_df[window_df['symbol'].str.contains(self.BIG_FUTURES_TAG, na=False)]
                if not big_rows.empty:
                    display_record = big_rows.iloc[-1]
                    trend_source = big_rows
                else:
                    display_record = window_df.iloc[-1]
                    trend_source = window_df

                display_price = display_record['price']
                idx_min = trend_source['price'].idxmin()
                idx_max = trend_source['price'].idxmax()
                trend = "UP" if idx_min < idx_max else "DOWN"
                big_bs = window_df[window_df['symbol'].str.contains(self.BIG_FUTURES_TAG, na=False)]['bs_val'].sum()
                small_bs = window_df[window_df['symbol'].str.contains(self.SMALL_FUTURES_TAG, na=False)]['bs_val'].sum()

                signal = 0
                signal_str = ""
                if trend == "UP" and small_bs > 0 and big_bs < 0:
                    signal = -1; signal_str = "short"
                elif trend == "DOWN" and small_bs < 0 and big_bs > 0:
                    signal = 1; signal_str = "long"

                last_window_signal = signal
                last_window_signal_str = signal_str

                if signal != 0 and signal != position:
                    if position != 0:
                        pnl_points = (display_price - entry_price) * position
                        exit_time = display_record['mattime']
                        holding_secs = None
                        try:
                            et = datetime.strptime(entry_time[:6], "%H%M%S")
                            xt = datetime.strptime(exit_time[:6], "%H%M%S")
                            holding_secs = (xt - et).total_seconds()
                            if holding_secs < 0:
                                holding_secs += 24*3600
                        except:
                            holding_secs = None
                        trades.append({
                            'entry_time': entry_time, 'exit_time': exit_time,
                            'entry_price': entry_price, 'exit_price': display_price,
                            'position': position, 'pnl_points': pnl_points,
                            'holding_secs': holding_secs, 'exit_reason': 'reverse_signal',
                            'session': self.classify_session(exit_time), 'index_when_exited': idx
                        })
                        print(f"[Trade] {entry_date} {self.format_time(entry_time)} @ {entry_price:.0f} ({'Long' if position==1 else 'Short'}) -> {row['logdate']} {self.format_time(exit_time)} @ {display_price:.0f} | PnL: {pnl_points:+.0f} | Reason: reverse_signal")
                        equity_sum += pnl_points
                        equity.append({'idx': idx, 'equity': equity_sum})
                        if pnl_points < 0:
                            consec_loss += 1
                            if consec_loss > max_consec_loss:
                                max_consec_loss = consec_loss
                        else:
                            consec_loss = 0

                    position = signal
                    entry_price = display_price
                    entry_time = display_record['mattime']
                    entry_date = row['logdate']
                    entry_day_high = current_day_high
                    entry_day_low = current_day_low

                window_buffer = []

        if position != 0:
            last_row = pd.DataFrame(all_ticks).iloc[-1]
            last_price = last_row['price']
            last_time = last_row['mattime']
            pnl_points = (last_price - entry_price) * position
            trades.append({
                'entry_time': entry_time, 'exit_time': last_time,
                'entry_price': entry_price, 'exit_price': last_price,
                'position': position, 'pnl_points': pnl_points,
                'holding_secs': None, 'exit_reason': 'end_of_data',
                'session': self.classify_session(last_time), 'index_when_exited': len(df)-1
            })
            print(f"[Trade] {entry_date} {self.format_time(entry_time)} @ {entry_price:.0f} ({'Long' if position==1 else 'Short'}) -> {last_row['logdate']} {self.format_time(last_time)} @ {last_price:.0f} | PnL: {pnl_points:+.0f} | Reason: end_of_data")
            equity_sum += pnl_points
            equity.append({'idx': len(df)-1, 'equity': equity_sum})
            if pnl_points < 0:
                consec_loss += 1
                if consec_loss > max_consec_loss:
                    max_consec_loss = consec_loss

        trades_df = pd.DataFrame(trades)
        equity_df = pd.DataFrame(equity).sort_values('idx').reset_index(drop=True)

        stats = {}
        for sess in ['day','night','other','unknown']:
            sub = trades_df[trades_df['session']==sess]
            if sub.empty:
                stats[sess] = {'trades':0,'total_pnl':0.0,'avg_holding_secs':None,'win_rate':None,'max_consec_loss':None}
            else:
                wins = (sub['pnl_points']>0).sum()
                total = len(sub)
                stats[sess] = {
                    'trades': total,
                    'total_pnl': sub['pnl_points'].sum(),
                    'avg_holding_secs': sub['holding_secs'].dropna().mean(),
                    'win_rate': wins/total,
                    'max_consec_loss': self._max_consecutive_losses(sub['pnl_points'].tolist())
                }

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join(output_dir, f"askbid_results_{ts}")
        os.makedirs(base, exist_ok=True)
        trades_csv = os.path.join(base, "trades.csv")
        trades_xlsx = os.path.join(base, "trades.xlsx")
        equity_png = os.path.join(base, "equity_curve.png")
        summary_txt = os.path.join(base, "summary.txt")
        stats_csv = os.path.join(base, "stats.csv")

        trades_df.to_csv(trades_csv, index=False)
        # write excel (requires openpyxl)
        with pd.ExcelWriter(trades_xlsx) as writer:
            trades_df.to_excel(writer, sheet_name='trades', index=False)
            equity_df.to_excel(writer, sheet_name='equity', index=False)
            pd.DataFrame.from_dict(stats, orient='index').to_excel(writer, sheet_name='stats')

        if not equity_df.empty:
            plt.figure()
            plt.plot(equity_df['idx'], equity_df['equity'])
            plt.title("Equity Curve")
            plt.xlabel("Tick Index")
            plt.ylabel("Cumulative PnL (points)")
            plt.grid(True)
            plt.savefig(equity_png)
            plt.close()

        pd.DataFrame.from_dict(stats, orient='index').to_csv(stats_csv)

        with open(summary_txt, "w", encoding="utf-8") as f:
            f.write("Summary of results\n")
            f.write(f"Processed files: {len(files)}\n")
            f.write(f"Total trades: {len(trades_df)}\n")
            f.write(f"Equity final: {equity_sum}\n\n")
            f.write("Per-session stats:\n")
            for k,v in stats.items():
                f.write(f"{k}: {v}\n")

            for k,v in stats.items():
                f.write(f"{k}: {v}\n")

        # print summary to console
        total_pnl = equity_sum
        overall_wins = trades_df[trades_df['pnl_points']>0].shape[0]
        overall_trades = trades_df.shape[0]
        win_rate = (overall_wins/overall_trades*100) if overall_trades>0 else None
        avg_hold = trades_df['holding_secs'].dropna().mean() if 'holding_secs' in trades_df.columns else None
        max_consec = max_consec_loss

        print("\n===== 回測結果 =====")
        print(f"總損益（點數）：{total_pnl}")
        if win_rate is not None:
            print(f"交易勝率：{win_rate:.2f}% ({overall_wins}/{overall_trades})")
        else:
            print("交易勝率：無交易")
        print(f"平均持倉時間（秒）：{avg_hold}")
        print(f"最大連續虧損（筆數）：{max_consec}")

        for s,v in stats.items():
            print(f"{s}: trades={v['trades']}, total_pnl={v['total_pnl']}, win_rate={v['win_rate']}")

        return {
            'trades_csv': trades_csv,
            'trades_xlsx': trades_xlsx,
            'equity_png': equity_png,
            'summary_txt': summary_txt,
            'stats_csv': stats_csv,
            'stats_csv': stats_csv
        }

    def _max_consecutive_losses(self, pnl_list):
        maxc = 0; cur = 0
        for p in pnl_list:
            if p < 0:
                cur += 1
                if cur > maxc:
                    maxc = cur
            else:
                cur = 0
        return maxc

def main():
    app = FuturesBatchProcessorGUI(window_size=1000)
    try:
        root_dir, start_dt, end_dt = app.choose_root_and_range()
        files = app.gather_files(root_dir, start_dt, end_dt)
        out = app.process(root_dir, files, output_dir=os.getcwd())
        root = tk.Tk(); root.withdraw()
        messagebox.showinfo("完成", f"結果已輸出到：\n{os.path.dirname(out['summary_txt'])}")
        print("輸出檔案：")
        for k,v in out.items():
            print(f"{k}: {v}")
    except Exception as e:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("錯誤", str(e))
        print("Error:", e)

if __name__ == '__main__':
    main()
