import requests
import pandas as pd

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

url = "https://api.kite.trade/instruments"
filename = "instruments.csv"
filtered_filename = "nifty_instruments.csv"

try:
    print("⬇️ Downloading latest instruments.csv...")
    response = requests.get(url)
    response.raise_for_status()  # Raise error for bad response

    with open(filename, "wb") as f:
        f.write(response.content)

    print("✅ instruments.csv downloaded successfully.")

    # Load and filter the CSV
    df = pd.read_csv(filename)
    
    # Filter where 'name' contains 'NIFTY' (case-insensitive)
    # nifty_df = df[df['name'].str.contains("NIFTY", case=False, na=False)]
    nifty_df = df[df['name'].isin(["NIFTY 50", "NIFTY"])]
    # Save filtered data
    nifty_df.to_csv(filtered_filename, index=False)
    print(f"✅ Filtered file saved as: {filtered_filename} | Rows: {len(nifty_df)}")

except Exception as e:
    print(f"❌ Failed: {e}")
