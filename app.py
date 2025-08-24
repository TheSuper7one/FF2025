import streamlit as st
import pandas as pd
import requests
import re
import unicodedata
import time

st.set_page_config(page_title="Live Draft Rankings Sync", layout="wide")
st.title("📊 Live Draft Rankings Sync — Excel‑Style Board + Live Sleeper Sync")

# --- CONFIG ---
GITHUB_RAW_URL = "https://raw.githubusercontent.com/TheSuper7one/FF2025/refs/heads/main/rankings.csv"
NAME_ALIASES = {
    "marvin harrison jr": "marvin harrison",
    "cameron ward": "cam ward",
    "cam ward": "cam ward"
}
REFRESH_INTERVAL = 3  # seconds — fast refresh during live draft

# --- Helpers ---
def normalize_name(name):
    if not isinstance(name, str):
        return ""
    name = name.lower()
    name = ''.join(c for c in unicodedata.normalize('NFD', name)
                   if unicodedata.category(c) != 'Mn')
    name = re.sub(r"[^\w\s]", "", name)
    return re.sub(r"\s+", " ", name).strip()

def apply_alias(name):
    norm = normalize_name(name)
    return NAME_ALIASES.get(norm, norm)

@st.cache_data(show_spinner=False)
def get_sleeper_players():
    players = requests.get("https://api.sleeper.app/v1/players/nfl").json()
    return pd.DataFrame([{
        "Sleeper_ID": pid,
        "Sleeper_Name": f"{pdata.get('first_name','')} {pdata.get('last_name','')}".strip(),
        "Sleeper_Pos": pdata.get("position", "") or "",
        "Sleeper_Team": pdata.get("team", "") or "",
        "norm_name": normalize_name(f"{pdata.get('first_name','')} {pdata.get('last_name','')}")
    } for pid, pdata in players.items()])

@st.cache_data(ttl=60)
def load_default_rankings():
    try:
        df = pd.read_csv(GITHUB_RAW_URL)
        return df
    except Exception as e:
        st.error(f"⚠️ Error loading rankings from GitHub: {e}")
        return pd.DataFrame(columns=["Player", "Sheet_Pos", "NFL Team", "Rank"])

def parse_rankings(df):
    blocks = {"OVERALL": 0, "QB": 5, "RB": 10, "WR": 15, "TE": 20, "DEF": 25, "K": 30}
    all_players, valid_positions = [], []
    for pos_name, start_col in blocks.items():
        block_df = df.iloc[:, start_col:start_col + 4]
        cols_found, rows_found = block_df.shape[1], block_df.dropna(subset=[block_df.columns[1]]).shape[0]
        status = "✅" if cols_found == 4 and rows_found > 0 else "⚠️"
        if status == "✅":
            valid_positions.append(pos_name)
            block_df.columns = ["Rank", "Player", "Sheet_Pos", "NFL Team"]
            block_df["Rank"] = pd.to_numeric(block_df["Rank"], errors="coerce").astype("Int64")
            block_df["Source_Pos"] = pos_name
            all_players.append(block_df.dropna(subset=["Player"]))
    st.session_state["valid_positions"] = valid_positions
    return pd.concat(all_players, ignore_index=True) if all_players else pd.DataFrame()

