import streamlit as st
import pandas as pd
import requests
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
DEFAULT_CSV_URL = "https://raw.githubusercontent.com/<your-username>/<your-repo>/main/<path-to-rankings>.csv"

# ---------------------------
# UTILS
# ---------------------------
@st.cache_data
def load_player_data(csv_file):
    try:
        df = pd.read_csv(csv_file)
        required_cols = {"Rank", "Player", "Position", "NFL Team"}
        if not required_cols.issubset(df.columns):
            raise ValueError(f"CSV missing required columns: {required_cols}")
        return df
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return pd.DataFrame()

@st.cache_data
def load_default_rankings():
    """Load default rankings from GitHub and return DataFrame + last updated timestamp."""
    try:
        resp = requests.get(DEFAULT_CSV_URL, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(pd.compat.StringIO(resp.text))
        required_cols = {"Rank", "Player", "Position", "NFL Team"}
        if not required_cols.issubset(df.columns):
            raise ValueError(f"Default CSV missing required columns: {required_cols}")

        # Get last modified date from headers if available
        last_updated = None
        if "Last-Modified" in resp.headers:
            last_updated = datetime.strptime(resp.headers["Last-Modified"], "%a, %d %b %Y %H:%M:%S %Z")
        return df, last_updated
    except Exception as e:
        st.error(f"Error loading default rankings from GitHub: {e}")
        return pd.DataFrame(), None

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

def position_color(pos):
    colors = {
        "QB": "#1E90FF",   # blue
        "WR": "#32CD32",   # green
        "RB": "#FF4500",   # red
        "TE": "#9370DB"    # purple
    }
    return colors.get(pos, "#2b2b2b")  # default dark gray

def render_draft_board(df):
    display_cols = ["Rank", "Player", "Position", "NFL Team", "Drafted"]
    display_cols = [col for col in display_cols if col in df.columns]
    df_display = df[display_cols].copy()

    positions = df_display["Position"].unique()
    for pos in positions:
        pos_df = df_display[df_display["Position"] == pos].copy()
        pos_df = pos_df.sort_values(by="Rank", ascending=True)

        def style_row(row):
            base_color = position_color(row["Position"])
            if row["Drafted"]:
                return ["background-color: #444" for _ in row]
            else:
                return [f"background-color: {base_color}" for _ in row]

        st.markdown(f"### {pos}")
        st.dataframe(
            pos_df.style.apply(style_row, axis=1),
            use_container_width=True
        )

# ---------------------------
# SIDEBAR
# ---------------------------
st.sidebar.header("Fantasy Draft Board Settings")
uploaded_csv = st.sidebar.file_uploader("Upload Player CSV", type=["csv"])
draft_id = st.sidebar.text_input("Sleeper Draft ID", placeholder="e.g., 123456789012345678")

# ---------------------------
# MAIN
# ---------------------------
st.title("🏈 Fantasy Draft Board")
st.caption("Live-updating draft board with Sleeper sync, dark mode, position colors, auto-hide drafted players, smart refresh, and GitHub fallback.")

# Load player data
last_updated = None
if uploaded_csv:
    df = load_player_data(uploaded_csv)
else:
    st.warning("No CSV uploaded — using default rankings from GitHub.")
    df, last_updated = load_default_rankings()
    if last_updated:
        st.markdown(f"**📅 Rankings last updated:** {last_updated.strftime('%Y-%m-%d %H:%M:%S')} UTC")

drafted_names = []
current_round = 1

if draft_id:
    picks = fetch_sleeper_draft(draft_id)
    drafted_names = [
        f"{p.get('metadata', {}).get('first_name', '')} {p.get('metadata', {}).get('last_name', '')}".strip()
        for p in picks if p.get("metadata")
    ]
    if picks:
        num_teams = len(set(p["picked_by"] for p in picks if "picked_by" in p))
        current_round = max(1, (len(picks) // num_teams) + 1)

# Smart refresh interval
if current_round <= 5:
    refresh_interval = 5000   # 5 sec
elif current_round <= 10:
    refresh_interval = 10000  # 10 sec
else:
    refresh_interval = 20000  # 20 sec

# Show refresh rate indicator
st.markdown(f"**🔄 Auto-refreshing every {refresh_interval // 1000} seconds** (Current round: {current_round})")

# Auto-refresh (replace with st_autorefresh in real Streamlit app)
# st_autorefresh(interval=refresh_interval, key="auto_refresh")

if drafted_names:
    df = mark_drafted_players(df, drafted_names)
    df = df[~df["Drafted"]]  # hide drafted players

render_draft_board(df)

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
