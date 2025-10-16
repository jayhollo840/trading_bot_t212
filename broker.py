import time
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import API_BASE_URL, API_KEY, SYMBOL

SEED_QTY = 1.5
EPS = 1e-6
SEED_MAX_ATTEMPTS = 12
SEED_INITIAL_DELAY = 1.0
SEED_BACKOFF = 1.5
SEED_MAX_DELAY = 5.0


class Broker:
    def __init__(self):
        self.base_url = API_BASE_URL.rstrip("/")
        self.symbol = SYMBOL
        self.session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=5,
                backoff_factor=0.3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods={"GET", "POST", "DELETE"},
            )
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        auth = (API_KEY or "").strip()
        if auth and not auth.lower().startswith("basic "):
            auth = f"Basic {auth}"
        if auth:
            self.session.headers["Authorization"] = auth
        self.session.headers["Accept"] = "application/json"
        self.seed_active = False
        self.events = []
        self._last_position = None
        self._last_pos_time = 0.0
        self._load_metadata()

    def _req(self, method, path, *, json=None, allow_404=False):
        url = f"{self.base_url}{path if path.startswith('/') else '/' + path}"
        resp = self.session.request(method, url, json=json, timeout=10)
        if allow_404 and resp.status_code == 404:
            return resp
        resp.raise_for_status()
        return resp

    def _load_metadata(self):
        if self.events:
            return
        instruments = self._req("GET", "/equity/metadata/instruments").json()
        inst = next(
            (row for row in instruments if row.get("ticker") == self.symbol), None
        )
        if not inst:
            raise RuntimeError(f"Ticker {self.symbol} not found.")
        schedule_id = inst.get("workingScheduleId")
        exchanges = self._req("GET", "/equity/metadata/exchanges").json()
        schedule = next(
            (
                s
                for ex in exchanges
                for s in ex.get("workingSchedules", [])
                if s.get("id") == schedule_id
            ),
            None,
        )
        if not schedule:
            raise RuntimeError(f"Schedule {schedule_id} not found for {self.symbol}.")
        self.events = sorted(
            (datetime.fromisoformat(ev["date"].replace("Z", "+00:00")), ev["type"])
            for ev in schedule.get("timeEvents", [])
            if ev.get("date") and ev.get("type")
        )

    def clock(self):
        now = datetime.now(timezone.utc)
        is_open = False
        next_open = next_close = None
        for stamp, kind in self.events:
            if stamp <= now:
                if kind == "OPEN":
                    is_open = True
                elif kind == "CLOSE":
                    is_open = False
            else:
                if is_open and kind == "CLOSE" and not next_close:
                    next_close = stamp
                elif not is_open and kind == "OPEN" and not next_open:
                    next_open = stamp
                if next_open and next_close:
                    break
        return {
            "is_open": is_open,
            "seconds_to_open": (
                max(int((next_open - now).total_seconds()), 0) if next_open else 0
            ),
            "minutes_to_close": (
                max(int((next_close - now).total_seconds() // 60), 0)
                if next_close
                else 0
            ),
        }

    def _position_raw(self, symbol):
        resp = self._req(
            "POST", "/equity/portfolio/ticker", json={"ticker": symbol}, allow_404=True
        )
        data = None if resp.status_code == 404 else resp.json()
        self._last_position = data
        self._last_pos_time = time.time()
        return data

    def _market_order(self, symbol, signed_qty):
        return self._req(
            "POST",
            "/equity/orders/market",
            json={"ticker": symbol, "quantity": signed_qty, "extendedHours": False},
        ).json()

    def _ensure_seed(self, symbol):
        if not self.seed_active:
            self._market_order(symbol, SEED_QTY)
        self.seed_active = True
        wait_seconds = SEED_INITIAL_DELAY
        for _ in range(SEED_MAX_ATTEMPTS):
            time.sleep(wait_seconds)
            data = self._position_raw(symbol)
            if data:
                return data
            wait_seconds = min(wait_seconds * SEED_BACKOFF, SEED_MAX_DELAY)
        self.seed_active = False
        return None

    def get_latest_bar(self, symbol, timeframe="1m"):
        """Return a synthetic OHLC bar using the most recent position snapshot."""
        data = self._position_raw(symbol) or self._ensure_seed(symbol)
        if not data:
            raise RuntimeError(
                f"Unable to obtain position data for {symbol}. "
                "Increase SEED_QTY or verify the instrument code and minimum order size."
            )
        qty = float(data.get("quantity", 0.0))
        if qty >= SEED_QTY - EPS:
            self.seed_active = True
        price = float(data.get("currentPrice"))
        ts = datetime.now(timezone.utc).isoformat()
        return {
            "ts": ts,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 0.0,
        }

    def get_equity(self):
        return float(self._req("GET", "/equity/account/cash").json().get("total", 0.0))

    def position(self, symbol):
        data = (
            self._last_position
            if time.time() - self._last_pos_time < 0.6
            else self._position_raw(symbol)
        )
        qty = float((data or {}).get("quantity", 0.0))
        if not data or abs(qty) < EPS:
            self.seed_active = False
            return 0.0
        if qty >= SEED_QTY - EPS or self.seed_active or qty <= -SEED_QTY - EPS:
            self.seed_active = True
            return qty - SEED_QTY
        return qty

    def place_order(self, symbol, side, qty, stop_loss=None, take_profit=None):
        if qty <= 0:
            raise ValueError("Quantity must be positive.")
        signed_qty = qty if side.lower() == "buy" else -qty
        market = self._market_order(symbol, signed_qty)
        return {"market": market, "exits": []}

    def close_position(self, symbol):
        qty = self.position(symbol)
        if abs(qty) < EPS:
            return True
        self.place_order(symbol, "sell" if qty > 0 else "buy", abs(qty))
        return True

    def _drop_seed(self):
        if not self.seed_active:
            return
        data = self._position_raw(self.symbol)
        qty = 0.0 if not data else float(data.get("quantity", 0.0))
        if abs(qty - SEED_QTY) < 0.01:
            self._market_order(self.symbol, -SEED_QTY)
            time.sleep(1.05)
        self.seed_active = False
        self._last_position = None

    def close(self):
        try:
            self._drop_seed()
        finally:
            self.session.close()
