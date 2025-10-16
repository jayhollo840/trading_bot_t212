"""broker.py"""

import os


API_BASE_URL = os.getenv("API_BASE_URL", "https://demo.trading212.com/api/v0")
API_KEY = os.getenv("DEMO_CREDS", "")

SYMBOL = os.getenv("SYMBOL", "ITMl_EQ")
TIMEFRAME = "1m"
WARMUP_SECONDS = 60
NO_NEW_TRADES_MIN = 15
RISK_PCT = 0.005
TP_R_MULT = 2.0
FAST = 9
SLOW = 21
BUY_DISCOUNT_PCT = 0.006
LOSS_THRESHOLD_PCT = 0.008
LOSS_CONFIRM_POLLS = 3
