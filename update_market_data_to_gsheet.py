"""
update_market_data_to_gsheet.py
Author: Le Hoang Quan

Purpose
-------
Update Google Sheet `market_data` with VNINDEX data from vnstock.

How to use locally
------------------
1) Install:
   pip install pandas gspread google-auth vnstock

2) Put your Google service account JSON file in the same folder, for example:
   service_account.json

3) Share your Google Sheet with the service account email.

4) Run:
   python update_market_data_to_gsheet.py

Notes
-----
- This script overwrites the `market_data` worksheet.
- Sheet name default: VNDIRECT_BI_DATA
- Worksheet default: market_data
"""

import os
from datetime import date
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


SHEET_NAME = os.getenv("GSHEET_NAME", "VNDIRECT_BI_DATA")
WORKSHEET_NAME = os.getenv("GSHEET_WORKSHEET", "market_data")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")

START_DATE = os.getenv("START_DATE", "2024-01-01")
END_DATE = os.getenv("END_DATE", date.today().strftime("%Y-%m-%d"))


def load_vnindex(start_date: str, end_date: str) -> pd.DataFrame:
    """Load VNINDEX data using vnstock and normalize columns."""
    try:
        from vnstock import stock_historical_data

        df = stock_historical_data(
            symbol="VNINDEX",
            start_date=start_date,
            end_date=end_date,
            resolution="1D",
            type="index",
        )
    except Exception:
        from vnstock import Vnstock

        stock = Vnstock().stock(symbol="VNINDEX", source="VCI")
        df = stock.quote.history(start=start_date, end=end_date, interval="1D")

    if df is None or df.empty:
        raise RuntimeError("Không lấy được dữ liệu VNINDEX từ vnstock.")

    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]

    rename_map = {}
    for c in df.columns:
        if c in ["time", "date", "tradingdate"]:
            rename_map[c] = "date"
        elif c in ["close", "close_price", "priceclose"]:
            rename_map[c] = "vnindex"
        elif c in ["volume", "total_volume"]:
            rename_map[c] = "volume"
        elif c in ["value", "trading_value", "total_value"]:
            rename_map[c] = "hose_liquidity_bn_vnd"

    df = df.rename(columns=rename_map)

    if "date" not in df.columns:
        raise RuntimeError(f"Không tìm thấy cột date trong dữ liệu vnstock. Columns: {list(df.columns)}")

    if "vnindex" not in df.columns:
        raise RuntimeError(f"Không tìm thấy cột close/vnindex trong dữ liệu vnstock. Columns: {list(df.columns)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["vnindex"] = pd.to_numeric(df["vnindex"], errors="coerce").round(2)

    if "hose_liquidity_bn_vnd" not in df.columns:
        if "volume" in df.columns:
            df["hose_liquidity_bn_vnd"] = pd.to_numeric(df["volume"], errors="coerce") / 1_000_000
        else:
            df["hose_liquidity_bn_vnd"] = None

    df["hose_liquidity_bn_vnd"] = pd.to_numeric(df["hose_liquidity_bn_vnd"], errors="coerce").round(0)

    if "vn30" not in df.columns:
        df["vn30"] = ""

    df["market_status"] = "Actual"
    df["data_type"] = "actual_vnstock"
    df["source_note"] = "VNINDEX data pulled via vnstock"
    df["source_url"] = "https://vnstocks.com/docs/vnstock/thong-ke-gia-lich-su"

    out_cols = [
        "date",
        "vnindex",
        "hose_liquidity_bn_vnd",
        "vn30",
        "market_status",
        "data_type",
        "source_note",
        "source_url",
    ]

    out = df[out_cols].dropna(subset=["date", "vnindex"]).sort_values("date")
    return out


def update_google_sheet(df: pd.DataFrame) -> None:
    """Overwrite market_data worksheet with DataFrame."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)

    spreadsheet = client.open(SHEET_NAME)

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=20)

    worksheet.clear()

    values = [df.columns.tolist()] + df.astype(object).where(pd.notnull(df), "").values.tolist()
    worksheet.update(values)

    print(f"Updated Google Sheet: {SHEET_NAME} / {WORKSHEET_NAME}")
    print(f"Rows uploaded: {len(df):,}")
    print(f"Date range: {df['date'].min()} -> {df['date'].max()}")


def main():
    print("Loading VNINDEX...")
    df = load_vnindex(START_DATE, END_DATE)

    print("Updating Google Sheet...")
    update_google_sheet(df)

    print("Done.")


if __name__ == "__main__":
    main()
