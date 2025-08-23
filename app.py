import requests
import streamlit as st

def get_sleeper_data(id_input):
    """
    Detects whether the ID is a league or draft and fetches the right data.
    """
    # Try league endpoint first
    league_url = f"https://api.sleeper.app/v1/league/{id_input}"
    league_resp = requests.get(league_url).json()

    if league_resp and isinstance(league_resp, dict) and "league_id" in league_resp:
        st.success("Detected: League ID ✅")
        return {"type": "league", "data": league_resp}

    # If league failed, try draft endpoint
    draft_url = f"https://api.sleeper.app/v1/draft/{id_input}"
    draft_resp = requests.get(draft_url).json()

    if draft_resp and isinstance(draft_resp, dict) and "draft_id" in draft_resp:
        st.success("Detected: Draft ID (mock or real) ✅")
        return {"type": "draft", "data": draft_resp}

    # If both fail
    st.error("Invalid ID — not a valid Sleeper league or draft.")
    return None

# Streamlit UI
st.title("Sleeper Draft Board")
id_input = st.text_input("Enter your Sleeper League ID or Draft ID:")

if id_input:
    result = get_sleeper_data(id_input)
    if result:
        st.write("Raw data:", result["data"])
        # You can now branch your logic:
        if result["type"] == "league":
            # Fetch league rosters, draft_id, etc.
            pass
        elif result["type"] == "draft":
            # Fetch picks directly from draft endpoint
            pass

