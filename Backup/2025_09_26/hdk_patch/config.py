# config.py
SYMBOL = "NIFTY 50"
OPTION_SYMBOL = "NIFTY"
CANDLE_DAYS = 11
REQUIRED_CANDLES = 20
SEGMENT = "NFO-OPT"

ACCESS_TOKEN_FILE = "access_token.json"
TRADE_ACCESS_TOKEN_FILE = "trade_access_token.json"
INSTRUMENTS_FILE = "nifty_instruments.csv"

LOG_FILE = "live_trading.log"
DB_FILE = "Trading.db"

#SERVER = "Local"
SERVER = "GCP"  # PROD or TEST

USER = "HDK"