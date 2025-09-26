import time
import datetime
from datetime import timedelta
import numpy as np
import pandas as pd
import sqlite3
import logging
from kitefunction import  place_option_hybrid_order, get_avgprice_from_positions, get_token_for_symbol, get_quotes, get_profile
from telegrambot import send_telegram_message
from config import  DB_FILE,SYMBOL,SEGMENT, CANDLE_DAYS as DAYS, REQUIRED_CANDLES, LOG_FILE,INSTRUMENTS_FILE, OPTION_SYMBOL
import os

# pd.set_option('future.no_silent_downcasting', True)

logging.basicConfig(
    filename=LOG_FILE,
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
instrument_token = get_token_for_symbol(SYMBOL)

if instrument_token is None:
    logging.error(f"❌ Instrument token for {SYMBOL} not found. Exiting.")
    exit(1)
logging.info(f"ℹ️ Instrument token for {SYMBOL}: {instrument_token} at current time {current_time}")


def log_instruments_file_mod_time(filename):
    
    try:
        mod_time = time.ctime(os.path.getmtime(filename))
        print(f"ℹ️ {filename} last modified: {mod_time}")
        logging.info(f"ℹ️ {filename} last modified: {mod_time}")
    except Exception as e:
        print(f"❌ Failed to get modification time of {filename}: {e}")
        logging.error(f"❌ Failed to get modification time of {filename}: {e}")


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS completed_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal TEXT,
            spot_entry REAL,
            option_symbol TEXT,
            strike INTEGER,
            expiry TEXT,
            option_sell_price REAL,
            entry_time TEXT,
            spot_exit REAL,
            option_buy_price REAL,
            exit_time TEXT,
            pnl REAL,
            qty INTEGER,
            interval TEXT,               
            real_trade TEXT,            
            entry_reason TEXT,           
            exit_reason TEXT,
            expiry_type TEXT,
            strategy TEXT            
        )
    """)
  
    c.execute("""
        CREATE TABLE IF NOT EXISTS open_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal TEXT,
            spot_entry REAL,
            option_symbol TEXT,
            strike INTEGER,
            expiry TEXT,
            option_sell_price REAL,
            entry_time TEXT,
            qty INTEGER,
            interval TEXT,               
            real_trade TEXT,             
            entry_reason TEXT,
            expiry_type TEXT,
            strategy TEXT            
        )
    """)
    conn.commit()
    conn.close()

def generate_godEma_signals(df, len1=8, len2=20):
    df['ema1'] = df['close'].ewm(span=len1, adjust=False).mean()
    df['ema2'] = df['close'].ewm(span=len2, adjust=False).mean()
    df['crossover'] = (df['ema1'] > df['ema2']) & (df['ema1'].shift(1) <= df['ema2'].shift(1))
    df['crossunder'] = (df['ema1'] < df['ema2']) & (df['ema1'].shift(1) >= df['ema2'].shift(1))
    trend = []
    current_trend = 0
    for i in range(len(df)):
        if df['crossover'].iloc[i]:
            current_trend = 1
        elif df['crossunder'].iloc[i]:
            current_trend = -1
        trend.append(current_trend)
    df['trend'] = trend
    df['twoAbove'] = (df['close'] > df['ema1']) & (df['close'] > df['ema2']) & \
                     (df['close'].shift(1) > df['ema1'].shift(1)) & (df['close'].shift(1) > df['ema2'].shift(1))
    df['twoBelow'] = (df['close'] < df['ema1']) & (df['close'] < df['ema2']) & \
                     (df['close'].shift(1) < df['ema1'].shift(1)) & (df['close'].shift(1) < df['ema2'].shift(1))
    buy_signals = []
    sell_signals = []
    buy_fired = False
    sell_fired = False
    prev_trend = 0
    for i in range(len(df)):
        curr_trend = df['trend'][i]
        new_cross = curr_trend != prev_trend
        if new_cross:
            buy_fired = False
            sell_fired = False
        buy = curr_trend == 1 and df['twoAbove'][i] and not buy_fired
        sell = curr_trend == -1 and df['twoBelow'][i] and not sell_fired
        buy_signals.append(buy)
        sell_signals.append(sell)
        if buy:
            buy_fired = True
        if sell:
            sell_fired = True
        prev_trend = curr_trend
    df['buySignal'] = buy_signals
    df['sellSignal'] = sell_signals
    return df

def wait_until_next_candle(config):
    now = datetime.datetime.now()
    gap = int(config['INTERVAL'].replace("minute", ""))
    start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    minutes_since_start = (now - start_time).seconds // 60
    wait_min = gap - (minutes_since_start % gap)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    next_candle_time = now + timedelta(minutes=wait_min)
    if next_candle_time > end_time:
        wait_sec = (end_time - now).total_seconds()
        print(f"⏳{config['INTERVAL']} Next candle would be after market close. Waiting only until {end_time.strftime('%H:%M:%S')}")
        logging.info(f"⏳{config['INTERVAL']} Next candle would be after market close. Waiting only until {end_time.strftime('%H:%M:%S')}")
    else:
        wait_sec = wait_min * 60 - now.second + 2
        next_candle_time = now + timedelta(seconds=wait_sec)
        print(f"⏳{config['INTERVAL']} Waiting {max(2, int(wait_sec))} seconds until next candle at {next_candle_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"⏳{config['INTERVAL']} Waiting {max(2, int(wait_sec))} seconds until next candle at {next_candle_time.strftime('%Y-%m-%d %H:%M:%S')}")
    time.sleep(max(2, int(wait_sec)))

def get_optimal_option(signal, spot, nearest_price, instruments_df, config):
    
    if config['EXPIRY'] == "NEXT_WEEK":
        days = 7
    elif config['EXPIRY'] == "NEXT_TO_NEXT_WEEK":
        days = 14
    strike = int(round(spot / 100.0) * 100)
    print(f"Signal: {signal}, Spot: {spot}, Nearest 100 Strike: {strike}")
    df = instruments_df.copy()
    best_option = None
    best_ltp_diff = float('inf')
    while True:
        if signal == "BUY":
            opt_type = "PE"
            strike -= 100
        else:
            opt_type = "CE"
            strike += 100
        df_filtered = df[
            (df['name'] == OPTION_SYMBOL) &
            (df['segment'] == SEGMENT) &
            (df['strike'] == strike) &
            (df['tradingsymbol'].str.endswith(opt_type))
        ].copy()
        if df_filtered.empty:
            print(f"⚠️ No options found for strike {strike}{opt_type}")
            break
        df_filtered['expiry'] = pd.to_datetime(df_filtered['expiry'])
        today = pd.Timestamp.today().normalize()
        
        if config['EXPIRY'] == "LAST":
            if today.day <= 15:
                month_ref = today
            else:
                month_ref = (today + pd.DateOffset(months=1)).replace(day=1)
            next_month = month_ref.replace(day=28) + timedelta(days=4)
            last_day_of_month = next_month - timedelta(days=next_month.day)
            last_tuesday = last_day_of_month - timedelta(days=(last_day_of_month.weekday() - 1) % 7)
            target_expiry = last_tuesday
        else:
            days_until_thursday = (3 - today.weekday() + 7) % 7
            this_week_thursday = today + timedelta(days=days_until_thursday)
            target_expiry = this_week_thursday + timedelta(days=days)

        week_start = target_expiry - timedelta(days=target_expiry.weekday())
        week_end = week_start + timedelta(days=6)
        target_options = df_filtered[
            (df_filtered['expiry'] >= week_start) & (df_filtered['expiry'] <= week_end)
        ].sort_values('expiry')
        if target_options.empty:
            print(f"❌ No options found in week {week_start.date()} to {week_end.date()} for strike {strike}{opt_type}")
            break
        opt = target_options.iloc[0]
        opt_symbol = opt['tradingsymbol']
        expiry = opt['expiry'].strftime('%Y-%m-%d')
        ltp = get_quotes(opt_symbol) or 0.0
        diff = abs(ltp - nearest_price)
        if diff < best_ltp_diff:
            best_ltp_diff = diff
            best_option = (opt_symbol, strike, expiry, ltp)
        else:
            break
    
    if best_option:
        print(f"✅{config['INTERVAL']} | {config['EXPIRY']}| Best option found: {best_option}")
        logging.info(f"{config['INTERVAL']} | Best option found: {best_option}")
        return best_option
    else:
        print(f"❌{config['INTERVAL']} | No suitable option found for signal {signal}")
        logging.info(f"{config['INTERVAL']} | No suitable option found for signal {signal}")
        return None, None, None, None

def save_open_position(trade, config):
    try:
        logging.info(f"Saving open position: {trade['OptionSymbol']} in {config['INTERVAL']} interval")
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        sql = """
            INSERT INTO open_trades (signal, spot_entry, option_symbol, strike, expiry, option_sell_price, entry_time, qty, interval, real_trade, entry_reason, expiry_type, strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            trade["Signal"], trade["SpotEntry"], trade['OptionSymbol'], trade["Strike"],
            trade["Expiry"], trade["OptionSellPrice"], trade["EntryTime"], trade["qty"],
            trade.get("Interval", config['INTERVAL']), trade.get("RealTrade", config['TRADE'])
            ,trade.get("EntryReason","MANUAL_ENTRY"), trade.get("ExpiryType",config['EXPIRY']), trade.get("Strategy",config['STRATEGY'])
        )
        # print("Executing SQL:", sql, "\nWith parameters:", params)
        c.execute(sql, params)
        conn.commit()
        conn.close()
        logging.info(f"✅ Open position saved successfully: {trade['OptionSymbol']} in {config['INTERVAL']} interval")
    except Exception as e:
        print(f"❌ Error saving open position: {e}")
        logging.error(f"{config['INTERVAL']} | Error saving open position: {e}")

