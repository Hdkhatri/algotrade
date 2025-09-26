import pyotp
import json
import requests
from kiteconnect import KiteConnect
from api_urls import LOGIN_URL, TWOFA_URL
from config import ACCESS_TOKEN_FILE
from credentials_zerodha import USERNAME, PASSWORD, API_SECRET, API_KEY, TOTP_TOKEN
def autologin_zerodha():
    session = requests.Session()

    # Step 1: Login with user_id and password
    response = session.post(LOGIN_URL, data={'user_id': USERNAME, 'password': PASSWORD})
    request_id = json.loads(response.text)['data']['request_id']

    # Step 2: Two-factor authentication
    twofa_pin = pyotp.TOTP(TOTP_TOKEN).now()
    session.post(
        TWOFA_URL,
        data={
            'user_id': USERNAME,
            'request_id': request_id,
            'twofa_value': twofa_pin,
            'twofa_type': 'totp'
        }
    )

    # Step 3: Generate request_token and access_token
    kite = KiteConnect(api_key=API_KEY)
    kite_url = kite.login_url()
    print("[INFO] Kite login URL:", kite_url)

    try:
        session.get(kite_url)
    except Exception as e:
        e_msg = str(e)
        if 'request_token=' in e_msg:
            request_token = e_msg.split('request_token=')[1].split(' ')[0].split('&action')[0]
            print('[INFO] Successful Login with Request Token:', request_token)

            access_token = kite.generate_session(request_token, API_SECRET)['access_token']
            kite.set_access_token(access_token)

            # Prepare token data
            token_data = {
                "access_token": access_token,
                "api_key": API_KEY,
                "api_secret": API_SECRET,
                "username": USERNAME
            }

            # ✅ Save to JSON
            with open(ACCESS_TOKEN_FILE, "w") as f:
                json.dump(token_data, f, indent=2)
            print(f"[INFO] Token saved to file: {ACCESS_TOKEN_FILE}")

            # ✅ Save to DB
            # save_token_to_db(token_data, DBNAME)
            # print(f"[INFO] Token also saved to database: {DBNAME}")

            return access_token
        else:
            print("[ERROR] Could not extract request_token from exception.")
            return None

if __name__ == "__main__":
    result = autologin_zerodha()

    if result:
        print("[✅] Access token generated and saved successfully.")
    else:
        print("[❌] Login failed.")
    

