def generate_ceo_action(market_df):

    actions = []

    latest = market_df.sort_values("date").iloc[-1]

    signal = latest.get("signal", "Neutral")
    change = latest.get("return_pct", 0)

    if signal == "SELL":
        actions.append("⚠️ Giảm margin, ưu tiên quản trị rủi ro")

    elif signal == "BUY":
        actions.append("🚀 Đẩy mạnh trading, tăng brokerage")

    if change < -2:
        actions.append("⚠️ Thị trường giảm mạnh → kiểm soát risk ngay")

    return actions