def delete_open_position(symbol, config, trade):
    try:
        logging.info(f"Deleting open position for {symbol} in {config['INTERVAL']} interval")
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        sql = "DELETE FROM open_trades WHERE option_symbol = ? and interval = ? and expiry_type = ? and strategy = ?"
        params = (symbol, config['INTERVAL'], trade.get("ExpiryType",config['EXPIRY']), trade.get("Strategy",config['STRATEGY']))
        # print("Executing SQL:", sql, "\nWith parameters:", params)
        c.execute(sql, params)
        conn.commit()
        conn.close()
        logging.info(f"✅ Open position for {symbol} deleted successfully in {config['INTERVAL']} interval")
    except Exception as e:
        print(f"❌ Error deleting open position for {symbol}: {e}")
        logging.error(f"{config['INTERVAL']} | Error deleting open position for {symbol}: {e}")

def load_open_position(config):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    sql = """
        SELECT signal, spot_entry, option_symbol, strike, expiry, 
               option_sell_price, entry_time, qty, interval, real_trade, entry_reason, expiry_type, strategy
        FROM open_trades where interval = ? and expiry_type = ? and strategy = ?
        ORDER BY id DESC LIMIT 1
    """
    params = (config['INTERVAL'], config['EXPIRY'], config['STRATEGY'])
    # print("Executing SQL:", sql, "\nWith parameters:", params)
    c.execute(sql, params)
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    position_data = {
        "Signal": row[0],
        "SpotEntry": row[1],
        "OptionSymbol": row[2],
        "Strike": row[3],
        "Expiry": row[4],
        "OptionSellPrice": row[5],
        "EntryTime": row[6],
        "qty": row[7],
        "Interval": row[8],
        "RealTrade": row[9],
        "EntryReason": row[10],
        "ExpiryType": row[11],
        "Strategy": row[12]
    }
    avg_price, broker_qty = get_avgprice_from_positions(position_data["OptionSymbol"])
    if broker_qty >= position_data["qty"]:
        print(f"✅ Broker position matches for Open Position or exceeds DB qty: {broker_qty} for {position_data['OptionSymbol']}")
        logging.info(f"✅ Broker position matches for Open Position or exceeds DB qty: {broker_qty} for {position_data['OptionSymbol']}")
    else:
        logging.warning(f"❌ Broker qty {broker_qty} for {position_data['OptionSymbol']} is less than DB qty {position_data['qty']} — treating as closed.")
        position_data["qty"] = 0
    print(f"✅{config['INTERVAL']} | Loaded open position from DB: {position_data}")
    return position_data

