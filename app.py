import streamlit as st
import pandas as pd
import requests
import time
from difflib import get_close_matches

st.set_page_config(page_title="Fantasy Draft Board", layout="wide")

# --- CONFIG ---
RANKINGS_URL = "https://raw.githubusercontent.com/<your-username>/<your-repo>/main/rankings.csv"
REFRESH_INTERVAL = 3  # seconds

# --- HELPERS ---
@st.cache_data(ttl=REFRESH_INTERVAL)
def fetch_drafted_ids(draft_id: str):
    """Fetch drafted player IDs from Sleeper."""
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    try:
        picks = requests.get(url, timeout=10).json()
        drafted_ids = {str(pick.get("player_id")) for pick in picks if pick.get("player_id")}
        ts = time.strftime("%H:%M:%S")
        return drafted_ids, ts
    except Exception:
        return set(), time.strftime("%H:%M:%S")

@st.cache_data
def load_rankings():
    """Load rankings from GitHub CSV."""
    df = pd.read_csv(RANKINGS_URL)
    df.columns = [c.strip().lower() for c in df.columns]
    return df

# --- APP LAYOUT ---
st.title("Fantasy Football Draft Board")

# Input League or Draft ID
league_id = st.text_input("Enter Sleeper League ID (or leave blank if you have a Draft ID)", "")
draft_id = st.text_input("Enter Sleeper Draft ID (optional if League ID provided)", "")

# Resolve Draft ID from League ID
if league_id and not draft_id:
    try:
        drafts = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/drafts", timeout=10).json()
        if drafts:
            draft_id = drafts[0]["draft_id"]
    except Exception:
        st.error("Failed to resolve Draft ID from League ID.")

# Load rankings
rankings = load_rankings()

# Fetch drafted players
if draft_id:
    drafted_ids, ts = fetch_drafted_ids(draft_id)
    
    # Fetch Sleeper player data once
    @st.cache_data
    def fetch_players():
        return requests.get("https://api.sleeper.app/v1/players/nfl", timeout=10).json()

    sleeper_players = fetch_players()

    # Map player names in rankings to Sleeper IDs
    def name_to_id(name, position=None):
        name_key = name.lower().replace(".", "").replace("'", "").strip()
        for pid, pdata in sleeper_players.items():
            if pdata.get("full_name") and pdata["full_name"].lower().replace(".", "").replace("'", "").strip() == name_key:
                if not position or pdata.get("position", "").lower() == position.lower():
                    return pid
        # fallback fuzzy
        matches = get_close_matches(name_key, [pdata.get("full_name", "").lower() for pdata in sleeper_players.values()], n=1, cutoff=0.9)
        if matches:
            for pid, pdata in sleeper_players.items():
                if pdata.get("full_name", "").lower() == matches[0]:
                    return pid
        return None

    rankings["sleeper_id"] = rankings.apply(lambda r: name_to_id(r["player"], r.get("pos")), axis=1)
    filtered = rankings[~rankings["sleeper_id"].isin(drafted_ids)]

    st.subheader("Available Players")
    st.dataframe(filtered.reset_index(drop=True))
    st.caption(f"Last synced with Sleeper: {ts}")
else:
    st.info("Enter a League ID or Draft ID to sync live picks.")

# --- AUTO REFRESH ---
if draft_id.strip():
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = time.time()
    now = time.time()
    if now - st.session_state["last_refresh"] > REFRESH_INTERVAL:
        st.session_state["last_refresh"] = now
        st.experimental_rerun()
