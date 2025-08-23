import streamlit as st
import pandas as pd
import requests
import re
from io import StringIO

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="Fantasy Draft Board", layout="wide")

# Your fixed PPR rankings CSV in GitHub (raw URL)
DEFAULT_CSV_URL = "https://raw.githubusercontent.com/TheSuper7one/FF2025/refs/heads/main/rankings.csv"

# Fixed visible columns
REQUIRED_COLS = ["Rank", "Player", "Position", "NFL Team"]

# ---------------------------
# HELPERS
# ---------------------------
def _norm(s: str) -> str:
    # lowercase + collapse non-alphanumerics to underscores
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")

def normalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Normalize common column variants to required names.
    Returns (normalized_df, mapping_used)
    mapping_used shows which original column mapped to each required.
    """
    if df.empty:
        # Ensure required columns exist even if empty
        for c in REQUIRED_COLS:
            if c not in df.columns:
                df[c] = pd.Series(dtype="object")
        return df[REQUIRED_COLS], {}

    norm_index = {_norm(c): c for c in df.columns}

    # Synonyms for each target
    rank_candidates = [
        "rank", "overall", "overall_rank", "consensus_rank", "rk", "ecr",
        "overall_ecr", "ovr", "rank_ecr"
    ]
    player_candidates = ["player", "player_name", "name", "full_name", "player_full_name"]
    pos_candidates = ["position", "pos"]
    team_candidates = ["nfl_team", "team", "tm", "nfl", "pro_team", "proteam"]

    mapping_used = {}

    def pick(syns):
        for key in syns:
            if key in norm_index:
                return norm_index[key]
        return None

    rank_src = pick(rank_candidates)
    player_src = pick(player_candidates)
    pos_src = pick(pos_candidates)
    team_src = pick(team_candidates)

    # Build normalized view
    out = pd.DataFrame(index=df.index)

    # Player (required)
    if player_src is None:
        # Try to recover: if only one of Name-like exists with title case, pick the longest string col
        # but safer: fail gracefully and create placeholder
        out["Player"] = df.iloc[:, 0].astype(str) if not df.empty else pd.Series(dtype="object")
        mapping_used["Player"] = df.columns[0] if len(df.columns) else None
    else:
        out["Player"] = df[player_src].astype(str)
        mapping_used["Player"] = player_src

    # Position (required)
    if pos_src is None:
        # Create empty; will render but let you see it's missing
        out["Position"] = ""
        mapping_used["Position"] = None
    else:
        out["Position"] = df[pos_src].astype(str).str.upper()
        mapping_used["Position"] = pos_src

    # NFL Team (required)
    if team_src is None:
        out["NFL Team"] = ""
        mapping_used["NFL Team"] = None
    else:
        out["NFL Team"] = df[team_src].astype(str).str.upper()
        mapping_used["NFL Team"] = team_src

    # Rank (required)
    if rank_src is None:
        # Fallback: sequential rank by current order
        out["Rank"] = range(1, len(df) + 1)
        mapping_used["Rank"] = None
    else:
        # Coerce numeric; if non-numeric, use order fallback
        rank_series = pd.to_numeric(df[rank_src], errors="coerce")
        if rank_series.isna().all():
            out["Rank"] = range(1, len(df) + 1)
            mapping_used["Rank"] = None
        else:
            out["Rank"] = rank_series
            mapping_used["Rank"] = rank_src

    # Sort by Rank ascending
    out = out.sort_values(by="Rank", ascending=True, kind="mergesort").reset_index(drop=True)

    return out[REQUIRED_COLS], mapping_used

def position_color(pos: str) -> str:
    colors = {
        "QB": "#1E90FF",   # blue
        "WR": "#32CD32",   # green
        "RB": "#FF4500",   # red
        "TE": "#9370DB"    # purple
    }
    return colors.get(str(pos).upper(), "#2b2b2b")

# ---------------------------
# DATA LOADING
# ---------------------------
def load_rankings(url: str) -> tuple[pd.DataFrame, dict]:
    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        df_raw = pd.read_csv(StringIO(resp.text))
        df_norm, mapping = normalize_columns(df_raw)
        return df_norm, mapping
    except Exception as e:
        st.error(f"Error loading rankings from GitHub: {e}")
        # Return empty normalized frame + mapping
        empty = pd.DataFrame(columns=REQUIRED_COLS)
        return empty, {}

# ---------------------------
# RENDER
# ---------------------------
def render_board(df: pd.DataFrame):
    if df.empty:
        st.warning("No data to display. Check your CSV URL and headers.")
        return

    positions = sorted(df["Position"].dropna().unique())
    if len(positions) == 0:
        st.warning("No positions detected. Check the Position column in your CSV.")
        return

    for pos in positions:
        pos_df = df[df["Position"] == pos].copy()

        def style_row(row):
            return [f"background-color: {position_color(row['Position'])}" for _ in row]

        st.markdown(f"### {pos}")
        st.dataframe(
            pos_df[REQUIRED_COLS].style.apply(style_row, axis=1),
            use_container_width=True
        )

# ---------------------------
# MAIN
# ---------------------------
st.title("🏈 Fantasy Draft Board (PPR Rankings)")
st.caption("Loads the latest PPR rankings from GitHub and displays with position colors.")

df, mapping = load_rankings(DEFAULT_CSV_URL)

with st.expander("Debug: detected column mapping", expanded=False):
    st.write({k: (v if v is not None else "(generated/fallback)") for k, v in mapping.items()})
    if not df.empty:
        st.write("First 3 rows (normalized):")
        st.dataframe(df.head(3), use_container_width=True)

render_board(df)

# ---------------------------
# STYLES
# ---------------------------
st.markdown(
    """
    <style>
    body { background-color: #1e1e1e; color: #f5f5f5; }
    .stDataFrame { background-color: #2b2b2b; }
    table { color: #f5f5f5 !important; }
    </style>
    """,
    unsafe_allow_html=True
)
