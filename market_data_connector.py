import pandas as pd
import numpy as np
from datetime import date

def _normalize_market(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    rename = {}
    for c in out.columns:
        if c in ["time", "tradingdate"]: rename[c] = "date"
        if c in ["close", "close_price", "priceclose"]: rename[c] = "vnindex"
        if c in ["hose_liquidity_bn_vnd", "market_turnover_trn", "value"]: rename[c] = "liquidity"
    out = out.rename(columns=rename)
    if "date" not in out.columns:
        return pd.DataFrame()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date")
    if "vnindex" not in out.columns:
        out["vnindex"] = np.nan
    if "liquidity" not in out.columns:
        out["liquidity"] = np.nan
    out["vnindex"] = pd.to_numeric(out["vnindex"], errors="coerce")
    out["liquidity"] = pd.to_numeric(out["liquidity"], errors="coerce")
    out["vnindex_return_pct"] = out["vnindex"].pct_change() * 100
    out["ma20"] = out["vnindex"].rolling(20, min_periods=5).mean()
    out["ma60"] = out["vnindex"].rolling(60, min_periods=10).mean()
    out["volatility_20d"] = out["vnindex_return_pct"].rolling(20, min_periods=5).std()
    out["trend_signal"] = np.where(out["vnindex"] >= out["ma20"], "Positive / above MA20", "Caution / below MA20")
    out["market_risk_flag"] = np.select(
        [out["vnindex_return_pct"] <= -2.0, out["vnindex_return_pct"] <= -1.0, out["vnindex_return_pct"] >= 2.0],
        ["Red - sharp fall", "Yellow - weak session", "Green - strong session"],
        default="Normal"
    )
    keep = ["date","vnindex","liquidity","vnindex_return_pct","ma20","ma60","volatility_20d","trend_signal","market_risk_flag"]
    return out[[c for c in keep if c in out.columns]]

def load_vnindex_auto(start_date="2024-01-01", end_date=None):
    if end_date is None:
        end_date = date.today().strftime("%Y-%m-%d")
    try:
        from vnstock import Quote
        q = Quote(symbol="VNINDEX", source="VCI")
        df = q.history(start=start_date, end=end_date, interval="1D")
        return _normalize_market(df)
    except Exception:
        pass
    try:
        from vnstock import stock_historical_data
        df = stock_historical_data(symbol="VNINDEX", start_date=start_date, end_date=end_date, resolution="1D")
        return _normalize_market(df)
    except Exception:
        return pd.DataFrame()

def make_market_fallback(start_date="2024-01-01"):
    dates = pd.bdate_range(start=start_date, end=pd.Timestamp.today().normalize())
    rng = np.random.default_rng(42)
    level = 1150 + np.cumsum(rng.normal(0.9, 7.5, len(dates)))
    out = pd.DataFrame({"date":dates,"vnindex":level.round(2),"liquidity":rng.normal(22000,4500,len(dates)).clip(8000,40000).round(0)})
    return _normalize_market(out)

def merge_market_sources(sheet_market=None, prefer_auto=True):
    auto = load_vnindex_auto() if prefer_auto else pd.DataFrame()
    if auto is not None and not auto.empty and auto["vnindex"].notna().sum() > 10:
        return auto
    sheet = _normalize_market(sheet_market) if sheet_market is not None and not sheet_market.empty else pd.DataFrame()
    if not sheet.empty:
        return sheet
    return make_market_fallback()

def market_ceo_signal(market_df):
    if market_df is None or market_df.empty:
        return {"latest_vnindex":0,"latest_return":0,"signal":"No data","action":"Check market data connection"}
    d = market_df.dropna(subset=["vnindex"]).sort_values("date")
    if d.empty:
        return {"latest_vnindex":0,"latest_return":0,"signal":"No data","action":"Check market data connection"}
    last = d.iloc[-1]
    ret = float(last.get("vnindex_return_pct",0) or 0)
    flag = str(last.get("market_risk_flag", "Normal"))
    if "Red" in flag: action = "Reduce aggressive margin push; prioritize client risk calls and cash management."
    elif "Yellow" in flag: action = "Monitor leveraged clients; focus on advisory and selective trading ideas."
    elif "Green" in flag: action = "Increase brokerage campaign; prioritize active clients and margin-qualified accounts."
    else: action = "Maintain balanced sales plan; focus on quality revenue and client activation."
    return {"latest_vnindex":round(float(last["vnindex"]),2),"latest_return":round(ret,2),"signal":flag,"action":action}
