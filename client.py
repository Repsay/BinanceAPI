import requests, hmac, hashlib, time, os, sys
import numpy as np

from operator import itemgetter

import binance.helpers as bhelp
from binance.exceptions import APIException, RequestException, WithdrawException

class Client(object):

    API_URL = "https://api.binance.{}/api"
    WITHDRAW_API_URL = "https://api.binance.{}/wapi"
    MARGIN_API_URL = "https://api.binance.{}/sapi"
    WEBSITE_URL = "https://www.binance.{}"
    FUTURES_URL = "https://fapi.binance.{}/fapi"
    PUBLIC_API_VERSION = "v3"
    PRIVATE_API_VERSION = "v3"
    WITHDRAW_API_VERSION = "v3"
    MARGIN_API_VERSION = "v1"
    FUTURES_API_VERSION = "v1"

    SYMBOL_TYPE_SPOT = "SPOT"

    ORDER_STATUS_NEW = "NEW"
    ORDER_STATUS_PARTIALLY_FILLED = "PARTIALLY_FILLED"
    ORDER_STATUS_FILLED = "FILLED"
    ORDER_STATUS_CANCELED = "CANCELED"
    ORDER_STATUS_PENDING_CANCEL = "PENDING_CANCEL"
    ORDER_STATUS_REJECTED = "REJECTED"
    ORDER_STATUS_EXPIRED = "EXPIRED"

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
    ORDER_TYPE_STOP_LOSS = "STOP_LOSS"
    ORDER_TYPE_STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    ORDER_TYPE_TAKE_PROFIT = "TAKE_PROFIT"
    ORDER_TYPE_TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    ORDER_TYPE_LIMIT_MAKER = "LIMIT_MAKER"

    TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
    TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
    TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

    ORDER_RESP_TYPE_ACK = "ACK"
    ORDER_RESP_TYPE_RESULT = "RESULT"
    ORDER_RESP_TYPE_FULL = "FULL"

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

    def __init__(self, api_key=None, api_secret=None, requests_params=None, tld="com"):
        """Binance API Client constructor

        :param api_key: API key
        :type api_key: str
        :param api_secret: API secret key
        :type api_secret: str
        :param request_params: optional - Dictornary of requests params to use for all calls
        :type requests_params: dict

        """
        self.API_URL = self.API_URL.format(tld)
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
        """Convert params to list with signature as last element

            :param data: dictionary with the params
            :type data: dict
            :return: list

        """

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

        """Do the request by the API

            :param method: type of getting data (get/post)
            :type method: str
            :param uri: url of the request
            :type uri: str
            :param signed: wether it needs a signature
            :type signed: bool
            :param force_params: #TODO
            :type force_params: bool
            :param kwargs: all params to send
            :type kwargs: dict


        """


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
        """Internal helper for handling API responses from the Binance server.
        Raises the appropriate exceptions when necessary; otherwise, returns the
        response.
        """
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
        """Return rate limits and list of symbols
        
        :returns: list - List of product dictionaries
        
        {
        "timezone": "UTC",
        "serverTime": 1565246363776,
        "rateLimits": [
            {
                {
                    "rateLimitType": "REQUEST_WEIGHT",
                    "interval": "MINUTE",
                    "intervalNum": 1,
                    "limit": 1200
                },
                {
                    "rateLimitType": "ORDERS",
                    "interval": "SECOND",
                    "intervalNum": 10,
                    "limit": 100
                },
                {
                    "rateLimitType": "ORDERS",
                    "interval": "DAY",
                    "intervalNum": 1,
                    "limit": 200000
                },
                {
                    "rateLimitType": "RAW_REQUESTS",
                    "interval": "MINUTE",
                    "intervalNum": 5,
                    "limit": 5000
                }
            }
        ],
        "exchangeFilters": [
            //These are the defined filters in the `Filters` section.
            //All filters are optional.
        ],
        "symbols": [
            {
            "symbol": "ETHBTC",
            "status": "TRADING",
            "baseAsset": "ETH",
            "baseAssetPrecision": 8,
            "quoteAsset": "BTC",
            "quotePrecision": 8,
            "quoteAssetPrecision": 8,
            "orderTypes": [
                "LIMIT",
                "LIMIT_MAKER",
                "MARKET",
                "STOP_LOSS",
                "STOP_LOSS_LIMIT",
                "TAKE_PROFIT",
                "TAKE_PROFIT_LIMIT"
            ],
            "icebergAllowed": true,
            "ocoAllowed": true,
            "isSpotTradingAllowed": true,
            "isMarginTradingAllowed": true,
            "filters": [
                //These are defined in the Filters section.
                //All filters are optional
            ],
            "permissions": [
                "SPOT",
                "MARGIN"
            ]
            }
        ]
        }"""


        return self._get("exchangeInfo")

    def get_pair_info(self, symbol):
        """Return information about a pair
        
        :param symbol: required e.g. ETHBTC
        :type symbol: str

        :returns: Dict or None


        {
            "symbol": "ETHBTC",
            "status": "TRADING",
            "baseAsset": "ETH",
            "baseAssetPrecision": 8,
            "quoteAsset": "BTC",
            "quotePrecision": 8,
            "orderTypes": ["LIMIT", "MARKET"],
            "icebergAllowed": false,
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.00000100",
                    "maxPrice": "100000.00000000",
                    "tickSize": "0.00000100"
                }, {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00100000",
                    "maxQty": "100000.00000000",
                    "stepSize": "0.00100000"
                }, {
                    "filterType": "MIN_NOTIONAL",
                    "minNotional": "0.00100000"
                }
            ]
        }"""

        result = self.get_exchange_info()

        for item in result["symbols"]:
            if item["symbol"] == symbol.upper():
                return item
        
        return None
    
    def ping(self):
        return self._get("ping")
    
    def get_server_time(self):
        return self._get("time")
    
    def get_all_tickers(self):
        """[
        {
            "symbol": "LTCBTC",
            "price": "4.00000200"
        },
        {
            "symbol": "ETHBTC",
            "price": "0.07946600"
        }
        ]"""

        return self._get("ticker/price")

    def get_orderbook_tickers(self):
        """[
        {
            "symbol": "LTCBTC",
            "bidPrice": "4.00000000",
            "bidQty": "431.00000000",
            "askPrice": "4.00000200",
            "askQty": "9.00000000"
        },
        {
            "symbol": "ETHBTC",
            "bidPrice": "0.07946700",
            "bidQty": "9.00000000",
            "askPrice": "100000.00000000",
            "askQty": "1000.00000000"
        }
        ]"""

        return self._get("ticker/bookTicker")
    
    def get_orderbook(self, **params):
        """{
        "lastUpdateId": 1027024,
        "bids": [
            [
            "4.00000000",     // PRICE
            "431.00000000"    // QTY
            ]
        ],
        "asks": [
            [
            "4.00000200",
            "12.00000000"
            ]
        ]
        }"""

        return self._get("depth", data=params)

    def get_recent_trades(self, **params):
        """[
        {
            "id": 28457,
            "price": "4.00000100",
            "qty": "12.00000000",
            "quoteQty": "48.000012",
            "time": 1499865549590,
            "isBuyerMaker": true,
            "isBestMatch": true
        }
        ]"""

        return self._get("trades", data=params)

    def get_historical_trades(self, **params):
        """[
        {
            "id": 28457,
            "price": "4.00000100",
            "qty": "12.00000000",
            "quoteQty": "48.000012",
            "time": 1499865549590, // Trade executed timestamp, as same as `T` in the stream
            "isBuyerMaker": true,
            "isBestMatch": true
        }
        ]"""

        return self._get("historicalTrades", data=params)
    
    def get_aggregate_trades(self, **params):
        """[
        {
            "a": 26129,         // Aggregate tradeId
            "p": "0.01633102",  // Price
            "q": "4.70443515",  // Quantity
            "f": 27781,         // First tradeId
            "l": 27781,         // Last tradeId
            "T": 1498793709153, // Timestamp
            "m": true,          // Was the buyer the maker?
            "M": true           // Was the trade the best price match?
        }
        ]"""

        return self._get("aggTrades", data=params)

    def aggregate_trade_iter(self, symbol, start_str=None, last_id=None):
        """
        :returns: an iterator of JSON objects, one per trade. The format of
        each object is identical to Client.aggregate_trades().
        """

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
        """[
        [
            1499040000000,      // Open time
            "0.01634790",       // Open
            "0.80000000",       // High
            "0.01575800",       // Low
            "0.01577100",       // Close
            "148976.11427815",  // Volume
            1499644799999,      // Close time
            "2434.19055334",    // Quote asset volume
            308,                // Number of trades
            "1756.87402397",    // Taker buy base asset volume
            "28.46694368",      // Taker buy quote asset volume
            "17928899.62484339" // Ignore.
        ]
        ]"""

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
        """{
        "mins": 5,
        "price": "9.35751834"
        }"""

        return self._get("avgPrice", data=params)
    
    def get_ticker(self, **params):
        """{
        "symbol": "BNBBTC",
        "priceChange": "-94.99999800",
        "priceChangePercent": "-95.960",
        "weightedAvgPrice": "0.29628482",
        "prevClosePrice": "0.10002000",
        "lastPrice": "4.00000200",
        "lastQty": "200.00000000",
        "bidPrice": "4.00000000",
        "askPrice": "4.00000200",
        "openPrice": "99.00000000",
        "highPrice": "100.00000000",
        "lowPrice": "0.10000000",
        "volume": "8913.30000000",
        "quoteVolume": "15.30000000",
        "openTime": 1499783499040,
        "closeTime": 1499869899040,
        "firstId": 28385,   // First tradeId
        "lastId": 28460,    // Last tradeId
        "count": 76         // Trade count
        }"""

        return self._get("ticker/24hr", data=params)
    
    def get_symbol_ticker(self, **params):
        """{
        "symbol": "LTCBTC",
        "price": "4.00000200"
        }"""

        return self._get("ticker/price", data=params)

    def get_orderbook_ticker(self, **params):
        """{
        "symbol": "LTCBTC",
        "bidPrice": "4.00000000",
        "bidQty": "431.00000000",
        "askPrice": "4.00000200",
        "askQty": "9.00000000"
        }"""

        return self._get("ticker/bookTicker", data=params)

    def create_order(self, **params):
        """{
        "symbol": "BTCUSDT",
        "orderId": 28,
        "orderListId": -1, //Unless OCO, value will be -1
        "clientOrderId": "6gCrw2kRUAF9CvJDGP16IP",
        "transactTime": 1507725176595,
        "price": "0.00000000",
        "origQty": "10.00000000",
        "executedQty": "10.00000000",
        "cummulativeQuoteQty": "10.00000000",
        "status": "FILLED",
        "timeInForce": "GTC",
        "type": "MARKET",
        "side": "SELL",
        "fills": [
            {
            "price": "4000.00000000",
            "qty": "1.00000000",
            "commission": "4.00000000",
            "commissionAsset": "USDT"
            },
            {
            "price": "3999.00000000",
            "qty": "5.00000000",
            "commission": "19.99500000",
            "commissionAsset": "USDT"
            },
            {
            "price": "3998.00000000",
            "qty": "2.00000000",
            "commission": "7.99600000",
            "commissionAsset": "USDT"
            },
            {
            "price": "3997.00000000",
            "qty": "1.00000000",
            "commission": "3.99700000",
            "commissionAsset": "USDT"
            },
            {
            "price": "3995.00000000",
            "qty": "1.00000000",
            "commission": "3.99500000",
            "commissionAsset": "USDT"
            }
        ]
        }"""

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
        return self._post("order/test", True, data=params)

    def get_order(self, **params):
        """{
        "symbol": "LTCBTC",
        "orderId": 1,
        "orderListId": -1, //Unless OCO, value will be -1
        "clientOrderId": "myOrder1",
        "price": "0.1",
        "origQty": "1.0",
        "executedQty": "0.0",
        "cummulativeQuoteQty": "0.0",
        "status": "NEW",
        "timeInForce": "GTC",
        "type": "LIMIT",
        "side": "BUY",
        "stopPrice": "0.0",
        "icebergQty": "0.0",
        "time": 1499827319559,
        "updateTime": 1499827319559,
        "isWorking": true,
        "origQuoteOrderQty": "0.000000"
        }"""

        return self._get("order", True, data=params)
    
    def get_all_orders(self, **params):
        """[
        {
            "symbol": "LTCBTC",
            "orderId": 1,
            "orderListId": -1, //Unless OCO, the value will always be -1
            "clientOrderId": "myOrder1",
            "price": "0.1",
            "origQty": "1.0",
            "executedQty": "0.0",
            "cummulativeQuoteQty": "0.0",
            "status": "NEW",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY",
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": true,
            "origQuoteOrderQty": "0.000000"
        }
        ]"""

        return self._get("allOrders", True, data=params)

    def cancel_order(self, **params):
        """{
        "symbol": "LTCBTC",
        "origClientOrderId": "myOrder1",
        "orderId": 4,
        "orderListId": -1, //Unless part of an OCO, the value will always be -1.
        "clientOrderId": "cancelMyOrder1",
        "price": "2.00000000",
        "origQty": "1.00000000",
        "executedQty": "0.00000000",
        "cummulativeQuoteQty": "0.00000000",
        "status": "CANCELED",
        "timeInForce": "GTC",
        "type": "LIMIT",
        "side": "BUY"
        }"""

        return self._delete("order", True, data=params)
    
    def cancel_all_orders_symbol(self, **params):
        """[
        {
            "symbol": "BTCUSDT",
            "origClientOrderId": "E6APeyTJvkMvLMYMqu1KQ4",
            "orderId": 11,
            "orderListId": -1,
            "clientOrderId": "pXLV6Hz6mprAcVYpVMTGgx",
            "price": "0.089853",
            "origQty": "0.178622",
            "executedQty": "0.000000",
            "cummulativeQuoteQty": "0.000000",
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY"
        },
        {
            "symbol": "BTCUSDT",
            "origClientOrderId": "A3EF2HCwxgZPFMrfwbgrhv",
            "orderId": 13,
            "orderListId": -1,
            "clientOrderId": "pXLV6Hz6mprAcVYpVMTGgx",
            "price": "0.090430",
            "origQty": "0.178622",
            "executedQty": "0.000000",
            "cummulativeQuoteQty": "0.000000",
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY"
        },
        {
            "orderListId": 1929,
            "contingencyType": "OCO",
            "listStatusType": "ALL_DONE",
            "listOrderStatus": "ALL_DONE",
            "listClientOrderId": "2inzWQdDvZLHbbAmAozX2N",
            "transactionTime": 1585230948299,
            "symbol": "BTCUSDT",
            "orders": [
            {
                "symbol": "BTCUSDT",
                "orderId": 20,
                "clientOrderId": "CwOOIPHSmYywx6jZX77TdL"
            },
            {
                "symbol": "BTCUSDT",
                "orderId": 21,
                "clientOrderId": "461cPg51vQjV3zIMOXNz39"
            }
            ],
            "orderReports": [
            {
                "symbol": "BTCUSDT",
                "origClientOrderId": "CwOOIPHSmYywx6jZX77TdL",
                "orderId": 20,
                "orderListId": 1929,
                "clientOrderId": "pXLV6Hz6mprAcVYpVMTGgx",
                "price": "0.668611",
                "origQty": "0.690354",
                "executedQty": "0.000000",
                "cummulativeQuoteQty": "0.000000",
                "status": "CANCELED",
                "timeInForce": "GTC",
                "type": "STOP_LOSS_LIMIT",
                "side": "BUY",
                "stopPrice": "0.378131",
                "icebergQty": "0.017083"
            },
            {
                "symbol": "BTCUSDT",
                "origClientOrderId": "461cPg51vQjV3zIMOXNz39",
                "orderId": 21,
                "orderListId": 1929,
                "clientOrderId": "pXLV6Hz6mprAcVYpVMTGgx",
                "price": "0.008791",
                "origQty": "0.690354",
                "executedQty": "0.000000",
                "cummulativeQuoteQty": "0.000000",
                "status": "CANCELED",
                "timeInForce": "GTC",
                "type": "LIMIT_MAKER",
                "side": "BUY",
                "icebergQty": "0.639962"
            }
            ]
        }
        ]"""

        return self._delete("openOrders", True, data=params)
    
    def get_open_orders(self, **params):
        """[
        {
            "symbol": "LTCBTC",
            "orderId": 1,
            "orderListId": -1, //Unless OCO, the value will always be -1
            "clientOrderId": "myOrder1",
            "price": "0.1",
            "origQty": "1.0",
            "executedQty": "0.0",
            "cummulativeQuoteQty": "0.0",
            "status": "NEW",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY",
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": true,
            "origQuoteOrderQty": "0.000000"
        }
        ]"""

        return self._get("openOrders", True, data=params)

    def get_account(self, **params):
        """
        
        No parameters required

        {
        "makerCommission": 15,
        "takerCommission": 15,
        "buyerCommission": 0,
        "sellerCommission": 0,
        "canTrade": true,
        "canWithdraw": true,
        "canDeposit": true,
        "updateTime": 123456789,
        "accountType": "SPOT",
        "balances": [
            {
            "asset": "BTC",
            "free": "4723846.89208129",
            "locked": "0.00000000"
            },
            {
            "asset": "LTC",
            "free": "4763368.68006011",
            "locked": "0.00000000"
            }
        ],
        "permissions": [
            "SPOT"
        ]
        }"""

        return self._get("account", True, data=params)
    
    def get_asset_balance(self, asset, **params):
        """{
        "asset": "BTC",
        "free": "4723846.89208129",
        "locked": "0.00000000"
        }"""

        result = self.get_account(**params)

        if "balances" in result:
            for balance in result["balances"]:
                if balance["asset"].lower() == asset.lower():
                    return balance
        
        return None

    def get_my_trades(self, **params):
        """[
        {
            "symbol": "BNBBTC",
            "id": 28457,
            "orderId": 100234,
            "orderListId": -1, //Unless OCO, the value will always be -1
            "price": "4.00000100",
            "qty": "12.00000000",
            "quoteQty": "48.000012",
            "commission": "10.10000000",
            "commissionAsset": "BNB",
            "time": 1499865549590,
            "isBuyer": true,
            "isMaker": false,
            "isBestMatch": true
        }
        ]"""

        return self._get("myTrades", True, data=params)

    def get_account_status(self, **params):
        """{
            "msg": "Order failed:Low Order fill rate! Will be reactivated after 5 minutes.",
            "success": true,
            "objs": [
                "5"
            ]
        }"""

        result = self._request_withdraw_api("get", "accountStatus.html", True, data=params)
        if not result["success"]:
            raise WithdrawException(result["msg"])
        return result

    def get_dust_log(self, **params):
        """{
            "success": true, 
            "results": {
                "total": 2,   //Total counts of exchange
                "rows": [
                    {
                        "transfered_total": "0.00132256",//Total transfered BNB amount for this exchange.
                        "service_charge_total": "0.00002699",   //Total service charge amount for this exchange.
                        "tran_id": 4359321,
                        "logs": [           //Details of  this exchange.
                            {
                                "tranId": 4359321,
                                "serviceChargeAmount": "0.000009",
                                "uid": "10000015",
                                "amount": "0.0009",
                                "operateTime": "2018-05-03 17:07:04",
                                "transferedAmount": "0.000441",
                                "fromAsset": "USDT"
                            },
                            {
                                "tranId": 4359321,
                                "serviceChargeAmount": "0.00001799",
                                "uid": "10000015",
                                "amount": "0.0009",
                                "operateTime": "2018-05-03 17:07:04",
                                "transferedAmount": "0.00088156",
                                "fromAsset": "ETH"
                            }
                        ],
                        "operate_time": "2018-05-03 17:07:04" //The time of this exchange.
                    },
                    {
                        "transfered_total": "0.00058795",
                        "service_charge_total": "0.000012",
                        "tran_id": 4357015,
                        "logs": [       // Details of  this exchange.
                            {
                                "tranId": 4357015,
                                "serviceChargeAmount": "0.00001",
                                "uid": "10000015",
                                "amount": "0.001",
                                "operateTime": "2018-05-02 13:52:24",
                                "transferedAmount": "0.00049",
                                "fromAsset": "USDT"
                            },
                            {
                                "tranId": 4357015,
                                "serviceChargeAmount": "0.000002",
                                "uid": "10000015",
                                "amount": "0.0001",
                                "operateTime": "2018-05-02 13:51:11",
                                "transferedAmount": "0.00009795",
                                "fromAsset": "ETH"
                            }
                        ],
                        "operate_time": "2018-05-02 13:51:11"
                    }
                ]
            }
        }"""

        result = self._request_withdraw_api("get", "userAssetDribbletLog.html", True, data=params)

        if not result["succes"]:
            raise WithdrawException(result["msg"])
        return result
    
    def transfer_dust(self, **params):
        """{
            "totalServiceCharge":"0.02102542",
            "totalTransfered":"1.05127099",
            "transferResult":[
                {
                    "amount":"0.03000000",
                    "fromAsset":"ETH",
                    "operateTime":1563368549307,
                    "serviceChargeAmount":"0.00500000",
                    "tranId":2970932918,
                    "transferedAmount":"0.25000000"
                },
                {
                    "amount":"0.09000000",
                    "fromAsset":"LTC",
                    "operateTime":1563368549404,
                    "serviceChargeAmount":"0.01548000",
                    "tranId":2970932918,
                    "transferedAmount":"0.77400000"
                },
                {
                    "amount":"248.61878453",
                    "fromAsset":"TRX",
                    "operateTime":1563368549489,
                    "serviceChargeAmount":"0.00054542",
                    "tranId":2970932918,
                    "transferedAmount":"0.02727099"
                }
            ]
        }"""

        return self._request_margin_api("post", "asset/dust", True, data=params)

    def get_asset_dividend_history(self, **params):
        """{
            "rows":[
                {
                    "amount":"10.00000000",
                    "asset":"BHFT",
                    "divTime":1563189166000,
                    "enInfo":"BHFT distribution",
                    "tranId":2968885920
                },
                {
                    "amount":"10.00000000",
                    "asset":"BHFT",
                    "divTime":1563189165000,
                    "enInfo":"BHFT distribution",
                    "tranId":2968885920
                }
            ],
            "total":2
        }"""

        return self._request_margin_api("get", "asset/assetDividend", True, data=params)

    def get_trade_fee(self, **params):
        """{
            "tradeFee": [
            {
            "symbol": "ADABNB",
            "maker": 0.9000,
            "taker": 1.0000
            },
            {
            "symbol": "BNBBTC",
            "maker": 0.3000,
            "taker": 0.3000
            }
        ],
            "success": true
        }"""

        result = self._request_withdraw_api("get", "tradeFee.html", True, data=params)
        if not result["success"]:
            raise WithdrawException(result["msg"])
        return result
    
    def get_asset_details(self, **params):
        """{
            "success": true,
            "assetDetail": {
                "CTR": {
                    "minWithdrawAmount": "70.00000000", //min withdraw amount
                    "depositStatus": false,//deposit status (false if ALL of networks' are false)
                    "withdrawFee": 35, // withdraw fee
                    "withdrawStatus": true, //withdraw status (false if ALL of networks' are false)
                    "depositTip": "Delisted, Deposit Suspended" //reason
                },
                "SKY": {
                    "minWithdrawAmount": "0.02000000",
                    "depositStatus": true,
                    "withdrawFee": 0.01,
                    "withdrawStatus": true
                }   
            }
        }"""

        result = self._request_withdraw_api("get", "assetDetail.html", True, data=params)
        if not result["success"]:
            raise WithdrawException(result["msg"])
        return result

    def withdraw(self, **params):
        """{
            "msg": "success",
            "success": true,
            "id":"7213fea8e94b4a5593d507237e5a555b"
        }"""

        if "asset" in params and "name" not in params:
            params["name"] = params["asset"]
        
        result = self._request_withdraw_api("post", "withdraw.html", True, data=params)

        if not result["success"]:
            raise WithdrawException(result["msg"])
        return result

    def get_deposit_history(self, **params):
        """[
            {
                "amount":"0.00999800",
                "coin":"PAXG",
                "network":"ETH",
                "status":1,
                "address":"0x788cabe9236ce061e5a892e1a59395a81fc8d62c",
                "addressTag":"",
                "txId":"0xaad4654a3234aa6118af9b4b335f5ae81c360b2394721c019b5d1e75328b09f3",
                "insertTime":1599621997000,
                "transferType":0,
                "confirmTimes":"12/12"
            },
            {
                "amount":"0.50000000",
                "coin":"IOTA",
                "network":"IOTA",
                "status":1,
                "address":"SIZ9VLMHWATXKV99LH99CIGFJFUMLEHGWVZVNNZXRJJVWBPHYWPPBOSDORZ9EQSHCZAMPVAPGFYQAUUV9DROOXJLNW",
                "addressTag":"",
                "txId":"ESBFVQUTPIWQNJSPXFNHNYHSQNTGKRVKPRABQWTAXCDWOAKDKYWPTVG9BGXNVNKTLEJGESAVXIKIZ9999",
                "insertTime":1599620082000,
                "transferType":0,
                "confirmTimes":"1/1"
            }
        ]"""

        return self._request_withdraw_api("get", "depositHistory.html", True, data=params)

    def get_withdraw_history(self, **params):
        """{
            "withdrawList": [
                {
                    "id":"7213fea8e94b4a5593d507237e5a555b",
                    "withdrawOrderId": None,    
                    "amount": 0.99,
                    "transactionFee": 0.01,
                    "address": "0x6915f16f8791d0a1cc2bf47c13a6b2a92000504b",
                    "asset": "ETH",
                    "txId": "0xdf33b22bdb2b28b1f75ccd201a4a4m6e7g83jy5fc5d5a9d1340961598cfcb0a1",
                    "applyTime": 1508198532000,
                    "status": 4
                },
                {
                    "id":"7213fea8e94b4a5534ggsd237e5a555b",
                    "withdrawOrderId": "withdrawtest", 
                    "amount": 999.9999,
                    "transactionFee": 0.0001,
                    "address": "463tWEBn5XZJSxLU34r6g7h8jtxuNcDbjLSjkn3XAXHCbLrTTErJrBWYgHJQyrCwkNgYvyV3z8zctJLPCZy24jvb3NiTcTJ",
                    "addressTag": "342341222",
                    "txId": "b3c6219639c8ae3f9cf010cdc24fw7f7yt8j1e063f9b4bd1a05cb44c4b6e2509",
                    "asset": "XMR",
                    "applyTime": 1508198532000,
                    "status": 4
                }
            ],
            "success": true
        }"""

        return self._request_withdraw_api("get", "withdrawHistory.html", True, data=params)

    def get_deposit_address(self, **params):
        """{
            "address": "0x6915f16f8791d0a1cc2bf47c13a6b2a92000504b",
            "success": true,
            "addressTag": "1231212",
            "asset": "BNB"
        }"""

        return self._request_withdraw_api("get", "depositAddress.html", True, data=params)
    
    def stream_get_listen_key(self):
        result = self._post("userDataStream", False, data={})
        return result["listenKey"]
    
    def stream_keepalive(self, listenKey):
        """{}"""

        params = {
            "listenKey": listenKey
        }

        return self._put("userDataStream", False, data=params)
    
    def stream_close(self, listenKey):
        """{}"""

        params = {
            "listenKey": listenKey
        }
        
        return self._delete("userDataStream", False, data=params)