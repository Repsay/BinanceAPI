import pyarrow.feather as feather
import pandas as pd
import numpy as np
import os

from talib import abstract
from talib import MA_Type
import talib as tb

from .exceptions import UnknownMATypeException, UnknownSymbolException

def get_pair_info(Client, symbol):
    result = Client.get_exchange_info()

    for item in result["symbols"]:
        if item["symbol"] == symbol.upper():
            return item
    
    raise UnknownSymbolException(symbol.upper())

def get_all_symbols(Client):
    #get all symbols from the exchange
    result = Client.get_exchange_info()

    #create empty list to store all symbols
    temp_lst = []

    for pair in result["symbols"]:
        temp_lst.append(pair["symbol"])

    #sort alphabeticly
    temp_lst = sorted(temp_lst)

    return temp_lst


def get_best_symbols(Client, n, quote="BTC"):
    
    """
    n = top n amount of symbols
    quote = qoute symbol to be trading with BTC for instance

    returns a list with best n amount of symbols with quote.
    """

    #recieve all possibilities
    symbols = get_all_symbols(Client)
    symbols = [symbol for symbol in symbols if symbol[-3:] == quote]
    
    #create temp dictonary to store all symbols with change percent in last 24hours
    temp_dic = {}

    for symbol in symbols:
        #for each symbol grab the price change percent of the last 24 hours
        param = {
            "symbol": symbol
        }

        result = Client.get_ticker(**param)

        temp_dic[result["symbol"]] = result["priceChangePercent"]        

    #sort the dictonary on value and only store list on temp
    temp_lst = [k for k, v in sorted(temp_dic.items(), key=lambda item: float(item[1]), reverse=True)]

    return np.array(temp_lst[:n])

def get_all_asset_balance(Client, n=0):
    #grab all account info
    result = Client.get_account()

    #temp dictonary to store all basesymbols with free coins
    temp_dic = {}

    for asset in result["balances"]:
        if float(asset["free"]) >= n:
            #only store all balances higher or equal to n
            temp_dic[asset["asset"]] = float(asset["free"])
        else:
            pass
    
    return temp_dic

def updateCandle(Client, symbol, interval):
        
        #check excistence of the folders and create structure if not already there
        filename = f"{Client.MAIN_PATH}/data/candles/{interval}"
        lastTime = 0
        colCandle = ["OpenTime","OpenPrice","HighPrice","LowPrice","ClosePrice","CloseTime","Volume","NumberTrades"]
        
        if not os.path.exists(filename):
            os.makedirs(filename)
        
        filename = f"{filename}/{symbol}.feather"

        if not os.path.isfile(filename):
            df = pd.DataFrame(columns=colCandle)
            feather.write_feather(df, filename)
        
        df = feather.read_feather(filename)

        if not df["OpenTime"].empty:
            lastTime = str(df["OpenTime"].iloc[-1])

        lst = []

        for candle in Client.get_historical_candles_generator(symbol, lastTime, interval):
            lst.append([int(candle[0]), float(candle[1]), float(candle[2]), float(candle[3]), float(candle[4]), int(candle[6]), float(candle[5]), int(candle[8])])

        df = df.append(pd.DataFrame(lst, columns=colCandle), ignore_index=True)

        feather.write_feather(df, filename)


def updateAllCandles(Client, symbols, interval):
    
    symbols = [symbol for symbol in symbols if "BTC" in symbol]

    for symbol in symbols:
        updateCandle(Client, symbol, interval)
        print(f"{symbol} Done")

def updateEMA(Client, symbol, emas, interval):

    First = True

    #check files and directories
    filename = f"{Client.MAIN_PATH}/data/candles/{interval}"
    filename2 = f"{Client.MAIN_PATH}/data/ema/{interval}"

    if not os.path.exists(filename):
        os.makedirs(filename)
    
    if not os.path.exists(filename2):
        os.makedirs(filename2)
    
    fn = f"{filename}/{symbol}.feather"
    fn2 = f"{filename2}/{symbol}.feather"

    if os.path.isfile(fn):
        df_cdl = feather.read_feather(fn)

        if not df_cdl["OpenTime"].empty:
        
            if os.path.isfile(fn2):
                df_ema = feather.read_feather(fn2)

                if not df_ema.empty:
                    First = False
                    ema_lastDate = df_ema.iloc[-1]
                    df_add = df_cdl.loc[df_cdl["OpenTime"] > ema_lastDate["OpenTime"], ["OpenTime", "ClosePrice"]]

                    if not df_add.empty:
                        for num in emas:
                            name = f"EMA{num}"
                            prevMA = ema_lastDate[name]
                            temp_lst = []

                            for close in df_add["ClosePrice"]:
                                prevMA = close * (2/(num+1)) + prevMA * (1 - (2/(num+1)))
                                temp_lst.append(prevMA)

                            df_add[name] = temp_lst

                        df_ema = df_ema.append(df_add, ignore_index=True)
                        feather.write_feather(df_ema, fn2)
            
            if First:
                df_ema2 = df_cdl.loc[:,["OpenTime", "ClosePrice"]]
            
                if not df_cdl.empty:
                    for num in emas:
                        name = f"EMA{num}"
                        df_ema2[name] = abstract.EMA(df_ema2["ClosePrice"], timeperiod=num)

                feather.write_feather(df_ema2, fn2)
        else:
            print("file is empty")

