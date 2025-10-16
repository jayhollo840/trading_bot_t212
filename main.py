import csv
import math
import os
import time
from statistics import mean

from broker import Broker, MarketDataUnavailable, RateLimitError
from config import (
    API_BASE_URL,
    API_KEY,
    BUY_DISCOUNT_PCT,
    LOSS_CONFIRM_POLLS,
    LOSS_THRESHOLD_PCT,
    NO_NEW_TRADES_MIN,
    RISK_PCT,
    SLOW,
    SYMBOL,
    TIMEFRAME,
    TP_R_MULT,
    WARMUP_SECONDS,
)

POSITION_EPS = 1e-6
WINDOW = max(SLOW, 20)


def sleep_for_rate_limit(err: RateLimitError, context: str):
    wait_seconds = max(int((err.retry_after or 30)), 5)
    print(
        f"Rate limit while {context}; sleeping {wait_seconds}s before retrying."
    )
    time.sleep(wait_seconds)


def wait_for_open(bkr: Broker):
    while True:
        clk = bkr.clock()
        if clk.get("is_open"):
            print(f"Market open at {API_BASE_URL}, warming up for {WARMUP_SECONDS}s")
            break
        seconds_to_open = int(clk.get("seconds_to_open", 0))
        sleep_for = max(seconds_to_open, 15)
        print(f"Market closed, waiting {sleep_for}s until open")
        time.sleep(sleep_for)
    time.sleep(WARMUP_SECONDS)


def minutes_to_close(bkr: Broker) -> int:
    return int(bkr.clock().get("minutes_to_close", 0))


def sma(vals, n):
    return mean(vals[-n:])


def log_trade(row: dict):
    path = "trades_log.csv"
    file_exists = os.path.exists(path)
    with open(path, "a", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["ts", "price", "signal", "qty", "sl", "tp", "note"]
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def run():
    bkr = Broker()
    bars = []
    last_ts = None
    trade = None
    try:
        print(
            f"Starting bot for {SYMBOL} ({TIMEFRAME}) using API key present={bool(API_KEY)}"
        )
        wait_for_open(bkr)
        print("Warmup complete, entering trading loop")
        while True:
            minutes_left = minutes_to_close(bkr)
            try:
                current_qty = bkr.position(SYMBOL)
            except RateLimitError as exc:
                sleep_for_rate_limit(exc, "checking open position")
                continue
            if trade and abs(current_qty) <= POSITION_EPS:
                trade = None
            if not trade and minutes_left <= NO_NEW_TRADES_MIN:
                print("Market closing soon, stopping for the day.")
                break
            try:
                bar = bkr.get_latest_bar(SYMBOL, TIMEFRAME)
            except RateLimitError as exc:
                sleep_for_rate_limit(exc, "fetching latest bar")
                continue
            except MarketDataUnavailable as exc:
                print(f"Market data unavailable: {exc}")
                time.sleep(60)
                continue
            ts = bar.get("ts")
            if ts == last_ts:
                time.sleep(5)
                continue
            last_ts = ts
            price = float(bar["close"])
            parsed_bar = {
                "ts": ts,
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": price,
                "volume": float(bar.get("volume", 0.0)),
            }
            bars.append(parsed_bar)
            if len(bars) > 500:
                bars = bars[-500:]

            if not trade and abs(current_qty) > POSITION_EPS:
                time.sleep(60)
                continue

            if trade:
                reason = None
                if minutes_left <= NO_NEW_TRADES_MIN:
                    reason = "session_close"
                else:
                    if price <= trade["stop"]:
                        trade["loss_polls"] += 1
                    else:
                        trade["loss_polls"] = 0
                    if price >= trade["target"]:
                        reason = "take_profit"
                    elif trade["loss_polls"] >= LOSS_CONFIRM_POLLS:
                        reason = "soft_stop"
                if reason:
                    exit_qty = trade["qty"]
                    try:
                        exit_order = bkr.place_order(SYMBOL, "sell", exit_qty)
                    except RateLimitError as exc:
                        sleep_for_rate_limit(exc, "closing position")
                        continue
                    order_note = exit_order.get("market", {}).get("id") or reason
                    print(f"{ts} | Exit {reason} qty={exit_qty} price={price:.2f}")
                    log_trade(
                        {
                            "ts": ts,
                            "price": price,
                            "signal": "sell",
                            "qty": -exit_qty,
                            "sl": trade["stop"],
                            "tp": trade["target"],
                            "note": order_note,
                        }
                    )
                    trade = None
                    time.sleep(60)
                    continue
                time.sleep(60)
                continue

            if minutes_left <= NO_NEW_TRADES_MIN:
                time.sleep(60)
                continue

            if len(bars) < WINDOW:
                time.sleep(60)
                continue

            avg_price = sma([b["close"] for b in bars], WINDOW)
            if price > avg_price * (1 - BUY_DISCOUNT_PCT):
                time.sleep(60)
                continue

            risk_per_share = price * LOSS_THRESHOLD_PCT
            if risk_per_share <= 0:
                time.sleep(60)
                continue

            try:
                equity = bkr.get_equity()
            except RateLimitError as exc:
                sleep_for_rate_limit(exc, "fetching account equity")
                continue
            qty = math.floor((equity * RISK_PCT) / risk_per_share)
            if qty <= 0:
                time.sleep(60)
                continue

            target = price * (1 + LOSS_THRESHOLD_PCT * TP_R_MULT)
            stop = price * (1 - LOSS_THRESHOLD_PCT)
            try:
                order_result = bkr.place_order(SYMBOL, "buy", qty)
            except RateLimitError as exc:
                sleep_for_rate_limit(exc, "placing entry order")
                continue
            market_order = order_result.get("market", {})
            order_note = market_order.get("id") or market_order.get("status", "")
            print(
                f"{ts} | Enter buy qty={qty} price={price:.2f} "
                f"target={target:.2f} stop={stop:.2f}"
            )
            log_trade(
                {
                    "ts": ts,
                    "price": price,
                    "signal": "buy",
                    "qty": qty,
                    "sl": stop,
                    "tp": target,
                    "note": f"entry {order_note}".strip(),
                }
            )
            trade = {
                "qty": qty,
                "entry": price,
                "stop": stop,
                "target": target,
                "loss_polls": 0,
            }
            time.sleep(60)
    finally:
        try:
            try:
                remaining = bkr.position(SYMBOL)
            except RateLimitError as exc:
                sleep_for_rate_limit(exc, "checking position during shutdown")
                try:
                    remaining = bkr.position(SYMBOL)
                except RateLimitError:
                    print(
                        "Rate limit persisted while checking for open positions. "
                        "Verify account state manually."
                    )
                    remaining = 0.0
            if abs(remaining) > POSITION_EPS:
                side = "sell" if remaining > 0 else "buy"
                abs_qty = abs(remaining)
                print("Flattening position on shutdown")
                attempts = 0
                while attempts < 3:
                    try:
                        order_response = bkr.place_order(SYMBOL, side, abs_qty)
                        log_trade(
                            {
                                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "price": 0,
                                "signal": "flatten",
                                "qty": -abs_qty if side == "sell" else abs_qty,
                                "sl": "",
                                "tp": "",
                                "note": order_response.get("market", {}).get(
                                    "id", "shutdown"
                                ),
                            }
                        )
                        break
                    except RateLimitError as exc:
                        attempts += 1
                        sleep_for_rate_limit(
                            exc, "flattening position during shutdown"
                        )
                else:
                    print(
                        "Unable to flatten position after repeated rate limits. "
                        "Please close the position manually."
                    )
        finally:
            bkr.close()


if __name__ == "__main__":
    run()
