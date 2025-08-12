# Minimal dashboard for OpenBooks API
# Shows health, overview stats, ratings distribution, and per-category table.

import os
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

API = os.getenv("API_BASE", "https://openbooks-api.onrender.com")

st.set_page_config(page_title="OpenBooks Dashboard", layout="wide")
st.title("OpenBooks • Mini Dashboard")

def get_json(path: str):
    url = f"{API}{path}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()

# --- Health ---
try:
    health = get_json("/api/v1/health")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", health.get("status", "unknown"))
    c2.metric("CSV present", "Yes" if health.get("csv_exists") else "No")
    c3.metric("Rows", health.get("rows", 0))
    c4.metric("Last updated", health.get("last_updated", "—"))
except Exception as e:
    st.error(f"Health check failed: {e}")

st.divider()

# --- Overview ---
st.subheader("Overview")
try:
    ov = get_json("/api/v1/stats/overview")
    c1, c2 = st.columns(2)
    c1.metric("Total books", ov.get("total_books", 0))
    c2.metric("Average price", f"{ov.get('avg_price', 0):.2f}")

    dist = ov.get("ratings_distribution", {})
    if dist:
        df = (
            pd.DataFrame({"rating": list(dist.keys()), "count": list(dist.values())})
              .assign(rating=lambda d: d["rating"].astype(int))
              .sort_values("rating")
        )
        st.bar_chart(df.set_index("rating"))
except Exception as e:
    st.error(f"Overview failed: {e}")

# --- By category ---
st.subheader("Per-category statistics")
try:
    cats = get_json("/api/v1/stats/categories")
    if cats:
        dfc = pd.DataFrame(cats)
        st.dataframe(dfc, use_container_width=True)
    else:
        st.info("No category data available.")
except Exception as e:
    st.error(f"Category stats failed: {e}")

st.caption(f"API base: {API}")
