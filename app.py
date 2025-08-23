import streamlit as st
import pandas as pd
import requests
from io import StringIO

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="Fantasy Draft Board", layout="wide")

# 🔹 Your fixed PPR rankings CSV in GitHub
DEFAULT_CSV_URL = "https://raw.githubusercontent.com/TheSuper7one/FF2025/refs/heads/main/rankings.csv"

REQUIRED_COLS = ["Rank", "Player", "Position", "NFL Team"]

# ---------------------------
# LOAD DATA
# ---------------------------
def load_rankings(url: str) -> pd.DataFrame:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))

        # Normalize column names
        rename_map = {
            "team": "NFL Team",
            "nfl": "NFL Team",
            "pos": "Position",
            "name": "Player"
        }
        df = df.rename(columns={c: rename_map.get(c.lower(), c) for c in df.columns})

        # Ensure required columns exist
        for col in REQUIRED_COLS:
            if col not in df.columns:
                st.error(f"Missing required column: {col}")
                return pd.DataFrame(columns=REQUIRED_COLS)

        return df
    except Exception as e:
        st.error(f"Error loading rankings from GitHub: {e}")
        return pd.DataFrame(columns=REQUIRED_COLS)

# ---------------------------
# COLOR FUNCTION
# ---------------------------
def position_color(pos: str) -> str:
    colors = {
        "QB": "#1E90FF",   # blue
        "WR": "#32CD32",   # green
        "RB": "#FF4500",   # red
        "TE": "#9370DB"    # purple
    }
    return colors.get(str(pos).upper(), "#2b2b2b")

# ---------------------------
# RENDER BOARD
# ---------------------------
def render_board(df: pd.DataFrame):
    positions = sorted(df["Position"].dropna().unique())
    for pos in positions:
        pos_df = df[df["Position"] == pos].copy()
        pos_df = pos_df.sort_values(by="Rank", ascending=True)

        def style_row(row):
            return [f"background-color: {position_color(row['Position'])}" for _ in row]

        st.markdown(f"### {pos}")
        st.dataframe(
            pos_df[REQUIRED_COLS].style.apply(style_row, axis=1),
            use_container_width=True
        )

# ---------------------------
# MAIN
# ---------------------------
st.title("🏈 Fantasy Draft Board (PPR Rankings)")
st.caption("Always loads the latest PPR rankings from GitHub.")

df = load_rankings(DEFAULT_CSV_URL)

if not df.empty:
    render_board(df)
else:
    st.warning("No data to display. Check your DEFAULT_CSV_URL and CSV format.")

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
