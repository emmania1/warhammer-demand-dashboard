import pandas as pd
import json
import os
from datetime import datetime

DATA_PATH = "data"

def load_csv(name):
    path = os.path.join(DATA_PATH, name)
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

def percent_change(series):
    if len(series) < 2:
        return None
    return float((series.iloc[-1] - series.iloc[-2]) / series.iloc[-2] * 100)

def build_summary():
    summary = {
        "date": str(datetime.now().date()),
        "reddit": {},
        "google_trends": {}
    }

    reddit = load_csv("reddit_data.csv")
    trends = load_csv("trends_data.csv")

    if reddit is not None and len(reddit) >= 2:
        summary["reddit"]["subscriber_growth_pct"] = percent_change(reddit["subscribers"])
        summary["reddit"]["current_subscribers"] = int(reddit["subscribers"].iloc[-1])
    else:
        summary["reddit"]["subscriber_growth_pct"] = None

    if trends is not None and len(trends) > 1:
        trend_avg = trends.groupby("date")["score"].mean()
        summary["google_trends"]["interest_change_pct"] = percent_change(trend_avg)
        summary["google_trends"]["current_avg_score"] = float(trend_avg.iloc[-1])
    else:
        summary["google_trends"]["interest_change_pct"] = None

    return summary

if __name__ == "__main__":
    summary = build_summary()
    with open("weekly_summary.json", "w") as f:
        json.dump(summary, f, indent=4)
    print("Weekly summary generated → weekly_summary.json")
