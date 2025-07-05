import credentials as c
# Import the required module from the fyers_apiv3 package
from fyers_apiv3 import fyersModel
import webbrowser
import time
import pyperclip


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

def create_session():      
    # Generate the auth code using the session model
    response = session.generate_authcode()
    # Print the auth code received in the response
    print(response)
    # Open the URL in the default web browser
    webbrowser.open(response)

create_session()





