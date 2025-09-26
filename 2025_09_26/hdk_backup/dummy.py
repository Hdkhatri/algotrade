import importlib
import threading
import pandas as pd

from commonFunction import hd_strategy, parallel_ema_strategy, record_trade, save_open_position, wait_until_next_candle
from config import INSTRUMENTS_FILE, SYMBOL,CANDLE_DAYS as DAYS
import dynamic
from commonFunction import close_position_and_no_new_trade, delete_open_position, get_next_expiry_optimal_option, get_optimal_option, init_db, load_open_position
from kitefunction import get_historical_df, get_quotes, get_token_for_symbol, place_aggressive_limit_order, place_option_hybrid_order
from datetime import datetime

tradingsymbol = "NIFTY2582125100CE"
qty = 75
ordertype = "BUY"

signal = "BUY"
last_expiry = "2025-08-28"
price = 24426.0
nearest_price = 40

def next_value(config):
    while True:
        importlib.reload(dynamic)
        config = dynamic.configs[config['INTERVAL']]
        # Simulate some processing
        print(f"Processing with config: {config['INTERVAL']} | TRADE: {config['EXPIRY']} | nearest LTP: {config['NEAREST_LTP']}")
        threading.Event().wait(1)   

instruments_df = pd.read_csv(INSTRUMENTS_FILE)
# threads = []
# intravals = dynamic.configs.keys()
# for interval in intravals:
#     config = dynamic.configs[interval]
#     init_db()
#     #t = threading.Thread(target=place_option_hybrid_order, args=(tradingsymbol, qty, ordertype,config))
#     #t = threading.Thread(target=get_next_expiry_optimal_option, args=(signal, last_expiry, price, nearest_price,instruments_df, config))
#     #t = threading.Thread(target= get_optimal_option, args=(signal, price, config['NEAREST_LTP'],instruments_df, config))
#     #t = threading.Thread(target= next_value, args=(config,))
#     #t = threading.Thread(target= wait_until_next_candle, args=(config,))
#     t = threading.Thread(target= load_open_position, args=(config,))
#     #t = threading.Thread(target= delete_open_position, args=(tradingsymbol, config))
#     t.start()
#     threads.append(t)
# for t in threads:
#     t.join()

# position = 'sell'
ts = '2025-08-17 10:00:00'
# trade = load_open_position(dynamic.configs['5minute'])
# close_position_and_no_new_trade(trade, position, price, ts, dynamic.configs['5minute'])


# ===============================================================
# config = dynamic.configs['3minute_nearest']
# trade  = load_open_position(config)
# #save_open_position(trade,config)
# if trade:
#     print("Loaded trade:", trade)
#     trade.update({
#         "OptionBuyPrice": 20,
#         "SpotExit": 24940.0, 
#         "ExitTime": ts,
#         "PnL": 40 - 20,
#         "qty": qty,
#         "ExitReason": "TARGET_HIT"
#     })
#     symbol = 'NIFTY2590924800CE'
#     record_trade(trade, config)
#     delete_open_position(symbol, config, trade)
#     
# else:
#     print("No open trade found.")

config = dynamic.configs['30minute_HDSTRATEGY']
# place_aggressive_limit_order(tradingsymbol = "NIFTY2590925000CE", qty = 75, ordertype="SELL", config = config, timeout=10)

#init_db()
instrument_token = get_token_for_symbol(SYMBOL)
df = get_historical_df(instrument_token, config['INTERVAL'], DAYS)
# df = hd_strategy_new(df)
df = parallel_ema_strategy(df)
# latest = df.iloc[0]
# print(latest['date'])
# latest_time = pd.to_datetime(latest['date'])
# now = datetime.now()

# if latest_time.hour == now.hour and latest_time.minute == now.minute:
#     print("Latest date matches current hour and minute.")
# elif latest_time.hour == 9 and latest_time.minute == 15:
#     print("Latest date matches 9:15.")
# else:
#     print("Latest date does not match current hour and minute or 9:15.")
print(df.tail(50))

# df = df.head(81)
# # ✅ Decide which row to use for signals
# if df.iloc[-1]['buySignal'] or df.iloc[-1]['sellSignal']:
#     latest = df.iloc[-1]
# elif df.iloc[-2]['buySignal'] or df.iloc[-2]['sellSignal']:
#     latest = df.iloc[-2]
# else:
#     latest = df.iloc[-1]  # No signal in last 2 candles

# print(latest)
# if latest['buySignal']:
#     print("Buy signal detected.")
# elif latest['sellSignal']:
#     print("Sell signal detected.")
# else:
#     print("No signal detected.")



# current_ltp = get_quotes("NIFTY2592324300PE")
# print("Current LTP:", current_ltp)