import pandas as pd
import numpy as np

DEFAULT_WEIGHTS = {
    "revenue": 0.30,
    "margin": 0.25,
    "active_clients": 0.20,
    "new_accounts": 0.15,
    "quality": 0.10,
}

def safe_num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)

def normalize_score(series, higher_is_better=True):
    s = safe_num(series)
    if len(s) == 0:
        return pd.Series(dtype=float)
    if s.max() == s.min():
        return pd.Series([70] * len(s), index=s.index)
    score = (s - s.min()) / (s.max() - s.min()) * 100
    if not higher_is_better:
        score = 100 - score
    return score.clip(0, 100)

def calculate_kpi_score(df, weights=None):
    weights = weights or DEFAULT_WEIGHTS.copy()
    out = df.copy()
    required = ["rm", "revenue", "margin", "new_accounts", "active_clients"]
    for col in required:
        if col not in out.columns:
            out[col] = 0
    out["score_revenue"] = normalize_score(out["revenue"])
    out["score_margin"] = normalize_score(out["margin"])
    out["score_active_clients"] = normalize_score(out["active_clients"])
    out["score_new_accounts"] = normalize_score(out["new_accounts"])
    if "compliance_issue" not in out.columns:
        out["compliance_issue"] = 0
    if "churn_clients" not in out.columns:
        out["churn_clients"] = 0
    out["score_quality"] = (100 - safe_num(out["compliance_issue"]) * 20 - safe_num(out["churn_clients"]) * 2).clip(0, 100)
    total_weight = sum(weights.values())
    if total_weight == 0:
        weights = DEFAULT_WEIGHTS.copy(); total_weight = sum(weights.values())
    weights = {k: v / total_weight for k, v in weights.items()}
    out["kpi_score"] = (
        out["score_revenue"] * weights.get("revenue", 0.30)
        + out["score_margin"] * weights.get("margin", 0.25)
        + out["score_active_clients"] * weights.get("active_clients", 0.20)
        + out["score_new_accounts"] * weights.get("new_accounts", 0.15)
        + out["score_quality"] * weights.get("quality", 0.10)
    ).round(1)
    out["rank"] = out["kpi_score"].rank(ascending=False, method="dense").astype(int)
    out["performance_band"] = np.select(
        [out["kpi_score"] >= 85, out["kpi_score"] >= 70, out["kpi_score"] >= 55],
        ["A - Top Performer", "B - Good", "C - Watchlist"],
        default="D - Action Required",
    )
    out["bonus_multiplier"] = np.select(
        [out["kpi_score"] >= 90, out["kpi_score"] >= 85, out["kpi_score"] >= 70, out["kpi_score"] >= 55],
        [1.5, 1.3, 1.0, 0.5],
        default=0.0,
    )
    out["bonus_policy"] = np.select(
        [out["kpi_score"] >= 85, out["kpi_score"] >= 70, out["kpi_score"] >= 55],
        ["Bonus accelerator / assign HNW leads", "Standard bonus / maintain target", "Coaching + weekly pipeline review"],
        default="Performance improvement plan",
    )
    out["recommendation"] = out.apply(generate_rm_recommendation, axis=1)
    return out.sort_values(["rank", "rm"])

def generate_rm_recommendation(row):
    recs = []
    if row.get("score_revenue", 0) < 50: recs.append("Push brokerage revenue")
    if row.get("score_margin", 0) < 50: recs.append("Review margin penetration")
    if row.get("score_active_clients", 0) < 50: recs.append("Reactivate dormant clients")
    if row.get("score_new_accounts", 0) < 50: recs.append("Improve new account acquisition")
    if row.get("score_quality", 100) < 70: recs.append("Check compliance / churn risk")
    return "; ".join(recs) if recs else "Maintain performance; assign higher-value clients"

def ceo_summary(kpi_df):
    if kpi_df is None or kpi_df.empty:
        return {"top_rm":"N/A","bottom_rm":"N/A","avg_score":0,"watchlist_count":0,"action_required_count":0}
    d = kpi_df.copy()
    return {
        "top_rm": d.sort_values("kpi_score", ascending=False).iloc[0]["rm"],
        "bottom_rm": d.sort_values("kpi_score", ascending=True).iloc[0]["rm"],
        "avg_score": round(float(d["kpi_score"].mean()), 1),
        "watchlist_count": int((d["performance_band"] == "C - Watchlist").sum()),
        "action_required_count": int((d["performance_band"] == "D - Action Required").sum()),
    }

def build_reward_table(kpi_df):
    d = kpi_df.copy()
    keep = ["rm", "rank", "kpi_score", "performance_band", "bonus_multiplier", "bonus_policy", "recommendation"]
    return d[[c for c in keep if c in d.columns]]
