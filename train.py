from numpy.testing._private.utils import tempdir
from binanceUpdate import update_candles, get_all_intervals
from binance.lib.enums import CandlestickInterval
from trader import Trader
import pyarrow.feather as feather
import pandas as pd
import numpy as np
import os
import random
from sklearn import preprocessing

SYMBOL = "BNBBTC"
INPUTROWS = 50
AMOUNTOFGENS = float('inf')
main_path_data = os.path.join("E:\\", "Binance", "data2")

POPULATION_SIZE = 5
MUTATION_RATE = 0.004

HIDDEN_LAYERS = [6 for i in range(20)]

UPDATE = False
IDX = 0

CLS = lambda: os.system("cls")

def pickOne(lst:list[Trader]):
    r = random.uniform(0,1)
    index = -1

    while r > 0:
        index += 1
        r -= lst[index].prob
    
    return lst[index]

def get_first_generation(layers) -> list[Trader]:
    global IDX
    base_trader = Trader(IDX, MUTATION_RATE, SYMBOL, layers)
    print(IDX, end='\r')
    traders = [base_trader]


    for i in range(IDX+1, IDX+POPULATION_SIZE):
        print(i, end='\r')
        if base_trader.brain.model_loaded:
            traders.append(base_trader.clone_mutate(i))
        else:
            traders.append(Trader(i, MUTATION_RATE, SYMBOL, layers))


    # for trader in traders:
    #     trader.tempStore()

    IDX += POPULATION_SIZE

    return traders

def get_all_dataframes() -> dict[CandlestickInterval, pd.DataFrame]:
    dfs = {}

    for interval in get_all_intervals():
        file_path = os.path.join(main_path_data, 'candles', interval.name, f'{SYMBOL}.feather')
        dfs[interval] = feather.read_feather(file_path)
    
    return dfs

CLS()

data_path = os.path.join(main_path_data, 'data', f'{SYMBOL}.feather')
if not os.path.exists(os.path.dirname(data_path)):
    os.makedirs(os.path.dirname(data_path))

intervals = get_all_intervals()

CLS()

if UPDATE or not os.path.isfile(data_path):
    update_candles(SYMBOL)
    dfs = get_all_dataframes()

    base_data: pd.DataFrame = dfs[CandlestickInterval.minutes1][["CloseTime", "OpenPrice", "HighPrice", "LowPrice", "ClosePrice","Volume","NumberTrades"]].iloc[45000:]
    data = base_data.copy()

    for interval in intervals:
        print(interval.name)
        if interval == CandlestickInterval.minutes1:
            del dfs[interval]
            continue
        else:
            temp_df = dfs[interval][["CloseTime", "OpenPrice", "HighPrice", "LowPrice", "ClosePrice","Volume","NumberTrades"]]
            data = pd.merge_asof(data.sort_values("CloseTime"), temp_df.sort_values("CloseTime"), on="CloseTime", suffixes=(None, f'_{interval.name}'))
            del dfs[interval]
            del temp_df
    
    data = pd.DataFrame(preprocessing.MinMaxScaler().fit_transform(data.values))

    feather.write_feather(data, data_path)
idx = 0
first = True
data: pd.DataFrame = feather.read_feather(data_path).iloc[:-45000]
highestFit = float('-inf') #[float('-inf') for i in range(len(HIDDEN_LAYERS))]
generationCount = 0 #[0 for i in range(len(HIDDEN_LAYERS))]
print("Generating traders")
bestTrader = None #[None for i in range(len(HIDDEN_LAYERS))]
previousTraders: list[Trader] = []

