
# Market Data PRO Upgrade - VNDIRECT BI

Author: Le Hoang Quan

## What changed

This package adds `market_data_connector.py` and upgrades `app_integrated_kpi.py`.

## Market data logic

Priority order:

1. Try automatic VNINDEX from `vnstock`
2. If unavailable, fallback to Google Sheet / local CSV `market_data`
3. If still unavailable, use fallback demo data so the app does not crash

## New market columns

- date
- vnindex
- liquidity
- vnindex_return_pct
- ma20
- ma60
- volatility_20d
- trend_signal
- market_risk_flag

## Streamlit entry point

Use:

```bash
streamlit run app_integrated_kpi.py
```

On Streamlit Cloud:

```text
Main file path: app_integrated_kpi.py
```

## Important note

VNINDEX can be pulled automatically via `vnstock`, but total market margin should still be maintained in Google Sheet `market_margin`, because there is no stable public API for market-wide margin balances.
