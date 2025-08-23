import streamlit as st
import pandas as pd
import requests
import re
import time

SLEEPER_BASE = "https://api.sleeper.app/v1"
AUTO_REFRESH_INTERVAL = 5
RANKINGS_CSV_URL = "https://raw.githubusercontent.com/TheSuper7one/FF2025/refs/heads/main/rankings.csv"

NAME_ALIASES = {
    "D.K. Metcalf": "DK Metcalf",
    "Kenneth Walker III": "Ken Walker",
}

def extract_draft_id(url_or_id):
    m = re.search(r"draft/(?:nfl/)?(\d+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()

def fetch_drafted_ids(draft_id):
    try:
        picks_url = f"{SLEEPER_BASE}/draft/{draft_id}/picks"
        picks = requests.get(picks_url).json()
        return [p["player_id"] for p in picks if "player_id" in p]
    except Exception as e:
        st.error(f"Error fetching drafted players: {e}")
        return []

def fetch_sleeper_players():
    try:
        players_url = f"{SLEEPER_BASE}/players/nfl"
        return requests.get(players_url).json()
    except Exception as e:
        st.error(f"Error fetching Sleeper players: {e}")
        return {}

def merge_rankings_with_sleeper(rankings_df, sleeper_players):
    sleeper_map = {}
    for pid, pdata in sleeper_players.items():
        name = pdata.get("full_name") or f"{pdata.get('first_name', '')} {pdata.get('last_name', '')}"
        sleeper_map[name.strip()] = pid
    rankings_df["Name_Mapped"] = rankings_df["Player"].replace(NAME_ALIASES)
    rankings_df["Sleeper_ID"] = rankings_df["Name_Mapped"].map(sleeper_map)
    unmatched = rankings_df[rankings_df["Sleeper_ID"].isna()]
    return rankings_df, unmatched

st.set_page_config(page_title="Fantasy Draft Board", layout="wide")
st.title("🏈 Fantasy Draft Board (Sleeper Live Sync)")

draft_url_input = st.text_input("Enter Sleeper Draft URL or ID (optional for live sync):")
auto_refresh = st.checkbox(f"Auto-refresh every {AUTO_REFRESH_INTERVAL} seconds during draft", value=True)

# Always load rankings from GitHub
rankings_df = pd.read_csv(RANKINGS_CSV_URL)

# If we have a draft URL, apply live sync
drafted_ids = []
unmatched_df = pd.DataFrame()
if draft_url_input.strip():
    draft_id = extract_draft_id(draft_url_input)
    sleeper_players = fetch_sleeper_players()
    rankings_df, unmatched_df = merge_rankings_with_sleeper(rankings_df, sleeper_players)
    drafted_ids = fetch_drafted_ids(draft_id)
    rankings_df["Drafted"] = rankings_df["Sleeper_ID"].isin(drafted_ids)
    filtered_df = rankings_df[~rankings_df["Drafted"]]
else:
    draft_id = None
    filtered_df = rankings_df

# Show board (20 rows visible)
rows_to_show = 20
row_height_px = 35
st.dataframe(filtered_df[["Rank", "Player", "Pos", "Team"]], height=rows_to_show * row_height_px)

# Debug info below
with st.expander("🔍 Parsing & API Debug Info"):
    st.write("Parsed Draft ID:", draft_id)
    st.write("Drafted IDs from Sleeper:", drafted_ids)
    st.write("Unmatched Players:", unmatched_df)

# Auto-refresh if in draft mode
if draft_url_input.strip() and auto_refresh:
    time.sleep(AUTO_REFRESH_INTERVAL)
    st.experimental_rerun()
