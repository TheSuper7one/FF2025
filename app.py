import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(
    page_title="Fantasy Draft Board",
    layout="wide",
    initial_sidebar_state="expanded"
)

SLEEPER_BASE = "https://api.sleeper.app/v1"

# ---------------------------
# UTILS
# ---------------------------
@st.cache_data
def load_player_data(csv_file):
    try:
        df = pd.read_csv(csv_file)
        required_cols = {"Player", "Position", "Team"}
        if not required_cols.issubset(df.columns):
            raise ValueError(f"CSV missing required columns: {required_cols}")
        return df
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return pd.DataFrame()

@st.cache_data
def fetch_sleeper_draft(draft_id):
    try:
        picks_url = f"{SLEEPER_BASE}/draft/{draft_id}/picks"
        resp = requests.get(picks_url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Could not fetch Sleeper draft data: {e}")
        return []

def mark_drafted_players(df, drafted_names):
    df["Drafted"] = df["Player"].isin(drafted_names)
    return df

def render_draft_board(df, rounds_ahead=3):
    positions = df["Position"].unique()
    for pos in positions:
        pos_df = df[df["Position"] == pos].copy()
        pos_df = pos_df.sort_values(by="Drafted", ascending=True)
        st.markdown(f"### {pos}")
        st.dataframe(
            pos_df.style.apply(
                lambda row: ["background-color: #444" if row.Drafted else "" for _ in row],
                axis=1
            ),
            use_container_width=True
        )

# ---------------------------
# SIDEBAR
# ---------------------------
st.sidebar.header("Fantasy Draft Board Settings")
uploaded_csv = st.sidebar.file_uploader("Upload Player CSV", type=["csv"])
draft_id = st.sidebar.text_input("Sleeper Draft ID", placeholder="e.g., 123456789012345678")
rounds_ahead = st.sidebar.slider("Rounds Look-Ahead", 1, 5, 3)

# ---------------------------
# MAIN
# ---------------------------
st.title("🏈 Fantasy Draft Board")
st.caption("Live-updating draft board with Sleeper sync and dark mode styling.")

if uploaded_csv:
    df = load_player_data(uploaded_csv)

    drafted_names = []
    if draft_id:
        picks = fetch_sleeper_draft(draft_id)
        drafted_names = [p.get("metadata", {}).get("first_name", "") + " " +
                         p.get("metadata", {}).get("last_name", "")
                         for p in picks if p.get("metadata")]

    if drafted_names:
        df = mark_drafted_players(df, drafted_names)

    render_draft_board(df, rounds_ahead=rounds_ahead)

else:
    st.info("Upload your player CSV in the sidebar to get started.")

# ---------------------------
# FOOTER
# ---------------------------
st.markdown(
    """
    <style>
    body { background-color: #1e1e1e; color: #f5f5f5; }
    .stDataFrame { background-color: #2b2b2b; }
    table { color: #f5f5f5 !important; }
    </style>
    """,
    unsafe_allow_html=True
)
