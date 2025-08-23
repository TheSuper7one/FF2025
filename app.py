import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="Fantasy Draft Board", layout="wide")

SLEEPER_BASE = "https://api.sleeper.app/v1"
# Your fixed rankings CSV in GitHub (raw URL)
DEFAULT_CSV_URL = "https://raw.githubusercontent.com/TheSuper7one/FF2025/refs/heads/main/rankings.csv"

# ---------------------------
# DATA LOADERS
# ---------------------------
@st.cache_data(show_spinner=False)
def load_default_rankings(url: str):
    last_updated = None
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        # Attempt to read Last-Modified header for display (if present)
        if "Last-Modified" in resp.headers:
            try:
                last_updated = datetime.strptime(resp.headers["Last-Modified"], "%a, %d %b %Y %H:%M:%S %Z")
            except Exception:
                last_updated = None
        df = pd.read_csv(StringIO(resp.text))
        return df, last_updated, None
    except Exception as e:
        return pd.DataFrame(), None, f"Error loading rankings from GitHub: {e}"

@st.cache_data(show_spinner=False)
def load_uploaded_rankings(file):
    try:
        df = pd.read_csv(file)
        return df, None
    except Exception as e:
        st.error(f"Error loading uploaded CSV: {e}")
        return pd.DataFrame(), e

@st.cache_data(show_spinner=False)
def fetch_sleeper_picks(draft_id: str):
    if not draft_id:
        return []
    try:
        url = f"{SLEEPER_BASE}/draft/{draft_id}/picks"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

def drafted_full_names(picks) -> list:
    names = []
    for p in picks:
        meta = p.get("metadata") or {}
        first = (meta.get("first_name") or "").strip()
        last = (meta.get("last_name") or "").strip()
        full = f"{first} {last}".strip()
        if full:
            names.append(full)
    return names

def mark_drafted(df: pd.DataFrame, names: list) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df = df.copy()
    if "Player" in df.columns:
        df["Drafted"] = df["Player"].isin(names)
    else:
        # If Player column isn't present, just ensure Drafted exists as False
        df["Drafted"] = False
    return df

# ---------------------------
# RENDERING
# ---------------------------
def render_board(df: pd.DataFrame):
    if df.empty:
        st.warning("No data to display.")
        return

    # Style: gray-out drafted rows if Drafted column exists
    def style_row(row):
        if "Drafted" in row and bool(row["Drafted"]):
            return ["background-color: #444444"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df.style.apply(style_row, axis=1),
        use_container_width=True
    )

# ---------------------------
# SIDEBAR
# ---------------------------
st.sidebar.header("Settings")
uploaded_csv = st.sidebar.file_uploader("Optional: Upload rankings CSV", type=["csv"])
draft_id = st.sidebar.text_input("Sleeper Draft ID", placeholder="e.g., 123456789012345678")

# ---------------------------
# MAIN
# ---------------------------
st.title("🏈 Fantasy Draft Board")
st.caption("Stable base — default GitHub rankings, optional upload override, Sleeper drafted highlighting.")

# Load rankings (upload overrides default)
if uploaded_csv is not None:
    df, _err = load_uploaded_rankings(uploaded_csv)
    source_note = "Using uploaded CSV"
    last_updated = None
else:
    df, last_updated, err = load_default_rankings(DEFAULT_CSV_URL)
    source_note = "Using default GitHub rankings"
    if err:
        st.error(err)

# Header info
cols = st.columns([2, 2, 1])
with cols[0]:
    st.markdown(f"**Source:** {source_note}")
with cols[1]:
    if last_updated:
        st.markdown(f"**📅 Rankings last updated:** {last_updated.strftime('%Y-%m-%d %H:%M:%S')} UTC")

# Manual refresh button
if st.button("🔄 Refresh now"):
    st.cache_data.clear()
    st.experimental_rerun()

# Fetch picks and mark drafted (non-destructive; shows all columns as-is)
picks = fetch_sleeper_picks(draft_id) if draft_id else []
names = drafted_full_names(picks) if picks else []
df_marked = mark_drafted(df, names)

# Render full table (no consolidation, no position color coding)
render_board(df_marked)

# ---------------------------
# FOOTER STYLE
# ---------------------------
st.markdown(
    """
    <style>
    body { background-color: #1e1e1e; color: #f5f5f5; }
    .stDataFrame { background-color: #2b2b2b; }
    .stMarkdown p { color: #f5f5f5; }
    </style>
    """,
    unsafe_allow_html=True
)
