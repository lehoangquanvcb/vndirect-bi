import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from market_data_connector import merge_market_sources, market_ceo_signal
from kpi_engine import calculate_kpi_score, ceo_summary, build_reward_table

st.set_page_config(page_title="VNDIRECT BI Enterprise + KPI Engine", page_icon="📊", layout="wide")
AUTHOR = "Le Hoang Quan"

def clean_columns(df):
    if df is None or df.empty: return df
    out = df.copy(); out.columns = [str(c).strip() for c in out.columns]; return out

def read_google_sheet():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        if "gcp_service_account" not in st.secrets: return None
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sheet_name = "VNDIRECT_BI_DATA"
        sheet_id = ""
        if "google_sheet" in st.secrets:
            sheet_name = st.secrets["google_sheet"].get("sheet_name", sheet_name)
            sheet_id = st.secrets["google_sheet"].get("sheet_id", "")
        spreadsheet = client.open_by_key(sheet_id) if sheet_id else client.open(sheet_name)
        def tab(name):
            try: return clean_columns(pd.DataFrame(spreadsheet.worksheet(name).get_all_records()))
            except Exception: return pd.DataFrame()
        return {"business":tab("business_daily"),"rm":tab("rm_kpi"),"client":tab("client_master"),"market":tab("market_data"),"margin":tab("market_margin"),"targets":tab("targets")}
    except Exception as e:
        st.sidebar.warning(f"Không đọc được Google Sheet, dùng local/demo. Lỗi: {e}")
        return None

def standardize_business(df):
    if df is None or df.empty: return pd.DataFrame()
    out = clean_columns(df).rename(columns={"revenue_bn_vnd":"revenue","profit_bn_vnd":"profit","brokerage_fee_bn_vnd":"fee_income","margin_interest_bn_vnd":"margin_income","trading_value_bn_vnd":"trading_value"})
    if "date" not in out.columns: out["date"] = pd.NaT
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ["revenue","profit","fee_income","margin_income","new_accounts","active_clients","trading_value"]:
        if c not in out.columns: out[c] = 0
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
    return out.dropna(subset=["date"]).sort_values("date")

def standardize_rm(df):
    if df is None or df.empty: return pd.DataFrame()
    out = clean_columns(df).rename(columns={"rm_name":"rm","revenue_bn_vnd":"revenue","brokerage_revenue_bn":"revenue","margin_balance_bn_vnd":"margin","margin_interest_bn_vnd":"margin"})
    if "rm" not in out.columns: out["rm"] = [f"RM{i+1:02d}" for i in range(len(out))]
    for c in ["revenue","margin","new_accounts","active_clients"]:
        if c not in out.columns: out[c] = 0
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
    if "compliance_issue" not in out.columns: out["compliance_issue"] = 0
    if "churn_clients" not in out.columns: out["churn_clients"] = 0
    return out

def standardize_client(df):
    if df is None or df.empty: return pd.DataFrame()
    out = clean_columns(df).rename(columns={"nav_bn_vnd":"nav","monthly_trading_value_bn_vnd":"trading_value","margin_balance_bn_vnd":"margin_balance"})
    for c in ["nav","trading_value","margin_balance"]:
        if c not in out.columns: out[c] = 0
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
    if "status" not in out.columns: out["status"] = "Active"
    return out

def demo_business_to_today():
    dates = pd.bdate_range("2024-01-01", pd.Timestamp.today().normalize())
    rng = np.random.default_rng(42); trend = np.linspace(0,1,len(dates))
    return pd.DataFrame({
        "date":dates,
        "revenue":(5.6+1.2*trend+rng.normal(0,0.7,len(dates))).clip(2.5).round(2),
        "profit":(1.0+0.35*trend+rng.normal(0,0.18,len(dates))).clip(0.2).round(2),
        "fee_income":(3.7+0.8*trend+rng.normal(0,0.55,len(dates))).clip(1.2).round(2),
        "margin_income":(2.1+0.45*trend+rng.normal(0,0.35,len(dates))).clip(0.6).round(2),
        "new_accounts":rng.integers(500,1250,len(dates)),
        "active_clients":rng.integers(9500,14500,len(dates)),
        "trading_value":rng.integers(85000,145000,len(dates)),
    })

