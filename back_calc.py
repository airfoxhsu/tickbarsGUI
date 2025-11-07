import trading_strategy_calc_back
# from datetime import datetime
import copy


def main():
    # H:\YuantaDayTrader\afternoon\Logs\20220624
    # H:\YQ32-20240201\Logs\20240308
    # H:\YQ32\YQ32-一單\Logs\20240311

    # filename = path+r"\event.log"
    # filename = r"" + input("請輸入要回測的檔案路徑: ")  # 如果字串已指定給變數,但不進行轉義,可用 r""+變數
    filename = r"H:\YQ32-20240201\Logs\20251107\event.log"
    ts = trading_strategy_calc_back.TradingStrategy()
    direction = "空"  # "多" #
    peaks = []
    temp_peaks = []
    Is_simulation = 0
    with open(filename, "r") as file:
        tick_generator = (tick.replace("  [全] MDS=1 Symbol=", ",").replace("=", ",").strip("\n").split(
            ",") for tick in file if "全" in tick and "tmatqty=-1" not in tick and "open=0" not in tick)
        for tick in tick_generator:
            # tick[1]：股票代號 [3]:參考價 [5]:開盤價 [15]:成交時間 [17]:成交價
            # tick[19]:單量 [21]:總成交量 [29]:bid [41]:askff
            try:
                MatchTime = tick[15]
                MatchPri = tick[17]

                if int(tick[15]) <= 134500000000 and tick[29] != "0":
                    # 初始化大小台資料庫、計算大小台個別總量、辨別內外盤、計算每一價位的成交量及量差
                    ts.execate_TXF_MXF(direction, tick[1], tick[3], tick[5], tick[15],
                                       tick[17], tick[19], tick[21], Is_simulation)

                    ts.execute_compare(
                        ts.price_compare_database, MatchTime, ts.new_price, ts.total_spread)
                    ts.execute_compare(
                        ts.temp_price_compare_database, MatchTime, ts.new_price, ts.temp_total_spread)
                    # ts.execute_compare(
                    #     ts.spread_compare_database, MatchTime, ts.total_spread, ts.new_price)

                    # if ts.price_compare_database.get("first_step_signal") and ts.price_compare_database and ts.spread_compare_database:
                    #     ts.first_step_signal(
                    #         MatchTime, direction, Is_simulation)

                    # if ts.price_compare_database.get("second_step_signal") and ts.price_compare_database and ts.spread_compare_database:
                    #     ts.second_step_signal(
                    #         MatchTime, direction, Is_simulation)

                    # # 找到所有的骆驼峰
                    # peaks = ts.find_peaks(ts.volumes_per_price)

                    # if peaks != temp_peaks:
                    #     set_peaks = set(peaks)
                    #     set_temp_peaks = set(temp_peaks)
                    #     temp_peaks = copy.deepcopy(peaks)
                    #     if ts.new_price in set_peaks.difference(set_temp_peaks):
                    #         ts.short_peak(MatchTime, direction, Is_simulation)

                    if ts.Index == 0 and ts.entry_signal:
                        if int(MatchTime) <= 130000000000:
                            # if ts.num<250000:
                            ts.handle_entry_signal(MatchTime, Is_simulation)

                    if ts.Index == -1:
                        if int(MatchTime) >= 132500000000:
                            ts.Index = 0
                            ts.profit += (ts.entry_price -
                                          ts.new_price-2)
                            print(
                                f'時間到 {MatchTime} {MatchPri}  損益: {ts.profit}')
                        # elif ts.short_signal["order_price"] < ts.new_price:
                        #     ts.handle_short_exit(MatchTime)

            except Exception as e:
                # print(e)
                pass
    amplitude = ts.price_compare_database["big_value"] - \
        ts.price_compare_database["small_value"]
    print(f"{MatchTime}   收盤價： {ts.new_price}   振幅: {amplitude}   筆數: {ts.count}  損益: {ts.profit}")
    print(ts.price_compare_database["big_array"])
    print(ts.price_compare_database["small_array"])
    print(
        f"{ts.TXF_database['total_volume']}  {ts.MXF_database['total_volume']}  {ts.MXF_database['current_total_volume']}")


if __name__ == "__main__":
    main()
