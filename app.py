import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

AUTHOR = "Le Hoang Quan"
APP_TITLE = "VNDIRECT Business Intelligence Dashboard"

st.set_page_config(page_title=APP_TITLE, page_icon="📈", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.1rem; padding-bottom: 2rem;}
.author-badge {background:#fff4e8;color:#9a4d00;padding:8px 12px;border-radius:999px;font-weight:700;display:inline-block;margin-bottom:8px}
.ceo-box {background:#111827;color:white;border-radius:18px;padding:18px;margin:8px 0;}
.warning-box {background:#fff7ed;border-left:6px solid #f97316;border-radius:12px;padding:14px;margin:8px 0;}
.good-box {background:#ecfdf5;border-left:6px solid #10b981;border-radius:12px;padding:14px;margin:8px 0;}
.bad-box {background:#fef2f2;border-left:6px solid #ef4444;border-radius:12px;padding:14px;margin:8px 0;}
.info-box {background:#eff6ff;border-left:6px solid #3b82f6;border-radius:12px;padding:14px;margin:8px 0;}
.footer {font-size:13px;color:#6b7280;text-align:center;margin-top:30px;}
@media (max-width: 768px) {.block-container {padding-left:.6rem; padding-right:.6rem;} h1{font-size:1.45rem;} h2{font-size:1.15rem;}}
</style>
""", unsafe_allow_html=True)

REQUIRED_SHEETS = ["business_daily", "rm_kpi", "client_master", "market_data", "market_margin", "targets_kpi", "kpi_weights", "ceo_action_rules"]

@st.cache_data
def read_local():
    b = pd.read_csv("data/business_daily.csv", parse_dates=["date"])
    r = pd.read_csv("data/rm_kpi.csv", parse_dates=["date"])
    c = pd.read_csv("data/client_master.csv")
    m = pd.read_csv("data/market_data.csv", parse_dates=["date"])
    mm = pd.DataFrame()
    t = pd.DataFrame()
    w = pd.DataFrame()
    rules = pd.DataFrame()
    return b, r, c, m, mm, t, w, rules

@st.cache_data(ttl=600)
def read_google_workbook(sheet_name_or_id: str, by_id: bool = False):
    import gspread
    from google.oauth2.service_account import Credentials
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_name_or_id) if by_id else gc.open(sheet_name_or_id)
    out = {}
    for tab in REQUIRED_SHEETS:
        try:
            ws = sh.worksheet(tab)
            out[tab] = pd.DataFrame(ws.get_all_records())
        except Exception:
            out[tab] = pd.DataFrame()
    return out

@st.cache_data(ttl=1800)
def fetch_vnindex_vnstock(days: int = 365):
    try:
        from vnstock import Quote
        end = date.today()
        start = end - timedelta(days=days)
        q = Quote(symbol="VNINDEX", source="VCI")
        df = q.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), interval="1D")
        df.columns = [str(c).lower() for c in df.columns]
        if "time" in df.columns:
            df = df.rename(columns={"time":"date"})
        if "close" in df.columns:
            df = df.rename(columns={"close":"vnindex"})
        if "value" in df.columns:
            df = df.rename(columns={"value":"market_turnover_trn"})
        keep = [c for c in ["date", "vnindex", "volume", "market_turnover_trn"] if c in df.columns]
        df = df[keep].copy()
        df["date"] = pd.to_datetime(df["date"])
        if "market_turnover_trn" in df.columns:
            df["market_turnover_trn"] = pd.to_numeric(df["market_turnover_trn"], errors="coerce") / 1_000_000_000_000
        return df
    except Exception as e:
        return pd.DataFrame({"connector_error": [str(e)]})

def normalize_dates(*dfs):
    out=[]
    for df in dfs:
        if isinstance(df, pd.DataFrame) and not df.empty and "date" in df.columns:
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        out.append(df)
    return out

def kpi_score(df, weights=None):
    x = df.copy()
    if x.empty:
        return x
    default = {"brokerage_revenue":0.30, "margin_balance":0.25, "clients_new_accounts":0.25, "quality_compliance":0.20}
    if weights is not None and not weights.empty and {"kpi_component","weight"}.issubset(weights.columns):
        w = dict(zip(weights["kpi_component"], pd.to_numeric(weights["weight"], errors="coerce")))
        default.update({k:v for k,v in w.items() if pd.notna(v)})
    def norm(s):
        s = pd.to_numeric(s, errors="coerce").fillna(0)
        if s.max() == s.min():
            return pd.Series([50]*len(s), index=s.index)
        return 100*(s-s.min())/(s.max()-s.min())
    revenue = norm(x["brokerage_revenue_bn"])
    margin = norm(x["margin_balance_bn"])
    clients = norm(x["active_clients"] + 0.8*x["new_accounts"])
    quality = 100 - norm(x["compliance_incidents"]*25 + x["client_churn_rate"]*100)
    x["risk_adjusted_score"] = default["brokerage_revenue"]*revenue + default["margin_balance"]*margin + default["clients_new_accounts"]*clients + default["quality_compliance"]*quality
    x["rating"] = pd.cut(x["risk_adjusted_score"], bins=[-1,60,75,88,101], labels=["C - Improve", "B - Good", "A - Strong", "S - Excellent"])
    return x

def ceo_actions(b, r, c, market, weights=None):
    actions=[]
    if b.empty or r.empty or c.empty:
        return ["Thiếu dữ liệu đầu vào. Kiểm tra các sheet business_daily, rm_kpi, client_master."]
    monthly = b.groupby("date", as_index=False).sum(numeric_only=True).sort_values("date")
    if len(monthly) >= 2:
        cur, prev = monthly.iloc[-1], monthly.iloc[-2]
        rev_growth = cur.revenue_bn/prev.revenue_bn - 1 if prev.revenue_bn else 0
        active_growth = cur.active_clients/prev.active_clients - 1 if prev.active_clients else 0
        if rev_growth < -0.05:
            actions.append("Doanh thu giảm so với kỳ trước: kích hoạt chiến dịch giao dịch lại cho nhóm khách hàng active nhưng giảm tần suất.")
        else:
            actions.append("Doanh thu giữ nhịp tích cực: ưu tiên mở rộng nhóm khách NAV cao và tần suất giao dịch ổn định.")
        if active_growth < 0:
            actions.append("Khách hàng active giảm: giao chỉ tiêu tái kích hoạt theo RM, đo bằng số khách quay lại giao dịch trong 14 ngày.")
    dormant = c[(c.days_since_last_trade > 90) & (c.nav_mn > 300)] if {"days_since_last_trade","nav_mn"}.issubset(c.columns) else pd.DataFrame()
    margin_opp = c[(c.nav_mn > 1000) & (c.margin_balance_mn < 0.1*c.nav_mn) & (c.risk_level != "High")] if {"nav_mn","margin_balance_mn","risk_level"}.issubset(c.columns) else pd.DataFrame()
    if len(dormant) > 0:
        actions.append(f"Có {len(dormant):,} khách dormant NAV > 300 triệu: tạo chiến dịch RM gọi lại + ưu đãi phí có điều kiện.")
    if len(margin_opp) > 0:
        actions.append(f"Có {len(margin_opp):,} khách tiềm năng margin: ưu tiên tư vấn margin có kiểm soát, không đẩy vào nhóm rủi ro cao.")
    latest_rm = r[r.date == r.date.max()].pipe(kpi_score, weights).sort_values("risk_adjusted_score")
    actions.append("3 RM cần coaching ngay: " + ", ".join(latest_rm.head(3).rm_name.astype(str).tolist()))
    if not market.empty and "vnindex" in market.columns and len(market.dropna(subset=["vnindex"])) >= 2:
        mk = market.dropna(subset=["vnindex"]).sort_values("date")
        chg = mk.iloc[-1].vnindex / mk.iloc[-2].vnindex - 1
        if chg < -0.03:
            actions.append("VNINDEX giảm mạnh: ưu tiên bảo vệ khách margin cao, giảm campaign margin đại trà, tăng tư vấn quản trị rủi ro.")
        elif chg > 0.03:
            actions.append("Thị trường thuận lợi: đẩy gói giao dịch cho khách Affluent/HNW đang có tiền chờ giải ngân.")
    return actions

def opportunity_engine(c):
    x=c.copy()
    if x.empty:
        return x
    actions=[]
    for _, row in x.iterrows():
        if row.days_since_last_trade > 90 and row.nav_mn > 300:
            actions.append("Reactivation")
        elif row.nav_mn > 1000 and row.margin_balance_mn < 0.1*row.nav_mn and row.risk_level != "High":
            actions.append("Margin Upsell")
        elif row.nav_mn > 3000 and row.monthly_trading_value_mn < 0.3*row.nav_mn:
            actions.append("Senior RM Coverage")
        else:
            actions.append("Maintain")
    x["recommended_action"] = actions
    x["opportunity_score"] = np.where(x.recommended_action.eq("Margin Upsell"), 90, np.where(x.recommended_action.eq("Senior RM Coverage"),80, np.where(x.recommended_action.eq("Reactivation"),75,50)))
    return x.sort_values("opportunity_score", ascending=False)

with st.sidebar:
    st.markdown(f"<div class='author-badge'>Author: {AUTHOR}</div>", unsafe_allow_html=True)
    st.title("VNDIRECT BI")
    data_mode = st.radio("Data source", ["Demo CSV", "Google Sheets - Service Account"], index=0)
    auto_market = st.toggle("Auto-fetch VNINDEX via vnstock", value=False)
    mobile = st.toggle("Mobile friendly mode", value=True)
    st.caption("CEO advisory | RM KPI | Client opportunity | Market connector")

business, rm, clients, market, market_margin, targets, weights, rules = read_local()
if data_mode == "Google Sheets - Service Account":
    try:
        sheet_id = st.secrets.get("GOOGLE_SHEET_ID", "")
        sheet_name = st.secrets.get("GOOGLE_SHEET_NAME", "VNDIRECT_BI_DATA")
        data = read_google_workbook(sheet_id or sheet_name, by_id=bool(sheet_id))
        business = data.get("business_daily", business)
        rm = data.get("rm_kpi", rm)
        clients = data.get("client_master", clients)
        market = data.get("market_data", market)
        market_margin = data.get("market_margin", market_margin)
        targets = data.get("targets_kpi", targets)
        weights = data.get("kpi_weights", weights)
        rules = data.get("ceo_action_rules", rules)
        st.sidebar.success("Connected to Google Sheets")
    except Exception as e:
        st.sidebar.error(f"Google Sheets connection failed: {e}")
        st.sidebar.info("Falling back to demo CSV.")

business, rm, market, market_margin, targets = normalize_dates(business, rm, market, market_margin, targets)

if auto_market:
    live = fetch_vnindex_vnstock()
    if not live.empty and "connector_error" not in live.columns and "vnindex" in live.columns:
        for col in ["margin_rate_pct", "deposit_rate_pct", "foreign_net_buy_bn"]:
            if col not in live.columns:
                live[col] = np.nan
        market = live
        st.sidebar.success("VNINDEX connector loaded")
    elif not live.empty and "connector_error" in live.columns:
        st.sidebar.warning("VNINDEX connector failed; using sheet/demo market_data.")

st.markdown(f"<div class='author-badge'>Built by {AUTHOR}</div>", unsafe_allow_html=True)
st.title("📈 VNDIRECT Business Intelligence Dashboard")
st.caption("CEO strategy | Business performance | RM KPI | Client opportunity | Market data | Google Sheets-ready")

if business.empty or rm.empty or clients.empty:
    st.error("Missing required data. Please check Google Sheets template tabs and headers.")
    st.stop()

latest_date = business.date.max()
start_date, end_date = st.date_input("Chọn giai đoạn", [business.date.min().date(), latest_date.date()])
business_f = business[(business.date.dt.date >= start_date) & (business.date.dt.date <= end_date)]
rm_f = rm[(rm.date.dt.date >= start_date) & (rm.date.dt.date <= end_date)]

labels = ["CEO", "KPI", "Client", "Market", "Warning", "Data"] if mobile else ["📌 CEO Action", "🎯 RM KPI", "👥 Client Opportunity", "📊 Market & Margin", "⚠️ Early Warning", "🗂 Data Model"]
tabs = st.tabs(labels)

with tabs[0]:
    total = business_f.sum(numeric_only=True)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Revenue", f"{total.get('revenue_bn',0):,.0f} bn VND")
    c2.metric("Brokerage fee", f"{total.get('brokerage_fee_bn',0):,.0f} bn")
    c3.metric("Margin income", f"{total.get('margin_interest_bn',0):,.0f} bn")
    c4.metric("Active clients", f"{int(total.get('active_clients',0)):,}")
    st.markdown("<div class='ceo-box'><h3>CEO Action for this month</h3></div>", unsafe_allow_html=True)
    for a in ceo_actions(business_f, rm_f, clients, market, weights):
        st.markdown(f"<div class='warning-box'>• {a}</div>", unsafe_allow_html=True)
    monthly = business_f.groupby("date", as_index=False).agg(revenue_bn=("revenue_bn","sum"), active_clients=("active_clients","sum"), cost_bn=("cost_bn","sum"))
    st.plotly_chart(px.line(monthly, x="date", y=["revenue_bn","cost_bn"], markers=True, title="Revenue vs Cost Trend"), use_container_width=True)
    st.plotly_chart(px.bar(business_f.groupby("channel", as_index=False)["revenue_bn"].sum(), x="channel", y="revenue_bn", title="Revenue by Channel"), use_container_width=True)

with tabs[1]:
    latest_rm = rm_f[rm_f.date == rm_f.date.max()].pipe(kpi_score, weights).sort_values("risk_adjusted_score", ascending=False)
    st.subheader("Risk-adjusted RM KPI Scoring")
    st.caption("Default score = 30% brokerage revenue + 25% margin balance + 25% clients/new accounts + 20% quality/compliance. Change weights in Google Sheet tab kpi_weights.")
    st.dataframe(latest_rm[["rm_name","branch","brokerage_revenue_bn","margin_balance_bn","active_clients","new_accounts","cost_bn","compliance_incidents","client_churn_rate","risk_adjusted_score","rating"]], use_container_width=True, hide_index=True)
    st.plotly_chart(px.bar(latest_rm, x="rm_name", y="risk_adjusted_score", color="rating", title="RM KPI Ranking"), use_container_width=True)
    low = latest_rm[latest_rm.risk_adjusted_score < 60]
    if not low.empty:
        st.markdown("<div class='bad-box'><b>Coaching list:</b> " + ", ".join(low.rm_name.tolist()) + "</div>", unsafe_allow_html=True)

with tabs[2]:
    opp = opportunity_engine(clients)
    st.subheader("Client Opportunity Engine")
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Reactivation", int((opp.recommended_action=="Reactivation").sum()))
    m2.metric("Margin Upsell", int((opp.recommended_action=="Margin Upsell").sum()))
    m3.metric("Senior RM Coverage", int((opp.recommended_action=="Senior RM Coverage").sum()))
    m4.metric("Total NAV", f"{opp.nav_mn.sum()/1000:,.1f} bn")
    st.dataframe(opp.head(100), use_container_width=True, hide_index=True)
    st.plotly_chart(px.scatter(opp, x="nav_mn", y="monthly_trading_value_mn", color="recommended_action", size="margin_balance_mn", hover_data=["client_id","rm_name","days_since_last_trade"], title="Client Opportunity Map"), use_container_width=True)

with tabs[3]:
    st.subheader("Market & Margin Monitor")
    if not market.empty:
        latest_m = market.dropna(subset=["date"]).sort_values("date").iloc[-1]
        a,b,c,d = st.columns(4)
        a.metric("VNINDEX", f"{latest_m.get('vnindex',0):,.2f}")
        b.metric("Market turnover", f"{latest_m.get('market_turnover_trn',0):,.2f} trn")
        c.metric("Margin rate", f"{latest_m.get('margin_rate_pct',np.nan):,.2f}%" if pd.notna(latest_m.get('margin_rate_pct',np.nan)) else "n/a")
        d.metric("Deposit rate", f"{latest_m.get('deposit_rate_pct',np.nan):,.2f}%" if pd.notna(latest_m.get('deposit_rate_pct',np.nan)) else "n/a")
        cols = [x for x in ["vnindex","market_turnover_trn"] if x in market.columns]
        st.plotly_chart(px.line(market.sort_values("date"), x="date", y=cols, markers=True, title="VNINDEX and Market Liquidity"), use_container_width=True)
    if market_margin is not None and not market_margin.empty:
        latest_mm = market_margin[market_margin.date == market_margin.date.max()].copy()
        st.dataframe(latest_mm.sort_values("margin_loan_bn", ascending=False), use_container_width=True, hide_index=True)
        st.plotly_chart(px.bar(latest_mm.sort_values("margin_loan_bn", ascending=False), x="broker", y="margin_loan_bn", color="brokerage_market_share_pct", title="Broker Margin Loan and Brokerage Share"), use_container_width=True)
    else:
        st.info("market_margin sheet is empty. Add quarterly margin loan and brokerage market share data there.")

with tabs[4]:
    st.subheader("Early Warning System")
    monthly = business_f.groupby("date", as_index=False).agg(revenue_bn=("revenue_bn","sum"), active_clients=("active_clients","sum"), cost_bn=("cost_bn","sum"))
    monthly["rev_mom"] = monthly.revenue_bn.pct_change()
    monthly["active_mom"] = monthly.active_clients.pct_change()
    latest = monthly.iloc[-1]
    warnings=[]
    if latest.rev_mom < -0.15: warnings.append("Revenue declined more than 15% month-on-month.")
    if latest.active_mom < 0: warnings.append("Active clients declined from previous month.")
    if latest.cost_bn/latest.revenue_bn > 0.6: warnings.append("Cost-to-income ratio exceeded 60%.")
    churn_rm = kpi_score(rm_f[rm_f.date==rm_f.date.max()], weights)
    high_churn = churn_rm[churn_rm.client_churn_rate > 0.12]
    if len(high_churn)>0: warnings.append("High churn risk among RMs: " + ", ".join(high_churn.rm_name.tolist()))
    if warnings:
        for w in warnings:
            st.markdown(f"<div class='bad-box'>⚠️ {w}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='good-box'>No critical warning based on current thresholds.</div>", unsafe_allow_html=True)
    st.plotly_chart(px.line(monthly, x="date", y=["rev_mom","active_mom"], markers=True, title="MoM warning indicators"), use_container_width=True)

with tabs[5]:
    st.subheader("Data Model & Google Sheets Structure")
    st.markdown("<div class='info-box'>Use the included XLSX template: <b>VNDIRECT_BI_Google_Sheet_Template_Le_Hoang_Quan.xlsx</b>. Upload it to Google Drive, open as Google Sheets, then share it with your service-account email.</div>", unsafe_allow_html=True)
    st.code("""Required Google Sheets tabs:
1. business_daily: date, channel, revenue_bn, brokerage_fee_bn, margin_interest_bn, other_income_bn, active_clients, new_accounts, trading_value_bn, cost_bn
2. rm_kpi: date, rm_name, branch, brokerage_revenue_bn, margin_balance_bn, active_clients, new_accounts, cost_bn, compliance_incidents, client_churn_rate
3. client_master: client_id, segment, rm_name, nav_mn, monthly_trading_value_mn, margin_balance_mn, days_since_last_trade, risk_level
4. market_data: date, vnindex, market_turnover_trn, margin_rate_pct, deposit_rate_pct, foreign_net_buy_bn
5. market_margin: date, broker, margin_loan_bn, equity_bn, margin_to_equity, brokerage_market_share_pct
6. kpi_weights: kpi_component, weight, description
7. ceo_action_rules: rule_id, area, condition, recommended_action, priority""")
    c1,c2,c3 = st.columns(3)
    with c1: st.write("business_daily", business.head())
    with c2: st.write("rm_kpi", rm.head())
    with c3: st.write("market_data", market.head())

st.markdown(f"<div class='footer'>Built by {AUTHOR} | VNDIRECT BI package | Google Sheets-ready | VNINDEX connector optional</div>", unsafe_allow_html=True)
