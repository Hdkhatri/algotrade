import credentials as c
# Import the required module from the fyers_apiv3 package
from fyers_apiv3 import fyersModel
import pandas as pd
import webbrowser
import time
import pyperclip
from datetime import datetime, timedelta

# Replace these values with your actual API credentials
client_id = c.client_id
secret_key = c.secret_key
redirect_uri = c.redirect_uri
response_type = c.response_type 
state = c.state
user_name = c.user_name
grant_type = c.grant_type  


# Create a session model with the provided credentials
session = fyersModel.SessionModel(
    client_id=client_id,
    secret_key=secret_key,
    redirect_uri=redirect_uri,
    response_type=response_type
)

def create_fyers_session(authcode):
    """
    Create a session object to handle the Fyers API authentication and token generation.
    Returns an authenticated FyersModel instance.
    """
    session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key, 
        redirect_uri=redirect_uri, 
        response_type=response_type, 
        grant_type=grant_type
    )
    session.set_token(authcode)
    response = session.generate_token()
    access_token = response['access_token']
    fyers_main = fyersModel.FyersModel(client_id=client_id, is_async=False, token=access_token, log_path="")
    return fyers_main,access_token

def fetch_and_save_history(access_token, SYMBOL, TIMEFRAME, FROM_DATE, TO_DATE):
    """
    Fetch historical data from Fyers API and save as CSV.
    Returns the CSV filename.
    """

    data = {
        "symbol": SYMBOL,
        "resolution": TIMEFRAME,
        "date_format": "1",
        "range_from": FROM_DATE,
        "range_to": TO_DATE,
        "cont_flag": "1"
    }
    fyers = fyersModel.FyersModel(client_id=client_id, is_async=False, token=access_token, log_path="")
    response = fyers.history(data=data)
    df = pd.DataFrame(response['candles'], columns=['time','open','high','low','close','volume'])
    print(df.iloc[-1]['close'])
    df['datetime'] = pd.to_datetime(df['time'],unit='s',utc=True).map(lambda x: x.tz_convert('Asia/Kolkata'))
    csv_name = "RawData/"+data['symbol'].split(":")[1]+str(data['resolution'])+"history"+data['range_from']+"_"+data['range_to']+".csv"
    print(csv_name)
    df.to_csv(csv_name, header=True, index=True)
    return csv_name

def fetch_data(access_token, SYMBOL, TIMEFRAME, FROM_DATE, TO_DATE):
    """
    Fetch historical data from Fyers API and save as CSV.
    Returns the CSV filename.
    """

    data = {
        "symbol": SYMBOL,
        "resolution": TIMEFRAME,
        "date_format": "1",
        "range_from": FROM_DATE,
        "range_to": TO_DATE,
        "cont_flag": "1"
    }
    fyers = fyersModel.FyersModel(client_id=client_id, is_async=False, token=access_token, log_path="")
    response = fyers.history(data=data)
    df = pd.DataFrame(response['candles'], columns=['time','open','high','low','close','volume'])
    print(df.iloc[-1]['close'])
    df['datetime'] = pd.to_datetime(df['time'],unit='s',utc=True).map(lambda x: x.tz_convert('Asia/Kolkata'))
    return df


def add_signals_and_strikes(df):
    # Clean column names
    df.columns = df.columns.str.strip()

    # Ensure correct data type
    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # Drop rows where 'close' is NaN
    df.dropna(subset=['close'], inplace=True)

    # === Compute EMA 11 and EMA 17 ===
    df['EMA_11'] = df['close'].ewm(span=11, adjust=False).mean()
    df['EMA_17'] = df['close'].ewm(span=17, adjust=False).mean()

    # === Initialize Signal and Strike columns ===
    df['Signal'] = None
    df['Strike_Price'] = None

    # === Position state tracker ===
    position_state = 0  # 0 = neutral, 1 = long, -1 = short

    # === Logic to generate buy/sell signals ===
    for i in range(len(df)):
        close = df.loc[i, 'close']
        ema11 = df.loc[i, 'EMA_11']
        ema17 = df.loc[i, 'EMA_17']

        # Flip to long
        if close > ema11 and close > ema17 and position_state != 1:
            df.at[i, 'Signal'] = 'Sell Short'
            nearest_500 = round(close / 500) * 500
            put_strike = nearest_500 - 1000
            df.at[i, 'Strike_Price'] = f'SELL {put_strike} PE'
            position_state = 1

        # Flip to short
        elif close < ema11 and close < ema17 and position_state != -1:
            df.at[i, 'Signal'] = 'Sell Long'
            nearest_500 = round(close / 500) * 500
            call_strike = nearest_500 + 1000
            df.at[i, 'Strike_Price'] = f'SELL {call_strike} CE'
            position_state = -1

    return df

def get_NextToNextweekThursday(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    # Find this week's Thursday
    days_to_this_thursday = (3 - dt.weekday() + 7) % 7
    this_week_thursday = dt + timedelta(days=days_to_this_thursday)
    # Move to next week's Thursday
    next_week_thursday = this_week_thursday + timedelta(days=7)
    # Move to next to next week's Thursday
    next_to_nextweek_thursday = next_week_thursday + timedelta(days=7)
    return next_to_nextweek_thursday.strftime("%Y-%m-%d")



def getSymbol(Ex_UnderlyingSymbol, expiry_date, strike, opt_type, Ex="NSE"):
    # Check if expiry_date is the last Thursday of the month
    dt_expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
    # Find last day of the month
    next_month = dt_expiry.replace(day=28) + timedelta(days=4)
    last_day_of_month = next_month - timedelta(days=next_month.day)
    # Find last Thursday of the month
    days_to_last_thursday = (last_day_of_month.weekday() - 3) % 7
    last_thursday = last_day_of_month - timedelta(days=days_to_last_thursday)
    YY = str(dt_expiry.year)[2:]
    strike_str = str(int(strike))
    opt_type_str = "CE" if opt_type.lower() == "call" else "PE"
    if dt_expiry == last_thursday:
        MMM = dt_expiry.strftime("%b").upper()
        symbol = f"{Ex}:{Ex_UnderlyingSymbol}{YY}{MMM}{strike_str}{opt_type_str}"
        return symbol
    # expiry_date in format YYYY-MM-DD
    dt = datetime.strptime(expiry_date, "%Y-%m-%d")
    YY = str(dt.year)[2:]
    M = str(dt.month)
    # Use special month codes for October, November, December
    if dt.month == 10:
        M = "O"
    elif dt.month == 11:
        M = "N"
    elif dt.month == 12:
        M = "D"
    dd = str(dt.day)
    strike_str = str(int(strike))
    opt_type_str = "CE" if opt_type.lower() == "call" else "PE"
    symbol = f"{Ex}:{Ex_UnderlyingSymbol}{YY}{M}{dd}{strike_str}{opt_type_str}"
    return symbol