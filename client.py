import requests
import hmac
import hashlib
import time
import os
import sys
import numpy as np

from operator import itemgetter

import binance.helpers as bhelp
from binance.exceptions import APIException, RequestException, WithdrawException

class Client(object):
    """
    Data is returned in ascending order. Oldest first, newest last
    time and timestamps related fields are in milliseconds
    
    """

    API_URL = "https://api.binance.{}/api"
    WITHDRAW_API_URL = "https://api.binance.{}/wapi"
    MARGIN_API_URL = "https://api.binance.{}/sapi"
    WEBSITE_URL = "https://www.binance.{}"
    FUTURES_URL = "https://fapi.binance.{}/fapi"
    TEST_API_URL = "https://testnet.binance.vision/api"
    PUBLIC_API_VERSION = "v3"
    PRIVATE_API_VERSION = "v3"
    WITHDRAW_API_VERSION = "v3"
    MARGIN_API_VERSION = "v1"
    FUTURES_API_VERSION = "v1"

    SYMBOL_STATUS_PRE_TRADING = "PRE_TRADING"
    SYMBOL_STATUS_TRADING = "TRADING"
    SYMBOL_STATUS_POST_TRADING = "POST_TRADING"
    SYMBOL_STATUS_END_OF_DAY = "END_OF_DAY"
    SYMBOL_STATUS_HALT = "HALT"
    SYMBOL_STATUS_AUCTION_MATCH = "AUCTION_MATCH"
    SYMBOL_STATUS_BREAK = "BREAK"

    SYMBOL_TYPE_SPOT = "SPOT"

    ORDER_STATUS_NEW = "NEW"
    ORDER_STATUS_PARTIALLY_FILLED = "PARTIALLY_FILLED"
    ORDER_STATUS_FILLED = "FILLED"
    ORDER_STATUS_CANCELED = "CANCELED"
    ORDER_STATUS_PENDING_CANCEL = "PENDING_CANCEL"
    ORDER_STATUS_REJECTED = "REJECTED"
    ORDER_STATUS_EXPIRED = "EXPIRED"

    OCO_STATUS_RESPONSE = "RESPONSE"
    OCO_STATUS_EXEC_STARTED = "EXEC_STARTED"
    OCO_STATUS_ALL_DONE = "ALL_DONE"
    OCO_STATUS_EXECUTING = "EXECUTING"
    OCO_STATUS_REJECT = "REJECT"

    CONTINGENCY_TYPE_OCO = "OCO"

    KLINE_INTERVAL_1MINUTE = "1m"
    KLINE_INTERVAL_3MINUTE = "3m"
    KLINE_INTERVAL_5MINUTE = "5m"
    KLINE_INTERVAL_15MINUTE = "15m"
    KLINE_INTERVAL_30MINUTE = "30m"
    KLINE_INTERVAL_1HOUR = "1h"
    KLINE_INTERVAL_2HOUR = "2h"
    KLINE_INTERVAL_4HOUR = "4h"
    KLINE_INTERVAL_6HOUR = "6h"
    KLINE_INTERVAL_8HOUR = "8h"
    KLINE_INTERVAL_12HOUR = "12h"
    KLINE_INTERVAL_1DAY = "1d"
    KLINE_INTERVAL_3DAY = "3d"
    KLINE_INTERVAL_1WEEK = "1w"
    KLINE_INTERVAL_1MONTH = "1M"

    SIDE_BUY = "BUY"
    SIDE_SELL = "SELL"

    ORDER_TYPE_LIMIT = "LIMIT"
    ORDER_TYPE_MARKET = "MARKET"
    ORDER_TYPE_STOP_LOSS = "STOP_LOSS"                  #MARKET order when the stopPrice is reached
    ORDER_TYPE_STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    ORDER_TYPE_TAKE_PROFIT = "TAKE_PROFIT"              #MARKET order when the stopPrice is reached
    ORDER_TYPE_TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    ORDER_TYPE_LIMIT_MAKER = "LIMIT_MAKER"              #LIMIT order that will be rejected if immediately matched and trade as a taker

    TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
    TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
    TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

    ORDER_RESP_TYPE_ACK = "ACK"
    ORDER_RESP_TYPE_RESULT = "RESULT"
    ORDER_RESP_TYPE_FULL = "FULL"

    RATE_LIMIT_REQUEST_WEIGHT = "REQUEST_WEIGHT"
    RATE_LIMIT_ORDERS = "ORDERS"
    RATE_LIMIT_RAW_REQUEST = "RAW_REQUESTS"

    RATE_LIMIT_INTERVAL_SECONDS = "SECOND"
    RATE_LIMIT_INTERVAL_MINUTES = "MINUTE"
    RATE_LIMIT_INTERVAL_DAYS = "DAY"

    # For accessing the data returned by Client.aggregate_trades().
    AGG_ID = "a"
    AGG_PRICE = "p"
    AGG_QUANTITY = "q"
    AGG_FIRST_TRADE_ID = "f"
    AGG_LAST_TRADE_ID = "l"
    AGG_TIME = "T"
    AGG_BUYER_MAKES = "m"
    AGG_BEST_MATCH = "M"

    MAIN_PATH = ""

    def __init__(self, api_key=None, api_secret=None, requests_params=None, tld="com", test=False):
        if not test:
            self.API_URL = self.API_URL.format(tld)
        else:
            self.API_URL = self.TEST_API_URL
        self.WITHDRAW_API_URL = self.WITHDRAW_API_URL.format(tld)
        self.MARGIN_API_URL = self.MARGIN_API_URL.format(tld)
        self.WEBSITE_URL = self.WEBSITE_URL.format(tld)
        self.FUTURES_URL = self.FUTURES_URL.format(tld)
        self.MAIN_PATH = os.path.dirname(os.path.realpath(sys.argv[0]))

        self.API_KEY = api_key
        self.API_SECRET = api_secret
        self.session = self._init_session()
        self._requests_params = requests_params
        self.response = None

        #To init DNS and SSL certificates
        self.ping()
    
    def _init_session(self):

        session = requests.session()
        session.headers.update({
            "Accept": "application/json",
            "User-Agent": "binance/python",
            "X-MBX-APIKEY": self.API_KEY
        })

        return session
    
    def _create_api_uri(self, path, signed=True, version=PUBLIC_API_VERSION):
        if signed:
            v = self.PRIVATE_API_VERSION
        else:
            v = version
        
        return self.API_URL + "/" + v + "/" + path
    
    def _create_withdraw_api_uri(self, path):
        return self.WITHDRAW_API_URL + "/" + self.WITHDRAW_API_VERSION + "/" + path
    
    def _create_margin_api_uri(self, path):
        return self.MARGIN_API_URL + "/" + self.MARGIN_API_VERSION + "/" + path
    
    def _create_website_uri(self, path):
        return self.WEBSITE_URL + "/" + path

    def _create_futures_api_uri(self, path):
        return self.FUTURES_URL + "/" + self.FUTURES_API_VERSION + "/" + path
    
    def _generate_signature(self, data):

        ordered_data = self._order_params(data)
        query_string = "&".join(["{}={}".format(elem[0], elem[1]) for elem in ordered_data])

        #encoding the signature for the link
        m = hmac.new(self.API_SECRET.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256)
        return m.hexdigest()

    def _order_params(self, data):

        has_signature = False
        params = []

        for key, value in data.items():
            if key == "signature":
                has_signature = True
            else:
                params.append((key, value))
        
        #sort params by key
        params.sort(key=itemgetter(0))

        if has_signature:
            params.append(("signature", data["signature"]))
        
        return params
    
    def _request(self, method, uri, signed, force_params=False, **kwargs):

        #set default requests timeout
        kwargs["timeout"] = 10

        #add global requests params
        if self._requests_params:
            kwargs.update(self._requests_params)

        #create key
        data = kwargs.get("data", None)
        if data and isinstance(data, dict):
            kwargs["data"] = data

            #find any requests params passed and apply them
            if "requests_params" in kwargs["data"]:
                #merge requests params into kwargs
                kwargs.update(kwargs["data"]["requests_params"])
                del(kwargs["data"]["requests_params"])
        
        if signed:
            #generate signature
            kwargs["data"]["timestamp"] = int(time.time() * 1000)
            kwargs["data"]["signature"] = self._generate_signature(kwargs["data"])
        
        #sort get and post params to match signature order
        if data:
            #sort post params
            kwargs["data"] = self._order_params(kwargs["data"])

            #remove any arguments with values of None
            null_args = [i for i, (key, value) in enumerate(kwargs["data"]) if value is None]
            for i in reversed(null_args): #remove in reversed order to not have shifting indexes
                del(kwargs["data"][i])

        if data and (method == "get" or force_params):
            kwargs["params"] = "&".join("{}={}".format(elem[0], elem[1]) for elem in kwargs["data"])
            del(kwargs["data"])

        self.response = getattr(self.session, method)(uri, **kwargs)
        return self._handle_response()

    def _request_api(self, method, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        uri = self._create_api_uri(path, signed, version)

        return self._request(method, uri, signed, **kwargs)

    def _request_withdraw_api(self, method, path, signed=False, **kwargs):
        uri = self._create_withdraw_api_uri(path)

        return self._request(method, uri, signed, True, **kwargs)

    def _request_margin_api(self, method, path, signed=False, **kwargs):
        uri = self._create_margin_api_uri(path)

        return self._request(method, uri, signed, **kwargs)

    def _request_website(self, method, path, signed=False, **kwargs):
        uri = self._create_website_uri(path)

        return self._request(method, uri, signed, **kwargs)

    def _request_futures_api(self, method, path, signed=False, **kwargs):
        uri = self._create_futures_api_uri(path)

        return self._request(method, uri, signed, True, **kwargs)

    def _handle_response(self):
        if not str(self.response.status_code).startswith("2"):
            raise APIException(self.response)
        try:
            return self.response.json()
        except ValueError:
            raise RequestException(f"Invalid Response: {self.response.text}")

    def _get(self, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        return self._request_api("get", path, signed, version, **kwargs)

    def _post(self, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        return self._request_api("post", path, signed, version, **kwargs)

    def _put(self, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        return self._request_api("put", path, signed, version, **kwargs)

    def _delete(self, path, signed=False, version=PUBLIC_API_VERSION, **kwargs):
        return self._request_api("delete", path, signed, version, **kwargs)

    def get_exchange_info(self):
        """Current exchange trading rules and symbol information
        :params: None
        :returns: dict -> {
            "timezone": str,
            "serverTime": int,
            "rateLimits": lst -> [dict -> {"rateLimitType": str, "interval": str, "intervalNum": int, "limit": int}],    #for all different rateLimitTypes
            "exchangeFilters": lst -> [#each filter has its own format],
            "symbols": lst -> [dict -> {
                "symbol": str,
                "status": str,
                "baseAsset": str,
                "baseAssetPrecision": int,
                "quoteAsset": str,
                "quotePrecision": int,
                "quoteAssetPrecision": int,
                "orderTypes": lst -> [str],
                "icebergAllowed": bool,
                "ocoAllowed": bool,
                "isSpotTradingAllowed": bool,
                "isMarginTradingAllowed": bool,
                "filters": lst -> [#each filter has its own format],
                "permissions": lst -> [str]
            }]
        }
        """
        return self._get("exchangeInfo")
    
    def ping(self):
        """Test connectivity to the Rest API
        :params: None
        :returns: dict -> {}
        """
        return self._get("ping")
    
    def get_server_time(self):
        """Test connectivity to the Rest API and get the current server time.
        :params: None
        :returns: dict -> {
            "serverTime": int
        }
        """
        return self._get("time")
    
    def get_all_tickers(self):
        return self._get("ticker/price")

    def get_orderbook_tickers(self):
        return self._get("ticker/bookTicker")
    
    def get_orderbook(self, **params):
        """Current order book
        :params: dict -> {
            "symbol": str,
            "limit": int    #Optional - Default: 100 - Valid: [5, 10, 20, 50, 100, 500, 1000, 5000]
        }
        :returns: dict -> {
            "lastUpdateId": int,
            "bids": lst -> [lst -> [str]],  #Price, Quantity
            "asks": lst -> [lst -> [str]]   #Price, Quantity
        }
        """
        return self._get("depth", data=params)

    def get_recent_trades(self, **params):
        """Recent trades
        :params: {
            "symbol": str,
            "limit": int    #Optional - Default: 500 - Max: 1000
        }
        :returns: lst -> [dict -> {
            "id": int,
            "price": str,
            "qty": str,
            "quoteQty": str,
            "time": int,
            "isBuyerMaker": bool,
            "isBestMatch": bool
        }]
        """
        return self._get("trades", data=params)

    def get_historical_trades(self, **params):
        """Older market trades
        :params: {
            "symbol": str,
            "limit": int,   #Optional - Default: 500 - Max: 1000
            "fromId": long  #Optional - Default: most recent trades
        }
        :returns: lst -> [dict -> {
            "id": int,
            "price": str,
            "qty": str,
            "quoteQty": str,
            "time": int,
            "isBuyerMaker": bool,
            "isBestMatch": bool
        }]
        """
        return self._get("historicalTrades", data=params)
    
    def get_aggregate_trades(self, **params):
        """Get compressed, aggregate trades. Trades that fill at the time, from the same order, with the same price will have the quantity aggregated.
        :params: {                  #When both startTime and endTime are sent time between start and end must be less than 1 hour. When neither fromId, startTime or endTime is sent most recent aggregate trades returned.
            "symbol": str,
            "fromId": long,     #Optional - INCLUSIVE
            "startTime": long,  #Optional - INCLUSIVE
            "endTime": long,    #Optional - INCLUSIVE
            "limit": int        #Optional - Default: 500 - Max: 1000
        }
        :returns: lst -> [dict -> {
            "a": int,   #Aggregate tradeId
            "p": str,   #Price
            "q": str,   #Quantity
            "f": int,   #First tradeId
            "l": int,   #Last tradeId
            "T": int,   #Timestamp
            "m": bool,  #was maker?
            "M": bool   #was best match?
        }]
        """
        return self._get("aggTrades", data=params)

    def aggregate_trade_iter(self, symbol, start_str=None, last_id=None):
        #You can only specify one of the two
        if start_str is not None and last_id is not None:
            raise ValueError(
                "start_time and last_id may not be simultaneously specified.")
        
        if last_id is None:
            #Without a last_id, we actually need the first trade.
            if start_str is None:

                params = {"symbol": symbol, "fromId": 0}

                trades = self.get_aggregate_trades(**params)
            else:
                if type(start_str) == int:
                    start_ts = start_str
                else:
                    start_ts = bhelp.date_to_milliseconds(start_str)
                
                while True:
                    #start time + an hour in milliseconds
                    end_ts = start_ts + (60 * 60 * 1000)

                    params = {"symbol":symbol, "StartTime":start_ts, "endTime":end_ts}

                    trades = self.get_aggregate_trades(**params)

                    if len(trades) > 0:
                        break

                    if end_ts > int(time.time() * 1000):
                        return
                    
                    start_ts = end_ts
            
            for trade in trades:
                yield trade
            last_id = trades[-1][self.AGG_ID]

        params = {"symbol": symbol, "fromId": last_id}

        while True:
            trades = self.get_aggregate_trades(**params)

            if len(trades) == 1:
                return
            
            trades.pop(0)

            for trade in trades:
                yield trade
                
            params["fromId"] = trades[-1][self.AGG_ID]

    def get_candles(self, **params):
        """Kline/candlestick bars for a symbol. Klines are uniquely identified by their open time.
        :params: {              #Neither startTime or endTime most recent returned
            "symbol": str,
            "interval": enum,
            "startTime": long,  #Optional - INCLUSIVE? #TODO
            "endTime": long,    #Optional - INCLUSIVE? #TODO
            "limit": int        #Optional - Default: 500 - Max: 1000
        }
        :returns: lst -> [lst -> [
            int,    #Open time
            str,    #Open price
            str,    #High price
            str,    #Low price
            str,    #Close price
            str,    #Volume
            int,    #Close time
            str,    #Quote asset volume
            int,    #Number of trades
            str,    #Taker buy base asset volume
            str,    #Taker buy quote asset volume
            str     #IGNORE
        ]]
        """
        return self._get("klines", data=params)

    def _get_earliest_valid_timestamp(self, symbol, interval=KLINE_INTERVAL_15MINUTE):
        #get earliest valid open timestamp from symbol

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1,
            "startTime": 0,
            "endTime": None
        }

        candles = self.get_candles(**params)

        return candles[0][0]
    
    def get_historical_candles(self, symbol, start_str, interval=KLINE_INTERVAL_15MINUTE, end_str=None, limit=500):
        output_data = []

        timeframe = bhelp.interval_to_milliseconds(interval)

        if type(start_str) == int:
            start_ts = start_str
        else:
            start_ts = bhelp.date_to_milliseconds(start_str)
        
        first_valid_ts = self._get_earliest_valid_timestamp(symbol, interval)
        start_ts = max(start_ts, first_valid_ts)

        end_ts = None
        if end_str:
            if type(end_str) == int:
                end_ts = end_str
            else:
                end_ts = bhelp.date_to_milliseconds(end_str)
        
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "startTime": start_ts,
            "endTime": end_ts
        }

        idx = 0
        while True:
            temp = self.get_candles(**params)

            if not len(temp):
                break

            output_data += temp

            params["startTime"] = temp[-1][0]

            idx += 1

            if len(temp) < limit:
                break

            params["startTime"] += timeframe

            if idx % 3 == 0:
                time.sleep(1)
            
        return output_data
    
    def get_historical_candles_generator(self, symbol, start_str, interval=KLINE_INTERVAL_15MINUTE, end_str=None):

        limit = 1000

        timeframe = bhelp.interval_to_milliseconds(interval)

        start_ts = int(start_str) + timeframe

        first_valid_ts = self._get_earliest_valid_timestamp(symbol, interval)
        start_ts = max(start_ts, first_valid_ts)

        end_ts = None
        if end_str:
            if type(end_str) == int:
                end_ts = end_str
            else:
                end_ts = bhelp.date_to_milliseconds(end_str)

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "startTime": start_ts,
            "endTime": end_ts
        }

        while True:
            output_data = np.array(self.get_candles(**params))

            if len(output_data) == 0 or len(output_data) == 1:
                break
            
            if len(output_data) < limit:
                output_data = np.delete(output_data, -1, axis=0)

            for output in output_data:
                yield output
            
            params["startTime"] = int(output_data[-1, 0])

            if len(output_data) < limit:
                break

            params["startTime"] += timeframe
           
    def get_avg_price(self, **params):
        """Current average price for a symbol
        :params: {
            "symbol": str
        }
        :returns: dict -> {
            "mins": int,
            "price": str
        }
        """
        return self._get("avgPrice", data=params)
    
    def get_ticker(self, **params):
        """24h rolling window price change statistics. Careful when accessing this with no symbol
        :params: {
            "symbol": str   #Optional
        }
        :returns: (When symbol sent): dict -> {     #When no symbol sent return lst of dict
            "symbol": str,
            "priceChange": str,
            "priceChangePercent": str,
            "weightedAvgPrice": str,
            "prevClosePrice": str,
            "lastPrice": str,
            "lastQty": str,
            "bidPrice": str,
            "askPrice": str,
            "openPrice": str,
            "highPrice": str,
            "lowPrice": str,
            "volume": str,
            "quoteVolume": str,
            "openTime": int,
            "closeTime": int,
            "firstId": int,
            "lastId": int,
            "count": int
        }
        """
        return self._get("ticker/24hr", data=params)
    
    def get_symbol_ticker(self, **params):
        """Latest price for a symbol or symbols
        :params: {
            "symbol": str   #Optional
        }
        :returns: (When symbol sent) -> dict -> {       #When no symbol sent return lst of dict
            "symbol": str,
            "price": str
        }
        """
        return self._get("ticker/price", data=params)

    def get_orderbook_ticker(self, **params):
        """Best price/qty on the order book for a symbol or symbols
        :params: {
            "symbol": str   #Optional
        }
        :returns: (When symbol sent) -> dict -> {       #When no symbol sent return lst of dict
            "symbol": str,
            "bidPrice": str,
            "bidQty": str,
            "askPrice": str,
            "askQty": str
        }
        """
        return self._get("ticker/bookTicker", data=params)

    def create_order(self, **params):
        """Send in a new order
        :params: {
            "symbol": str,
            "side": enum,
            "type": enum,
            "timeInForce": enum,            #Optional
            "quantity": decimal,            #Optional
            "quoteOrderQty": decimal,       #Optional
            "price": decimal,               #Optional
            "newClientOrderId": str,        #Optional   #unique id open orders - automatically generated if not sent - Same newClientOrderId can be accepted only when the previous one is filled, otherwise rejected
            "stopPrice": decimal,           #Optional
            "icebergQty": decimal,          #Optional   #When icebergQty sent timeInForce set to GTC
            "newOrderRespType": enum,       #Optional   #Set response - MARKET and LIMIT Default: FULL other Default: ACK
            "recvWindow": long,             #Optional   #Max: 60000
            "timestamp": long
        }

        Additional mandatory parameters based on type:
        LIMIT:              timeInForce - quantity - price
        MARKET:             quantity or quoteOrderQty
        STOP_LOSS:          quantity - stopPrice
        STOP_LOSS_LIMIT:    timeInForce - quantity - price - stopPrice
        TAKE_PROFIT:        quantity - stopPrice
        TAKE_PROFIT_LIMIT:  timeInForce - quantity - price - stopPrice
        LIMIT_MAKER:        quantity - price

        :returns:
        (newOrderRespType = ACK) -> dict -> {
            "symbol": str,
            "orderId": int,
            "orderListId": int, #Unless OCO, value will be -1
            "clientOrderId": str,
            "transactTime": int
        }
        (newOrderRespType = RESULT) -> dict -> {
            "symbol": str,
            "orderId": int,
            "orderListId": int, #Unless OCO, value will be -1
            "clientOrderId": str,
            "transactTime": int,
            "price": str,
            "origQty": str,
            "executedQty": str,
            "cummulativeQuoteQty": str,
            "status": str,
            "timeInForce": str,
            "type": str,
            "side": str
        }
        (newOrderRespType = FULL) -> dict -> {
            "symbol": str,
            "orderId": int,
            "orderListId": int, #Unless OCO, value will be -1
            "clientOrderId": str,
            "transactTime": int,
            "price": str,
            "origQty": str,
            "executedQty": str,
            "cummulativeQuoteQty": str,
            "status": str,
            "timeInForce": str,
            "type": str,
            "side": str,
            "fills": lst -> [dict -> {
                "price": str,
                "qty": str,
                "commission": str,
                "commissionAsset": str
            }]
        }
        """
        return self._post("order", True, data=params)

    def order_limit(self, timeInForce=TIME_IN_FORCE_GTC, **params):
        params.update({
            "type": self.ORDER_TYPE_LIMIT,
            "timeInForce": timeInForce
        })

        return self.create_order(**params)
    
    def order_limit_buy(self, timeInForce=TIME_IN_FORCE_GTC, **params):
        params.update({
            "side": self.SIDE_BUY
        })

        return self.order_limit(timeInForce=timeInForce, **params)
    
    def order_limit_sell(self, timeInForce=TIME_IN_FORCE_GTC, **params):
        params.update({
            "side": self.SIDE_SELL
        })

        return self.order_limit(timeInForce=timeInForce, **params)

    def order_market(self, **params):
        params.update({
            "type": self.ORDER_TYPE_MARKET
        })

        return self.create_order(**params)
    
    def order_market_buy(self, **params):
        params.update({
            "side": self.SIDE_BUY
        })

        return self.order_market(**params)

    def order_market_sell(self, **params):
        params.update({
            "side": self.SIDE_SELL
        })

        return self.order_market(**params)
    
    def create_oco_order(self, **params):
        return self._post("order/oco", True, data=params)
    
    def order_oco_buy(self, **params):
        params.update({
            "side": self.SIDE_BUY
        })

        return self.create_oco_order(**params)
    
    def order_oco_sell(self, **params):
        params.update({
            "side": self.SIDE_SELL
        })

        return self.create_oco_order(**params)
    
    def create_test_order(self, **params):
        """Test new order creation and signature/recvWindow long. Creates and validates a new order but does not send it into the matching engine.
        :params: {
            "symbol": str,
            "side": enum,
            "type": enum,
            "timeInForce": enum,            #Optional
            "quantity": decimal,            #Optional
            "quoteOrderQty": decimal,       #Optional
            "price": decimal,               #Optional
            "newClientOrderId": str,        #Optional   #unique id open orders - automatically generated if not sent - Same newClientOrderId can be accepted only when the previous one is filled, otherwise rejected
            "stopPrice": decimal,           #Optional
            "icebergQty": decimal,          #Optional   #When icebergQty sent timeInForce set to GTC
            "newOrderRespType": enum,       #Optional   #Set response - MARKET and LIMIT Default: FULL other Default: ACK
            "recvWindow": long,             #Optional   #Max: 60000
            "timestamp": long
        }

        Additional mandatory parameters based on type:
        LIMIT:              timeInForce - quantity - price
        MARKET:             quantity or quoteOrderQty
        STOP_LOSS:          quantity - stopPrice
        STOP_LOSS_LIMIT:    timeInForce - quantity - price - stopPrice
        TAKE_PROFIT:        quantity - stopPrice
        TAKE_PROFIT_LIMIT:  timeInForce - quantity - price - stopPrice
        LIMIT_MAKER:        quantity - price

        :returns: dict -> {}
        """
        return self._post("order/test", True, data=params)

    def get_order(self, **params):
        return self._get("order", True, data=params)
    
    def get_all_orders(self, **params):
        return self._get("allOrders", True, data=params)

    def cancel_order(self, **params):
        return self._delete("order", True, data=params)
    
    def cancel_all_orders_symbol(self, **params):
        return self._delete("openOrders", True, data=params)
    
    def get_open_orders(self, **params):
        return self._get("openOrders", True, data=params)

    def get_account(self, **params):
        return self._get("account", True, data=params)
    
    def get_asset_balance(self, asset, **params):
        result = self.get_account(**params)

        if "balances" in result:
            for balance in result["balances"]:
                if balance["asset"].lower() == asset.lower():
                    return balance
        
        return None

    def get_my_trades(self, **params):
        return self._get("myTrades", True, data=params)

    def get_account_status(self, **params):
        result = self._request_withdraw_api("get", "accountStatus.html", True, data=params)
        if not result["success"]:
            raise WithdrawException(result["msg"])
        return result

    def get_dust_log(self, **params):
        result = self._request_withdraw_api("get", "userAssetDribbletLog.html", True, data=params)

        if not result["succes"]:
            raise WithdrawException(result["msg"])
        return result
    
    def transfer_dust(self, **params):
        return self._request_margin_api("post", "asset/dust", True, data=params)

    def get_asset_dividend_history(self, **params):
        return self._request_margin_api("get", "asset/assetDividend", True, data=params)

    def get_trade_fee(self, **params):
        result = self._request_withdraw_api("get", "tradeFee.html", True, data=params)
        if not result["success"]:
            raise WithdrawException(result["msg"])
        return result
    
    def get_asset_details(self, **params):
        result = self._request_withdraw_api("get", "assetDetail.html", True, data=params)
        if not result["success"]:
            raise WithdrawException(result["msg"])
        return result

    def withdraw(self, **params):
        if "asset" in params and "name" not in params:
            params["name"] = params["asset"]
        
        result = self._request_withdraw_api("post", "withdraw.html", True, data=params)

        if not result["success"]:
            raise WithdrawException(result["msg"])
        return result

    def get_deposit_history(self, **params):
        return self._request_withdraw_api("get", "depositHistory.html", True, data=params)

    def get_withdraw_history(self, **params):
        return self._request_withdraw_api("get", "withdrawHistory.html", True, data=params)

    def get_deposit_address(self, **params):
        return self._request_withdraw_api("get", "depositAddress.html", True, data=params)
    
    def stream_get_listen_key(self):
        result = self._post("userDataStream", False, data={})
        return result["listenKey"]
    
    def stream_keepalive(self, listenKey):
        params = {
            "listenKey": listenKey
        }

        return self._put("userDataStream", False, data=params)
    
    def stream_close(self, listenKey):
        params = {
            "listenKey": listenKey
        }
        
        return self._delete("userDataStream", False, data=params)