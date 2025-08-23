import streamlit as st
import pandas as pd
import requests
import re
import time

st.set_page_config(page_title="Live Draft Cheat Sheet + Sleeper Tracker", layout="wide")

# ---------- Helpers ----------
def safe_get_json(url, timeout=10):
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json(), None
        except ValueError:
            return None, f"Invalid JSON from {url} (first 200 chars): {resp.text[:200]}"
    except requests.RequestException as e:
        return None, str(e)

def extract_draft_id(text):
    if not text:
        return ""
    match = re.search(r"(\d{9,})", text)  # allow 9+ digits
    return match.group(1) if match else text.strip()

# ---------- Normalize BDGE export ----------
def normalize_rankings(file_path_or_buffer):
    df = pd.read_csv(file_path_or_buffer)
    sections = {
        "OVERALL": 0,
        "QB": 5,
        "RB": 10,
        "WR": 15,
        "TE": 20,
        "DEF": 25,
        "K": 30,
        "SUPERFLEX": 35
    }
    all_rows = []
    for section, start in sections.items():
        sub = df.iloc[:, start:start+4].copy()
        if sub.shape[1] < 4:
            continue
        sub.columns = ["Rank", "Player", "Position", "Team"]
        sub = sub.dropna(subset=["Player"])
        sub["SourceList"] = section
        sub["Rank"] = pd.to_numeric(sub["Rank"], errors="coerce").astype("Int64")
        sub["Team"] = sub["Team"].astype(str).str.strip()
        sub["Position"] = sub["Position"].astype(str).str.strip()
        sub["Player"] = sub["Player"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        all_rows.append(sub)
    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame(columns=["Rank","Player","Position","Team","SourceList"])

# ---------- Sleeper API ----------
@st.cache_data
def load_player_db():
    url = "https://api.sleeper.app/v1/players/nfl"
    data, err = safe_get_json(url)
    if err or not isinstance(data, dict):
        st.warning(f"Could not load player database: {err}")
        return {}
    return data

def fetch_picks(draft_id):
    if not draft_id or not draft_id.isdigit():
        return [], "Invalid draft ID"
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    data, err = safe_get_json(url)
    if err:
        return [], f"Error fetching picks: {err}"
    if not isinstance(data, list):
        return [], "Unexpected picks format"
    return data, None

def mark_drafted(df, picks, player_db):
    if df.empty:
        df["Drafted"] = []
        return df
    drafted_ids = [str(p.get("player_id")) for p in picks if p.get("player_id") is not None]
    drafted_names = {player_db.get(pid, {}).get("full_name") for pid in drafted_ids if pid in player_db}
    drafted_names = {n for n in drafted_names if n}
    df["Drafted"] = df["Player"].isin(drafted_names)
    return df

# ---------- Draft Order Tracker ----------
TOTAL_TEAMS = 12
MY_SLOT = 8

def current_pick_state(picks_made):
    current_pick_number = (len(picks_made) + 1) if isinstance(picks_made, list) else 1
    current_round = (current_pick_number - 1) // TOTAL_TEAMS + 1
    pick_in_round = (current_pick_number - 1) % TOTAL_TEAMS + 1
    return current_pick_number, current_round, pick_in_round

def render_sleeper_row(round_num, picks, player_db):
    order = list(range(1, TOTAL_TEAMS + 1))
    if round_num % 2 == 0:
        order.reverse()
    by_pick_no = {p.get("pick_no"): p for p in picks if p.get("pick_no") is not None}
    cells = []
    for slot in order:
        overall_pick_no = (round_num - 1) * TOTAL_TEAMS + slot
        pdata = by_pick_no.get(overall_pick_no)
        if pdata and pdata.get("player_id"):
            pid = str(pdata["player_id"])
            name = player_db.get(pid, {}).get("full_name", "Unknown")
            pos = player_db.get(pid, {}).get("position", "")
            txt = f"{name} {pos}".strip()
            style = (
                "background-color:#23272a;color:#aab2bd;padding:6px 8px;"
                "border-radius:6px;flex:1;text-align:center;font-size:0.8em;"
                "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
            )
        else:
            txt = str(slot)
            style = (
                "background-color:#3a3d42;color:#ffffff;padding:6px 8px;"
                "border-radius:6px;flex:1;text-align:center;font-weight:600;"
                "font-size:0.85em;"
            )
        my_slot_even = (TOTAL_TEAMS - MY_SLOT + 1)
        is_my_slot = (
            (round_num % 2 == 1 and slot == MY_SLOT)
            or (round_num % 2 == 0 and slot == my_slot_even)
        )
        if is_my_slot:
            style += "border:2px solid #7289da;"
        cells.append(f"<div style='{style}'>{txt}</div>")
    return f"<div style='display:flex;gap:6px;margin:6px 0;'>{''.join(cells)}</div>"

# ---------- Dark-mode styling ----------
def style_cheat_sheet(df):
    def style_row(row):
        base_bg = "#2c2f33"
        text_color = "#ffffff" if not row.Drafted else "#888888"
        decoration = "line-through" if row.Drafted else "none"
        return [
            f"background-color: {base_bg}; color: {text_color}; text-decoration: {decoration}; font-size: 0.95em; padding: 6px;"
            for _ in row
        ]
    return df.style.apply(style_row, axis=1).set_table_styles([
        {"selector": "thead th", "props": [("background-color", "#23272a"), ("color", "#7289da"), ("font-weight", "bold"), ("font-size", "0.9em"), ("padding", "8px")]}
    ])

# ---------- UI ----------
st.markdown("## 🏈 Live Draft Cheat Sheet + Sleeper Tracker")

left, right = st.columns([2, 1])
with left:
    uploaded_file = st.file_uploader("Optional: Upload updated BDGE CSV to override", type="csv")
with right:
    draft_input = st.text_input("Sleeper Draft ID or URL")
    draft_id = extract_draft_id(draft_input)

colA, colB = st.columns([1, 3])
with colA:
    auto_refresh = st.checkbox("Auto refresh", value=True)
with colB:
    refresh_rate = st.slider("Refresh every (sec)", 5, 60, 10)

load_button = st.button("Load Draft Data")

# Load rankings
if uploaded_file:
    cheat_df = normalize_rankings(uploaded_file)
else:
    cheat_df = normalize_rankings("rankings.csv")

if cheat_df.empty:
    st.warning("No rows detected from rankings CSV.")
    st.stop()

# Auto-refresh logic
if auto_refresh and draft_id and load_button is False:
    st.experimental_rerun()

if draft_id and (load_button or auto_refresh):
    player_db = load_player_db()
    picks, err = fetch_picks(draft_id)
    if err:
        st.warning(err)
    elif not picks:
        st.info("Draft found, but no picks yet. Waiting for draft to start…")
    else:
        cheat_df = mark_drafted(cheat_df, picks, player_db)
        st.dataframe(style_cheat_sheet(cheat_df), use_container_width=True)
        st.markdown("### Draft Board")
        for r in range(1, ((len(picks) // TOTAL_TEAMS) + 2)):
            st.markdown(render_sleeper_row(r, picks, player_db), unsafe_allow_html=True)
    if auto_refresh:
        time.sleep(refresh_rate)
        st.experimental_rerun()
