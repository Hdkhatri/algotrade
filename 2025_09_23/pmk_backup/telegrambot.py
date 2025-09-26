import requests
import json
import logging
import time

TOKEN = '8139252134:AAEb0FqEgKriVy6i6FiAIu554Oupd9IuCgE'

# url = f'https://api.telegram.org/bot{TOKEN}/getUpdates'

# res = requests.get(url)
# print(json.dumps(res.json(), indent=4))


CHAT_ID = 5827825724  # replace with your actual chat_id


def send_telegram_message_old1(message):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    data = {
        'chat_id': CHAT_ID,
        'text': message
    }
    response = requests.post(url, data=data)

def send_telegram_message(message, retries=3, delay=2):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    data = {
        'chat_id': CHAT_ID,
        'text': message
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                return True
            else:
                logging.error(f"⚠️ Telegram API error (status {response.status_code}): {response.text}")
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Error sending Telegram message (Attempt {attempt}/{retries}): {e}")

        # retry after delay
        if attempt < retries:
            time.sleep(delay)

    return False

# if __name__ == "__main__":
#     message = 'test message from pmk script'
#     send_telegram_message(message)