while generationCount <= AMOUNTOFGENS:

    totalFitness = 0
    new = False
    allTraders: list[Trader] = []
    if first:
        base_trader = Trader(idx, MUTATION_RATE, SYMBOL, HIDDEN_LAYERS[0])

    for i in range(len(HIDDEN_LAYERS)):
        layer = HIDDEN_LAYERS[i]
        traders: list[Trader] = []
        for j in range(POPULATION_SIZE):
            print(f'Generating trader {idx}')
            if first:
                if idx == 0:
                    traders.append(base_trader)
                else:
                    if base_trader.brain.model_loaded:
                        traders.append(base_trader.clone_mutate(idx))
                    else:
                        traders.append(Trader(idx, MUTATION_RATE, SYMBOL, layer))
            else:
                traders.append(pickOne(previousTraders).clone_mutate(idx))
            
            idx += 1
            

        CLS()
        line = ''
        for trader in allTraders:
            line = f"{line}trader {trader.idx} - fitness: {trader.fitness:.4f}, prob: {trader.prob:.4f}, trades: {trader.tradesCounter}, ptrades: {trader.tradesProfit}, profit: {trader.profit:.4f}, counter: {trader.counter}\n"
        print(line)
        print(f"Start generation {generationCount} - {i+1}/{len(HIDDEN_LAYERS)}")

        died_traders = []

        for p in range(0, len(data)):
            inputs: np.ndarray = np.delete(data.iloc[INPUTROWS + p:p:-1].to_numpy(), 0, 1).flatten()
            for k in reversed(range(len(traders))):
                traders[k].think(inputs)

                if traders[k].profit < 0 or (traders[k].counter % 120 == 0 and (traders[k].lastCounter == traders[k].tradesCounter)):
                    traders[k].profit = 0
                    died_traders.append(traders.pop(k))
                    continue
            
                if traders[k].counter % 120 == 0:
                    print(f"id: {traders[k].idx}\tcounter: {traders[k].counter}\tfit: {traders[k].fitness:.4f}\tprof: {traders[k].profit:.4f}\ttrades: {traders[k].tradesCounter}\tpt: {traders[k].tradesProfit}")

                if traders[k].counter % 120 == 0:
                    traders[k].lastCounter = traders[k].tradesCounter

            if len(traders) == 0:
                break
        
        print("All died!")

        tempTraders: list[Trader] = []
        
        if len(traders) > 0:
            tempTraders.extend(traders)
        
        if len(died_traders) > 0:
            tempTraders.extend(died_traders)
        
        for trader in tempTraders:
            if trader.profit < 0:
                trader.profit = 0

            if trader.tradesCounter > 0:
                extra_score = trader.counter #trader.tradesProfit/trader.tradesCounter * trader.counter + trader.counter
            else:
                extra_score = 0
            
            if trader.fitness > 0:
                trader.fitness = trader.profit * 100000 + extra_score
            else:
                trader.fitness = trader.profit * 100000 + extra_score
        
        if len(allTraders) < 5:
            allTraders.extend(tempTraders)
        else:
            allTraders.extend(tempTraders)
            allTraders = sorted(allTraders, key=lambda x: x.fitness, reverse=True)[:5]

        traders = []    
        died_traders = []
    
    for trader in allTraders:
        score = trader.fitness
        
        if score > 0:
            totalFitness += score
            trader.fitness = score
        else:
            trader.fitness = 0
            trader.profit = 0
        
        if score > highestFit:
            highestFit = trader.fitness
            bestTrader = trader
            new = True

    if not new:
        totalFitness += bestTrader.fitness
        allTraders.append(bestTrader)

    if new and totalFitness > 0:
        bestTrader.store()

    for trader in allTraders:
        if totalFitness > 0:
            trader.prob = trader.fitness / totalFitness
        else:
            trader.prob = 0
    
    print("Summary:")
    line = f"\nGeneration {generationCount}\n"

    for trader in allTraders:
            line = f"{line}trader {trader.idx} - fitness: {trader.fitness:.4f}, prob: {trader.prob:.4f}, trades: {trader.tradesCounter}, ptrades: {trader.tradesProfit}, profit: {trader.profit:.4f}, counter: {trader.counter}\n"
        
    print(line)

    fh = open(f"{main_path_data}/run.txt","a")
    fh.write(line)
    fh.close()

    idx = 0

    previousTraders = allTraders[:]
    first = False
        
    # if generationCount != AMOUNTOFGENS:
    #     print("Generating New Population")
    #     for i in range(len(HIDDEN_LAYERS)):
    #         traders = []
    #         for j in range(POPULATION_SIZE):
    #             print(j+1, end="\r")
                
    #             child: Trader = pickOne(allTraders)

    #             child = child.clone_mutate(IDX)
    #             child.tempStore()
    #             IDX += 1

    #             traders.append(child)
    #         traders_list[i] = traders
        
    generationCount += 1



        

