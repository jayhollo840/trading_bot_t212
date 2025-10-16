# api_references.py
#!/usr/bin/env python3
"""
API reference data structures.
"""
import os
from dataclasses import dataclass
from typing import List, Optional


# API URLs
LIVE_MARKET_BASE_URL = "https://live.trading212.com/"
DEMO_MARKET_BASE_URL = "https://demo.trading212.com/"
CASH_BALANCE_URL = "equity/account/cash"
MARKET_ORDER_URL = "equity/orders/market"
GET_ORDER_BY_ID_URL = "equity/orders/{order_id}"
TICKER_POSITIONS_URL = "equity/portfolio/{ticker}"
INSTRUMENT_LIST_URL = "equity/metadata/instruments"
HISTORICAL_ORDERS_URL = "equity/history/orders"
CREDENTIALS = os.environ.get("DEMO_CREDS")
AUTH_HEADERS = {"Authorization": f"Basic {CREDENTIALS}"} if CREDENTIALS else {}

# Rate limits (per API docs as of 2024-06-10)
CASH_RATE_LIM = 2.0  # seconds between calls to cash endpoints
PLACE_ORDER_LIM = 1.2  # seconds between calls to order endpoints
GET_ORDER_LIM = 1.0  # seconds between calls to order endpoints
PORTFOLIO_RATE_LIMIT = 1.0  # seconds between calls to portfolio endpoints
INSTRUMENT_RATE_LIMIT = 50.0  # seconds between calls to instrument endpoints
HISTORICAL_RATE_LIMIT = 10.0  # seconds between calls to historical endpoints


# Request application/json bodies
@dataclass
class PlaceMarketOrder:
    """Parameters for submitting a market order."""

    extendedhours: bool
    quantity: float  # -ve for sell, +ve for buy
    ticker: str

    def to_payload(self) -> dict[str, float | bool | str]:
        """Return a JSON payload matching the Trading 212 schema."""
        return {
            "extendedHours": self.extendedhours,
            "quantity": self.quantity,
            "ticker": self.ticker,
        }


@dataclass
class GetOrderHistory:
    """Parameters for fetching historical orders."""

    cursor: Optional[int]
    ticker: str
    limit: int


# Resposes from API endpoints
@dataclass
class ResponseHeaders:
    """HTTP rate limit counters for the most recent API call."""

    rate_limit_limit: int
    rate_limit_period: int
    rate_limit_remaining: int
    rate_limit_reset: int
    rate_limit_used: int


@dataclass
class CashBalance:
    """Breakdown of available, invested, and pending cash amounts."""

    blocked: float
    free: float
    invested: float
    piecash: float
    ppl: float
    result: float
    total: float


# pylint: disable=too-many-instance-attributes
@dataclass
class MarketOrder:
    """Details about a submitted market order and its execution progress."""

    creationtime: str
    filledqty: float
    filledvalue: float
    id: int
    limitprice: float
    quantity: float
    status: str
    stopprice: float
    strategy: str
    ticker: str
    type: str
    value: float


@dataclass
class GetOrderById:
    """Expanded order details returned when fetching a specific order."""

    creationtime: str
    extendedhours: bool
    filledqty: float
    filledvalue: float
    id: int
    limitprice: float
    quantity: float
    status: str
    stopprice: float
    strategy: str
    ticker: str
    type: str
    value: float


@dataclass
class TickerPosition:
    """Current holdings for a specific instrument in the portfolio."""

    avgprice: float
    currentprice: float
    frontend: str
    fxppl: float
    initialfilldate: str
    maxbuy: float
    maxsell: float
    piequantity: float
    ppl: float
    quantity: float
    ticker: str


@dataclass
class InstrumentList:
    """Metadata describing an individual tradable instrument."""

    addedon: str
    currencycode: str
    isin: str
    name: str
    shortname: str
    ticker: str
    type: str
    workingscheduleid: int


@dataclass
class Tax:
    """Tax component assessed on a filled order."""

    fillid: str
    name: str
    quantity: float
    timecharged: str


@dataclass
class Item:
    """Execution record capturing an individual historical order fill."""

    datecreated: str
    dateexecuted: str
    datemodified: str
    executor: str
    extendedhours: bool
    fillcost: float
    fillid: int
    fillprice: float
    fillresult: float
    filltype: str
    filledquantity: float
    filledvalue: float
    id: int
    limitprice: float
    orderedquantity: float
    orderedvalue: float
    parentorder: int
    status: str
    stopprice: float
    taxes: List[Tax]
    ticker: str
    timevalidity: str
    type: str


@dataclass
class HistoricalOrders:
    """Paginated collection of historical order records."""

    items: List[Item]
    nextpagepath: Optional[str] = None