@st.cache_data(ttl=600)
def load_data():
    gs = read_google_sheet()
    if gs is not None and not gs["business"].empty:
        return (standardize_business(gs["business"]), standardize_rm(gs["rm"]), standardize_client(gs["client"]), gs["market"], gs["margin"], gs["targets"], "Google Sheets")
    business = demo_business_to_today()
    rng = np.random.default_rng(7)
    rm = pd.DataFrame({"rm":[f"RM{i:02d}" for i in range(1,31)],"revenue":rng.uniform(1.2,4.5,30).round(2),"margin":rng.uniform(0.6,3.0,30).round(2),"new_accounts":rng.integers(20,90,30),"active_clients":rng.integers(130,420,30),"compliance_issue":rng.choice([0,0,0,1],30),"churn_clients":rng.integers(1,15,30)})
    client = pd.DataFrame({"client_id":[f"C{i:04d}" for i in range(1,501)],"segment":rng.choice(["Mass","Affluent","HNW","Dormant"],500,p=[.55,.25,.1,.1]),"nav":rng.lognormal(1.2,.8,500).round(2),"trading_value":rng.lognormal(1.0,.9,500).round(2),"margin_balance":rng.lognormal(.5,.8,500).round(2),"status":rng.choice(["Active","Dormant","Watch"],500,p=[.72,.18,.1])})
    margin = pd.DataFrame({"date":["2024-Q1","2024-Q2","2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3"],"total_margin_market":[210000,230000,255000,280000,300000,330000,370000],"margin_growth":[.05,.095,.109,.098,.071,.10,.121],"broker_margin_share":[.07,.071,.073,.075,.076,.078,.08]})
    targets = pd.DataFrame({"metric":["revenue","profit","new_accounts","active_clients"],"target":[1400,300,150000,12000]})
    return business, rm, client, pd.DataFrame(), margin, targets, "Demo extended to today"

business, rm, client, market_sheet, margin, targets, source = load_data()
market = merge_market_sources(market_sheet, prefer_auto=True)
market_signal = market_ceo_signal(market)

st.sidebar.title("VNDIRECT BI")
st.sidebar.caption(f"Author: {AUTHOR}")
st.sidebar.success(f"Data source: {source}")
st.sidebar.caption(f"Business data to: {business['date'].max().date() if not business.empty else 'N/A'}")
st.sidebar.header("KPI Weighting")
w_revenue = st.sidebar.slider("Revenue",0.0,1.0,0.30,0.05); w_margin=st.sidebar.slider("Margin",0.0,1.0,0.25,0.05); w_active=st.sidebar.slider("Active clients",0.0,1.0,0.20,0.05); w_new=st.sidebar.slider("New accounts",0.0,1.0,0.15,0.05); w_quality=st.sidebar.slider("Quality / compliance",0.0,1.0,0.10,0.05)
total_w = w_revenue+w_margin+w_active+w_new+w_quality
weights={"revenue":w_revenue/total_w,"margin":w_margin/total_w,"active_clients":w_active/total_w,"new_accounts":w_new/total_w,"quality":w_quality/total_w}
kpi=calculate_kpi_score(rm,weights); summary=ceo_summary(kpi)
latest_business=business.sort_values("date").tail(30)
monthly_revenue=float(latest_business["revenue"].sum()); monthly_profit=float(latest_business["profit"].sum()); new_accounts=int(latest_business["new_accounts"].sum()); active_clients=int(latest_business["active_clients"].iloc[-1])

st.title("VNDIRECT Business Intelligence & KPI Engine")
st.caption(f"Author: {AUTHOR}")
c1,c2,c3,c4,c5=st.columns(5)
c1.metric("30D Revenue",f"{monthly_revenue:,.1f}"); c2.metric("30D Profit",f"{monthly_profit:,.1f}"); c3.metric("New Accounts",f"{new_accounts:,.0f}"); c4.metric("Active Clients",f"{active_clients:,.0f}"); c5.metric("Avg RM KPI",f"{summary['avg_score']:,.1f}")
m1,m2,m3=st.columns(3); m1.metric("VNINDEX latest",f"{market_signal['latest_vnindex']:,.2f}"); m2.metric("VNINDEX daily return",f"{market_signal['latest_return']:,.2f}%"); m3.metric("Market signal",market_signal["signal"])

