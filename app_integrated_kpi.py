
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from market_data_connector import merge_market_sources, market_ceo_signal
from kpi_engine import calculate_kpi_score, ceo_summary, build_reward_table

st.set_page_config(
    page_title="VNDIRECT BI Enterprise + KPI Engine",
    page_icon="📊",
    layout="wide",
)

AUTHOR = "Le Hoang Quan"

st.sidebar.title("VNDIRECT BI")
st.sidebar.caption(f"Author: {AUTHOR}")
st.sidebar.markdown("---")

def try_read_csv(paths):
    for p in paths:
        try:
            return pd.read_csv(p)
        except Exception:
            pass
    return None

@st.cache_data
def load_local_data():
    # Package fallback mode: load local csv if available; otherwise create demo data.
    business = try_read_csv(["data/business_daily.csv", "business_daily.csv"])
    rm = try_read_csv(["data/rm_kpi.csv", "rm_kpi.csv"])
    client = try_read_csv(["data/client_master.csv", "client_master.csv"])
    market = try_read_csv(["data/market_data.csv", "market_data.csv"])
    margin = try_read_csv(["data/market_margin.csv", "market_margin.csv"])
    targets = try_read_csv(["data/targets.csv", "targets.csv"])

    if business is None:
        dates = pd.date_range("2024-01-01", periods=180, freq="B")
        business = pd.DataFrame({
            "date": dates,
            "revenue": np.random.normal(5.8, 0.8, len(dates)).round(2),
            "profit": np.random.normal(1.0, 0.2, len(dates)).round(2),
            "fee_income": np.random.normal(3.8, 0.6, len(dates)).round(2),
            "margin_income": np.random.normal(2.2, 0.4, len(dates)).round(2),
            "new_accounts": np.random.randint(500, 1200, len(dates)),
            "active_clients": np.random.randint(9000, 13000, len(dates)),
            "trading_value": np.random.randint(90000, 130000, len(dates)),
        })

    if rm is None:
        rm = pd.DataFrame({
            "rm": [f"RM{i:02d}" for i in range(1, 31)],
            "revenue": np.random.uniform(1.2, 4.5, 30).round(2),
            "margin": np.random.uniform(0.6, 3.0, 30).round(2),
            "new_accounts": np.random.randint(20, 90, 30),
            "active_clients": np.random.randint(130, 420, 30),
            "compliance_issue": np.random.choice([0, 0, 0, 1], 30),
            "churn_clients": np.random.randint(1, 15, 30),
        })

    if client is None:
        client = pd.DataFrame({
            "client_id": [f"C{i:04d}" for i in range(1, 501)],
            "segment": np.random.choice(["Mass", "Affluent", "HNW", "Dormant"], 500, p=[0.55, 0.25, 0.10, 0.10]),
            "nav": np.random.lognormal(1.2, 0.8, 500).round(2),
            "trading_value": np.random.lognormal(1.0, 0.9, 500).round(2),
            "margin_balance": np.random.lognormal(0.5, 0.8, 500).round(2),
            "status": np.random.choice(["Active", "Dormant", "Watch"], 500, p=[0.72, 0.18, 0.10]),
        })

    if market is None:
        dates = pd.date_range("2024-01-01", periods=180, freq="B")
        market = pd.DataFrame({
            "date": dates,
            "vnindex": 1100 + np.cumsum(np.random.normal(0.8, 8, len(dates))).round(2),
            "liquidity": np.random.randint(12000, 28000, len(dates)),
        })

    if margin is None:
        margin = pd.DataFrame({
            "date": ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4", "2025-Q1", "2025-Q2", "2025-Q3"],
            "total_margin_market": [210000, 230000, 255000, 280000, 300000, 330000, 370000],
            "margin_growth": [0.05, 0.095, 0.109, 0.098, 0.071, 0.100, 0.121],
            "broker_margin_share": [0.07, 0.071, 0.073, 0.075, 0.076, 0.078, 0.08],
        })

    if targets is None:
        targets = pd.DataFrame({
            "metric": ["revenue", "profit", "new_accounts", "active_clients"],
            "target": [1400, 300, 150000, 12000],
        })

    return business, rm, client, market, margin, targets