def record_trade(trade, config):
    print(f"✅ Recording trade: {trade}")
    logging.info(f"✅ Recording trade: {trade}")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    sql = """
        INSERT INTO completed_trades (signal, spot_entry, option_symbol, strike, expiry, option_sell_price,
        entry_time, spot_exit, option_buy_price, exit_time, pnl, qty, interval, real_trade, entry_reason, exit_reason, expiry_type, strategy)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        trade["Signal"], trade["SpotEntry"], trade['OptionSymbol'], trade["Strike"],
        trade["Expiry"], trade["OptionSellPrice"], trade["EntryTime"],
        trade["SpotExit"], trade["OptionBuyPrice"], trade["ExitTime"], trade["PnL"], trade["qty"],
        trade.get("Interval", config['INTERVAL']), trade.get("RealTrade", config['TRADE']),
        trade.get("EntryReason","MANUAL_ENTRY"), trade.get("ExitReason","MANUAL_EXIT"), trade.get("ExpiryType",config['EXPIRY']), trade.get("Strategy",config['STRATEGY'])
    )
    # print("Executing SQL:", sql, "\nWith parameters:", params)
    c.execute(sql, params)
    conn.commit()
    conn.close()
    print(f"📊 Trade recorded in DB.")
    logging.info(f"📊 Trade recorded in DB.")

def get_next_expiry_optimal_option(signal, last_expiry, price, nearest_price, instruments_df, config):
    
    try:
        df = instruments_df.copy()
        base_strike = int(round(price / 100.0) * 100)
        opt_type = "PE" if signal == "BUY" else "CE"
        today = pd.Timestamp.today().normalize()
        last_expiry_date = pd.to_datetime(last_expiry)
        if signal == "BUY":
            strike = base_strike - 100
            strike_adjustment = -100
        else:
            strike = base_strike + 100
            strike_adjustment = 100
        best_option = None
        best_ltp_diff = float('inf')
        previous_strike = None
        previous_ltp = None
        previous_symbol = None
        while True:
            df_filtered = df[
                (df['name'] == OPTION_SYMBOL) &
                (df['segment'] == SEGMENT) &
                (df['strike'] == strike) &
                (df['tradingsymbol'].str.endswith(opt_type))
            ].copy()
            if df_filtered.empty:
                break
            df_filtered['expiry'] = pd.to_datetime(df_filtered['expiry'])
            df_next_expiry = df_filtered[df_filtered['expiry'] > last_expiry_date].copy()
            if df_next_expiry.empty:
                break
            df_next_expiry = df_next_expiry.sort_values('expiry')
            next_expiry = df_next_expiry.iloc[0]['expiry']
            if config['EXPIRY'] == "LAST":
                if today.day <= 15:
                    month_str = today.strftime('%b').upper()
                else:
                    next_month = (today + pd.DateOffset(months=1))
                    month_str = next_month.strftime('%b').upper()
                df_same_expiry = df_next_expiry[df_next_expiry['tradingsymbol'].str.contains(month_str)].copy()
                if df_same_expiry.empty:
                    break
            else:
                df_same_expiry = df_next_expiry[df_next_expiry['expiry'] == next_expiry].copy()
            if df_same_expiry.empty:
                break
            option = df_same_expiry.iloc[0]
            opt_symbol = option['tradingsymbol']
            ltp = get_quotes(opt_symbol) or 0.0
            if ltp == 0.0:
                strike += strike_adjustment
                continue
            if ltp > nearest_price:
                previous_strike = strike
                previous_ltp = ltp
                previous_symbol = opt_symbol
                strike += strike_adjustment
                continue
            if previous_strike is not None and previous_ltp is not None:
                prev_diff = abs(previous_ltp - nearest_price)
                curr_diff = abs(ltp - nearest_price)
                if prev_diff <= curr_diff:
                    best_strike = previous_strike
                    best_ltp = previous_ltp
                    best_symbol = previous_symbol
                else:
                    best_strike = strike
                    best_ltp = ltp
                    best_symbol = opt_symbol
            else:
                best_strike = strike
                best_ltp = ltp
                best_symbol = opt_symbol
            best_expiry = next_expiry.strftime('%Y-%m-%d')
            print(f"✅ Found option: {best_symbol} | Strike: {best_strike} | Expiry: {best_expiry} | LTP: {best_ltp}")
            return best_symbol, best_strike, best_expiry, best_ltp
        print(f"❌ No suitable option found for signal {signal} after {last_expiry}")
        return None, None, None, None
    except Exception as e:
        print(f"❌ Error in get_next_expiry_optimal_option: {e}")
        logging.error(f"Error in get_next_expiry_optimal_option: {e}")
        return None, None, None, None

def is_market_open():
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return False
    return datetime.time(9, 15) <= now.time() <= datetime.time(15, 30)

def will_market_open_within_minutes(minutes=60):
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        days_until_monday = 7 - now.weekday()
        next_monday = now + datetime.timedelta(days=days_until_monday)
        market_open_time = next_monday.replace(hour=9, minute=15, second=0, microsecond=0)
    else:
        market_open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
        if now.time() >= datetime.time(15, 30):
            market_open_time = market_open_time + datetime.timedelta(days=1)
            if market_open_time.weekday() >= 5:
                days_until_monday = 7 - market_open_time.weekday()
                market_open_time = market_open_time + datetime.timedelta(days=days_until_monday)
        elif now.time() < datetime.time(9, 15):
            pass
        else:
            return True
    time_diff = market_open_time - now
    minutes_until_open = time_diff.total_seconds() / 60
    return minutes_until_open <= minutes

def close_position_and_no_new_trade(trade, position, close, ts, config):
    now = datetime.datetime.now()
    trade.update({
        "SpotExit": close,
        "ExitTime": ts,
        "OptionBuyPrice": get_quotes(trade['OptionSymbol']),
    })
    print(f"📥 HDK GCP  {config['INTERVAL']} Exiting BUY: Buying back {trade['OptionSymbol']} | Qty: {trade['qty']}")
    logging.info(f"📥 Exiting BUY: Buying back {trade['OptionSymbol']} | Qty: {trade['qty']}")
    order_id, avg_price, qty = place_option_hybrid_order(trade['OptionSymbol'], trade["qty"], "BUY", config)
    logging.info(f"📥 Exiting BUY: Buying back {trade['OptionSymbol']} | Qty: {trade['qty']}")
    if avg_price is None:
        avg_price = get_quotes(trade['OptionSymbol'])
        qty = config['QTY']
    trade.update({
        "OptionBuyPrice": avg_price,
        "ExitTime": ts,
        "PnL": trade["OptionSellPrice"] - avg_price,
        "qty": qty,
        "ExitReason": "INTRADAY_EXIT",

    })
    logging.info(f" trade : {trade} and  config : {config}")
    record_trade(trade, config)
    delete_open_position(trade['OptionSymbol'], config, trade)
    send_telegram_message(f"⏰HDK GCP  TRADE close {position} \n{trade['OptionSymbol']} @ ₹{trade['OptionBuyPrice']:.2f}")
    return {}, None

def who_tried():
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    profile = get_profile()
    if profile is None:
        print("❌ Profile not found. Exiting.")
        logging.error("❌ Profile not found. Exiting.")
        send_telegram_message("❌ Profile not found. Exiting.")
        return
    else:
        print(f"ℹ️ Profile: {profile} | Current Time: {current_time}")
        logging.info(f"{get_profile()} tried to execute program at | Current Time: {current_time}")
        send_telegram_message(f"ℹ️ {get_profile()} for  tried to execute program at | Current Time: {current_time}\n")




def _parse_interval_to_minutes(interval_str: str) -> int:
    """
    Accepts common formats like: "1", "3", "5", "15", "30", "60",
    or "1minute","5min","15m","1h","60min", etc. Returns minutes as int.
    """
    s = str(interval_str).strip().lower()
    if s.endswith(("minute", "minutes")):
        s = s.split("minute")[0]
    elif s.endswith(("min", "m")):
        s = s[:-1]
    elif s.endswith(("hour", "hours", "h")):
        # e.g. "1h"
        num = int(''.join(ch for ch in s if ch.isdigit()))
        return num * 60
    # default: numeric minutes
    num = int(''.join(ch for ch in s if ch.isdigit()))
    return max(1, num)

def get_next_candle_time(interval_str: str, from_dt=None):
    # """
    # Given INTERVAL (e.g., "5", "5min", "15m", "1h"), return the datetime
    # when the next candle should start (rounded up), using 9:15 as the reference start time.
    # """
    # # Align all intervals to start from 9:15 (first candle), e.g. 9:15, 9:30, 9:45, ...
    # minutes = _parse_interval_to_minutes(interval_str)
    # if from_dt is None:
    #     from_dt = datetime.datetime.now()
    # base = from_dt.replace(hour=9, minute=15, second=0, microsecond=0)
    # if from_dt < base:
    #     return base
    # # Calculate minutes since 9:15
    # delta = from_dt - base
    # passed_blocks = int(delta.total_seconds() // 60 // minutes)
    # next_candle = base + timedelta(minutes=(passed_blocks + 1) * minutes)
    # # Don't go past 15:15
    # market_end = from_dt.replace(hour=15, minute=30, second=0, microsecond=0)
    # if next_candle > market_end:
    #     next_candle = market_end
    # return next_candle
    import math
    if from_dt is None:
        from_dt = datetime.datetime.now()
    minutes = _parse_interval_to_minutes(interval_str)
    # Round up to the next interval boundary
    total_minutes = from_dt.hour * 60 + from_dt.minute
    next_blocks = math.floor(total_minutes / minutes) + 1
    next_total_minutes = next_blocks * minutes
    next_hour = (next_total_minutes // 60) % 24
    next_minute = next_total_minutes % 60
    next_dt = from_dt.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
    # If rounding produced a time in the past (possible at midnight boundary), add a day
    if next_dt <= from_dt:
        next_dt = next_dt + datetime.timedelta(minutes=minutes)
    return next_dt

def convertIntoHeikinashi(df):
    ha_df = df.copy()
    ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = [df['open'].iloc[0]]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i-1] + ha_close.iloc[i-1]) / 2)
    ha_high = pd.DataFrame({'high': df['high'], 'ha_open': ha_open, 'ha_close': ha_close}).max(axis=1)
    ha_low = pd.DataFrame({'low': df['low'], 'ha_open': ha_open, 'ha_close': ha_close}).min(axis=1)
    ha_df['open'] = ha_open
    ha_df['close'] = ha_close
    ha_df['high'] = ha_high
    ha_df['low'] = ha_low
    return ha_df



