import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Warhammer Demand Monitor", layout="wide")

st.title("Warhammer Demand Intelligence Dashboard")

# ===============================
# LOAD DATA
# ===============================

reddit_path = "../data/reddit_data.csv"
trends_path = "../data/trends_data.csv"

reddit_exists = os.path.exists(reddit_path)
trends_exists = os.path.exists(trends_path)

if reddit_exists:
    reddit_df = pd.read_csv(reddit_path)
    reddit_df["date"] = pd.to_datetime(reddit_df["date"])
else:
    reddit_df = None

if trends_exists:
    trends_df = pd.read_csv(trends_path)
    trends_df["date"] = pd.to_datetime(trends_df["date"])
else:
    trends_df = None

# ===============================
# REDDIT SECTION
# ===============================

st.header("Reddit Community Growth")

if reddit_df is not None:
    st.line_chart(reddit_df.set_index("date")["subscribers"])
    latest = reddit_df.iloc[-1]
    st.metric("Latest Subscribers", f"{latest['subscribers']:,}")
else:
    st.warning("No Reddit data yet.")

# ===============================
# GOOGLE TRENDS SECTION
# ===============================

st.header("Google Search Interest")

if trends_df is not None:
    pivot = trends_df.pivot(index="date", columns="keyword", values="score")
    st.line_chart(pivot)
else:
    st.warning("No Trends data yet.")

# ===============================
# DEMAND STATUS
# ===============================

st.header("Demand Summary")

if reddit_df is not None and len(reddit_df) > 1:
    growth = reddit_df["subscribers"].pct_change().iloc[-1] * 100
    st.write(f"Reddit Daily Growth: {growth:.2f}%")
else:
    st.write("Not enough data to compute growth.")