# Trading 212 Mean-Reversion Bot

Automated equities trading loop that connects to the Trading 212 REST API, watches the market clock, and runs a simple mean-reversion strategy. The bot warms up on session open, sizes entries based on configurable risk parameters, places market orders, and writes fills to `trades_log.csv` for later analysis.

## Features
- Session-aware loop that waits for market open and stops trading ahead of the close.
- SMA-based discount check to trigger long entries with configurable risk/reward.
- Robust `Broker` wrapper with retrying HTTP session, instrument metadata caching, and seed-position handling for price discovery.
- Trade logging to CSV and graceful shutdown that flattens any remaining position.
- Baseline pytest covering seed order backoff logic for deterministic testing.

## Project Layout
- `main.py` – orchestrates the trading loop, risk checks, and trade logging.
- `broker.py` – thin Trading 212 client with session retries, clock helpers, and order placement.
- `config.py` – centralizes environment-driven settings (API base URL, credentials, risk knobs).
- `api_references.py` – request/response documentation for the API surface.
- `tests/` – pytest suite (extend with additional scenarios as logic evolves).
- `requirements.txt` – pinned runtime dependencies.

## Prerequisites
- Python 3.11
- Trading 212 demo or live credentials with API access (supply via environment variables or a local `.env` file)

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration
Settings are read from environment variables in `config.py`. The most important are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_BASE_URL` | `https://demo.trading212.com/api/v0` | Trading 212 API host (switch to live URL when ready). |
| `DEMO_CREDS` | *(empty)* | Base64-encoded HTTP Basic credentials (`user:pass`). |
| `SYMBOL` | `ITMl_EQ` | Instrument ticker to trade. |
| `RISK_PCT` | `0.005` | Percentage of account equity risked per trade. |
| `LOSS_THRESHOLD_PCT` | `0.008` | Stop distance as a percentage of price. |
| `TP_R_MULT` | `2.0` | Reward multiplier relative to stop distance. |

Copy the variables into a `.env` file or export them in your shell before launching the bot:

```bash
export DEMO_CREDS="base64-user-pass"
export SYMBOL="TEST_TICKER"
python main.py
```

## Running the Bot
```bash
python main.py
```

Runtime logs stream to stdout. Fills are appended to `trades_log.csv` with timestamp, price, signal, quantity, stop, target, and a free-form note. The bot automatically flattens any open position on exit.

## Testing
Add new unit tests under `tests/` and run them with:

```bash
pytest
```

Mock external HTTP calls (for example using `monkeypatch`) to keep tests deterministic and avoid hitting the Trading 212 API.

## Operational Notes
- Keep credentials out of source control; `.env` is ignored by Git.
- If you integrate additional venues or instruments, extend `broker.py` with venue-specific metadata handling and document the change.
- Review `api_references.py` when adding endpoints to ensure payloads stay aligned with the provider documentation.
