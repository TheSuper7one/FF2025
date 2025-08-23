import streamlit as st
import pandas as pd
import requests
import re
import unicodedata
from streamlit_autorefresh import st_autorefresh  # ✅ Correct import for timed refresh

st.set_page_config(page_title="Live Draft Rankings Sync", layout="wide")
st.title("📊 Live Draft Rankings Sync — Excel‑Style Board + Live Sleeper Sync")

# --- CONFIG ---
GITHUB_RAW_URL = "https://raw.githubusercontent.com/TheSuper7one/FF2025/refs/heads/main/rankings.csv"

# --- Manual name overrides for Sleeper mapping ---
NAME_ALIASES = {
    "marvin harrison jr": "marvin harrison",
    "cameron ward": "cam ward",
    "cam ward": "cam ward"
}

# --- Helper: normalize + alias ---
def normalize_name(name):
    if not isinstance(name, str):
        return ""
    name = name.lower()
    name = ''.join(c for c in unicodedata.normalize('NFD', name)
                   if unicodedata.category(c) != 'Mn')
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
        first = pdata.get('first_name', '') or ''
        last = pdata.get('last_name', '') or ''
        full_name = f"{first} {last}".strip()
        pos = pdata.get("position", "") or ""
        team = pdata.get("team", "") or ""
        player_list.append({
            "Sleeper_ID": pid,
            "Sleeper_Name": full_name,
            "Sleeper_Pos": pos,
            "Sleeper_Team": team,
            "norm_name": normalize_name(full_name),
        })
    return pd.DataFrame(player_list)

# --- Cached: load rankings from GitHub ---
@st.cache_data(show_spinner=False)
def load_default_rankings():
    return pd.read_csv(GITHUB_RAW_URL, skiprows=1)

# --- Parse multi‑section CSV into one DataFrame ---
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

        block_df.columns = ["Rank", "Player", "Sheet_Pos", "NFL Team"]
        block_df["Rank"] = pd.to_numeric(block_df["Rank"], errors="coerce").astype("Int64")
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
uploaded_file = st.file_uploader(
    "Upload rankings.csv (optional — will use GitHub default if empty)", type="csv"
)
draft_url = st.text_input("Sleeper Draft ID or URL (optional for live sync)")
auto_sync = st.toggle("Auto-refresh")
interval = st.slider("Refresh interval (seconds)", 5, 30, 10)

# New toggle to show/hide drafted players
show_drafted = st.toggle("Show Drafted Players", value=False)

if auto_sync:
    st_autorefresh(interval=interval * 1000, key="autorefresh")

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

    # Normalize with aliases
    rankings["norm_name"] = rankings["Player"].apply(apply_alias)
    rankings["NFL Team"] = rankings["NFL Team"].fillna("").astype(str).str.upper()

    sleeper_df = get_sleeper_players()

    # Strict match: name + position + team
    strict_merged = rankings.merge(
        sleeper_df[["Sleeper_ID", "norm_name", "Sleeper_Pos", "Sleeper_Team"]],
        left_on=["norm_name", "Sheet_Pos", "NFL Team"],
        right_on=["norm_name", "Sleeper_Pos", "Sleeper_Team"],
        how="left"
    )

    # Relaxed match: name + position only
    unmatched_mask = strict_merged["Sleeper_ID"].isna()
    if unmatched_mask.any():
        relaxed = rankings.loc[unmatched_mask].merge(
            sleeper_df[["Sleeper_ID", "norm_name", "Sleeper_Pos"]],
            left_on=["norm_name", "Sheet_Pos"],
            right_on=["norm_name", "Sleeper_Pos"],
            how="left"
        )
        strict_merged.loc[unmatched_mask, "Sleeper_ID"] = relaxed["Sleeper_ID"].values

    merged = strict_merged

    # Position filter buttons
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

    active = st.session_state.active_pos
    filtered = merged[merged["Source_Pos"] == active].copy()

    # Deduplicate: prefer rows with Sleeper_ID, then lower Rank
    filtered["has_id"] = filtered["Sleeper_ID"].notna().astype(int)
    filtered = filtered.sort_values(by=["has_id", "Rank"], ascending=[False, True])
    filtered = filtered.drop_duplicates(subset=["norm_name"], keep="first")
    filtered = filtered.drop(columns=["has_id"])

    # Draft sync
    drafted_ids = []
    if draft_url:
        draft_id = extract_draft_id(draft_url)
        drafted_ids = fetch_drafted_ids(draft_id)

    filtered["Drafted"] = filtered["Sleeper_ID"].isin(drafted_ids)

    # Apply toggle logic
    if not show_drafted:
        visible_df = filtered[~filtered["Drafted"]].copy()
    else:
        visible_df = filtered.copy()

    # Rename for cleaner UI
    visible_df = visible_df.rename(columns={"Sheet_Pos": "Pos"})

    # Drafted column as checkmark
    visible_df["Drafted"] = visible_df["Drafted"].apply(lambda x: "✅" if x else "")

    # Display
    display_cols = ["Rank", "Player", "Pos", "NFL Team", "Drafted"]
    st.dataframe(visible_df[display_cols], use_container_width=True)

    if auto_sync:
        st.caption(f"🔄 Auto-refreshing every {interval} seconds…")

    # Show unmatched players (with consistent Pos label)
    unmatched = merged[merged["Sleeper_ID"].isna()].drop_duplicates(subset=["norm_name"])
    if not unmatched.empty:
        unmatched = unmatched.rename(columns={"Sheet_Pos": "Pos"})
        with st.expander("⚠️ Players not matched to Sleeper IDs"):
            st.write(unmatched[["Player
