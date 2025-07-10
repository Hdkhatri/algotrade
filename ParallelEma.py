from fyers_apiv3 import fyersModel
import pandas as pd
import numpy as np
import credentials as c
from fyers_apiv3.FyersWebsocket import data_ws
import time
import json
from datetime import datetime, timedelta
from fyers import add_signals_and_strikes, create_fyers_session, ema_breakout_strategy, ema_ribbon_strategy, fetch_and_save_history, fetch_data, get_NextToNextweekThursday, getSymbol
from xlsxwriter import Workbook


# Read the URL from the file
with open("URL.txt", "r") as file:
    url = file.read().strip()
#print("URL from file:", url)


# Extract the auth code from the URL
s1 = url.split('auth_code=')
authcode = s1[1].split('&state')[0]

# Define your Fyers API credentials
client_id = c.client_id
secret_key = c.secret_key
redirect_uri = c.redirect_uri # Replace with your redirect URI
response_type = c.response_type 
grant_type = c.grant_type  

# Create a session model with the provided credentials
fyers_main,access_token = create_fyers_session(authcode)
# Make a request to get the user profile information
user_profile = fyers_main.get_profile()

#print("Mobile Number:", user_profile['data']['mobile_number'])
#print("user_profile :", user_profile)
#print("Access Token:", access_token)


# Initialize Parameters to fetch historical data
SYMBOL= "NSE:NIFTY50-INDEX"
TIMEFRAME = "15"  # 60 minutes
FROM_DATE = "2025-05-01"
TO_DATE = "2025-07-09"

 
RaWDataCsv = fetch_and_save_history(access_token,SYMBOL,TIMEFRAME,FROM_DATE,TO_DATE)
print("Index Data CSV saved as:", RaWDataCsv)
# Read the CSV file and print the first five rows
df = pd.read_csv(RaWDataCsv)
#print(df.head())

# Usage:
df = ema_breakout_strategy(df)
filename = "Parallel_"+ TIMEFRAME + ".xlsx"
df.to_excel(filename, index=False)

# === Extract trade pairs and create Result sheet ===
# === Extract trade pairs and create Result sheet ===
result = []
active_trade = None
trade = None  # <- moved outside loop to persist between iterations

for i, row in df.iterrows():
    signal = row['Signal']
    strike_info = row['Strike_Price']
    # Check if signal and strike_info are not NaN
    if pd.notna(signal) and pd.notna(strike_info) and signal in ['Sell Long', 'Sell Short'] and strike_info != '':
        # Parse strike price and option type
        parts = strike_info.split()
        strike_price = int(parts[1])
        option_type = 'put' if 'PE' in parts[2] else 'call'
        date = row['datetime']
        date_only=date.split(" ")[0]
        next_to_nextweek_thursday = get_NextToNextweekThursday(date_only)
        option_symbol = getSymbol("NIFTY", next_to_nextweek_thursday, strike_price, option_type, Ex="NSE")
        print(option_symbol)
        option_symbol_df = fetch_data(access_token,option_symbol,TIMEFRAME,date_only,date_only)
        price = row['close']

        print(f"signal: {signal}, trade: {trade}")

        if signal == 'Sell Long':
            if trade == 'long' and active_trade:
                # If active_trade has option_symbol, set Buy Price from option_symbol_df
                buy_price = price
                if active_trade.get('option_symbol'):
                    if not option_symbol_df.empty:
                        match_row = option_symbol_df[option_symbol_df['datetime'].astype(str) == str(date)]
                        if not match_row.empty:
                            buy_price = match_row.iloc[0]['close']
                active_trade['Buy Date'] = date
                active_trade['Buy Price'] = buy_price
                if active_trade.get('Sell Price') is not None:
                    active_trade['Difference'] = active_trade['Sell Price'] - buy_price
                result.append(active_trade)
                active_trade = None

            # Find the close value from option_symbol_df where datetime == date
            sell_price = None
            if not option_symbol_df.empty:
                # Ensure both are strings for comparison
                match_row = option_symbol_df[option_symbol_df['datetime'].astype(str) == str(date)]
                if not match_row.empty:
                    sell_price = match_row.iloc[0]['close']
            # Start new short trade
            active_trade = {
                'Entry Date': date,
                'strike price': strike_price,
                'type': option_type,
                'option_symbol': option_symbol,
                'Sell Price': sell_price
            }
            trade = 'short'

        elif signal == 'Sell Short':
            if trade == 'short' and active_trade:
                 # If active_trade has option_symbol, set Buy Price from option_symbol_df
                buy_price = price
                if active_trade.get('option_symbol'):
                    if not option_symbol_df.empty:
                        match_row = option_symbol_df[option_symbol_df['datetime'].astype(str) == str(date)]
                        if not match_row.empty:
                            buy_price = match_row.iloc[0]['close']
                active_trade['Buy Date'] = date
                active_trade['Buy Price'] = buy_price
                if active_trade.get('Sell Price') is not None:
                    active_trade['Difference'] = active_trade['Sell Price'] - buy_price
                result.append(active_trade)
                active_trade = None

            # Find the close value from option_symbol_df where datetime == date
            sell_price = None
            if not option_symbol_df.empty:
                # Ensure both are strings for comparison
                match_row = option_symbol_df[option_symbol_df['datetime'].astype(str) == str(date)]
                if not match_row.empty:
                    sell_price = match_row.iloc[0]['close']
            # Start new short trade
            active_trade = {
                'Entry Date': date,
                'strike price': strike_price,
                'type': option_type,
                'option_symbol': option_symbol,
                'Sell Price': sell_price
            }
            trade = 'long'

# Final closing of open trade is optional (only if needed)
# if active_trade is not None:
#     result.append(active_trade)

# Convert result list to DataFrame
result_df = pd.DataFrame(result)

# === Save both sheets to Excel ===
with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name='RawData')
    result_df.to_excel(writer, index=False, sheet_name='Result')

print("✅ Excel with RawData and Result sheets saved as: ", filename)





print("Updated Excel with signals saved as: ", filename)
