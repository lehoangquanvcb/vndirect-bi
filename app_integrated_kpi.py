import streamlit as st
import pandas as pd
import plotly.express as px

from decision_engine import generate_ceo_action

st.set_page_config(layout="wide")

st.title("📊 VNDIRECT BI Dashboard - Le Hoang Quan")

# =====================
# LOAD DATA (NO GOOGLE CLOUD)
# =====================
@st.cache_data
def load_market_data():
    try:
        df = pd.read_csv(
            "https://raw.githubusercontent.com/USERNAME/vndirect-market-data/main/market_data_real.csv"
        )
        df["date"] = pd.to_datetime(df["date"])
        source = "GitHub (REAL)"
    except:
        df = pd.read_csv("data/market_data.csv")
        df["date"] = pd.to_datetime(df["date"])
        source = "LOCAL (fallback)"

    return df, source

market_df, source = load_market_data()

st.caption(f"Data source: {source}")

# =====================
# CEO ACTION
# =====================
actions = generate_ceo_action(market_df)

st.header("🚨 CEO ACTION CENTER")

for a in actions:
    st.warning(a)

# =====================
# MARKET CHART
# =====================
st.subheader("VNINDEX")

fig = px.line(market_df, x="date", y=["vnindex", "ma20"])
st.plotly_chart(fig, use_container_width=True)

# =====================
# TABLE
# =====================
st.subheader("Market Data")

st.dataframe(market_df.tail(50), use_container_width=True)
