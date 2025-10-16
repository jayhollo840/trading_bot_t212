import broker
from broker import Broker, SEED_INITIAL_DELAY, SEED_QTY


def test_ensure_seed_handles_delayed_position(monkeypatch):
    """Broker waits for the seed position long enough before failing."""
    monkeypatch.setattr(Broker, "_load_metadata", lambda self: None)
    bkr = Broker()

    order_calls = []

    def fake_order(symbol, qty):
        order_calls.append((symbol, qty))
        return {"ticker": symbol, "quantity": qty}

    responses = [None] * 5 + [{"quantity": SEED_QTY, "currentPrice": "100.00"}]
    position_calls = []

    def fake_position(symbol):
        position_calls.append(symbol)
        if responses:
            return responses.pop(0)
        return {"quantity": SEED_QTY, "currentPrice": "100.00"}

    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(bkr, "_market_order", fake_order)
    monkeypatch.setattr(bkr, "_position_raw", fake_position)
    monkeypatch.setattr(broker.time, "sleep", fake_sleep)

    data = bkr._ensure_seed("ITMl_EQ")

    assert data["currentPrice"] == "100.00"
    assert order_calls == [("ITMl_EQ", SEED_QTY)]
    assert len(position_calls) == 6  # 5 misses + 1 success
    assert sleeps and sleeps[0] >= SEED_INITIAL_DELAY
    assert bkr.seed_active is True
