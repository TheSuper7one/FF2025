import streamlit as st
import pandas as pd
import requests
import re
import unicodedata

st.set_page_config(page_title="Live Draft Rankings Sync", layout="wide")
st.title("📊 Live Draft Rankings Sync — Auto ID Mapping + GitHub Fallback (Cached)")

# --- CONFIG ---
GITHUB_RAW_URL = "https://raw.githubusercontent.com/TheSuper7one/FF2025/refs/heads/main/rankings.csv"

# --- Helper: normalize names ---
def normalize_name(name):
    if not isinstance(name, str):
        return ""
    name = name.lower()
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

# --- Cached: fetch Sleeper player database ---
@st.cache_data(show_spinner=False)
def get_sleeper_players():
    url = "https://api.sleeper.app/v1/players/nfl"
    players = requests.get(url).json()
    player_list = []
    for pid, pdata in players.items():
        full_name = f"{pdata.get('first_name','')} {pdata.get('last_name','')}".strip()
        pos = pdata.get("position", "")
        player_list.append({
            "Sleeper_ID": pid,
            "Player": full_name,
            "Pos": pos,
            "norm_name": normalize_name(full_name)
        })
    return pd.DataFrame(player_list)

# --- Cached: load rankings from GitHub ---
@st.cache_data(show_spinner=False)
def load_default_rankings():
    return pd.read_csv(GITHUB_RAW_URL)

# --- Fetch drafted player IDs ---
def extract_draft_id(url_or_id):
    match = re.search(r"draft/(\d+)", url_or_id)
    return match.group(1) if match else url_or_id.strip()

def fetch_drafted_ids(draft_id):
    picks_url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    r = requests.get(picks_url)
    if r.status_code != 200:
        return []
    picks = r.json()
    return [p.get("player_id") for p in picks if "player_id" in p]

# --- Inputs ---
uploaded_file = st.file_uploader("Upload rankings.csv (optional — will use GitHub default if empty)", type="csv")
draft_url = st.text_input("Sleeper Draft ID or URL (optional for live sync)")
auto_sync = st.toggle("Auto-refresh")
interval = st.slider("Refresh interval (seconds)", 5, 30, 10)

if auto_sync:
    st_autorefresh = st.autorefresh(interval=interval * 1000, key="autorefresh")

# --- Load rankings ---
if uploaded_file:
    rankings = pd.read_csv(uploaded_file)
else:
    try:
        rankings = load_default_rankings()
        st.caption("📂 Loaded default rankings from GitHub (cached for this session)")
    except Exception as e:
        st.error(f"Could not load default rankings from GitHub: {e}")
        rankings = None

# --- Main logic ---
if rankings is not None:
    if "Player" not in rankings.columns:
        st.error("Rankings file must have a 'Player' column.")
    else:
        # Normalize and map IDs
        rankings["norm_name"] = rankings["Player"].apply(normalize_name)
        sleeper_df = get_sleeper_players()
        merged = rankings.merge(
            sleeper_df[["Sleeper_ID", "norm_name", "Pos"]],
            on="norm_name",
            how="left"
        )

        # Filters
        positions = ["ALL"] + sorted(merged["Pos"].dropna().unique())
        pos_filter = st.selectbox("Filter by position", positions)
        top_n = st.number_input(
            "Show top N overall",
            min_value=1,
            max_value=len(merged),
            value=len(merged)
        )

        # Apply filters
        filtered = merged.copy()
        if pos_filter != "ALL":
            filtered = filtered[filtered["Pos"] == pos_filter]
        filtered = filtered.head(top_n)

        # Draft sync
        drafted_ids = []
        if draft_url:
            draft_id = extract_draft_id(draft_url)
            drafted_ids = fetch_drafted_ids(draft_id)

        # Mark drafted players
        filtered["Drafted"] = filtered["Sleeper_ID"].isin(drafted_ids)

        # Style drafted players
        styled = filtered.style.apply(
            lambda row: [
                'text-decoration: line-through; color: gray' if row.Drafted else ''
                for _ in row
            ],
            axis=1
        )

        st.dataframe(styled, use_container_width=True)

        if auto_sync:
            st.caption(f"🔄 Auto-refreshing every {interval} seconds…")

        # Show unmatched players
        unmatched = merged[merged["Sleeper_ID"].isna()]
        if not unmatched.empty:
            with st.expander("⚠️ Players not matched to Sleeper IDs"):
                st.write(unmatched[["Player"]])
else:
    st.info("No rankings available — upload a file or check GitHub URL.")
