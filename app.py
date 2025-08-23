import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Live Draft Cheat Sheet", layout="wide")

# ---------- Normalize BDGE export ----------
def normalize_rankings(uploaded_file):
    df = pd.read_csv(uploaded_file)

    sections = {
        "OVERALL": 0,
        "QB": 4,
        "RB": 8,
        "WR": 12,
        "TE": 16,
        "DEF": 20,
        "K": 24,
        "SUPERFLEX": 28
    }

    all_rows = []
    for section, start_col in sections.items():
        sub = df.iloc[:, start_col:start_col+4].copy()
        sub.columns = ["Rank", "Player", "Position", "Team"]
        sub = sub.dropna(subset=["Player"])
        sub["SourceList"] = section
        sub["Rank"] = pd.to_numeric(sub["Rank"], errors="coerce").astype("Int64")
        all_rows.append(sub)

    final_df = pd.concat(all_rows, ignore_index=True)
    return final_df

# ---------- Sleeper API helpers ----------
@st.cache_data
def load_player_db():
    url = "https://api.sleeper.app/v1/players/nfl"
    return requests.get(url).json()

def fetch_picks(draft_id):
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    return requests.get(url).json()

def mark_drafted(df, picks, player_db):
    drafted_ids = [str(p['player_id']) for p in picks if p.get('player_id')]
    drafted_names = {player_db[pid]['full_name'] for pid in drafted_ids if pid in player_db}
    df['Drafted'] = df['Player'].isin(drafted_names)
    return df

# ---------- Tier color mapping ----------
def tier_color(tier):
    colors = {
        1: "#FFD700",  # gold
        2: "#ADD8E6",  # light blue
        3: "#90EE90",  # light green
        4: "#FFB6C1",  # light pink
        5: "#FFA07A",  # light salmon
    }
    return colors.get(tier, "#FFFFFF")  # default white

# ---------- UI ----------
st.title("🏈 Live Draft Cheat Sheet (BDGE Style)")

uploaded_file = st.file_uploader("Upload your BDGE export CSV", type="csv")
draft_id = st.text_input("Sleeper Draft ID")
refresh_rate = st.slider("Refresh every (seconds)", 5, 60, 10)

if uploaded_file and draft_id:
    cheat_df = normalize_rankings(uploaded_file)
    player_db = load_player_db()

    picks = fetch_picks(draft_id)
    cheat_df = mark_drafted(cheat_df, picks, player_db)

    # Optional: add Tier column if not present
    if "Tier" not in cheat_df.columns:
        cheat_df["Tier"] = None

    # Filters
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        view_mode = st.radio("View", ["Overall", "By Position"])
    with col2:
        hide_drafted = st.checkbox("Hide Drafted Players", value=False)
    with col3:
        search_term = st.text_input("Search Player")

    if view_mode == "Overall":
        filtered_df = cheat_df[cheat_df["SourceList"] == "OVERALL"]
    else:
        pos = st.selectbox("Position", sorted(cheat_df["Position"].dropna().unique()))
        filtered_df = cheat_df[cheat_df["Position"] == pos]

    if hide_drafted:
        filtered_df = filtered_df[~filtered_df["Drafted"]]

    if search_term:
        filtered_df = filtered_df[filtered_df["Player"].str.contains(search_term, case=False, na=False)]

    # Style drafted players + tier colors
    def style_rows(row):
        styles = []
        bg_color = tier_color(row.Tier) if pd.notna(row.Tier) else "#FFFFFF"
        for col in row.index:
            if row.Drafted:
                styles.append(f'background-color: {bg_color}; color: gray; text-decoration: line-through;')
            else:
                styles.append(f'background-color: {bg_color};')
        return styles

    st.dataframe(
        filtered_df.style.apply(style_rows, axis=1),
        use_container_width=True
    )

    st.experimental_rerun()
