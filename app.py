import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from io import StringIO

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(
    page_title="Fantasy Draft Board",
    layout="wide",
    initial_sidebar_state="expanded"
)

SLEEPER_BASE = "https://api.sleeper.app/v1"

# IMPORTANT: Replace with your real raw GitHub CSV URL for PPR rankings
# Example: "https://raw.githubusercontent.com/your-user/your-repo/main/data/ppr_rankings.csv"
DEFAULT_CSV_URL = "https://raw.githubusercontent.com/<your-username>/<your-repo>/main/<path-to-rankings>.csv"

REQUIRED_COLS = {"Rank", "Player", "Position", "NFL Team"}

# ---------------------------
# UTILS
# ---------------------------
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common column variants to required names and ensure Drafted column exists."""
    if df.empty:
        return df

    # Build a lowercase mapping of existing columns
    lower_map = {c.lower().strip(): c for c in df.columns}

    # Candidate mappings (left: possible input, right: required)
    candidates = {
        "rank": "Rank",
        "overall": "Rank",
        "ecr": "Rank",
        "player": "Player",
        "name": "Player",
        "position": "Position",
        "pos": "Position",
        "nfl team": "NFL Team",
        "team": "NFL Team",
        "nfl": "NFL Team"
    }

    rename_map = {}
    for k, target in candidates.items():
        if k in lower_map:
            rename_map[lower_map[k]] = target

    if rename_map:
        df = df.rename(columns=rename_map)

    # Ensure required columns exist (don’t crash later)
    # If Rank is missing but there is an index, we can create a best-effort Rank
    if "Rank" not in df.columns:
        df["Rank"] = range(1, len(df) + 1)

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        # Keep the dataframe but warn; render() will guard appropriately
        st.warning(f"Some required columns are missing after normalization: {sorted(list(missing))}")

    # Ensure Drafted exists
    if "Drafted" not in df.columns:
        df["Drafted"] = False

    return df


@st.cache_data(show_spinner=False)
def load_player_data(csv_file) -> pd.DataFrame:
    try:
        df = pd.read_csv(csv_file)
        return normalize_columns(df)
    except Exception as e:
        st.error(f"Error loading uploaded CSV: {e}")
        return pd.DataFrame(columns=list(REQUIRED_COLS) + ["Drafted"])


@st.cache_data(show_spinner=False)
def load_default_rankings(url: str):
    """Load default rankings from GitHub and return (DataFrame, last_updated_dt_utc or None)."""
    if not url or "<your-" in url:
        st.info("Default rankings URL is not set. Please update DEFAULT_CSV_URL in the code or upload a CSV.")
        return pd.DataFrame(columns=list(REQUIRED_COLS) + ["Drafted"]), None

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df = normalize_columns(df)

        # Parse Last-Modified from headers if present
        last_updated = None
        if "Last-Modified" in resp.headers:
            try:
                last_updated = datetime.strptime(resp.headers["Last-Modified"], "%a, %d %b %Y %H:%M:%S %Z")
            except Exception:
                last_updated = None

        return df, last_updated
    except Exception as e:
        st.warning(f"Could not fetch default rankings from GitHub: {e}")
        return pd.DataFrame(columns=list(REQUIRED_COLS) + ["Drafted"]), None


@st.cache_data(show_spinner=False)
def fetch_sleeper_picks(draft_id: str):
    """Return raw picks list from Sleeper for a draft id."""
    if not draft_id:
        return []
    try:
        picks_url = f"{SLEEPER_BASE}/draft/{draft_id}/picks"
        resp = requests.get(picks_url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Could not fetch Sleeper draft data: {e}")
        return []


def extract_drafted_names(picks) -> list:
    """Build full name list from Sleeper pick metadata."""
    names = []
    for p in picks:
        meta = p.get("metadata") or {}
        first = (meta.get("first_name") or "").strip()
        last = (meta.get("last_name") or "").strip()
        full = f"{first} {last}".strip()
        if full:
            names.append(full)
    return names


def estimate_current_round(picks) -> int:
    """Estimate current round from number of unique teams and total picks."""
    if not picks:
        return 1
    teams = {p.get("picked_by") for p in picks if p.get("picked_by")}
    num_teams = max(1, len(teams))  # avoid div by zero
    return max(1, (len(picks) // num_teams) + 1)


def position_color(pos: str) -> str:
    colors = {
        "QB": "#1E90FF",   # blue
        "WR": "#32CD32",   # green
        "RB": "#FF4500",   # red
        "TE": "#9370DB"    # purple
    }
    return colors.get(str(pos).upper(), "#2b2b2b")  # default dark gray


def render_draft_board(df: pd.DataFrame):
    """Render per-position tables with fixed visible columns and color-coding."""
    # Guard: ensure required columns exist
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        st.error(f"Cannot render board. Missing required columns: {sorted(list(missing))}")
        return

    # Hide drafted players for display
    if "Drafted" in df.columns:
        df_view = df[~df["Drafted"]].copy()
    else:
        df_view = df.copy()
        df_view["Drafted"] = False

    # If nothing to show, say so gracefully
    if df_view.empty:
        st.info("No available players to display.")
        return

    # Fixed visible columns
    display_cols = ["Rank", "Player", "Position", "NFL Team", "Drafted"]
    df_display = df_view[display_cols].copy()

    # Render by position
    positions = list(df_display["Position"].dropna().astype(str).str.upper().unique())
    for pos in sorted(positions):
        pos_df = df_display[df_display["Position"].astype(str).str.upper() == pos].copy()
        if pos_df.empty:
            continue
        pos_df = pos_df.sort_values(by="Rank", ascending=True)

        def style_row(row):
            base_color = position_color(row["Position"])
            return [f"background-color: {base_color}" for _ in row]

        st.markdown(f"### {pos}")
        st.dataframe(
            pos_df.style.apply(style_row, axis=1),
            use_container_width=True
        )


# ---------------------------
# SIDEBAR
# ---------------------------
st.sidebar.header("Fantasy Draft Board Settings")
uploaded_csv = st.sidebar.file_uploader("Upload Player CSV", type=["csv"])
draft_id = st.sidebar.text_input("Sleeper Draft ID", placeholder="e.g., 123456789012345678")
st.sidebar.caption("Tip: Leave CSV empty to use the default GitHub PPR rankings.")

# ---------------------------
# MAIN
# ---------------------------
st.title("🏈 Fantasy Draft Board")
st.caption("Stable base: GitHub fallback, safe rendering, position colors, and drafted-player hiding.")

# Load rankings
last_updated = None
if uploaded_csv:
    df = load_player_data(uploaded_csv)
else:
    df, last_updated = load_default_rankings(DEFAULT_CSV_URL)
    if last_updated:
        st.markdown(f"**📅 Rankings last updated:** {last_updated.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    elif DEFAULT_CSV_URL and "<your-" not in DEFAULT_CSV_URL:
        st.markdown("**📅 Rankings last updated:** unavailable")

# Fetch picks and mark drafted (safe even if df is empty)
picks = fetch_sleeper_picks(draft_id) if draft_id else []
drafted_names = extract_drafted_names(picks) if picks else []
current_round = estimate_current_round(picks) if picks else 1

if not df.empty and "Player" in df.columns:
    df["Drafted"] = df["Player"].isin(drafted_names)

# Manual refresh control while we stabilize
col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🔄 Refresh now"):
        st.experimental_rerun()
with col2:
    st.write(f"Current round estimate: {current_round}")

# Render board (handles empty/missing columns safely)
render_draft_board(df)

# ---------------------------
# FOOTER
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
