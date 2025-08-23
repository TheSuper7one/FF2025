import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime

st.set_page_config(page_title="Sleeper Draft Board", layout="wide")

# ---------- Safe API fetch ----------
def safe_get_json(url):
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

# ---------- Extract ID from URL or raw input ----------
def extract_id(user_input):
    match = re.search(r"(\d{15,})", user_input)
    return match.group(1) if match else user_input.strip()

# ---------- Fetch picks ----------
def fetch_picks(draft_id):
    picks_url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    picks_data, picks_err = safe_get_json(picks_url)
    if picks_err:
        return None, picks_err
    return picks_data, None

# ---------- Format picks ----------
def format_picks_table(picks):
    if not picks:
        return pd.DataFrame()
    df = pd.DataFrame(picks)
    keep_cols = ["round", "pick_no", "player_id", "roster_id", "picked_by"]
    for col in keep_cols:
        if col not in df.columns:
            df[col] = None
    return df[keep_cols].sort_values(by=["round", "pick_no"])

# ---------- Streamlit UI ----------
st.title("🏈 Sleeper Draft Board")
st.write("Paste a **Sleeper League ID**, **Draft ID**, or full Sleeper draft URL (mock or real).")

user_input = st.text_input("Sleeper League/Draft URL or ID:")
if user_input:
    draft_id = extract_id(user_input)

    # Try to get draft info
    draft_url = f"https://api.sleeper.app/v1/draft/{draft_id}"
    draft_data, draft_err = safe_get_json(draft_url)

    if draft_err:
        if "404" in draft_err:
            st.warning("📅 This draft lobby exists but has not started yet. Picks will appear once it begins.")
        else:
            st.error(f"❌ {draft_err}")
    elif draft_data:
        status = draft_data.get("status", "").lower()
        if status == "pre_draft":
            start_time = draft_data.get("start_time")
            if start_time:
                start_dt = datetime.fromtimestamp(start_time / 1000)
                st.info(f"📅 Draft scheduled to start at {start_dt} (local time).")
            else:
                st.info("📅 Draft has not started yet.")
        else:
            st.success(f"✅ Draft status: {status.capitalize()}")
            picks, err = fetch_picks(draft_id)
            if err:
                st.error(f"Could not fetch picks: {err}")
            else:
                st.subheader("Draft Picks")
                st.dataframe(format_picks_table(picks))