def updateAllEMA(Client, symbols, emas, interval):

    symbols = [symbol for symbol in symbols if "BTC" in symbol]

    length = len(symbols)
    cur_amount = 0

    for i in range(length):
        new_amount = int((i/length) * 10)
        if cur_amount < new_amount:
            cur_amount = new_amount
            print("*"*cur_amount, end="\r")
        updateEMA(Client, symbols[i], emas, interval)

def updateMA(Client, symbol, mas, interval, ma_type):

    if ma_type == MA_Type.SMA:
        folder = "ma"
    elif ma_type == MA_Type.WMA:
        folder = "wma"
    else:
        raise UnknownMATypeException()
    
    #check files and directories
    filename = f"{Client.MAIN_PATH}/data/candles/{interval}"
    filename2 = f"{Client.MAIN_PATH}/data/{folder}/{interval}"

    if not os.path.exists(filename):
        os.makedirs(filename)
    
    if not os.path.exists(filename2):
        os.makedirs(filename2)
    
    fn = f"{filename}/{symbol}.feather"
    fn2 = f"{filename2}/{symbol}.feather"

    if os.path.isfile(fn):
        df_cdl = feather.read_feather(fn)

        if not df_cdl["OpenTime"].empty:
        
            if os.path.isfile(fn2):
                df_ma = feather.read_feather(fn2)
            else:
                df_ma = pd.DataFrame(columns=["OpenTime","ClosePrice"])
                feather.write_feather(df_ma, fn2)

            length_old = len(df_ma.index)

            if not df_ma.empty:
                if length_old >= mas[-1]:
                    ma_lastDate = df_ma["OpenTime"].iloc[-(mas[-1] - 1)]
                    length_old = mas[-1] - 1
                else:
                    ma_lastDate = df_ma["OpenTime"].iloc[0]
            else:
                ma_lastDate = 0

            df_add = df_cdl.loc[df_cdl["OpenTime"] >= ma_lastDate, ["OpenTime", "ClosePrice"]]

            if not df_add.empty:
                for num in mas:
                    name = f"MA{num}"
                    df_add[name] = abstract.MA(df_add["ClosePrice"], timeperiod=num, matype=ma_type)
                
                df_add = df_add[length_old:]

                df_ma = df_ma.append(df_add, ignore_index=True)

                feather.write_feather(df_ma, fn2)
            else:
                print("Nothing to do")
        else:
            print("file is empty")

def updateAllMA(Client, symbols, mas, interval, ma_type):

    symbols = [symbol for symbol in symbols if "BTC" in symbol]

    length = len(symbols)
    cur_amount = 0

    for i in range(length):
        new_amount = int((i/length) * 10)
        if cur_amount < new_amount:
            cur_amount = new_amount
            print("*"*cur_amount, end="\r")
        updateMA(Client, symbols[i], mas, interval, ma_type)


def get_all_intervals(Client):
    intervals = [Client.KLINE_INTERVAL_1MINUTE, Client.KLINE_INTERVAL_3MINUTE, Client.KLINE_INTERVAL_5MINUTE, Client.KLINE_INTERVAL_15MINUTE, Client.KLINE_INTERVAL_30MINUTE, Client.KLINE_INTERVAL_1HOUR, Client.KLINE_INTERVAL_2HOUR, Client.KLINE_INTERVAL_4HOUR, Client.KLINE_INTERVAL_6HOUR, Client.KLINE_INTERVAL_8HOUR, Client.KLINE_INTERVAL_12HOUR, Client.KLINE_INTERVAL_1DAY, Client.KLINE_INTERVAL_3DAY, Client.KLINE_INTERVAL_1WEEK]
    
    return intervals