tabs=st.tabs(["CEO Action","Business Dashboard","KPI Engine","RM Ranking","Reward Policy","Client Opportunity","Market & Margin","Data"])
with tabs[0]:
    st.subheader("CEO Action Summary")
    st.info(f"Top RM: {summary['top_rm']} | Bottom RM: {summary['bottom_rm']} | Watchlist: {summary['watchlist_count']} | Action Required: {summary['action_required_count']}")
    actions=[]
    if summary["watchlist_count"]>0: actions.append("Tổ chức weekly pipeline review cho nhóm C - Watchlist.")
    if summary["action_required_count"]>0: actions.append("Áp dụng Performance Improvement Plan cho nhóm D.")
    dormant=int((client["status"].astype(str).str.lower()=="dormant").sum()) if "status" in client.columns else 0
    if dormant>0: actions.append(f"Kích hoạt lại {dormant} khách hàng dormant bằng campaign phí giao dịch/margin.")
    actions.append("Market action: "+market_signal["action"])
    for a in actions: st.write("✅ "+a)
with tabs[1]:
    st.subheader("Business Dashboard")
    st.caption(f"Dữ liệu đang chạy đến: {business['date'].max().date()}")
    fig=px.line(business.sort_values("date"),x="date",y=["revenue","profit","fee_income","margin_income"],title="Business Performance Through Current Date")
    st.plotly_chart(fig,use_container_width=True)
    st.dataframe(business.tail(100),use_container_width=True,hide_index=True)
with tabs[2]:
    st.subheader("KPI Engine Overview")
    st.plotly_chart(px.bar(kpi.sort_values("kpi_score",ascending=False),x="rm",y="kpi_score",color="performance_band"),use_container_width=True)
with tabs[3]:
    st.subheader("RM Ranking")
    cols=["rm","rank","kpi_score","performance_band","revenue","margin","new_accounts","active_clients","score_quality","recommendation"]
    st.dataframe(kpi[[c for c in cols if c in kpi.columns]],use_container_width=True,hide_index=True)
with tabs[4]:
    st.subheader("Reward / Penalty Policy")
    st.dataframe(build_reward_table(kpi),use_container_width=True,hide_index=True)
with tabs[5]:
    st.subheader("Client Opportunity Engine")
    d=client.copy()
    d["opportunity"]=np.select([(d["nav"]>=d["nav"].quantile(.75))&(d["trading_value"]<=d["trading_value"].quantile(.4)),(d["margin_balance"]<=d["margin_balance"].quantile(.3))&(d["trading_value"]>=d["trading_value"].quantile(.6)),d["status"].astype(str).str.lower().eq("dormant")],["High NAV - low trading: assign senior RM","Margin upsell candidate","Dormant reactivation"],default="Maintain service")
    st.dataframe(d.sort_values("nav",ascending=False).head(100),use_container_width=True,hide_index=True)
with tabs[6]:
    st.subheader("Market Data PRO")
    st.info(f"VNINDEX latest: {market_signal['latest_vnindex']:,.2f} | Daily return: {market_signal['latest_return']:,.2f}% | Signal: {market_signal['signal']} | Action: {market_signal['action']}")
    if "date" in market.columns:
        st.plotly_chart(px.line(market.sort_values("date"),x="date",y=[c for c in ["vnindex","ma20","ma60"] if c in market.columns],title="VNINDEX with MA20 / MA60"),use_container_width=True)
        if "vnindex_return_pct" in market.columns: st.plotly_chart(px.bar(market.sort_values("date").tail(60),x="date",y="vnindex_return_pct",title="VNINDEX Daily Return - Last 60 Sessions"),use_container_width=True)
    st.subheader("Market Data Table"); st.dataframe(market.tail(120),use_container_width=True,hide_index=True)
    st.subheader("Market Margin"); st.dataframe(margin,use_container_width=True,hide_index=True)
with tabs[7]:
    st.subheader("Raw Data")
    sub=st.selectbox("Dataset",["business","rm","client","market","margin","targets"])
    st.dataframe({"business":business,"rm":rm,"client":client,"market":market,"margin":margin,"targets":targets}[sub],use_container_width=True,hide_index=True)
st.markdown("---"); st.caption(f"© {AUTHOR} | VNDIRECT BI Enterprise KPI Integrated")
