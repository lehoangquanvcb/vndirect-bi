# VNDIRECT BI Enterprise KPI Market Current

Main file for Streamlit Cloud:

```text
app_integrated_kpi.py
```

This version fixes the chart stopping at Sep 2024. Demo business data now extends to the current business day. If Streamlit Secrets are configured, the app reads Google Sheets first.

For real business data, update Google Sheet `business_daily`. For market data, the app attempts VNINDEX auto fetch through `vnstock`, then falls back to Google Sheet/local/demo.