def extract_draft_id(url_or_id):
    m = re.search(r"draft/(?:nfl/)?(\d+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()

# --- LIVE fetch of drafted IDs (no caching) ---
def fetch_drafted_ids_live(draft_id):
    if not draft_id:
        return []
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return [p.get("player_id") for p in r.json() if "player_id" in p]
    except Exception as e:
        st.warning(f"Error fetching picks: {e}")
    return []

# --- Inputs ---
draft_url = st.text_input("Sleeper Draft ID or URL (optional for live sync)")

# --- Load rankings ---
raw_df = load_default_rankings()

if not raw_df.empty:
    rankings = parse_rankings(raw_df)
    rankings["norm_name"] = rankings["Player"].apply(apply_alias)
    rankings["NFL Team"] = rankings["NFL Team"].fillna("").astype(str).str.upper()
    sleeper_df = get_sleeper_players()

    # Strict match
    strict = rankings.merge(
        sleeper_df[["Sleeper_ID", "norm_name", "Sleeper_Pos", "Sleeper_Team"]],
        left_on=["norm_name", "Sheet_Pos", "NFL Team"],
        right_on=["norm_name", "Sleeper_Pos", "Sleeper_Team"],
        how="left"
    )

    # Relaxed match
    unmatched_mask = strict["Sleeper_ID"].isna()
    if unmatched_mask.any():
        relaxed = rankings.loc[unmatched_mask].merge(
            sleeper_df[["Sleeper_ID", "norm_name", "Sleeper_Pos"]],
            left_on=["norm_name", "Sheet_Pos"],
            right_on=["norm_name", "Sleeper_Pos"],
            how="left"
        )
        strict.loc[unmatched_mask, "Sleeper_ID"] = relaxed["Sleeper_ID"].values

    merged = strict

    # Initialize active position
    if "active_pos" not in st.session_state:
        st.session_state["active_pos"] = "OVERALL"

    # Position filter buttons
    positions = st.session_state.get("valid_positions", [])
    if positions:
        cols = st.columns(len(positions))
        for i, pos in enumerate(positions):
            if cols[i].button(pos):
                st.session_state["active_pos"] = pos
    else:
        st.warning("No valid position blocks found.")

    # --- Draft sync ---
    draft_id = extract_draft_id(draft_url) if draft_url else None
    drafted_ids = fetch_drafted_ids_live(draft_id) if draft_id else []
    last_sync = time.strftime("%H:%M:%S") if draft_id else None

    # Filter visible players for active position
    active = st.session_state["active_pos"]
    filtered = merged[merged["Source_Pos"] == active].copy()
    filtered["Drafted"] = filtered["Sleeper_ID"].isin(drafted_ids)
    visible_df = filtered[~filtered["Drafted"]].copy()
    visible_df = visible_df.rename(columns={"Sheet_Pos": "Pos"})
    visible_df.reset_index(drop=True, inplace=True)  # <-- Reset index to remove weird 0 Player row

    # Text color mapping
    pos_text_colors = {"RB": "darkred", "WR": "darkgreen", "QB": "#66b2ff", "TE": "violet", "DEF": "white", "K": "white"}

    def style_player_column(df):
        return df.style.apply(
            lambda col: [f"color: {pos_text_colors.get(pos, 'black')}; font-weight: bold" if col.name == "Player" else "" for pos in df["Pos"]],
            axis=0
        )

    rows_to_show = 15
    row_height_px = 35
    styled_df = style_player_column(visible_df[["Rank", "Player", "Pos", "NFL Team"]])
    st.dataframe(styled_df, use_container_width=True, height=rows_to_show * row_height_px)

    if draft_url.strip():
        st.caption(f"🔄 Auto-refreshing every {REFRESH_INTERVAL} seconds…")
        if last_sync:
            st.caption(f"⏱️ Last synced with Sleeper at {last_sync}")

    # Only show unmatched players
    unmatched = merged[merged["Sleeper_ID"].isna()].drop_duplicates(subset=["norm_name"])
    if not unmatched.empty:
        unmatched = unmatched.rename(columns={"Sheet_Pos": "Pos"})
        with st.expander("⚠️ Players not matched to Sleeper IDs"):
            st.write(unmatched[["Player", "Pos", "NFL Team"]])

else:
    st.info("No rankings available — check GitHub URL.")

# --- Auto-rerun ---
if draft_url.strip():
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = time.time()
    now = time.time()
    if now - st.session_state["last_refresh"] > REFRESH_INTERVAL:
        st.session_state["last_refresh"] = now
        st.experimental_rerun()