def hd_strategy(df: pd.DataFrame, maLength: int = 50) -> pd.DataFrame:
    """
    Python version of HdStrategy1.2 from Pine Script.
    Input: DataFrame with ['date','open','high','low','close','volume']
    Output: DataFrame with ['trend','buySignal','sellSignal']
    """
    # print(df.tail(5))
    # === Moving Average ===
    df["sma"] = df["close"].rolling(maLength).mean()

    # === Condition ===
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)

    df["condition"] = (prev_high > df["high"]) & (prev_low < df["low"])
    df["isUptrend"] = df["close"] > df["sma"]
    df["isDowntrend"] = df["close"] < df["sma"]

    # === Buy & Sell Levels (like Pine's var persistence with ffill) ===
    df["buyat"] = np.where(df["condition"], prev_high, np.nan)
    df["sellat"] = np.where(df["condition"], prev_low, np.nan)
    df["buyat"] = df["buyat"].ffill()
    df["sellat"] = df["sellat"].ffill()

    # === Raw signals (crossover / crossunder with persistence levels) ===
    df["raw_buy_signal"] = (df["close"] > df["buyat"]) & (df["close"].shift(1) <= df["buyat"].shift(1))
    df["raw_sell_signal"] = (df["close"] < df["sellat"]) & (df["close"].shift(1) >= df["sellat"].shift(1))

    # === Final signals with trend tracking ===
    buy_signals, sell_signals, trends = [], [], []
    currentTrend = 0  # 0 = neutral, 1 = long, -1 = short

    for buy, sell in zip(df["raw_buy_signal"], df["raw_sell_signal"]):
        if buy:
            buy_signals.append(True)
            sell_signals.append(False)
            currentTrend = 1
        elif sell:
            buy_signals.append(False)
            sell_signals.append(True)
            currentTrend = -1
        else:
            buy_signals.append(False)
            sell_signals.append(False)
        trends.append(currentTrend)

    df["buySignal"] = buy_signals
    df["sellSignal"] = sell_signals
    df["trend"] = trends

    # === Cleanup ===
    df.drop(columns=["condition","isUptrend","isDowntrend",
                     "raw_buy_signal","raw_sell_signal"], inplace=True)

    return df

