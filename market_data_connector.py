
import pandas as pd
import numpy as np
from datetime import date, timedelta

def _normalize_vnstock_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize vnstock output into dashboard schema."""
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    rename_map = {}

    # Common vnstock column variants
    for c in out.columns:
        lc = str(c).lower()
        if lc in ["time", "date", "tradingdate"]:
            rename_map[c] = "date"
        elif lc in ["close", "close_price", "priceclose"]:
            rename_map[c] = "vnindex"
        elif lc in ["volume", "total_volume"]:
            rename_map[c] = "volume"
        elif lc in ["value", "trading_value", "total_value"]:
            rename_map[c] = "liquidity"

    out = out.rename(columns=rename_map)

    if "date" not in out.columns:
        return pd.DataFrame()

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date")

    if "vnindex" not in out.columns:
        # Try close if still present
        if "close" in out.columns:
            out["vnindex"] = pd.to_numeric(out["close"], errors="coerce")
        else:
            out["vnindex"] = np.nan

    # Liquidity: if no traded value, estimate from volume where possible.
    if "liquidity" not in out.columns:
        if "volume" in out.columns:
            # Conservative display-only proxy in VND billion.
            out["liquidity"] = pd.to_numeric(out["volume"], errors="coerce") / 1_000_000
        else:
            out["liquidity"] = np.nan

    out["vnindex"] = pd.to_numeric(out["vnindex"], errors="coerce")
    out["liquidity"] = pd.to_numeric(out["liquidity"], errors="coerce")

    # Add analytical columns used by CEO/market dashboard.
    out["vnindex_return_pct"] = out["vnindex"].pct_change() * 100
    out["ma20"] = out["vnindex"].rolling(20, min_periods=5).mean()
    out["ma60"] = out["vnindex"].rolling(60, min_periods=10).mean()
    out["volatility_20d"] = out["vnindex_return_pct"].rolling(20, min_periods=5).std()
    out["trend_signal"] = np.select(
        [
            out["vnindex"] >= out["ma20"],
            out["vnindex"] < out["ma20"],
        ],
        ["Positive / above MA20", "Caution / below MA20"],
        default="N/A"
    )
    out["market_risk_flag"] = np.select(
        [
            out["vnindex_return_pct"] <= -2.0,
            out["vnindex_return_pct"] <= -1.0,
            out["vnindex_return_pct"] >= 2.0,
        ],
        ["Red - sharp fall", "Yellow - weak session", "Green - strong session"],
        default="Normal"
    )

    keep = [
        "date", "vnindex", "liquidity", "vnindex_return_pct",
        "ma20", "ma60", "volatility_20d", "trend_signal", "market_risk_flag"
    ]
    return out[[c for c in keep if c in out.columns]]

def load_vnindex_auto(start_date="2024-01-01", end_date=None) -> pd.DataFrame:
    """Load VNINDEX using vnstock. Returns empty DataFrame if unavailable."""
    if end_date is None:
        end_date = date.today().strftime("%Y-%m-%d")

    try:
        # vnstock old API style
        from vnstock import stock_historical_data
        df = stock_historical_data(
            symbol="VNINDEX",
            start_date=start_date,
            end_date=end_date,
            resolution="1D",
            type="index"
        )
        return _normalize_vnstock_columns(df)
    except Exception:
        pass

    try:
        # vnstock newer API style
        from vnstock import Vnstock
        stock = Vnstock().stock(symbol="VNINDEX", source="VCI")
        df = stock.quote.history(start=start_date, end=end_date, interval="1D")
        return _normalize_vnstock_columns(df)
    except Exception:
        return pd.DataFrame()

def make_market_fallback(start_date="2024-01-01", periods=520) -> pd.DataFrame:
    """Fallback demo market data. It is only used when API and sheet data are unavailable."""
    dates = pd.bdate_range(start=start_date, periods=periods)
    rng = np.random.default_rng(42)
    level = 1150 + np.cumsum(rng.normal(0.9, 7.5, len(dates)))
    out = pd.DataFrame({
        "date": dates,
        "vnindex": level.round(2),
        "liquidity": rng.normal(22000, 4500, len(dates)).clip(8000, 40000).round(0),
    })
    return _normalize_vnstock_columns(out)

def merge_market_sources(sheet_market: pd.DataFrame = None, prefer_auto: bool = True) -> pd.DataFrame:
    """Prefer live VNINDEX when available; otherwise use sheet/local data."""
    auto = load_vnindex_auto() if prefer_auto else pd.DataFrame()

    if auto is not None and not auto.empty and auto["vnindex"].notna().sum() > 10:
        return auto

    if sheet_market is not None and not sheet_market.empty:
        return _normalize_vnstock_columns(sheet_market)

    return make_market_fallback()

def market_ceo_signal(market_df: pd.DataFrame) -> dict:
    if market_df is None or market_df.empty:
        return {
            "latest_vnindex": 0,
            "latest_return": 0,
            "signal": "No data",
            "action": "Check market data connection",
        }

    d = market_df.dropna(subset=["vnindex"]).sort_values("date")
    if d.empty:
        return {
            "latest_vnindex": 0,
            "latest_return": 0,
            "signal": "No data",
            "action": "Check market data connection",
        }

    last = d.iloc[-1]
    latest_return = float(last.get("vnindex_return_pct", 0) or 0)
    flag = str(last.get("market_risk_flag", "Normal"))

    if "Red" in flag:
        action = "Reduce aggressive margin push; prioritize client risk calls and cash management."
    elif "Yellow" in flag:
        action = "Monitor leveraged clients; focus on advisory and selective trading ideas."
    elif "Green" in flag:
        action = "Increase brokerage campaign; prioritize active clients and margin-qualified accounts."
    else:
        action = "Maintain balanced sales plan; focus on quality revenue and client activation."

    return {
        "latest_vnindex": round(float(last["vnindex"]), 2),
        "latest_return": round(latest_return, 2),
        "signal": flag,
        "action": action,
    }
