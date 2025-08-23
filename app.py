import streamlit as st
from streamlit_autorefresh import st_autorefresh   ### NEW
import pandas as pd
import requests

# ===== CONFIG =====
REFRESH_INTERVAL = 3  # seconds
SLEEPER_BASE = "https://api.sleeper.app/v1"

# ===== SESSION STATE =====
if "draft_url" not in st.session_state:
    st.session_state["draft_url"] = ""

# ===== AUTO-REFRESH =====
### NEW — only auto-refresh if we already have a draft URL
if st.session_state["draft_url"].strip():
    st_autorefresh(interval=REFRESH_INTERVAL * 1000, key="draft_refresh")

# ===== FUNCTIONS =====
@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)   ### NEW TTL
def fetch_drafted_ids(draft_id):
    url = f"{SLEEPER_BASE}/draft/{draft_id}/picks"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    return [p.get("player_id") for p in data if "player_id" in p]

@st.cache_data(show_spinner=False)
def fetch_players():
    url = f"{SLEEPER_BASE}/players/nfl"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def parse_draft_id(draft_url):
    return draft_url.rstrip("/").split("/")[-1]

def color_for_position(pos):
    colors = {
        "QB": "#FFD700",  # gold
        "RB": "#90EE90",  # light green
        "WR": "#ADD8E6",  # light blue
        "TE": "#FFB6C1",  # light pink
        "DEF": "#D3D3D3", # light gray
        "K": "#FFA500"    # orange
    }
    return f"background-color: {colors.get(pos, 'white')}"

# ===== UI =====
st.set_page_config(page_title="Live Fantasy Draft Board", layout="wide")
st.title("🏈 Live Fantasy Draft Board")

draft_url = st.text_input("Enter Sleeper Draft URL:", value=st.session_state["draft_url"])
st.session_state["draft_url"] = draft_url

if draft_url.strip():
    draft_id = parse_draft_id(draft_url)

    # Fetch data
    drafted_ids = fetch_drafted_ids(draft_id)
    players_data = fetch_players()

    # Build DataFrame
    df = pd.DataFrame([
        {
            "Rank": p.get("fantasy_positions", [""])[0],
            "Player": p.get("full_name", ""),
            "Pos": p.get("position", ""),
            "Team": p.get("team", "")
        }
        for pid, p in players_data.items()
        if pid not in drafted_ids
    ])

    # Sort by position then player name
    df = df.sort_values(by=["Pos", "Player"]).reset_index(drop=True)

    # Display with color coding
    st.dataframe(
        df.style.apply(lambda row: [color_for_position(row["Pos"])] * len(row), axis=1),
        use_container_width=True
    )
else:
    st.info("Paste your Sleeper draft URL to begin.")
