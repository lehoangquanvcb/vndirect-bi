import pandas as pd
from datetime import date
from vnstock import Vnstock

START_DATE = "2024-01-01"
END_DATE = date.today().strftime("%Y-%m-%d")

print("Loading VNINDEX...")

stock = Vnstock().stock(symbol="VNINDEX", source="VCI")

df = stock.quote.history(
    start=START_DATE,
    end=END_DATE,
    interval="1D"
)

df = df.rename(columns={
    "time": "date",
    "close": "vnindex"
})

df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

df["return_pct"] = df["vnindex"].pct_change()*100
df["ma20"] = df["vnindex"].rolling(20).mean()

df["signal"] = "Neutral"
df.loc[df["return_pct"] <= -2, "signal"] = "SELL"
df.loc[df["return_pct"] >= 2, "signal"] = "BUY"

df.to_csv("market_data_real.csv", index=False)

print("✅ market_data_real.csv updated")