business, rm, client, market_sheet, margin, targets = load_local_data()

# Market Data PRO:
# Prefer automatic VNINDEX via vnstock. If unavailable, fallback to Google Sheet/local CSV.
market = merge_market_sources(market_sheet, prefer_auto=True)
market_signal = market_ceo_signal(market)

# Date cleanup
for df in [business, market]:
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

st.title("VNDIRECT Business Intelligence & KPI Engine")
st.caption(f"Author: {AUTHOR}")

st.sidebar.header("KPI Weighting")
w_revenue = st.sidebar.slider("Revenue", 0.0, 1.0, 0.30, 0.05)
w_margin = st.sidebar.slider("Margin", 0.0, 1.0, 0.25, 0.05)
w_active = st.sidebar.slider("Active clients", 0.0, 1.0, 0.20, 0.05)
w_new = st.sidebar.slider("New accounts", 0.0, 1.0, 0.15, 0.05)
w_quality = st.sidebar.slider("Quality / compliance", 0.0, 1.0, 0.10, 0.05)
total_w = w_revenue + w_margin + w_active + w_new + w_quality
weights = {
    "revenue": w_revenue / total_w,
    "margin": w_margin / total_w,
    "active_clients": w_active / total_w,
    "new_accounts": w_new / total_w,
    "quality": w_quality / total_w,
}

kpi = calculate_kpi_score(rm, weights)
summary = ceo_summary(kpi)

latest_business = business.sort_values("date").tail(30) if "date" in business.columns else business.tail(30)
monthly_revenue = float(pd.to_numeric(latest_business.get("revenue", 0), errors="coerce").fillna(0).sum())
monthly_profit = float(pd.to_numeric(latest_business.get("profit", 0), errors="coerce").fillna(0).sum())
new_accounts = int(pd.to_numeric(latest_business.get("new_accounts", 0), errors="coerce").fillna(0).sum())
active_clients = int(pd.to_numeric(latest_business.get("active_clients", 0), errors="coerce").fillna(0).iloc[-1]) if "active_clients" in latest_business.columns and len(latest_business) else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("30D Revenue", f"{monthly_revenue:,.1f}")
c2.metric("30D Profit", f"{monthly_profit:,.1f}")
c3.metric("New Accounts", f"{new_accounts:,.0f}")
c4.metric("Active Clients", f"{active_clients:,.0f}")
c5.metric("Avg RM KPI", f"{summary['avg_score']:,.1f}")

m1, m2, m3 = st.columns(3)
m1.metric("VNINDEX latest", f"{market_signal['latest_vnindex']:,.2f}")
m2.metric("VNINDEX daily return", f"{market_signal['latest_return']:,.2f}%")
m3.metric("Market signal", market_signal["signal"])

tabs = st.tabs([
    "CEO Action",
    "Business Dashboard",
    "KPI Engine",
    "RM Ranking",
    "Reward Policy",
    "Client Opportunity",
    "Market & Margin",
    "Data"
])

with tabs[0]:
    st.subheader("CEO Action Summary")
    st.info(
        f"Top RM: {summary['top_rm']} | Bottom RM: {summary['bottom_rm']} | "
        f"Watchlist: {summary['watchlist_count']} | Action Required: {summary['action_required_count']}"
    )

    actions = []
    if summary["watchlist_count"] > 0:
        actions.append("Tổ chức weekly pipeline review cho nhóm C - Watchlist.")
    if summary["action_required_count"] > 0:
        actions.append("Áp dụng Performance Improvement Plan cho nhóm D.")
    if "status" in client.columns:
        dormant = int((client["status"].astype(str).str.lower() == "dormant").sum())
        if dormant > 0:
            actions.append(f"Kích hoạt lại {dormant} khách hàng dormant bằng campaign phí giao dịch/margin.")
    if monthly_profit / monthly_revenue < 0.20 if monthly_revenue else False:
        actions.append("Rà soát chất lượng doanh thu vì biên lợi nhuận 30 ngày thấp hơn 20%.")

    if not actions:
        actions = ["Duy trì đà tăng trưởng; ưu tiên phân bổ khách hàng HNW cho nhóm RM A."]
    actions.append("Market action: " + market_signal["action"])

    for a in actions:
        st.write("✅ " + a)