import pandas as pd

def parallel_ema_strategy(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Parallel EMA High/Low Strategy (converted from Pine Script)

    Args:
        df (pd.DataFrame): Must have columns ['open', 'high', 'low', 'close']
        period (int): EMA period (default=20)

    Returns:
        pd.DataFrame: Original df + ['emaHigh','emaLow','buySignal','sellSignal','trend']
    """
    # === EMA of High and Low ===
    df["emaHigh"] = df["high"].ewm(span=period, adjust=False).mean()
    df["emaLow"]  = df["low"].ewm(span=period, adjust=False).mean()

    # === Two consecutive closes above/below ===
    buyCondRaw  = (df["close"].shift(1) > df["emaHigh"].shift(1)) & (df["close"] > df["emaHigh"])
    sellCondRaw = (df["close"].shift(1) < df["emaLow"].shift(1))  & (df["close"] < df["emaLow"])

    # === Only trigger when condition is new (no duplicates) ===
    # df["buySignal"]  = buyCondRaw & (~buyCondRaw.shift(1).fillna(False))
    # df["sellSignal"] = sellCondRaw & (~sellCondRaw.shift(1).fillna(False))

    df["buySignal"]  = buyCondRaw & (~buyCondRaw.shift(1, fill_value=False))
    df["sellSignal"] = sellCondRaw & (~sellCondRaw.shift(1, fill_value=False))

    # === Trend column (1 = long, -1 = short, 0 = neutral) ===
    trends = []
    currentTrend = 0
    for buy, sell in zip(df["buySignal"], df["sellSignal"]):
        if buy:
            currentTrend = 1
        elif sell:
            currentTrend = -1
        trends.append(currentTrend)

    df["trend"] = trends

    return df

