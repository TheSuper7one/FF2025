import streamlit as st
import pandas as pd
import requests

# CONFIG
LEAGUE_ID = st.text_input("Enter your Sleeper League ID")
CSV_FILE = "rankings.csv"

@st.cache_data
def load_rankings():
    return pd.read_csv(CSV_FILE)

def get_draft_id(league_id):
    url = f"https://api.sleeper.app/v1/league/{league_id}/drafts"
    return requests.get(url).json()[0]["draft_id"]

def get_drafted_players(draft_id):
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    picks = requests.get(url).json()
    return {f"{p['metadata']['first_name']} {p['metadata']['last_name']}" 
            for p in picks if "metadata" in p}

rankings = load_rankings()

if LEAGUE_ID:
    draft_id = get_draft_id(LEAGUE_ID)
    drafted = get_drafted_players(draft_id)
    available = rankings[~rankings["Player"].isin(drafted)]

    pos_filter = st.selectbox("Filter by position", ["ALL", "QB", "RB", "WR", "TE", "DEF", "K"])
    if pos_filter != "ALL":
        available = available[available["Position"] == pos_filter]

    st.dataframe(available.sort_values("Rank"))
