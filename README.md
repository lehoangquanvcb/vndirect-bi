# VNDIRECT BI Enterprise Dashboard

Author: **Le Hoang Quan**

This package contains a Streamlit dashboard for CEO advisory, business performance management, RM KPI scoring, client opportunity, early warning, and market/margin monitoring.

## Files

- `app.py`: Streamlit application
- `requirements.txt`: Python dependencies
- `data/`: demo CSV fallback data
- `VNDIRECT_BI_Google_Sheet_Template_Le_Hoang_Quan.xlsx`: Google Sheets template
- `secrets_template.toml`: template for Streamlit Secrets

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Google Sheets setup

1. Upload `VNDIRECT_BI_Google_Sheet_Template_Le_Hoang_Quan.xlsx` to Google Drive.
2. Open it with Google Sheets.
3. Rename the Google Sheet to `VNDIRECT_BI_DATA`.
4. Create a Google Cloud service account, enable Google Sheets API and Drive API.
5. Share the Google Sheet with the service account email as Editor.
6. In Streamlit Cloud, paste the content from `secrets_template.toml` into App settings -> Secrets.
7. Select data source `Google Sheets - Service Account` in the sidebar.

## Market connector

The app has an optional `Auto-fetch VNINDEX via vnstock` toggle. If it works in your environment, VNINDEX will be loaded automatically. Business, KPI, client, and margin data remain managed in Google Sheets.

## Notes

Do not upload your real service-account JSON or private key to GitHub.