with tabs[1]:
    st.subheader("Business Dashboard")
    if "date" in business.columns:
        fig = px.line(business.sort_values("date"), x="date", y=[c for c in ["revenue", "profit", "fee_income", "margin_income"] if c in business.columns])
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(business.tail(50), use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("KPI Engine Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Average KPI", summary["avg_score"])
    c2.metric("Top RM", summary["top_rm"])
    c3.metric("Watchlist", summary["watchlist_count"])
    c4.metric("Action Required", summary["action_required_count"])
    fig = px.bar(kpi.sort_values("kpi_score", ascending=False), x="rm", y="kpi_score", color="performance_band")
    st.plotly_chart(fig, use_container_width=True)

with tabs[3]:
    st.subheader("RM Ranking")
    cols = ["rm", "rank", "kpi_score", "performance_band", "revenue", "margin", "new_accounts", "active_clients", "score_quality", "recommendation"]
    st.dataframe(kpi[[c for c in cols if c in kpi.columns]], use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Reward / Penalty Policy")
    st.dataframe(build_reward_table(kpi), use_container_width=True, hide_index=True)

with tabs[5]:
    st.subheader("Client Opportunity Engine")
    d = client.copy()
    for col in ["nav", "trading_value", "margin_balance"]:
        if col not in d.columns:
            d[col] = 0
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0)

    d["opportunity"] = np.select(
        [
            (d["nav"] >= d["nav"].quantile(0.75)) & (d["trading_value"] <= d["trading_value"].quantile(0.40)),
            (d["margin_balance"] <= d["margin_balance"].quantile(0.30)) & (d["trading_value"] >= d["trading_value"].quantile(0.60)),
            d.get("status", "").astype(str).str.lower().eq("dormant") if "status" in d.columns else False,
        ],
        [
            "High NAV - low trading: assign senior RM",
            "Margin upsell candidate",
            "Dormant reactivation",
        ],
        default="Maintain service",
    )
    st.dataframe(d.sort_values("nav", ascending=False).head(100), use_container_width=True, hide_index=True)

with tabs[6]:
    st.subheader("Market Data PRO")
    st.info(
        f"VNINDEX latest: {market_signal['latest_vnindex']:,.2f} | "
        f"Daily return: {market_signal['latest_return']:,.2f}% | "
        f"Signal: {market_signal['signal']} | "
        f"Action: {market_signal['action']}"
    )

    if "date" in market.columns:
        chart_cols = [c for c in ["vnindex", "ma20", "ma60"] if c in market.columns]
        if chart_cols:
            fig = px.line(market.sort_values("date"), x="date", y=chart_cols, title="VNINDEX with MA20 / MA60")
            st.plotly_chart(fig, use_container_width=True)

        if "vnindex_return_pct" in market.columns:
            fig2 = px.bar(
                market.sort_values("date").tail(60),
                x="date",
                y="vnindex_return_pct",
                title="VNINDEX Daily Return - Last 60 Sessions"
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Market Data Table")
    st.dataframe(market.tail(120), use_container_width=True, hide_index=True)

    st.subheader("Market Margin")
    st.caption("Margin toàn thị trường thường không có API public ổn định; cập nhật qua Google Sheet `market_margin`.")
    st.dataframe(margin, use_container_width=True, hide_index=True)

with tabs[7]:
    st.subheader("Raw Data")
    sub = st.selectbox("Dataset", ["business", "rm", "client", "market", "margin", "targets"])
    data_map = {
        "business": business,
        "rm": rm,
        "client": client,
        "market": market,
        "margin": margin,
        "targets": targets,
    }
    st.dataframe(data_map[sub], use_container_width=True, hide_index=True)

st.markdown("---")
st.caption(f"© {AUTHOR} | VNDIRECT BI Enterprise KPI Integrated")
