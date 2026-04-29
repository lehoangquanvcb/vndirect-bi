"""
update_market_data_to_gsheet.py
Author: Le Hoang Quan

FIX for vnstock ImportError:
- Uses the newer vnstock API: Vnstock().stock(...).quote.history(...)
- Falls back to old API only if available.
- Updates Google Sheet worksheet: market_data

Before running:
1) pip install --upgrade pandas gspread google-auth vnstock
2) Put service_account.json in the same folder
3) Share Google Sheet "VNDIRECT_BI_DATA" to service account email
4) python update_market_data_to_gsheet.py
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


def normalize_market_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize market data columns to dashboard schema."""
    if df is None or df.empty:
        raise RuntimeError("VNINDEX data is empty.")

    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]

    rename = {}
    for c in df.columns:
        if c in ["time", "date", "tradingdate"]:
            rename[c] = "date"
        elif c in ["close", "close_price", "priceclose"]:
            rename[c] = "vnindex"
        elif c in ["volume", "total_volume"]:
            rename[c] = "volume"
        elif c in ["value", "trading_value", "total_value"]:
            rename[c] = "hose_liquidity_bn_vnd"

    df = df.rename(columns=rename)

    if "date" not in df.columns:
        raise RuntimeError(f"Không tìm thấy cột date/time. Columns hiện có: {list(df.columns)}")

    if "vnindex" not in df.columns:
        raise RuntimeError(f"Không tìm thấy cột close/vnindex. Columns hiện có: {list(df.columns)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["vnindex"] = pd.to_numeric(df["vnindex"], errors="coerce").round(2)

    if "hose_liquidity_bn_vnd" not in df.columns:
        if "volume" in df.columns:
            # Proxy only if traded value is unavailable.
            df["hose_liquidity_bn_vnd"] = pd.to_numeric(df["volume"], errors="coerce") / 1_000_000
        else:
            df["hose_liquidity_bn_vnd"] = ""

    if "vn30" not in df.columns:
        df["vn30"] = ""

    df["market_status"] = "Actual"
    df["data_type"] = "real_vnstock"
    df["source_note"] = "VNINDEX pulled via vnstock"
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


def load_vnindex_new_api() -> pd.DataFrame:
    """Load VNINDEX using newer vnstock API."""
    from vnstock import Vnstock

    errors = []

    # Try common sources
    for source in ["VCI", "TCBS"]:
        try:
            stock = Vnstock().stock(symbol="VNINDEX", source=source)
            df = stock.quote.history(start=START_DATE, end=END_DATE, interval="1D")
            return normalize_market_df(df)
        except Exception as e:
            errors.append(f"{source}: {e}")

    raise RuntimeError("Không lấy được VNINDEX bằng vnstock new API. Errors: " + " | ".join(errors))


def load_vnindex_old_api() -> pd.DataFrame:
    """Fallback for older vnstock API if installed."""
    try:
        from vnstock import stock_historical_data
    except Exception as e:
        raise RuntimeError(f"Old API stock_historical_data không khả dụng: {e}")

    df = stock_historical_data(
        symbol="VNINDEX",
        start_date=START_DATE,
        end_date=END_DATE,
        resolution="1D",
        type="index",
    )
    return normalize_market_df(df)


def load_vnindex() -> pd.DataFrame:
    """Try new API first, then old API."""
    try:
        print("Trying vnstock new API...")
        return load_vnindex_new_api()
    except Exception as e1:
        print(f"New API failed: {e1}")
        print("Trying vnstock old API...")
        return load_vnindex_old_api()


def update_google_sheet(df: pd.DataFrame) -> None:
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

    print("✅ Google Sheet updated successfully")
    print(f"Sheet: {SHEET_NAME} / {WORKSHEET_NAME}")
    print(f"Rows: {len(df):,}")
    print(f"Date range: {df['date'].min()} -> {df['date'].max()}")


def main():
    print("Loading VNINDEX...")
    df = load_vnindex()

    print("Preview:")
    print(df.tail())

    print("Updating Google Sheet...")
    update_google_sheet(df)

    print("Done.")


if __name__ == "__main__":
    main()
