import streamlit as st
import pandas as pd
import requests
import re

st.set_page_config(page_title="Live Draft Rankings Sync", layout="wide")
st.title("📊 Live Draft Rankings Sync")

# --- Inputs ---
draft_url = st.text_input("Sleeper Draft ID or URL")
uploaded_file = st.file_uploader("Upload rankings.csv", type="csv")
auto_sync = st.toggle("Auto-refresh")
interval = st.slider("Refresh interval (seconds)", 5, 30, 10)

# --- Helper functions ---
def extract_draft_id(url_or_id):
    match = re.search(r"draft/(\d+)", url_or_id)
    return match.group(1) if match else url_or_id.strip()

def fetch_drafted_players(draft_id):
    picks_url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    r = requests.get(picks_url)
    if r.status_code != 200:
        return []
    picks = r.json()
    return [
        f"{p['metadata'].get('first_name','')} {p['metadata'].get('last_name','')}".strip()
        for p in picks if 'metadata' in p
    ]

# --- Auto-refresh logic ---
if auto_sync:
    st.experimental_rerun() if "last_refresh" in st.session_state else None
    st.session_state["last_refresh"] = True
    st_autorefresh = st.experimental_rerun  # placeholder for clarity

# --- Main display ---
if uploaded_file and draft_url:
    draft_id = extract_draft_id(draft_url)
    drafted = fetch_drafted_players(draft_id)
    rankings = pd.read_csv(uploaded_file)

    # Mark drafted players
    rankings['Drafted'] = rankings['Player'].isin(drafted)

    # Style drafted players
    styled = rankings.style.apply(
        lambda row: [
            'text-decoration: line-through; color: gray' if row.Drafted else ''
            for _ in row
        ],
        axis=1
    )

    st.dataframe(styled, use_container_width=True)

    if auto_sync:
        st.caption(f"🔄 Auto-refreshing every {interval} seconds…")
else:
    st.info("Upload your rankings.csv and enter a Sleeper draft URL to begin.")
