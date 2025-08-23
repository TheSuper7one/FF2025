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

# ---------- Helper: Get latest draft_id for a league ----------
def get_latest_draft_id_for_league(league_id):
    drafts_url = f"https://api.sleeper.app/v1/league/{league_id}/drafts"
    drafts_data, err = safe_get_json(drafts_url)
    if err or not drafts_data:
        return None
    # drafts_data is a list; take the first (most recent) draft
    return drafts_data[0].get("draft_id")

# ---------- Helper: Detect ID type and resolve to draft_id ----------
def detect_id_type_and_get_draft_id(id_input):
    # Try league first
    league_url = f"https://api.sleeper.app/v1/league/{id_input}"
    league_data, league_err = safe_get_json(league_url)
    if league_data and "league_id" in league_data:
        draft_id = get_latest_draft_id_for_league(id_input)
        return {"type": "league", "draft_id": draft_id, "data": league_data}

    # Try draft
    draft_url = f"https://api.sleeper.app/v1/draft/{id_input}"
    draft_data, draft_err = safe_get_json(draft_url)
    if draft_data and "draft_id" in draft_data:
        return {"type": "draft", "draft_id": id_input, "data": draft_data}

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
    result = detect_id_type_and_get_draft_id(id_input)

    if result.get("error"):
        st.error(f"❌ {result['error']}")
    elif not result.get("draft_id"):
        st.warning("No draft found for this ID.")
    else:
        if result["type"] == "league":
            st.success(f"✅ Detected: League ID — {result['data'].get('name', '')}")
        elif result["type"] == "draft":
            st.success("✅ Detected: Draft ID (mock or real)")

        picks, err = fetch_picks(result["draft_id"])
        if err:
            st.error(f"Could not fetch picks: {err}")
        else:
            st.subheader("Draft Picks")
            st.dataframe(format_picks_table(picks))
