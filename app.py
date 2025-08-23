import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="Fantasy Draft Board", layout="wide")

# --- Load rankings CSV from GitHub ---
@st.cache_data
def load_rankings(url):
    try:
        r = requests.get(url)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        st.error(f"Error loading rankings: {e}")
        return None

# --- Load Sleeper player data ---
@st.cache_data
def load_sleeper_players():
    try:
        r = requests.get("https://api.sleeper.app/v1/players/nfl")
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame.from_dict(data, orient="index")
        return df
    except Exception as e:
        st.error(f"Error loading Sleeper data: {e}")
        return None

# --- Normalize player names for matching ---
def normalize_name(name):
    return (
        str(name)
        .lower()
        .replace(".", "")
        .replace("-", " ")
        .replace("'", "")
        .strip()
    )

# --- Main ---
st.title("🏈 Fantasy Draft Board")

rankings_url = st.text_input(
    "Enter GitHub CSV URL for rankings:",
    value="https://raw.githubusercontent.com/your/repo/main/rankings.csv"
)

raw_df = load_rankings(rankings_url)
sleeper_df = load_sleeper_players()

if raw_df is not None and sleeper_df is not None:
    # Normalize names
    raw_df["norm_name"] = raw_df["Player"].apply(normalize_name)
    sleeper_df["norm_name"] = sleeper_df["full_name"].apply(normalize_name)

    # Merge rankings with Sleeper data
    merged = pd.merge(
        raw_df,
        sleeper_df[["norm_name", "player_id", "team"]],
        on="norm_name",
        how="left"
    )

    merged = merged.rename(columns={
        "player_id": "Sleeper_ID",
        "team": "NFL Team",
        "Position": "Pos"
    })

    # --- Display draft board ---
    st.subheader("Draft Board")
    display_cols = ["Rank", "Player", "Pos", "NFL Team"]
    st.dataframe(
        merged[display_cols],
        use_container_width=True,
        hide_index=True
    )
    # --- Only show unmatched players if there are any ---
    unmatched = (
        merged[merged["Sleeper_ID"].isna()]
        .drop_duplicates(subset=["norm_name"])
        .dropna(subset=["Player"])  # remove blank phantom rows
    )
    unmatched = unmatched[unmatched["Player"].str.strip().ne("")]  # remove whitespace-only names

    if not unmatched.empty:
        unmatched = unmatched.rename(columns={"Sheet_Pos": "Pos"})
        with st.expander("⚠️ Players not matched to Sleeper IDs"):
            st.write(unmatched[["Player", "Pos", "NFL Team"]])
else:
    st.info("No rankings available — check GitHub URL.")
