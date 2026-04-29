
# VNDIRECT BI Enterprise + KPI Engine

Author: Le Hoang Quan

## Main apps

- `app.py`: original dashboard app from previous package.
- `app_integrated_kpi.py`: upgraded integrated app with KPI Engine, CEO Action, RM Ranking, Reward Policy, Client Opportunity and Market & Margin.

## Recommended Streamlit entry point

Use:

```bash
streamlit run app_integrated_kpi.py
```

On Streamlit Cloud, set:

```text
Main file path: app_integrated_kpi.py
```

## Files added

- `kpi_engine.py`
- `app_integrated_kpi.py`
- `README_KPI_INTEGRATED.md`

## KPI Engine logic

Score components:

- Revenue: 30%
- Margin: 25%
- Active clients: 20%
- New accounts: 15%
- Quality/compliance: 10%

The app allows you to change weights from the sidebar.

## Expected rm_kpi columns

Required:

- rm
- revenue
- margin
- new_accounts
- active_clients

Optional:

- compliance_issue
- churn_clients
- trading_value
- client_count
- conversion_rate

## Deploy

1. Upload all files to GitHub.
2. Deploy to Streamlit Cloud.
3. Select `app_integrated_kpi.py` as the main file.
4. Send the Streamlit link to your CEO.
