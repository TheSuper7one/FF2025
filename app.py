import streamlit as st
import pandas as pd
import requests
import re
import unicodedata

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

@st.cache_data(show_spinner=False)
def load_default_rankings():
    # No skiprows — CSV already has proper header
    return pd.read_csv(GITHUB_RAW_URL)

def parse_rankings(df):
    blocks = {"OVERALL": 0, "QB": 5, "RB": 10, "WR": 15, "TE": 20, "DEF": 25, "K": 30}
    all_players, valid_positions, debug_rows = [], [], []
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
        debug_rows.append({"Position": pos_name, "Start Col": start_col, "Cols Found": cols_found,
                           "Rows Found": rows_found, "Status": status})
    st.session_state["valid_positions"] = valid_positions
    return pd.concat(all_players, ignore_index=True), pd.DataFrame(debug_rows)

def extract_draft_id(url_or_id):
    m = re.search(r"draft/(?:nfl/)?(\d+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()

def fetch_raw_picks_json(draft_id):
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    r = requests.get(url)
    return r.json() if r.status_code == 200 else []

def fetch_drafted_ids(draft_id):
    data = fetch_raw_picks_json(draft_id)
    return [p.get("player_id") for p in data if "player_id" in p]

# --- Inputs ---
draft_url = st.text_input("Sleeper Draft ID or URL (optional for live sync)")

# Conditional fast auto-refresh: only when draft URL is entered
if draft_url.strip():
    st.components.v1.html(f"<meta http-equiv='refresh' content='{REFRESH_INTERVAL}'>", height=0)

# --- Load rankings from GitHub ---
try:
    raw_df = load_default_rankings()
    st.caption("📂 Loaded default rankings from GitHub")
except Exception as e:
    st.error(f"Could not load default rankings: {e}")
    raw_df = None

# --- Main logic ---
if raw_df is not None:
    rankings, debug_table = parse_rankings(raw_df)
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
        st.warning("No valid position blocks found.")

    active = st.session_state.active_pos
    filtered = merged[merged["Source_Pos"] == active].copy()
    filtered["has_id"] = filtered["Sleeper_ID"].notna().astype(int)
    filtered = filtered.sort_values(by=["has_id", "Rank"], ascending=[False, True])
    filtered = filtered.drop_duplicates(subset=["norm_name"], keep="first").drop(columns=["has_id"])

    # Draft sync
    draft_id = extract_draft_id(draft_url) if draft_url else None
    drafted_ids = fetch_drafted_ids(draft_id) if draft_id else []
    filtered["Drafted"] = filtered["Sleeper_ID"].isin(drafted_ids)

    # Hide drafted players entirely
    visible_df = filtered[~filtered["Drafted"]].copy()
    visible_df = visible_df.rename(columns={"Sheet_Pos": "Pos"})

    # --- Position-based text color mapping ---
    pos_text_colors = {
        "RB": "darkred",
        "WR": "darkgreen",
        "QB": "darkblue",
        "TE": "indigo"
    }

    def style_player_column(df):
        return df.style.apply(
            lambda col: [
                f"color: {pos_text_colors.get(pos, 'black')}; font-weight: bold" if col.name == "Player" else ""
                for pos in df["Pos"]
            ],
            axis=0
        )

    # Display board with 15 visible rows
    rows_to_show = 15
    row_height_px = 35
    styled_df = style_player_column(visible_df[["Rank", "Player", "Pos", "NFL Team"]])

    st.dataframe(styled_df,
                 use_container_width=True,
                 height=rows_to_show * row_height_px)

    if draft_url.strip():
        st.caption(f"🔄 Auto-refreshing every {REFRESH_INTERVAL} seconds…")

    # --- Debug section below board ---
    with st.expander("📋 Debug Info"):
        if draft_url.strip():
            st.write("🛠 DEBUG — Parsed Draft ID:", draft_id)
            st.write("🛠 DEBUG — Raw /picks JSON:", fetch_raw_picks_json(draft_id))
            st.write("🛠 DEBUG — Drafted IDs from Sleeper:", drafted_ids)
        st.table(debug_table)

    unmatched = merged[merged["Sleeper_ID"].isna()].drop_duplicates(subset=["norm_name"])
    if not unmatched.empty:
        unmatched = unmatched.rename(columns={"Sheet_Pos": "Pos"})
        with st.expander("⚠️ Players not matched to Sleeper IDs"):
            st.write(unmatched[["Player", "Pos", "NFL Team"]])
else:
    st.info("No rankings available — check GitHub URL.")
