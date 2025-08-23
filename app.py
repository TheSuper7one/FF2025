import streamlit as st
import pandas as pd
import requests
import re
import time

# -------------------------
# CONFIG
# -------------------------
SLEEPER_BASE = "https://api.sleeper.app/v1"
AUTO_REFRESH_INTERVAL = 5  # seconds
RANKINGS_CSV_URL = "https://raw.githubusercontent.com/TheSuper7one/FF2025/refs/heads/main/rankings.csv"

# -------------------------
# NAME ALIASES (expand as needed)
# -------------------------
NAME_ALIASES = {
    "D.K. Metcalf": "DK Metcalf",
    "Kenneth Walker III": "Ken Walker",
    # Add more as needed
}

# -------------------------
# FUNCTIONS
# -------------------------
def extract_draft_id(url_or_id):
    """
    Extracts the numeric draft ID from a Sleeper draft URL or returns the ID if already given.
    Handles URLs like:
    - https://sleeper.com/draft/123456789012345678
    - https://sleeper.com/draft/nfl/123456789012345678
    """
    m = re.search(r"draft/(?:nfl/)?(\d+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()

def fetch_drafted_ids(draft_id):
    """Fetch drafted player IDs from Sleeper."""
    try:
        picks_url = f"{SLEEPER_BASE}/draft/{draft_id}/picks"
        picks = requests.get(picks_url).json()
        return [p["player_id"] for p in picks if "player_id" in p]
    except Exception as e:
        st.error(f"Error fetching drafted players: {e}")
        return []

def fetch_sleeper_players():
    """Fetch Sleeper player data."""
    try:
        players_url = f"{SLEEPER_BASE}/players/nfl"
        return requests.get(players_url).json()
    except Exception as e:
        st.error(f"Error fetching Sleeper players: {e}")
        return {}

def merge_rankings_with_sleeper(rankings_df, sleeper_players):
    """Merge rankings CSV with Sleeper player IDs."""
    sleeper_map = {}
    for pid, pdata in sleeper_players.items():
        name = pdata.get("full_name") or f"{pdata.get('first_name', '')} {pdata.get('last_name', '')}"
        sleeper_map[name.strip()] = pid

    # Apply aliases
    rankings_df["Name_Mapped"] = rankings_df["Player"].replace(NAME_ALIASES)

    # Map to Sleeper IDs
    rankings_df["Sleeper_ID"] = rankings_df["Name_Mapped"].map(sleeper_map)

    # Track unmatched
    unmatched = rankings_df[rankings_df["Sleeper_ID"].isna()]

    return rankings_df, unmatched

# -------------------------
# STREAMLIT APP
# -------------------------
st.set_page_config(page_title="Fantasy Draft Board", layout="wide")

st.title("🏈 Fantasy Draft Board (Sleeper Live Sync)")

# Input for Sleeper draft URL or ID
draft_url_input = st.text_input("Enter Sleeper Draft URL or ID:")

# Auto-refresh toggle
auto_refresh = st.checkbox(f"Auto-refresh every {AUTO_REFRESH_INTERVAL} seconds during draft", value=True)

if draft_url_input:
    draft_id = extract_draft_id(draft_url_input)

    # Load rankings from GitHub
    rankings_df = pd.read_csv(RANKINGS_CSV_URL)

    # Fetch Sleeper data
    sleeper_players = fetch_sleeper_players()
    rankings_df, unmatched_df = merge_rankings_with_sleeper(rankings_df, sleeper_players)

    # Fetch drafted IDs
    drafted_ids = fetch_drafted_ids(draft_id)

    # Mark drafted players
    rankings_df["Drafted"] = rankings_df["Sleeper_ID"].isin(drafted_ids)

    # Filter out drafted players
    filtered_df = rankings_df[~rankings_df["Drafted"]]

    # Show draft board with 20 visible rows
    rows_to_show = 20
    row_height_px = 35
    st.dataframe(filtered_df[["Rank", "Player", "Pos", "Team"]], height=rows_to_show * row_height_px)

    # Debug info moved below
    with st.expander("🔍 Parsing & API Debug Info"):
        st.write("Parsed Draft ID:", draft_id)
        st.write("Drafted IDs from Sleeper:", drafted_ids)
        st.write("Unmatched Players:", unmatched_df)

    # Auto-refresh logic
    if auto_refresh:
        time.sleep(AUTO_REFRESH_INTERVAL)
        st.experimental_rerun()

else:
    st.info("Please enter your Sleeper draft URL/ID to start live sync.")
