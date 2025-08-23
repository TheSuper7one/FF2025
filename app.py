import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Sleeper Draft Board", layout="wide")

# ---------- Helper: Safe API fetch ----------
def safe_get_json(url):
    """Fetch JSON safely from a URL, returning (data, error_message)."""
    try:
        resp = requests.get(url)
    except requests.RequestException as e:
        return None, f"Network error: {e}"
    if resp.status_code != 200:
        return None, f"Error {resp.status_code}: {resp.text}"
    try:
        return resp.json(), None
    except ValueError:
        return None, "Response was not valid JSON"

# ---------- Helper: Detect ID type ----------
def detect_id_type(id_input):
    """Detects whether the ID is a league or draft and returns type + data."""
    # Try league endpoint first
    league_url = f"https://api.sleeper.app/v1/league/{id_input}"
    league_data, league_err = safe_get_json(league_url)
    if league_data and isinstance(league_data, dict) and "league_id" in league_data:
        return {"type": "league", "data": league_data}

    # Try draft endpoint
    draft_url = f"https://api.sleeper.app/v1/draft/{id_input}"
    draft_data, draft_err = safe_get_json(draft_url)
    if draft_data and isinstance(draft_data, dict) and "draft_id" in draft_data:
        return {"type": "draft", "data": draft_data}

    # If both fail
    return {"type": None, "error": league_err or draft_err or "Invalid ID"}

# ---------- Helper: Fetch picks ----------
def fetch_picks(draft_id):
    picks_url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    picks_data, picks_err = safe_get_json(picks_url)
    if picks_err:
        return None, picks_err
    return picks_data, None

# ---------- Helper: Format picks ----------
def format_picks_table(picks):
    if not picks:
        return pd.DataFrame()
    df = pd.DataFrame(picks)
    # Keep only useful columns
    keep_cols = ["round", "pick_no", "player_id", "roster_id", "picked_by"]
    for col in keep_cols:
        if col not in df.columns:
            df[col] = None
    return df[keep_cols].sort_values(by=["round", "pick_no"])

# ---------- Streamlit UI ----------
st.title("🏈 Sleeper Draft Board")
st.write("Enter either a **Sleeper League ID** or a **Sleeper Draft ID** (mock or real).")

id_input = st.text_input("Sleeper League/Draft ID:")

if id_input:
    result = detect_id_type(id_input)

    if result.get("error"):
        st.error(f"❌ {result['error']}")
    elif result["type"] == "league":
        st.success(f"✅ Detected: League ID — {result['data'].get('name', '')}")
        draft_id = result["data"].get("draft_id")
        if draft_id:
            picks, err = fetch_picks(draft_id)
            if err:
                st.error(f"Could not fetch picks: {err}")
            else:
                st.subheader("Draft Picks")
                st.dataframe(format_picks_table(picks))
        else:
            st.warning("No draft_id found for this league.")
    elif result["type"] == "draft":
        st.success("✅ Detected: Draft ID (mock or real)")
        picks, err = fetch_picks(id_input)
        if err:
            st.error(f"Could not fetch picks: {err}")
        else:
            st.subheader("Draft Picks")
            st.dataframe(format_picks_table(picks))
