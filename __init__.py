"""
An unofficial Python wrapper for the Binance exchange API

.. moduleauthor:: Jasper Delahaije

"""
from .client import Client

from .exceptions import APIException
from .exceptions import RequestException
from .exceptions import OrderException
from .exceptions import OrderMinAmountException
from .exceptions import OrderMinTotalException
from .exceptions import OrderUnknownSymbolException
from .exceptions import OrderInactiveSymbolException
from .exceptions import WithdrawException

from .helpers import date_to_milliseconds
from .helpers import interval_to_milliseconds

from .functions import get_all_symbols
from .functions import get_best_symbols
from .functions import get_all_asset_balance
from .functions import updateCandle
from .functions import updateAllCandles
from .functions import updateEMA
from .functions import updateAllEMA
from .functions import updateMA
from .functions import updateAllMA
from .functions import get_all_intervals
