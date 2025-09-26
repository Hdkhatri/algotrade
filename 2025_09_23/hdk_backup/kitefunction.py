import json
import pandas as pd
import datetime, time
import os
import logging
from kiteconnect import KiteConnect
from config import ACCESS_TOKEN_FILE, INSTRUMENTS_FILE, LOG_FILE


logging.basicConfig(
    filename=LOG_FILE,
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# Load instruments.csv
instruments_df = pd.read_csv(INSTRUMENTS_FILE)


def get_kite_client():
    try:
        with open(ACCESS_TOKEN_FILE, "r") as f:
            token_data = json.load(f)
        kite = KiteConnect(api_key=token_data["api_key"])
        kite.set_access_token(token_data["access_token"])
        return kite
    except Exception as e:
        print("❌ Could not load access token:", e)
        logging.error(f"Error loading access token: {e}")
        return None
    

def get_profile():
    kite = get_kite_client()
    if kite:
        try:
            profile = kite.profile()
            return profile["user_name"]
        except Exception as e:
            print("❌ Error fetching profile:", e)
            logging.error(f"Error fetching profile: {e}")
    return None



def get_token_for_symbol(symbol):
    df = instruments_df

    row = df[df["tradingsymbol"] == symbol]
    if row.empty:
        row = df[df["name"] == symbol]

    if not row.empty:
        return int(row["instrument_token"].values[0])
    else:
        print(f"❌ Symbol not found: {symbol}")
        logging.error(f"Symbol not found: {symbol}")
        return None



def get_historical_df(instrument_token, interval, days):
    kite = get_kite_client()
    now = datetime.datetime.now()
    from_date = (now - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    to_date = now.strftime('%Y-%m-%d')
    data = kite.historical_data(instrument_token, from_date, to_date, interval)
    return pd.DataFrame(data)


def get_quotes(symbol):
    kite = get_kite_client()
    try:
        full_symbol = f"NFO:{symbol}"
        quote = kite.ltp([full_symbol])
        return quote[full_symbol]['last_price']
    except Exception as e:
        print(f"❌ Error fetching quote for {symbol}: {e}")
        logging.error(f"Error fetching quote for {symbol}: {e}")
        return None



def get_avgprice_from_positions(tradingsymbol):
    kite = get_kite_client()
    try:
        positions = kite.positions()["net"]
        for pos in positions:
            if pos["tradingsymbol"] == tradingsymbol:
                avg_price = pos.get("average_price", 0.0)
                qty = pos.get("quantity", 0)

                if qty < 0:
                    logging.info(f"🔃 Detected SELL entry for {tradingsymbol}, quantity {qty}")
                    qty = abs(qty)
                else:
                    logging.info(f"📥 Detected BUY entry for {tradingsymbol}, quantity {qty}")

                return avg_price, qty
    except Exception as e:
        print(f"⚠️ Error fetching LTP from positions {tradingsymbol}: {e}")
        logging.error(f"Error fetching LTP from positions {tradingsymbol}: {e}")
    return None, 0


def place_aggressive_limit_order(tradingsymbol, qty, ordertype, config=None, timeout=5):
    
    print(config)
    if config['TRADE'].lower() != "yes":
        return "SIMULATED_ORDER", None, 0

    kite = get_kite_client()
    tx_type = kite.TRANSACTION_TYPE_SELL if ordertype.upper() == "SELL" else kite.TRANSACTION_TYPE_BUY
    symbol = "NFO:" + tradingsymbol

    filled_qty = 0
    avg_price = 0.0
    order_id = None
    start_time = time.time()

    try:
        while time.time() - start_time < timeout:
            quote = kite.quote(symbol)
            depth = quote[symbol].get("depth", {})

            if ordertype.upper() == "SELL":
                best_price = depth.get("buy", [{}])[0].get("price")
                if best_price is None:
                    best_price = get_quotes(tradingsymbol)
                limit_price = round(best_price - 0.05, 1)  # slightly aggressive
            else:
                best_price = depth.get("sell", [{}])[0].get("price")
                if best_price is None:
                    best_price = get_quotes(tradingsymbol)
                limit_price = round(best_price + 0.05, 1)  # slightly aggressive

            if not order_id:  # first time, place order
                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange="NFO",
                    tradingsymbol=tradingsymbol,
                    transaction_type=tx_type,
                    quantity=qty,
                    order_type=kite.ORDER_TYPE_LIMIT,
                    price=limit_price,
                    product=kite.PRODUCT_NRML
                )
            else:  # modify if already placed
                kite.modify_order(
                    variety=kite.VARIETY_REGULAR,
                    order_id=order_id,
                    price=limit_price
                )

            # Check fills
            history = get_historical_order(order_id)
            if history:
                filled_qty = sum(o["quantity"] for o in history if o["status"] == "COMPLETE")
                if filled_qty > 0:
                    avg_price = sum(
                        o["average_price"] * o["quantity"] for o in history if o["status"] == "COMPLETE") / filled_qty
                    avg_price = round(avg_price, 2)
                if filled_qty >= qty:
                    return order_id, avg_price, filled_qty

            time.sleep(0.3)  # short polling delay

        # Timeout reached - cancel unfilled qty
        if filled_qty < qty and order_id:
            try:
                kite.cancel_order(variety=kite.VARIETY_REGULAR, order_id=order_id)
                print(f"🛑 Cancelled remaining {qty - filled_qty} qty for {tradingsymbol}")
                logging.info(f"Cancelled remaining {qty - filled_qty} qty for {tradingsymbol}")
            except Exception as ce:
                print(f"⚠ Failed to cancel unfilled qty: {ce}")
                logging.error(f"Failed to cancel unfilled qty: {ce}")

        print(f"⚠️ Timeout: Filled {filled_qty}/{qty} for {tradingsymbol}")
        return order_id, avg_price, filled_qty

    except Exception as e:
        print(f"❌ Aggressive Limit Order failed: {e}")
        return None, None, 0



def get_historical_order(order_id):
    kite = get_kite_client()
    try:
        orders = kite.order_history(order_id)
        if not orders:
            print(f"⚠️ No order history found for Order ID: {order_id}")
            logging.warning(f"No order history for Order ID: {order_id}")
            return []

        order_details = []
        for order in orders:
            order_details.append({
                "order_id": order.get("order_id", ""),
                "tradingsymbol": order.get("tradingsymbol", ""),
                "transaction_type": order.get("transaction_type", ""),
                "quantity": order.get("quantity", 0),
                "status": order.get("status", ""),
                "average_price": order.get("average_price", 0.0),
                "placed_at": order.get("order_timestamp", "")
            })

        return order_details

    except Exception as e:
        print(f"❌ Error fetching order history for {order_id}: {e}")
        logging.error(f"Error fetching order history for {order_id}: {e}")
        return []





def place_option_hybrid_order(tradingsymbol, qty, ordertype,config):

    return place_aggressive_limit_order(tradingsymbol, qty, ordertype,config)























