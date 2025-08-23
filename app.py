import streamlit as st
import pandas as pd
import requests
import re
import unicodedata

st.set_page_config(page_title="Live Draft Rankings Sync", layout="wide")
st.title("📊 Live Draft Rankings Sync — Excel‑Style Board + Live Sleeper Sync")

# --- CONFIG ---
GITHUB_RAW_URL = "https://raw.githubusercontent.com/TheSuper7one/FF2025/refs/heads/main/rankings.csv"

# --- Manual name overrides for Sleeper mapping ---
NAME_ALIASES = {
    "marvin harrison jr": "marvin harrison",
    "cameron ward": "cam ward",  # map to Sleeper's listing
    "cam ward": "cam ward"
}

# --- Helper: normalize + alias ---
def normalize_name(name):
    if not isinstance(name, str):
        return ""
    name = name.lower()
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

def apply_alias(name):
    norm = normalize_name(name)
    return NAME_ALIASES.get(norm, norm)

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
    return pd.read_csv(GITHUB_RAW_URL, skiprows=1)

# --- Parse multi‑section CSV into one DataFrame with debug + skip invalid ---
def parse_rankings(df):
    blocks = {
        "OVERALL": 0,
        "QB": 5,
        "RB": 10,
        "WR": 15,
        "TE": 20,
        "DEF": 25,
        "K": 30
    }
    all_players = []
    valid_positions = []

    st.subheader("📋 Parsing Debug Info")
    debug_rows = []

    for pos_name, start_col in blocks.items():
        block_df = df.iloc[:, start_col:start_col + 4]
        cols_found = block_df.shape[1]
        rows_found = block_df.dropna(subset=[block_df.columns[1]]).shape[0]

        if cols_found == 4 and rows_found > 0:
            status = "✅"
            valid_positions.append(pos_name)
        else:
            status = "⚠️"

        debug_rows.append({
            "Position": pos_name,
            "Start Col": start_col,
            "Cols Found": cols_found,
            "Rows Found": rows_found,
            "Status": status
        })

        if status == "⚠️":
            continue

        block_df.columns = ["Rank", "Player", "Pos", "NFL Team"]
        block_df["Source_Pos"] = pos_name
        block_df = block_df.dropna(subset=["Player"])
        all_players.append(block_df)

    st.table(pd.DataFrame(debug_rows))
    st.session_state["valid_positions"] = valid_positions

    return pd.concat(all_players, ignore_index=True)

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
    raw_df = pd.read_csv(uploaded_file, skiprows=1)
else:
    try:
        raw_df = load_default_rankings()
        st.caption("📂 Loaded default rankings from GitHub (cached for this session)")
    except Exception as e:
        st.error(f"Could not load default rankings from GitHub: {e}")
        raw_df = None

# --- Main logic ---
if raw_df is not None:
    rankings = parse_rankings(raw_df)

    # Apply alias mapping before merge
    rankings["norm_name"] = rankings["Player"].apply(apply_alias)

    sleeper_df = get_sleeper_players()
    merged = rankings.merge(
        sleeper_df[["Sleeper_ID", "norm_name", "Pos"]],
        on="norm_name",
        how="left"
    )

    # --- Position filter buttons (only valid ones) ---
    positions = st.session_state.get("valid_positions", [])
    if positions:
        cols = st.columns(len(positions))
        if "active_pos" not in st.session_state:
            st.session_state.active_pos = positions[0]
        for i, pos in enumerate(positions):
            if cols[i].button(pos):
                st.session_state.active_pos = pos
    else:
        st.warning("No valid position blocks found in the rankings file.")

    # Filter by active position
    filtered = merged[merged["Source_Pos"] == st.session_state.active_pos]

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

    # Show unmatched players (deduped)
    unmatched = merged[merged["Sleeper_ID"].isna()].drop_duplicates(subset=["norm_name"])
    if not unmatched.empty:
        with st.expander("⚠️ Players not matched to Sleeper IDs"):
            st.write(unmatched[["Player"]])
else:
    st.info("No rankings available — upload a file or check GitHub URL.")
