
"""
update_market_data_to_gsheet.py (FIXED VERSION)
Fix:
- Avoid JWT error by safer credential loading
- Clear logging
"""

import os
from datetime import date
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


SHEET_NAME = "VNDIRECT_BI_DATA"
WORKSHEET_NAME = "market_data"
SERVICE_ACCOUNT_FILE = "service_account.json"

START_DATE = "2024-01-01"
END_DATE = date.today().strftime("%Y-%m-%d")


def load_vnindex():
    from vnstock import stock_historical_data

    df = stock_historical_data(
        symbol="VNINDEX",
        start_date=START_DATE,
        end_date=END_DATE,
        resolution="1D",
        type="index",
    )

    df = df.rename(columns={
        "time": "date",
        "close": "vnindex"
    })

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    df = df[["date", "vnindex"]].dropna()

    df["market_status"] = "Actual"
    df["data_type"] = "real_vnstock"

    return df


def update_google_sheet(df):
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=scope
    )

    client = gspread.authorize(creds)

    spreadsheet = client.open(SHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    worksheet.clear()

    data = [df.columns.tolist()] + df.values.tolist()
    worksheet.update(data)

    print("✅ Google Sheet updated successfully")


def main():
    print("Loading VNINDEX...")
    df = load_vnindex()

    print("Updating Google Sheet...")
    update_google_sheet(df)


if __name__ == "__main__":
    main()
