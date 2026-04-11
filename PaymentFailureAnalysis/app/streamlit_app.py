import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import streamlit.components.v1 as components
from pathlib import Path

st.set_page_config(layout="wide", page_title="PaymentGuard")

# ─── DATA ──────────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    data_path = Path(__file__).resolve().parents[1] / 'data' / 'transactions_raw.csv'
    data = pd.read_csv(data_path)
    data['timestamp'] = pd.to_datetime(data['timestamp'], errors='coerce')
    data['is_failed'] = (data['status'] == 'Failed').astype(int)
    if 'resolution_time_mins' not in data.columns:
        rmap = {
            'wrong_pin': 3, 'insufficient_funds': 2, 'bank_server_timeout': 30,
            'network_failure': 12, 'invalid_account': 120, 'wrong_ifsc': 150,
            'duplicate_txn': 6, 'account_blocked': 60, 'fraud_blocked': 45,
            'outside_neft_hours': 10, 'none': 0, 'network_error': 12
        }
        data['resolution_time_mins'] = data['failure_reason'].map(rmap).fillna(15)
        
    mask = data['failure_reason'].notna()
    data.loc[mask, 'failure_reason'] = data.loc[mask, 'failure_reason'].astype(str).str.replace('_', ' ').str.title()

    if 'is_high_risk' not in data.columns:
        data['is_high_risk'] = (
            (data['hour'].isin([22, 23, 0, 1])) |
            (data['day_of_month'] >= 28)
        ).astype(int)
    return data

df = load_data()

# ─── RELIABILITY SCORES ────────────────────────────────────────────────────────
@st.cache_data
def compute_scores(data):
    sev_map = {
        'Wrong Pin': 2, 'Insufficient Funds': 2, 'Bank Server Timeout': 9,
        'Network Failure': 6, 'Invalid Account': 5, 'Wrong Ifsc': 5,
        'Duplicate Txn': 4, 'Account Blocked': 8, 'Fraud Blocked': 9,
        'Outside Neft Hours': 3, 'None': 0, 'Network Error': 6
    }
    grp = data.groupby(['bank_name', 'payment_channel']).agg(
        total=('is_failed', 'count'),
        failures=('is_failed', 'sum'),
        avg_res=('resolution_time_mins', 'mean')
    ).reset_index()
    grp['failure_rate'] = grp['failures'] / grp['total'] * 100
    fd = data[data['is_failed'] == 1].copy()
    fd['sev'] = fd['failure_reason'].map(sev_map).fillna(5)
    sv = fd.groupby(['bank_name', 'payment_channel'])['sev'].mean().reset_index()
    sv.columns = ['bank_name', 'payment_channel', 'avg_sev']
    grp = grp.merge(sv, on=['bank_name', 'payment_channel'], how='left')
    grp['avg_sev'] = grp['avg_sev'].fillna(5)

    def norm(s, mn, mx):
        return 0 if mx == mn else (s - mn) / (mx - mn) * 100

    grp['fr_n'] = grp['failure_rate'].apply(lambda x: norm(x, grp['failure_rate'].min(), grp['failure_rate'].max()))
    grp['rt_n'] = grp['avg_res'].apply(lambda x: norm(x, grp['avg_res'].min(), grp['avg_res'].max()))
    grp['sv_n'] = grp['avg_sev'].apply(lambda x: norm(x, grp['avg_sev'].min(), grp['avg_sev'].max()))
    grp['score'] = ((100 - grp['fr_n']) * 0.5 + (100 - grp['rt_n']) * 0.3 + (100 - grp['sv_n']) * 0.2).round(1)
    grp['combo'] = grp['bank_name'] + ' ' + grp['payment_channel']

    def grade(s):
        if s >= 80: return 'Excellent', '#0f6d6d', '#e4f1ed'
        if s >= 60: return 'Good', '#D97706', '#fef3c7'
        return 'At Risk', '#DC2626', '#fee2e2'

    grp[['grade', 'grade_color', 'grade_bg']] = grp['score'].apply(lambda x: pd.Series(grade(x)))
    return grp.sort_values('score', ascending=False).reset_index(drop=True)

scores_df = compute_scores(df)

# ─── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>

:root {
    --p1: #0f6d6d;
    --p2: #208c7a;
    --p3: #49aa7e;
    --p4: #7bc77a;
    --p5: #b6e174;
    --p6: #f9f871;
    --sidebar-bg: var(--p1);
    --text-on-sidebar: #FFFFFF;
    --text-on-light: var(--p1);
    --nav-card: rgba(255, 255, 255, 0.11);
    --nav-card-hover: rgba(255, 255, 255, 0.22);
    --nav-border: rgba(255, 255, 255, 0.28);
    --glass-bg: rgba(255, 255, 255, 0.76);
    --glass-bg-strong: rgba(255, 255, 255, 0.88);
    --glass-border: rgba(32, 140, 122, 0.24);
    --glass-shadow: 0 14px 30px rgba(15, 109, 109, 0.12);
}

[data-testid="stAppViewContainer"] {
    background:
    radial-gradient(circle at 12% -20%, rgba(182, 225, 116, 0.18), transparent 46%),
    radial-gradient(circle at 96% 8%, rgba(249, 248, 113, 0.08), transparent 38%),
        linear-gradient(140deg, #f8ffef 0%, #f2fcec 45%, #ecf8f3 100%) !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(170deg, var(--p1) 0%, var(--p2) 58%, var(--p3) 100%);
    border-right: none;
    position: sticky;
    top: 0;
    height: 100vh;
}

[data-testid="stSidebar"] > div:first-child {
    height: 100vh;
    overflow-y: hidden !important;
}

section.main > div {
    max-width: 100% !important;
    padding-left: 0.85rem !important;
    padding-right: 0.85rem !important;
    padding-top: 0 !important;
}

section.main .block-container {
    padding-top: 0 !important;
    padding-bottom: 2.5rem !important;
    margin-top: 0 !important;
}

[data-testid="stAppViewContainer"] .main,
[data-testid="stAppViewContainer"] .main .block-container,
[data-testid="stAppViewContainer"] .main > div {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

[data-testid="stHeader"] {
    display: none !important;
    background: transparent !important;
    height: 0 !important;
    min-height: 0 !important;
}

[data-testid="stAppViewContainer"] {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

[data-testid="stMainBlockContainer"] {
    padding-top: 0.7rem !important;
    padding-left: 1.10rem !important;
    padding-right: 1.10rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 100% !important;
    width: 100% !important;
    margin-top: 0 !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}

[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }

section[data-testid="stSidebar"] .block-container {
    padding-left: 0.9rem !important;
    padding-right: 0.9rem !important;
    padding-top: 3rem !important;
    padding-bottom: 2rem !important;
}

.sidebar-title {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text-on-sidebar);
    margin-bottom: 2.5rem;
    text-align: center;
}

.sidebar-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.80);
    text-transform: uppercase;
    margin-top: 1rem;
    margin-bottom: 0.5rem;
}

section[data-testid="stSidebar"] .stSelectbox > label,
section[data-testid="stSidebar"] .stDateInput > label,
section[data-testid="stSidebar"] .stMultiSelect > label {
    color: var(--text-on-sidebar) !important;
    font-weight: 600;
}

section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
    width: 100%;
    cursor: pointer !important;
}

section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div {
    background-color: #F8FAFC !important;
    border-radius: 14px !important;
    border: 1px solid #D9DEE7 !important;
    min-height: 48px;
    padding-left: 8px;
    display: flex;
    align-items: center;
    cursor: pointer !important;
}

section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span,
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] div {
    color: #1F2937 !important;
}

section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] svg {
    fill: #374151 !important;
}

/* Cursor behavior: pointer for dropdown UI, text only for editable inputs */
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] [role="button"],
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] [role="combobox"],
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="select"] [role="button"],
section[data-testid="stSidebar"] .stDateInput [data-baseweb="input"] {
    cursor: pointer !important;
}

section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] input,
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="select"] input {
    cursor: text !important;
    caret-color: auto !important;
}

[role="listbox"],
[role="option"],
[data-baseweb="menu"],
[data-baseweb="menu"] * {
    cursor: pointer !important;
}

.sidebar-nav {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 18px;
    margin-top: 0.5rem;
}

.sidebar-nav-link {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    box-sizing: border-box;
    padding: 12px 14px;
    border: 1px solid transparent;
    border-radius: 16px;
    text-decoration: none !important;
    color: var(--text-on-sidebar) !important;
    background: rgba(255, 255, 255, 0.14);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    transition: transform 0.24s ease, background 0.24s ease, border-color 0.24s ease;
}

.sidebar-nav-link:hover {
    background: var(--nav-card-hover);
    border-color: var(--nav-border);
    transform: translateX(2px);
}

.sidebar-nav-link.is-active {
    background: linear-gradient(130deg, #ffffff 0%, rgba(182, 225, 116, 0.58) 100%);
    border-color: rgba(123, 199, 122, 0.7);
    color: var(--text-on-light) !important;
    font-weight: 600;
    box-shadow: 0 8px 18px rgba(15, 109, 109, 0.22);
}

.sidebar-nav-icon {
    width: 1.35em; height: 1.35em;
    display: inline-flex; align-items: center; justify-content: center;
    color: currentColor;
}

.sidebar-nav-icon svg {
    width: 1.15em; height: 1.15em;
    stroke: currentColor; fill: none;
    stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
}

.sidebar-nav-text { flex: 1; white-space: nowrap; }

section[data-testid="stSidebar"] hr { border-color: rgba(255, 255, 255, 0.25); }

section[data-testid="stSidebar"][aria-expanded="false"] {
    min-width: 88px !important; max-width: 88px !important; transform: translateX(0) !important;
}

section[data-testid="stSidebar"][aria-expanded="false"] .sidebar-title,
section[data-testid="stSidebar"][aria-expanded="false"] .sidebar-label,
section[data-testid="stSidebar"][aria-expanded="false"] .stSelectbox,
section[data-testid="stSidebar"][aria-expanded="false"] .stMultiSelect,
section[data-testid="stSidebar"][aria-expanded="false"] .stDateInput,
section[data-testid="stSidebar"][aria-expanded="false"] hr { display: none !important; }

section[data-testid="stSidebar"][aria-expanded="false"] .sidebar-nav-link {
    padding: 12px 8px; justify-content: center;
}

section[data-testid="stSidebar"][aria-expanded="false"] .sidebar-nav-text { display: none; }

@keyframes ovFadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}

@keyframes ovGlow {
    0%   { box-shadow: 0 0 0 rgba(32, 140, 122, 0.0); }
    50%  { box-shadow: 0 10px 26px rgba(32, 140, 122, 0.14); }
    100% { box-shadow: 0 0 0 rgba(32, 140, 122, 0.0); }
}

@keyframes ovRise {
    from { opacity: 0; transform: translateY(12px) scale(0.995); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}

.ov-title-row {
    display: flex; align-items: center; justify-content: space-between;
    gap: 1rem; margin-top: -0.35rem; margin-bottom: 1rem;
    animation: ovFadeUp 0.45s ease-out;
}

.filter-sidebar-shell {
    position: fixed;
    top: 0.9rem;
    right: 1rem;
    width: min(340px, 33vw);
    height: calc(100vh - 1.8rem);
    overflow-y: auto;
    background: var(--glass-bg-strong);
    border: 1px solid var(--glass-border);
    border-radius: 16px;
    box-shadow: 0 14px 34px rgba(15, 109, 109, 0.20);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    padding: 0.8rem 0.8rem 1rem;
    z-index: 999;
}

.filter-sidebar-title {
    margin: 0;
    color: #102A43;
    font-size: 1rem;
    font-weight: 800;
}

.filter-sidebar-sub {
    margin: 0.15rem 0 0.8rem;
    color: #486581;
    font-size: 0.82rem;
}

.st-key-right_filter_sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    right: 1rem;
    left: auto !important;
    width: min(340px, 34vw);
    height: auto;
    overflow-y: auto;
    padding: 1rem 0.95rem 1.1rem;
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.24);
    background: linear-gradient(170deg, var(--p1) 0%, var(--p2) 58%, var(--p3) 100%);
    box-shadow: 0 14px 34px rgba(15, 109, 109, 0.25);
    z-index: 999;
}

.st-key-right_filter_sidebar > div {
    display: flex;
    flex-direction: column;
    height: auto !important;
    justify-content: flex-start !important;
}

.st-key-right_filter_sidebar .stSelectbox label,
.st-key-right_filter_sidebar .stMarkdown p {
    color: rgba(255, 255, 255, 0.92) !important;
}

.st-key-right_filter_sidebar .filter-sidebar-title {
    color: #FFFFFF !important;
}

.st-key-right_filter_sidebar .sidebar-label {
    font-size: 0.95rem !important;
    letter-spacing: 0.04em;
}

.st-key-right_filter_sidebar .filter-header-title {
    text-align: center;
    font-size: 1.6rem !important;
    font-weight: 900 !important;
    letter-spacing: 0.12em;
    color: #FFFFFF;
    margin: 0;
}

.st-key-right_filter_sidebar .filter-sidebar-sub {
    color: rgba(255, 255, 255, 0.72) !important;
}

.st-key-right_filter_sidebar .stSelectbox > label {
    font-size: 1.05rem !important;
    font-weight: 700 !important;
}

.st-key-right_filter_sidebar [data-testid="stSelectbox"],
.st-key-right_filter_sidebar .stSelectbox,
.st-key-right_filter_sidebar .stSelectbox [data-baseweb="select"] {
    width: 100% !important;
    max-width: 100% !important;
}

.st-key-right_filter_sidebar .stSelectbox [data-baseweb="select"] > div {
    min-height: 52px !important;
    display: flex !important;
    align-items: center !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

/* Force text vertical centering */
.st-key-right_filter_sidebar .stSelectbox [data-baseweb="select"] span {
    display: flex !important;
    align-items: center !important;
    height: 100%;
}

.st-key-right_filter_sidebar .stSelectbox [data-baseweb="select"] [role="combobox"] {
    font-size: 1.12rem !important;
}

.st-key-right_filter_sidebar .stSelectbox [data-baseweb="select"] > div {
    background: #F1F3F6 !important;
    border-radius: 14px !important;
    border: 1px solid #D4DBE3 !important;
}

.st-key-right_filter_sidebar .stSelectbox [data-baseweb="select"] span,
.st-key-right_filter_sidebar .stSelectbox [data-baseweb="select"] div {
    color: #1F2937 !important;
}
            

.st-key-right_filter_sidebar .filter-content-spacer {
    flex: 0.6 1 auto;
    min-height: 0.5rem;
}

.st-key-right_filter_sidebar .filter-controls-wrap {
    margin-top: 0.5rem;
    margin-bottom: 0.5rem;
}

.st-key-right_filter_sidebar .st-key-close_filter_sidebar {
    display: flex;
    justify-content: flex-end;
    align-items: center !important;
    padding-top: 0px;
}

.st-key-right_filter_sidebar .st-key-close_filter_sidebar button {
    width: 38px !important;
    height: 38px !important;
    border-radius: 12px !important;
    background: rgba(255,255,255,0.85) !important;
    color: #0f6d6d !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    font-size: 1.1rem !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
}

.st-key-right_filter_sidebar .st-key-close_filter_sidebar button p,
.st-key-right_filter_sidebar .st-key-close_filter_sidebar button div {
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    margin: 0 !important;
    padding: 0 !important;
    width: 100%;
    height: 100%;
}

.st-key-right_filter_sidebar button[kind="secondary"]:hover {
    background: rgba(255,255,255,0.28) !important;
    transform: scale(1.05);
}

.filter-open-btn {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    height: 100%;
}

@media (max-width: 980px) {
    .filter-sidebar-shell {
        width: min(88vw, 340px);
        right: 0.6rem;
    }

    .st-key-right_filter_sidebar {
        width: min(88vw, 340px);
        top: 0;
        bottom: 0;
        right: 0.6rem;
        transform: none;
    }
}

.ov-header-block {
    display: flex;
    flex-direction: column;
    margin: 0;
    padding: 0;
}

.ov-title-row {
    display: flex; align-items: center; justify-content: flex-start;
    gap: 1rem; margin: 0; padding: 0;
    animation: ovFadeUp 0.45s ease-out;
}

.ov-title-icon {
    width: 40px; height: 40px; border-radius: 12px;
    display: inline-flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, var(--p1), var(--p3));
    color: #FFFFFF;
    box-shadow: 0 8px 20px rgba(15, 109, 109, 0.28);
    animation: ovGlow 4.2s ease-in-out infinite;
}

.ov-title-icon svg { width: 22px; height: 22px; stroke: currentColor; fill: none; stroke-width: 2; }

.ov-title-text { display: flex; align-items: center; margin: 0 !important; padding: 0 !important; line-height: normal !important; color: #102A43; font-weight: 800; letter-spacing: 0.2px; font-size: 2.25rem !important; pointer-events: none !important; }
.ov-subtitle { margin: 0.2rem 0 0 calc(40px + 1rem) !important; padding: 0 !important; color: #486581; font-size: 0.92rem; line-height: 1.45; }

a.header-anchor { display: none !important; }
[class*="st-key-hiddentrigger_"] { display: none !important; position: absolute !important; width: 0 !important; height: 0 !important; opacity: 0 !important; pointer-events: none !important; }

.ov-title-row-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
}

.custom-filter-btn {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    width: 38px;
    height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: #486581;
    transition: all 0.2s;
    box-shadow: var(--glass-shadow);
}
.custom-filter-btn:hover {
    background: var(--glass-bg-strong);
    color: #102A43;
    border-color: rgba(73, 170, 126, 0.55);
}
.custom-filter-btn svg { width: 22px; height: 22px; }

.ov-kpi-card {
    background: var(--glass-bg); border: 1px solid var(--glass-border);
    border-radius: 16px; padding: 14px 14px 12px;
    box-shadow: var(--glass-shadow);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    animation: ovRise 0.45s ease-out;
    transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
}

.ov-kpi-card:hover {
    transform: translateY(-3px);
    border-color: rgba(73, 170, 126, 0.55);
    box-shadow: 0 14px 26px rgba(15, 109, 109, 0.18);
}

.ov-kpi-label { color: #627D98; font-size: 0.82rem; margin-bottom: 0.25rem; }
.ov-kpi-value { color: #102A43; font-weight: 800; font-size: 1.35rem; margin-bottom: 0.2rem; }
.ov-kpi-delta { color: var(--p2); font-size: 0.8rem; font-weight: 600; }

.ov-panel {
    background: var(--glass-bg); border: 1px solid var(--glass-border);
    border-radius: 16px; padding: 12px; box-shadow: var(--glass-shadow);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    animation: ovFadeUp 0.5s ease-out;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--glass-bg-strong); border: 1px solid var(--glass-border) !important;
    border-radius: 16px; box-shadow: var(--glass-shadow);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    transition: transform 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease;
}

[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform: translateY(-2px);
    border-color: rgba(73, 170, 126, 0.45) !important;
    box-shadow: 0 14px 28px rgba(15, 109, 109, 0.16);
}

[data-testid="stPlotlyChart"] {
    animation: ovRise 0.55s ease-out;
}

.ov-panel-title { margin: 2px 2px 8px; color: #102A43; font-size: 1rem; font-weight: 700; }
.ov-table-title { margin: 0.2rem 0 0.6rem; color: #102A43; font-size: 1rem; font-weight: 700; }

.ov-table-container {
    background: var(--glass-bg); border: 1px solid var(--glass-border);
    border-radius: 16px; overflow: hidden; box-shadow: var(--glass-shadow);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    animation: ovFadeUp 0.5s ease-out;
}

.ov-table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }

.ov-table thead {
    background: linear-gradient(132deg, var(--p1) 0%, var(--p2) 48%, var(--p3) 100%);
    position: sticky; top: 0; z-index: 10;
}

.ov-table thead th {
    color: #FFFFFF; font-weight: 700; padding: 14px 12px;
    text-align: left; letter-spacing: 0.3px; text-transform: uppercase; font-size: 0.75rem;
}

.th-content { display: flex; align-items: center; justify-content: space-between; position: relative; }
.th-content span { display: inline-flex; align-items: center; }
.sort-icon-indicator { margin-left: 6px; display: inline-block; font-size: 0.9em; min-width: 12px; }
.sort-dropdown-container { position: relative; display: inline-flex; align-items: center; margin-left: 6px; }
.sort-toggle-btn { background: transparent; border: none; cursor: pointer; color: rgba(255,255,255,0.75); padding: 0; outline: none; display: inline-flex; align-items: center; }
.sort-toggle-btn:hover { color: #FFF; }
.sort-toggle-btn svg { width: 14px; height: 14px; stroke-width: 2.5; stroke: currentColor; fill: none; transition: fill 0.2s, stroke 0.2s; }
.sort-menu {
    display: none; position: absolute; top: calc(100% + 8px); left: 0;
    background: var(--glass-bg-strong); color: #102A43; min-width: 135px;
    border-radius: 8px; border: 1px solid var(--glass-border);
    box-shadow: 0 8px 24px rgba(15,109,109,0.18); z-index: 100;
    overflow: hidden; backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
}
.sort-dropdown-container.active .sort-menu { display: block; animation: ovFadeUp 0.15s ease-out; }
.sort-option {
    padding: 10px 14px; font-size: 0.78rem; font-weight: 600; cursor: pointer;
    transition: background 0.15s, color 0.15s; text-transform: none; color: #486581;
}
.sort-option:hover { background: rgba(73, 170, 126, 0.15); color: #102A43; }
.sort-option.active { color: var(--p1); font-weight: 800; background: rgba(73, 170, 126, 0.08); }

.ov-table tbody tr { border-bottom: 1px solid #E5E7EB; transition: background-color 0.2s ease; }
.ov-table tbody tr:hover { background-color: rgba(73, 170, 126, 0.10); }
.ov-table tbody td { padding: 12px 12px; color: #1F2937; vertical-align: middle; }
.ov-table tbody tr:last-child { border-bottom: none; }

.ov-transaction-id { font-weight: 600; color: var(--p1); font-family: 'Monaco','Courier New',monospace; font-size: 0.85rem; }
.ov-timestamp { color: #627D98; font-size: 0.88rem; }
.ov-amount { font-weight: 700; color: #102A43; font-size: 0.94rem; }

.ov-badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; text-align: center; }
.ov-badge-resolved { background-color: rgba(73, 170, 126, 0.2); color: var(--p1); }
.ov-badge-failed { background-color: rgba(220, 38, 38, 0.12); color: #DC2626; }
.ov-badge-pending { background-color: rgba(245, 158, 11, 0.12); color: #D97706; }

.ov-error-category { max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #486581; }

.ov-about-card {
    background: var(--glass-bg); border: 1px solid var(--glass-border);
    border-radius: 12px; padding: 14px 18px; margin-bottom: 20px;
    box-shadow: var(--glass-shadow); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    transition: all 0.35s ease;
    overflow: hidden;
}
.ov-about-header { display: flex; justify-content: space-between; align-items: center; }
.ov-about-title-wrap { display: flex; align-items: center; gap: 8px; }
.ov-about-title { font-weight: 700; color: #102A43; font-size: 1.05rem; }
.ov-about-info-btn, .ov-about-close-btn {
    background: none; border: none; cursor: pointer; color: #627D98;
    display: flex; align-items: center; justify-content: center;
    transition: color 0.2s; padding: 0; outline: none;
}
.ov-about-info-btn:hover { color: var(--p1); }
.ov-about-close-btn:hover { color: #DC2626; }
.ov-about-content {
    max-height: 0; opacity: 0; transition: max-height 0.4s ease, opacity 0.3s ease, margin-top 0.3s ease;
}
.ov-about-card.expanded .ov-about-content {
    max-height: 500px; opacity: 1; margin-top: 14px;
}
.ov-about-card.dismissed {
    opacity: 0; max-height: 0 !important; margin: 0 !important; padding: 0 18px !important; border: none !important;
}
.ov-about-content p { margin: 0 0 8px 0; font-size: 0.9rem; color: #486581; line-height: 1.5; }
.ov-about-content p:last-child { margin-bottom: 0; }
.ov-about-content strong { color: #102A43; font-weight: 700; }

/* Insight cards for Prediction page */
.insight-card {
    background: var(--glass-bg); border: 1px solid var(--glass-border);
    border-radius: 12px; padding: 14px 16px; margin-bottom: 10px;
    animation: ovRise 0.5s ease-out;
    transition: transform 0.22s ease, box-shadow 0.22s ease;
}
.insight-card:hover { transform: translateY(-3px); box-shadow: 0 14px 26px rgba(15, 109, 109, 0.16); }
.insight-num { font-size: 0.75rem; font-weight: 700; color: var(--p2); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
.insight-title { font-size: 0.95rem; font-weight: 700; color: #102A43; margin-bottom: 4px; }
.insight-body { font-size: 0.84rem; color: #486581; line-height: 1.55; }
.insight-rec { font-size: 0.82rem; color: var(--p1); font-weight: 600; margin-top: 6px; }

.insights-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    align-items: stretch;
}

.insights-grid .insight-card {
    margin-bottom: 0;
    height: 100%;
}

.insight-card.span-2 {
    grid-column: 1 / -1;
}

@media (max-width: 980px) {
    .insights-grid {
        grid-template-columns: 1fr;
    }
    .insight-card.span-2 {
        grid-column: auto;
    }
}

/* Risk checker result */
.risk-result {
    border-radius: 16px; padding: 22px 16px; text-align: center;
    animation: ovFadeUp 0.4s ease-out;
}
.risk-result-label { font-size: 1.05rem; font-weight: 700; margin-bottom: 8px; }
.risk-result-rate { font-size: 2.8rem; font-weight: 800; margin: 0; line-height: 1; }
.risk-result-sub { font-size: 0.83rem; margin-top: 6px; opacity: 0.75; }
.risk-result-meta { font-size: 0.88rem; margin-top: 14px; }

/* Reliability alert */
.rel-alert {
    background: linear-gradient(145deg, rgba(182, 225, 116, 0.18), rgba(73, 170, 126, 0.12));
    border: 1px solid rgba(32, 140, 122, 0.35);
    border-left: 6px solid var(--p2);
    border-radius: 14px;
    padding: 12px 14px;
    box-shadow: 0 10px 22px rgba(15, 109, 109, 0.10);
    animation: ovRise 0.35s ease-out;
}

.rel-alert-title {
    font-size: 1.02rem;
    font-weight: 800;
    color: #102A43;
    margin-bottom: 2px;
}

.rel-alert-meta {
    font-size: 0.86rem;
    color: #486581;
    margin-bottom: 10px;
}

.rel-alert-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.rel-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid rgba(32, 140, 122, 0.22);
    border-radius: 999px;
    padding: 5px 10px;
    font-size: 0.82rem;
    color: #1f2937;
}

.rel-chip-score {
    color: var(--p1);
    font-weight: 700;
}
            
/* ===== FILTER UI IMPROVEMENTS ===== */

/* Reduce overall spacing */
.st-key-right_filter_sidebar {
    padding: 0.5rem 0.7rem 0.8rem !important;
}

/* Reduce gap between elements */
.st-key-right_filter_sidebar .filter-controls-wrap {
    margin-top: 0.2rem !important;
    margin-bottom: 0.2rem !important;
}

/* Reduce label spacing */
.st-key-right_filter_sidebar .stSelectbox > label {
    margin-bottom: 0.2rem !important;
}

/* Reduce spacing between dropdowns */
.st-key-right_filter_sidebar [data-testid="stSelectbox"] {
    margin-bottom: 0.5rem !important;
}

/* Fix vertical alignment of dropdown text */
.st-key-right_filter_sidebar .stSelectbox [data-baseweb="select"] > div {
    min-height: 52px !important;
    display: flex !important;
    align-items: center !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

.st-key-right_filter_sidebar .stSelectbox [data-baseweb="select"] span {
    display: flex !important;
    align-items: center !important;
    height: 100%;
}

/* Force interactive pointers on dropdown inputs and portals globally */
[data-baseweb="select"], [data-baseweb="select"] * { cursor: pointer !important; }
li[role="option"], li[role="option"] * { cursor: pointer !important; }

/* Clear button styling */
.st-key-right_filter_sidebar .stButton {
    display: flex;
    justify-content: center;
    margin-top: 1rem;
}

.st-key-right_filter_sidebar .stButton button {
    background: #FFFFFF !important;
    color: #0f6d6d !important;
    border: none !important;
    border-radius: 14px !important;
    font-weight: 600 !important;
    padding: 10px 18px !important;
    transition: all 0.2s ease !important;
}

.st-key-right_filter_sidebar .stButton button:hover {
    background: #f1f5f9 !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 14px rgba(0,0,0,0.08);
}

/* Open filters button perfect centering */
.filter-open-btn [data-testid="stButton"] button {
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 12px !important;
    width: 44px !important;
    height: 44px !important;
}

.filter-open-btn [data-testid="stButton"] button p,
.filter-open-btn [data-testid="stButton"] button div {
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    padding: 0 !important;
    margin: 0 !important;
    width: 100%;
    height: 100%;
}

/* Custom Tooltip Enhancements */
.js-plotly-plot .hoverlayer .hovertext > path.bg {
    filter: drop-shadow(0px 8px 18px rgba(15, 109, 109, 0.16)) !important;
}

.js-plotly-plot .hoverlayer {
    transition: opacity 0.15s ease-in-out !important;
}

.js-plotly-plot .hoverlayer .hovertext {
    pointer-events: none !important;
}

</style>
""", unsafe_allow_html=True)

# ─── SIDEBAR ───────────────────────────────────────────────────────────────────
icon_svgs = {
    "overview":          '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect></svg>',
    "failure-analysis":  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17l6-6 4 4 8-8"></path><path d="M21 10V4h-6"></path></svg>',
    "time-analysis":     '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="13" r="8"></circle><path d="M12 13V9"></path><path d="M12 13l3 2"></path><path d="M9 2h6"></path></svg>',
    "deep-dive":         '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="M21 21l-4.3-4.3"></path></svg>',
    "prediction":        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l1.8 3.8L18 7.1l-3 2.9.7 4.1-3.7-2-3.7 2 .7-4.1-3-2.9 4.2-1.3z"></path><path d="M19 16a3 3 0 110 6 3 3 0 010-6z"></path></svg>',
    "reliability":       '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v6c0 5-3.5 8.7-7 9-3.5-.3-7-4-7-9V6z"></path><path d="M9 12l2 2 4-4"></path></svg>',
    "heatmap":           '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2v10"></path><path d="M9 6h6"></path><path d="M12 12a4 4 0 100 8 4 4 0 000-8z"></path></svg>'
}

nav_items = [
    ("overview",         "Overview"),
    ("failure-analysis", "Failure Analysis"),
    ("time-analysis",    "Time Analysis"),
    ("deep-dive",        "Deep Dive"),
    ("prediction",       "Prediction"),
    ("reliability",      "Reliability"),
    ("heatmap",          "Heatmap"),
]

with st.sidebar:
    st.markdown('<div class="sidebar-title">Payment Failure Analysis</div>', unsafe_allow_html=True)

    valid_ids = {item_id for item_id, _ in nav_items}

    raw_page = st.query_params.get("page", "overview")
    if isinstance(raw_page, list):
        raw_page = raw_page[0] if raw_page else "overview"
        
    if "current_page" not in st.session_state:
        st.session_state.current_page = raw_page if raw_page in valid_ids else "overview"

    selected_page_id = st.session_state.current_page

    nav_html = ['<div class="sidebar-nav">']
    for item_id, item_text in nav_items:
        active_class = " is-active" if item_id == selected_page_id else ""
        nav_html.append(
            f'<a class="sidebar-nav-link{active_class}" href="javascript:void(0)" data-page="{item_id}" target="_self">'
            f'<span class="sidebar-nav-icon">{icon_svgs[item_id]}</span>'
            f'<span class="sidebar-nav-text">{item_text}</span>'
            '</a>'
        )
    nav_html.append('</div>')
    st.markdown(''.join(nav_html), unsafe_allow_html=True)

    # Hidden Streamlit native buttons mapped to purely visual HTML targets
    st.markdown('''<style>
        [data-testid="stSidebar"] [class*="st-key-navbtn_"] {
            display: none !important;
            position: absolute !important;
            width: 0 !important;
            height: 0 !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
    </style>''', unsafe_allow_html=True)
    
    for item_id, _ in nav_items:
        if st.button("x", key=f"navbtn_{item_id}"):
            st.session_state.current_page = item_id
            st.query_params["page"] = item_id
            st.rerun()

    # Global Passive SPA execution bridge (intercepts custom links -> activates Streamlit)
    components.html("""
    <script>
        const doc = window.parent.document;
        if (doc._spa_router_listener) {
            doc.removeEventListener('click', doc._spa_router_listener);
        }
        doc._spa_router_listener = function(e) {
            const link = e.target.closest('.sidebar-nav-link');
            if (link) {
                e.preventDefault();
                const pageId = link.getAttribute('data-page');
                const btn = doc.querySelector(`.st-key-navbtn_${pageId} button`);
                if (btn) btn.click();
            }
            const filterBtn = e.target.closest('.custom-filter-btn');
            if (filterBtn) {
                e.preventDefault();
                const btn = doc.querySelector(`.st-key-hiddentrigger_filter button`);
                if (btn) btn.click();
            }

            const relInfoBtn = e.target.closest('.rel-info-icon');
            if (relInfoBtn) {
                e.preventDefault();
                const target = doc.getElementById('rel-calc-section');
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    // Expand the expander automatically for better UX
                    setTimeout(() => {
                        const summaries = Array.from(doc.querySelectorAll('summary'));
                        for (let s of summaries) {
                            if (s.textContent.includes('How the reliability score is calculated')) {
                                const details = s.closest('details');
                                if (details && !details.hasAttribute('open')) {
                                    s.click();
                                }
                                break;
                            }
                        }
                    }, 300);
                }
            }
            
            if (!e.target.closest('.sort-dropdown-container')) {
                doc.querySelectorAll('.sort-dropdown-container.active').forEach(el => el.classList.remove('active'));
            }

            const sortBtn = e.target.closest('.sort-toggle-btn');
            if (sortBtn) {
                e.preventDefault();
                const container = sortBtn.closest('.sort-dropdown-container');
                const wasActive = container.classList.contains('active');
                doc.querySelectorAll('.sort-dropdown-container.active').forEach(el => el.classList.remove('active'));
                if (!wasActive) container.classList.add('active');
            }

            const infoBtn = e.target.closest('.ov-about-info-btn');
            if (infoBtn) {
                e.preventDefault();
                const card = infoBtn.closest('.ov-about-card');
                card.classList.toggle('expanded');
            }
            
            const closeBtn = e.target.closest('.ov-about-close-btn');
            if (closeBtn) {
                e.preventDefault();
                const card = closeBtn.closest('.ov-about-card');
                card.style.maxHeight = card.scrollHeight + 'px';
                setTimeout(() => card.classList.add('dismissed'), 10);
                setTimeout(() => {
                    const btn = doc.querySelector('.st-key-hiddentrigger_dismiss_about button');
                    if (btn) btn.click();
                }, 400);
            }

            const sortOpt = e.target.closest('.sort-option');
            if (sortOpt) {
                e.preventDefault();
                const action = sortOpt.getAttribute('data-action');
                const th = sortOpt.closest('th');
                const table = th.closest('table');
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                const headers = Array.from(th.closest('tr').querySelectorAll('th'));
                const index = headers.indexOf(th);
                
                headers.forEach(h => {
                    h.querySelectorAll('.sort-option').forEach(opt => opt.classList.remove('active'));
                    const ind = h.querySelector('.sort-icon-indicator');
                    if (ind) ind.innerText = '';
                });
                
                sortOpt.classList.add('active');
                doc.querySelectorAll('.sort-dropdown-container.active').forEach(el => el.classList.remove('active'));

                if (action === 'reset') {
                    rows.sort((a, b) => parseInt(a.getAttribute('data-orig-idx')) - parseInt(b.getAttribute('data-orig-idx')));
                } else {
                    const isAsc = (action === 'asc');
                    const ind = th.querySelector('.sort-icon-indicator');
                    if (ind) ind.innerText = isAsc ? ' ↑' : ' ↓';
                    
                    rows.sort((a, b) => {
                        const aVal = a.querySelectorAll('td')[index].innerText.trim();
                        const bVal = b.querySelectorAll('td')[index].innerText.trim();
                        const aNum = parseFloat(aVal.replace(/[^0-9.-]+/g,""));
                        const bNum = parseFloat(bVal.replace(/[^0-9.-]+/g,""));
                        const aDate = Date.parse(aVal);
                        const bDate = Date.parse(bVal);
                        
                        if (!isNaN(aNum) && !isNaN(bNum) && !aVal.match(/[a-zA-Z]/)) {
                            return isAsc ? aNum - bNum : bNum - aNum;
                        } else if (!isNaN(aDate) && !isNaN(bDate)) {
                            return isAsc ? aDate - bDate : bDate - aDate;
                        } else {
                            return isAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                        }
                    });
                }
                rows.forEach(row => tbody.appendChild(row));
            }
        };
        doc.addEventListener('click', doc._spa_router_listener);
    </script>
    """, height=0, width=0)

    page_lookup = {item_id: item_text for item_id, item_text in nav_items}

if "show_filter_sidebar" not in st.session_state:
    st.session_state.show_filter_sidebar = False

channel_options = ["All Channels"] + sorted(df['payment_channel'].dropna().unique())
bank_options = ["All Banks"] + sorted(df['bank_name'].dropna().unique())
date_options = ["All Dates", "Last 7 Days", "Last 30 Days", "Last 90 Days", "This Month", "This Quarter"]
reason_options = ["All Reasons"] + sorted(df['failure_reason'].dropna().unique())

if "selected_channel" not in st.session_state:
    st.session_state.selected_channel = "All Channels"
if "selected_bank" not in st.session_state:
    st.session_state.selected_bank = "All Banks"
if "selected_date_range" not in st.session_state:
    st.session_state.selected_date_range = "All Dates"
if "selected_reason" not in st.session_state:
    st.session_state.selected_reason = "All Reasons"

if st.session_state.show_filter_sidebar:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            display: block !important;
            min-width: 88px !important;
            max-width: 88px !important;
            width: 88px !important;
            transform: translateX(0) !important;
        }
        section[data-testid="stSidebar"] .sidebar-title {
            display: none !important;
        }
        section[data-testid="stSidebar"] .sidebar-nav-link {
            padding: 12px 8px !important;
            justify-content: center !important;
        }
        section[data-testid="stSidebar"] .sidebar-nav-text {
            display: none !important;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-left: 0.45rem !important;
            padding-right: 0.45rem !important;
        }
        [data-testid="stMainBlockContainer"] {
            padding-right: min(360px, 36vw) !important;
        }
        @media (max-width: 980px) {
            section[data-testid="stSidebar"] {
                min-width: 76px !important;
                max-width: 76px !important;
                width: 76px !important;
            }
            [data-testid="stMainBlockContainer"] {
                padding-right: 0.8rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

selected_channel = st.session_state.selected_channel
selected_bank = st.session_state.selected_bank
selected_date_range = st.session_state.selected_date_range
selected_reason = st.session_state.selected_reason

# ─── FILTER ────────────────────────────────────────────────────────────────────
filtered_df = df.copy()

if selected_channel != "All Channels":
    filtered_df = filtered_df[filtered_df['payment_channel'] == selected_channel]
if selected_bank != "All Banks":
    filtered_df = filtered_df[filtered_df['bank_name'] == selected_bank]

latest_ts = filtered_df['timestamp'].max()
if pd.notna(latest_ts):
    if selected_date_range == "Last 7 Days":
        filtered_df = filtered_df[filtered_df['timestamp'] >= latest_ts - pd.Timedelta(days=7)]
    elif selected_date_range == "Last 30 Days":
        filtered_df = filtered_df[filtered_df['timestamp'] >= latest_ts - pd.Timedelta(days=30)]
    elif selected_date_range == "Last 90 Days":
        filtered_df = filtered_df[filtered_df['timestamp'] >= latest_ts - pd.Timedelta(days=90)]
    elif selected_date_range == "This Month":
        filtered_df = filtered_df[filtered_df['timestamp'] >= latest_ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)]
    elif selected_date_range == "This Quarter":
        qm = ((latest_ts.month - 1) // 3) * 3 + 1
        qs = latest_ts.replace(month=qm, day=1, hour=0, minute=0, second=0, microsecond=0)
        filtered_df = filtered_df[filtered_df['timestamp'] >= qs]

if selected_reason != "All Reasons":
    filtered_df = filtered_df[filtered_df['failure_reason'] == selected_reason]

# ─── HELPERS ───────────────────────────────────────────────────────────────────
def page_title(pid, subtitle):
    filter_btn_html = ""
    if not st.session_state.show_filter_sidebar:
        filter_btn_html = (
            '<button class="custom-filter-btn" title="Open filters">'
            '<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="currentColor">'
            '<path d="M440-160q-17 0-28.5-11.5T400-200v-240L168-736q-15-20-4.5-42t36.5-22h560q26 0 36.5 22t-4.5 42L560-440v240q0 17-11.5 28.5T520-160h-80Zm40-308 198-252H282l198 252Zm0 0Z"/>'
            '</svg>'
            '</button>'
        )

    html_content = (
        f'<div class="ov-header-block" style="width: 100%;">'
        f'<div class="ov-title-row-container">'
        f'<div class="ov-title-row">'
        f'<span class="ov-title-icon">{icon_svgs[pid]}</span>'
        f'<div class="ov-title-text" style="white-space: nowrap;">{page_lookup[pid]}</div>'
        f'</div>'
        f'{filter_btn_html}'
        f'</div>'
        f'<p class="ov-subtitle">{subtitle}</p>'
        f'</div>'
    )
    st.markdown(html_content, unsafe_allow_html=True)
    
    if not st.session_state.show_filter_sidebar:
        if st.button("x", key="hiddentrigger_filter"):
            st.session_state.show_filter_sidebar = True
            st.rerun()

def render_filter_sidebar():
    if not st.session_state.show_filter_sidebar:
        return

    with st.container(border=True, key="right_filter_sidebar"):
        left_col, header_col, right_col = st.columns([0.15, 0.70, 0.15], vertical_alignment="center")

        with header_col:
            st.markdown('<div class="filter-header-title">FILTERS</div>', unsafe_allow_html=True)

        with right_col:
            if st.button("✕", key="close_filter_sidebar", help="Close filters"):
                st.session_state.show_filter_sidebar = False
                st.rerun()

        st.markdown('<div style="height:0.2rem;"></div>', unsafe_allow_html=True)

        st.markdown('<div class="filter-controls-wrap">', unsafe_allow_html=True)
        st.selectbox("Payment Channel", options=channel_options, key="selected_channel")
        st.selectbox("Bank", options=bank_options, key="selected_bank")
        st.selectbox("Date Range", options=date_options, key="selected_date_range")
        st.selectbox("Failure Reason", options=reason_options, key="selected_reason")
        st.markdown('</div>', unsafe_allow_html=True)


        cc1, cc2, cc3 = st.columns([1, 3, 1])
        with cc2:
            def reset_filters():
                st.session_state.selected_channel = "All Channels"
                st.session_state.selected_bank = "All Banks"
                st.session_state.selected_date_range = "All Dates"
                st.session_state.selected_reason = "All Reasons"
                
            st.button("Clear all filters", key="clear_all_filters", use_container_width=True, on_click=reset_filters)

render_filter_sidebar()

def kpi(label, value, delta):
    return (
        f'<div class="ov-kpi-card">'
        f'<div class="ov-kpi-label">{label}</div>'
        f'<div class="ov-kpi-value">{value}</div>'
        f'<div class="ov-kpi-delta">{delta}</div>'
        f'</div>'
    )

def bar_layout(fig, x_title="", y_title="", margin_b=10):
    fig.update_layout(
        margin=dict(l=10, r=10, t=8, b=margin_b),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis_title=x_title, yaxis_title=y_title,
        coloraxis_showscale=False, showlegend=False
    )
    return fig

_THEME_SCALE = ["#0f6d6d", "#208c7a", "#49aa7e", "#7bc77a", "#b6e174"]
_TEAL_SCALE = _THEME_SCALE
_HEAT_SCALE  = _THEME_SCALE

import plotly.io as pio
_HOVER_BG = "rgba(245, 252, 250, 0.98)"
_HOVER_BORDER = "rgba(15, 109, 109, 0.22)"
_HOVER_TEXT = "#15302f"
_HOVER_ACCENT = "#0f6d6d"

_HOVER_THEME = go.layout.Template(
    layout=go.Layout(
        hoverlabel=dict(
            bgcolor=_HOVER_BG,
            bordercolor=_HOVER_BORDER,
            font=dict(size=14, color=_HOVER_TEXT, family="Inter, system-ui, sans-serif"),
            namelength=-1,
            align="left"
        ),
        hovermode="closest"
    )
)
pio.templates["pg_hover"] = _HOVER_THEME
px.defaults.template = "plotly_white+pg_hover"

import plotly.io as pio

pio.templates["custom_theme"] = go.layout.Template(
    layout=go.Layout(
        font=dict(color="#1f2937"),  # DARK TEXT
        xaxis=dict(
            title_font=dict(color="#1f2937"),
            tickfont=dict(color="#374151")
        ),
        yaxis=dict(
            title_font=dict(color="#1f2937"),
            tickfont=dict(color="#374151")
        ),
        legend=dict(
            font=dict(color="#1f2937")
        )
    )
)

px.defaults.template = "plotly_white+pg_hover+custom_theme"

px.defaults.color_discrete_sequence = _THEME_SCALE
px.defaults.color_continuous_scale = _THEME_SCALE
_sp = '<div style="height:16px;"></div>'

def render_html_table(tdf, columns, headers, formatters=None):
    html = '<div class="ov-table-container"><table class="ov-table"><thead><tr>'
    for h in headers:
        html += (
            f'<th>'
            f'<div class="th-content">'
            f'<span>{h}<span class="sort-icon-indicator"></span></span>'
            f'<div class="sort-dropdown-container">'
            f'<button class="sort-toggle-btn" title="Sort Column">'
            f'<svg viewBox="0 0 24 24" stroke="currentColor" fill="none" stroke-width="2">'
            f'<path stroke-linecap="round" stroke-linejoin="round" d="M8 9l4-4 4 4m0 6l-4 4-4-4" />'
            f'</svg>'
            f'</button>'
            f'<div class="sort-menu">'
            f'<div class="sort-option" data-action="asc">Sort Ascending ↑</div>'
            f'<div class="sort-option" data-action="desc">Sort Descending ↓</div>'
            f'<div class="sort-option" data-action="reset">Reset Default</div>'
            f'</div>'
            f'</div>'
            f'</div>'
            f'</th>'
        )
    html += '</tr></thead><tbody>'
    for r_idx, (_, row) in enumerate(tdf.iterrows()):
        html += f'<tr data-orig-idx="{r_idx}">'
        for i, col in enumerate(columns):
            val = row[col]
            if formatters and col in formatters:
                cell = formatters[col](val, row)
            else:
                cell = str(val) if pd.notna(val) else '—'
            html += f'<td>{cell}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'
    return html

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
if selected_page_id == "overview":
    ov = filtered_df.dropna(subset=["timestamp"]).sort_values("timestamp").copy()

    page_title("overview", "Interactive payment performance cockpit")
    st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

    if st.session_state.get('show_about_card', True):
        st.markdown('''
        <div class="ov-about-card">
            <div class="ov-about-header">
                <div class="ov-about-title-wrap">
                    <span class="ov-about-title">About This Dashboard</span>
                    <button class="ov-about-info-btn" title="More information">
                        <svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="currentColor"><path d="M440-280h80v-240h-80v240Zm40-320q17 0 28.5-11.5T520-640q0-17-11.5-28.5T480-680q-17 0-28.5 11.5T440-640q0 17 11.5 28.5T480-600Zm0 520q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Z"/></svg>
                    </button>
                </div>
            </div>
            <div class="ov-about-content">
                <p>This dashboard is based on a dataset of <strong style="color: var(--p1);">10,000 transactions</strong> and focuses on analyzing failures within them. The charts highlight different <strong style="color: var(--p1);">failure reasons</strong>, their frequency, and <strong style="color: var(--p1);">patterns</strong> across time or categories. Instead of showing all transaction details, it focuses on understanding where and why failures occur, helping identify key <strong style="color: var(--p1);">problem areas</strong> and improve overall <strong style="color: var(--p1);">transaction reliability</strong>.</p>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    total   = len(ov)
    failed  = int(ov["is_failed"].sum()) if total else 0
    success = total - failed
    fr      = (failed / total * 100) if total else 0.0
    sr      = (success / total * 100) if total else 0.0
    rel     = 100 - fr
    vol     = float(ov["amount"].sum()) if total else 0.0

    if total:
        lts = ov["timestamp"].max()
        cw  = ov[ov["timestamp"] >= lts - pd.Timedelta(days=7)]
        pw  = ov[(ov["timestamp"] >= lts - pd.Timedelta(days=14)) & (ov["timestamp"] < lts - pd.Timedelta(days=7))]
        d_txn = len(cw) - len(pw)
    else:
        d_txn = 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:  st.markdown(kpi("Transactions",    f"{total:,}",        f"Last 7d delta: {d_txn:+d}"), unsafe_allow_html=True)
    with k2:  st.markdown(kpi("Failure Rate",    f"{fr:.2f}%",        "Reliability inverse metric"), unsafe_allow_html=True)
    with k3:  st.markdown(kpi("Reliability Score", f"{rel:.2f}%",     "Higher is better"), unsafe_allow_html=True)
    with k4:  st.markdown(kpi("Total Volume",    f"₹{vol:,.0f}",     f"Success: {sr:.2f}%"), unsafe_allow_html=True)

    st.markdown(_sp, unsafe_allow_html=True)

    c1, c2 = st.columns([1.7, 1])
    with c1:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Transactions Trend</div>', unsafe_allow_html=True)
            td = ov.set_index("timestamp").resample("D").agg(total_txns=("transaction_id","count"), failed_txns=("is_failed","sum")).reset_index()
            fig = px.line(td, x="timestamp", y=["total_txns","failed_txns"], markers=True,
                          color_discrete_map={"total_txns":"#0f6d6d","failed_txns":"#49aa7e"})
            fig.update_layout(margin=dict(l=10,r=10,t=8,b=10), legend_title_text="",
                              plot_bgcolor="white", paper_bgcolor="white",
                              xaxis_title="", yaxis_title="", hovermode="x unified")
            fig.update_traces(line=dict(width=3))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Status Mix</div>', unsafe_allow_html=True)
            sd = ov["status"].value_counts().reset_index()
            sd.columns = ["status","count"]
            fig = px.pie(sd, names="status", values="count", hole=0.68,
                         color="status", color_discrete_sequence=_THEME_SCALE)
            fig.update_traces(
                hovertemplate=(
                    f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Status</span><br>"
                    f"<b>%{{label}}</b><br>"
                    f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Count</span><br>"
                    f"<b>%{{value:,}}</b><extra></extra>"
                ),
                textinfo="none",
                sort=False
            )
            fig.update_layout(margin=dict(l=10,r=10,t=8,b=10), showlegend=True,
                              legend_orientation="h", legend_y=-0.1,
                              plot_bgcolor="white", paper_bgcolor="white",
                              hoverlabel=dict(
                                  bgcolor=_HOVER_BG,
                                  bordercolor=_HOVER_BORDER,
                                  font=dict(size=14, color=_HOVER_TEXT, family="Inter, system-ui, sans-serif"),
                                  align="left"
                              ))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)
    c3, c4 = st.columns(2)

    with c3:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Top Failure Reasons</div>', unsafe_allow_html=True)
            rd = (ov[ov["is_failed"]==1]["failure_reason"].fillna("Unknown")
                  .value_counts().head(6).sort_values(ascending=True).reset_index())
            rd.columns = ["failure_reason","count"]
            fig = px.bar(rd, x="count", y="failure_reason", orientation="h",
                         color="count", color_continuous_scale=_TEAL_SCALE)
            fig.update_layout(margin=dict(l=10,r=10,t=8,b=58), coloraxis_showscale=True,
                              coloraxis_colorbar=dict(title="Count",orientation="h",thickness=12,len=0.62,
                                                      x=0.5,xanchor="center",y=-0.32,nticks=4,tickfont=dict(size=11),title_side="top"),
                              plot_bgcolor="white", paper_bgcolor="white", xaxis_title="", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    with c4:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Failure Rate by Channel</div>', unsafe_allow_html=True)
            cd = ov.groupby("payment_channel")["is_failed"].mean().mul(100).round(2).sort_values(ascending=False).reset_index()
            cd.columns = ["payment_channel","failure_rate"]
            fig = px.bar(cd, x="payment_channel", y="failure_rate", color="failure_rate", color_continuous_scale=_TEAL_SCALE)
            fig.update_layout(margin=dict(l=10,r=10,t=8,b=58), coloraxis_showscale=True,
                              coloraxis_colorbar=dict(title="Failure %",orientation="h",thickness=12,len=0.62,
                                                      x=0.5,xanchor="center",y=-0.32,nticks=4,tickfont=dict(size=11),title_side="top"),
                              plot_bgcolor="white", paper_bgcolor="white", xaxis_title="", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)
    st.markdown('<div class="ov-table-title">Recent Transactions</div>', unsafe_allow_html=True)

    t12 = ov.sort_values("timestamp", ascending=False).head(12)

    def _status_cell(v, row):
        sl = str(v).strip().lower()
        if sl == 'success': return f'<span class="ov-badge ov-badge-resolved">Success</span>'
        if sl == 'failed':  return f'<span class="ov-badge ov-badge-failed">Failed</span>'
        return f'<span class="ov-badge ov-badge-pending">Pending</span>'

    def _tid(v, row):   return f'<span class="ov-transaction-id">{str(v)[:12]}</span>'
    def _ts(v, row):    return f'<span class="ov-timestamp">{pd.Timestamp(v).strftime("%b %d, %H:%M:%S") if pd.notna(v) else "N/A"}</span>'
    def _amt(v, row):   return f'<span class="ov-amount">₹{float(v):,.2f}</span>'
    def _reason(v, row): return str(v).replace('_', ' ').title() if pd.notna(v) else '—'

    st.markdown(render_html_table(
        t12,
        ["transaction_id","timestamp","payment_channel","bank_name","amount","failure_reason","status"],
        ["Transaction ID","Timestamp","Type","Bank","Amount","Error","Status"],
        {"transaction_id":_tid,"timestamp":_ts,"amount":_amt,"status":_status_cell,"failure_reason":_reason}
    ), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: FAILURE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
elif selected_page_id == "failure-analysis":
    fa = filtered_df.copy()
    page_title("failure-analysis", "Transaction failure patterns across channels, banks and causes")
    st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

    total   = len(fa)
    failed  = int(fa['is_failed'].sum())
    fr      = round(failed / total * 100, 2) if total else 0
    fd      = fa[fa['is_failed'] == 1]
    top_r   = fd['failure_reason'].value_counts().index[0].replace('_',' ').title() if len(fd) > 0 else 'N/A'
    worst_c = fa.groupby('payment_channel')['is_failed'].mean().idxmax() if total > 0 else 'N/A'

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("Total Failed",         f"{failed:,}",       f"of {total:,} transactions"),        unsafe_allow_html=True)
    with k2: st.markdown(kpi("Failure Incidence Rate", f"{fr}%",           "System baseline"),                   unsafe_allow_html=True)
    with k3: st.markdown(kpi("Top Failure Cause",    top_r,               "Most frequent"),                     unsafe_allow_html=True)
    with k4: st.markdown(kpi("Worst Channel",        worst_c,             "Highest failure rate"),               unsafe_allow_html=True)

    st.markdown(_sp, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Failure Volume by Payment Channel</div>', unsafe_allow_html=True)
            d = fd.groupby('payment_channel').size().reset_index(name='failures').sort_values('failures', ascending=False)
            fig = bar_layout(px.bar(d, x='payment_channel', y='failures', color='failures', color_continuous_scale=_TEAL_SCALE), y_title="Failed Transactions")
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Failure Volume by Issuing Bank</div>', unsafe_allow_html=True)
            d = fd.groupby('bank_name').size().reset_index(name='failures').sort_values('failures', ascending=False)
            fig = bar_layout(px.bar(d, x='bank_name', y='failures', color='failures', color_continuous_scale=_TEAL_SCALE), y_title="Failed Transactions")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="ov-panel-title">Distribution of Failure Causes</div>', unsafe_allow_html=True)
        d = fd['failure_reason'].value_counts().reset_index()
        d.columns = ['reason','count']
        d = d.sort_values('count', ascending=True)
        d['pct'] = (d['count'] / d['count'].sum() * 100).round(1)
        d['label'] = d['reason'].str.replace('_', ' ').str.title()
        fig = px.bar(d, x='count', y='label', orientation='h',
                     color='count', color_continuous_scale=_TEAL_SCALE,
                     text=d['pct'].apply(lambda x: f'{x}%'))
        fig.update_traces(textposition='outside')
        fig.update_layout(margin=dict(l=10,r=60,t=8,b=10),
                          plot_bgcolor='white', paper_bgcolor='white',
                          xaxis_title='Transaction Count', yaxis_title='',
                          coloraxis_showscale=False, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)
    c3, c4 = st.columns(2)

    with c3:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Failure Incidence Rate by Channel (%)</div>', unsafe_allow_html=True)
            d = fa.groupby('payment_channel')['is_failed'].mean().mul(100).round(2).reset_index()
            d.columns = ['channel','rate']
            d = d.sort_values('rate', ascending=False)
            fig = bar_layout(px.bar(d, x='channel', y='rate', color='rate', color_continuous_scale=_HEAT_SCALE), y_title="Failure Rate (%)")
            st.plotly_chart(fig, use_container_width=True)

    with c4:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Failure Incidence Rate by Bank (%)</div>', unsafe_allow_html=True)
            d = fa.groupby('bank_name')['is_failed'].mean().mul(100).round(2).reset_index()
            d.columns = ['bank','rate']
            d = d.sort_values('rate', ascending=False)
            fig = bar_layout(px.bar(d, x='bank', y='rate', color='rate', color_continuous_scale=_HEAT_SCALE), y_title="Failure Rate (%)")
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: TIME ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
elif selected_page_id == "time-analysis":
    ta = filtered_df.copy()
    page_title("time-analysis", "Temporal failure patterns — hourly, daily and salary-window analysis")
    st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

    hr   = ta.groupby('hour')['is_failed'].mean().mul(100)
    base = round(ta['is_failed'].mean() * 100, 2)
    thr  = round(base * 1.5, 2)
    peak = int(hr.idxmax()) if len(hr) > 0 else 0
    peak_rate = round(hr.max(), 2) if len(hr) > 0 else 0

    night = ta[ta['hour'].isin([22,23,0,1])]['is_failed'].mean() * 100
    salary = ta[ta['day_of_month'] >= 28]['is_failed'].mean() * 100
    normal = ta[ta['day_of_month'] < 28]['is_failed'].mean() * 100

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("Peak Failure Hour",     f"{peak:02d}:00",          f"{peak_rate:.1f}% failure rate"),  unsafe_allow_html=True)
    with k2: st.markdown(kpi("Night Window Rate",     f"{night:.1f}%",           "10pm–1am (hrs 22–01)"),            unsafe_allow_html=True)
    with k3: st.markdown(kpi("Salary Day Rate",       f"{salary:.1f}%",          f"vs {normal:.1f}% normal days"),   unsafe_allow_html=True)
    with k4: st.markdown(kpi("1.5× Threshold",        f"{thr:.1f}%",             f"Baseline: {base}%"),              unsafe_allow_html=True)

    st.markdown(_sp, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="ov-panel-title">Failure Incidence Rate by Hour of Day (%)</div>', unsafe_allow_html=True)
        hr_df = hr.reset_index()
        hr_df.columns = ['hour','rate']
        colors = ['#b6e174' if rate > thr else '#49aa7e' for rate in hr_df['rate']]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=hr_df['hour'], y=hr_df['rate'], marker_color=colors, name='Failure Rate'))
        fig.add_hline(y=base, line_dash='dash', line_color='#208c7a', line_width=1.5,
                      annotation_text=f'Baseline {base}%', annotation_position='right')
        fig.add_hline(y=thr, line_dash='dot', line_color='#b6e174', line_width=1.5,
                      annotation_text=f'1.5× Threshold {thr}%', annotation_position='right')
        fig.update_layout(margin=dict(l=10,r=120,t=8,b=10),
                          plot_bgcolor='white', paper_bgcolor='white',
                          xaxis_title='Hour of Day', yaxis_title='Failure Incidence Rate (%)',
                          showlegend=False, bargap=0.05)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="ov-panel-title">Failure Incidence Rate by Day of Month (%) — Salary window highlighted</div>', unsafe_allow_html=True)
        dr = ta.groupby('day_of_month')['is_failed'].mean().mul(100).reset_index()
        dr.columns = ['day','rate']
        cols_d = ['#b6e174' if d >= 28 else '#49aa7e' for d in dr['day']]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=dr['day'], y=dr['rate'], marker_color=cols_d, name='Failure Rate'))
        fig.add_hline(y=base, line_dash='dash', line_color='#208c7a', line_width=1.5,
                      annotation_text=f'Baseline {base}%', annotation_position='right')
        fig.add_vrect(x0=27.5, x1=31.5, fillcolor='rgba(249,248,113,0.16)', line_width=0,
                      annotation_text='Salary window', annotation_position='top left')
        fig.update_layout(margin=dict(l=10,r=120,t=8,b=10),
                          plot_bgcolor='white', paper_bgcolor='white',
                          xaxis_title='Day of Month', yaxis_title='Failure Incidence Rate (%)',
                          showlegend=False, bargap=0.05)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Failure Rate by Day of Week (%)</div>', unsafe_allow_html=True)
            dow_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
            dw = ta.groupby('day_of_week')['is_failed'].mean().mul(100).round(2).reset_index()
            dw.columns = ['dow','rate']
            dw['dow'] = pd.Categorical(dw['dow'], categories=dow_order, ordered=True)
            dw = dw.sort_values('dow')
            fig = bar_layout(px.bar(dw, x='dow', y='rate', color='rate', color_continuous_scale=_HEAT_SCALE), y_title="Failure Rate (%)")
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Salary Window vs Normal Day Comparison (%)</div>', unsafe_allow_html=True)
            comp = pd.DataFrame({
                'Window': ['Normal days (1–27)', 'Salary window (28–31)'],
                'Rate':   [round(normal, 2), round(salary, 2)]
            })
            fig = px.bar(comp, x='Window', y='Rate',
                         color='Rate', color_continuous_scale=_HEAT_SCALE,
                         text=comp['Rate'].apply(lambda x: f'{x}%'))
            fig.update_traces(textposition='outside', textfont_size=13)
            fig.update_layout(margin=dict(l=10,r=10,t=8,b=10),
                              plot_bgcolor='white', paper_bgcolor='white',
                              xaxis_title='', yaxis_title='Failure Incidence Rate (%)',
                              coloraxis_showscale=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: DEEP DIVE
# ═══════════════════════════════════════════════════════════════════════════════
elif selected_page_id == "deep-dive":
    dd = filtered_df.copy()
    page_title("deep-dive", "Cross-dimensional analysis — channel × hour heatmap, MTTR and bank+channel combos")
    st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="ov-panel-title">Failure Incidence Rate by Payment Channel × Hour of Day (%)</div>', unsafe_allow_html=True)
        pivot = dd.pivot_table(values='is_failed', index='payment_channel', columns='hour', aggfunc='mean').mul(100).round(1)
        fig = px.imshow(pivot, color_continuous_scale=_THEME_SCALE, aspect='auto', text_auto='.1f')
        fig.update_layout(margin=dict(l=10,r=10,t=8,b=10),
                          plot_bgcolor='white', paper_bgcolor='white',
                          xaxis_title='Hour of Day', yaxis_title='')
        fig.update_coloraxes(colorbar=dict(title='Failure %', thickness=14, len=0.8))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Mean Time to Recovery (MTTR) by Failure Cause (min)</div>', unsafe_allow_html=True)
            rt = (dd[dd['is_failed']==1].groupby('failure_reason')['resolution_time_mins']
                  .mean().round(1).reset_index().sort_values('resolution_time_mins', ascending=True))
            rt.columns = ['reason','mttr']
            rt['label'] = rt['reason'].str.replace('_', ' ').str.title()
            fig = px.bar(rt, x='mttr', y='label', orientation='h',
                         color='mttr', color_continuous_scale=_HEAT_SCALE,
                         text=rt['mttr'].apply(lambda x: f'{x:.0f}m'))
            fig.update_traces(textposition='outside')
            fig.update_layout(margin=dict(l=10,r=50,t=8,b=10),
                              plot_bgcolor='white', paper_bgcolor='white',
                              xaxis_title='Average MTTR (minutes)', yaxis_title='',
                              coloraxis_showscale=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Failure Rate by Bank + Channel Combination (Top 10)</div>', unsafe_allow_html=True)
            combo = dd.groupby(['bank_name','payment_channel'])['is_failed'].mean().mul(100).round(2).reset_index()
            combo['combo'] = combo['bank_name'] + ' ' + combo['payment_channel']
            combo = combo.sort_values('is_failed', ascending=True).tail(10)
            fig = px.bar(combo, x='is_failed', y='combo', orientation='h',
                         color='is_failed', color_continuous_scale=_HEAT_SCALE,
                         text=combo['is_failed'].apply(lambda x: f'{x}%'))
            fig.update_traces(textposition='outside')
            fig.update_layout(margin=dict(l=10,r=50,t=8,b=10),
                              plot_bgcolor='white', paper_bgcolor='white',
                              xaxis_title='Failure Incidence Rate (%)', yaxis_title='',
                              coloraxis_showscale=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="ov-panel-title">Full Bank × Channel Failure Rate Matrix (%)</div>', unsafe_allow_html=True)
        matrix = dd.pivot_table(values='is_failed', index='bank_name', columns='payment_channel', aggfunc='mean').mul(100).round(1)
        fig = px.imshow(matrix, color_continuous_scale=_THEME_SCALE, aspect='auto', text_auto='.1f')
        fig.update_layout(margin=dict(l=10,r=10,t=8,b=10),
                          plot_bgcolor='white', paper_bgcolor='white',
                          xaxis_title='Payment Channel', yaxis_title='Bank')
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: PREDICTION
# ═══════════════════════════════════════════════════════════════════════════════
elif selected_page_id == "prediction":
    pr = filtered_df.copy()
    page_title("prediction", "Statistical failure prediction — high-risk windows, UPI vs NEFT and live risk checker")
    st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

    total    = len(pr)
    base_loc = round(pr['is_failed'].mean() * 100, 2) if total else 0
    hr_count = int(pr['is_high_risk'].sum()) if total else 0
    hr_rate  = round(pr[pr['is_high_risk']==1]['is_failed'].mean() * 100, 2) if hr_count else 0
    nm_rate  = round(pr[pr['is_high_risk']==0]['is_failed'].mean() * 100, 2) if total else 0
    mult     = round(hr_rate / nm_rate, 2) if nm_rate else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("High-Risk Transactions", f"{hr_count:,}",   f"{round(hr_count/total*100,1) if total else 0}% of total"), unsafe_allow_html=True)
    with k2: st.markdown(kpi("High-Risk Failure Rate", f"{hr_rate}%",     "Night window + salary days"),  unsafe_allow_html=True)
    with k3: st.markdown(kpi("Normal Failure Rate",    f"{nm_rate}%",     "Standard transaction windows"), unsafe_allow_html=True)
    with k4: st.markdown(kpi("Risk Multiplier",        f"{mult}×",        "High-risk vs normal"),          unsafe_allow_html=True)

    st.markdown(_sp, unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Failure Rate: High-Risk vs Normal Windows (%)</div>', unsafe_allow_html=True)
            cmp = pd.DataFrame({'Window': ['Normal', 'High-Risk'], 'Rate': [nm_rate, hr_rate]})
            fig = px.bar(cmp, x='Window', y='Rate', color='Window',
                         color_discrete_map={'Normal':'#49aa7e','High-Risk':'#b6e174'},
                         text=cmp['Rate'].apply(lambda x: f'{x}%'))
            fig.add_hline(y=base_loc, line_dash='dash', line_color='#208c7a', line_width=1.5,
                          annotation_text=f'Baseline {base_loc}%', annotation_position='right')
            fig.update_traces(textposition='outside', textfont_size=13)
            fig.update_layout(margin=dict(l=10,r=80,t=8,b=10),
                              plot_bgcolor='white', paper_bgcolor='white',
                              xaxis_title='', yaxis_title='Failure Rate (%)',
                              showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Safest vs Riskiest Combination (%)</div>', unsafe_allow_html=True)
            upi_n = pr[(pr['payment_channel']=='UPI') & (pr['hour'].isin([22,23,0,1]))]['is_failed'].mean() * 100
            neft_d = pr[(pr['payment_channel']=='NEFT') & (~pr['hour'].isin([22,23,0,1]))]['is_failed'].mean() * 100
            upi_n = round(upi_n, 1) if not np.isnan(upi_n) else 0
            neft_d = round(neft_d, 1) if not np.isnan(neft_d) else 0
            cmp2 = pd.DataFrame({'Combo': ['NEFT Daytime', 'UPI Night'], 'Rate': [neft_d, upi_n]})
            fig = px.bar(cmp2, x='Combo', y='Rate', color='Combo',
                         color_discrete_map={'NEFT Daytime':'#49aa7e','UPI Night':'#b6e174'},
                         text=cmp2['Rate'].apply(lambda x: f'{x}%'))
            fig.update_traces(textposition='outside', textfont_size=13)
            fig.update_layout(margin=dict(l=10,r=10,t=8,b=10),
                              plot_bgcolor='white', paper_bgcolor='white',
                              xaxis_title='', yaxis_title='Failure Rate (%)',
                              showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)
    st.markdown('<div class="ov-table-title">Transaction Risk Checker</div>', unsafe_allow_html=True)

    inp1, inp2, result_col = st.columns([1, 1, 1.2])
    risk_channels = sorted(pr['payment_channel'].dropna().unique())
    risk_banks = sorted(pr['bank_name'].dropna().unique())
    if not risk_channels:
        risk_channels = sorted(df['payment_channel'].dropna().unique())
    if not risk_banks:
        risk_banks = sorted(df['bank_name'].dropna().unique())

    hc_loc = pr.groupby(['hour', 'payment_channel'])['is_failed'].mean().mul(100).round(2).reset_index()
    hc_loc.columns = ['hour', 'channel', 'rate']
    baseline_loc = round(pr['is_failed'].mean() * 100, 2) if len(pr) else 0.0

    with inp1:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Channel & Bank</div>', unsafe_allow_html=True)
            risk_ch  = st.selectbox("Payment Channel", risk_channels, key='rch')
            risk_bk  = st.selectbox("Bank", risk_banks, key='rbk')

    with inp2:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Timing</div>', unsafe_allow_html=True)
            range_options = ["00:00 – 05:59 (Late Night)", "06:00 – 11:59 (Morning)", "12:00 – 17:59 (Afternoon)", "18:00 – 23:59 (Evening)"]
            risk_time_range = st.selectbox("Time Window", range_options, index=2, key='rhr')
            risk_day = st.selectbox("Day of Month (1–31)", list(range(1, 32)), index=14, key='rdy')

    with result_col:
        with st.container(border=True):
            st.markdown('<div class="ov-panel-title">Risk Assessment</div>', unsafe_allow_html=True)
            if risk_time_range == range_options[0]: risk_hr_list = list(range(0, 6))
            elif risk_time_range == range_options[1]: risk_hr_list = list(range(6, 12))
            elif risk_time_range == range_options[2]: risk_hr_list = list(range(12, 18))
            else: risk_hr_list = list(range(18, 24))

            mask = (hc_loc['hour'].isin(risk_hr_list)) & (hc_loc['channel'] == risk_ch)
            pred = float(hc_loc[mask]['rate'].mean()) if mask.any() else baseline_loc
            is_night   = any(h in [22, 23, 0, 1] for h in risk_hr_list)
            is_sal     = risk_day >= 28
            is_high    = is_night or is_sal
            rfactor    = round(pred / baseline_loc, 2) if baseline_loc else 1.0

            if is_high:
                bg, border, tc, lbl = '#eef8d7','#b6e174','#0f6d6d','HIGH RISK'
            else:
                bg, border, tc, lbl = '#edfbe9','#7bc77a','#0f6d6d','LOW RISK'

            st.markdown(f'''
            <div style="background:{bg};border:1.5px solid {border};border-radius:14px;padding:18px 14px;text-align:center;">
                <div style="font-size:1.05rem;font-weight:700;color:{tc};margin-bottom:8px">{lbl}</div>
                <div style="font-size:2.6rem;font-weight:800;color:{tc};line-height:1">{pred:.1f}%</div>
                <div style="font-size:0.82rem;color:#486581;margin-top:5px">predicted failure rate</div>
                <div style="font-size:0.88rem;color:#486581;margin-top:12px">
                    Baseline {baseline_loc}% &nbsp;·&nbsp; Risk factor {rfactor}×
                </div>
            </div>''', unsafe_allow_html=True)

            reasons = []
            if is_night:  reasons.append(f'Night maintenance window ({risk_time_range.split(" (")[0]})')
            if is_sal:    reasons.append(f'Salary credit window (Day {risk_day})')
            ch_base = round(pr[pr['payment_channel']==risk_ch]['is_failed'].mean()*100, 1)
            reasons.append(f'{risk_ch} base failure rate: {ch_base}%')
            for r in reasons:
                st.markdown(f'<div style="color:#486581;font-size:0.83rem;padding:3px 0 0">▸ {r}</div>', unsafe_allow_html=True)

    st.markdown(_sp, unsafe_allow_html=True)
    st.markdown('<div class="ov-table-title">Predictive Insights for Banking Operations</div>', unsafe_allow_html=True)

    insights = [
        ("Insight 1", "Night Window Alert",
         f"Transactions during 10pm–1am fail at {hr_rate:.1f}% — {mult}× the normal rate of {nm_rate:.1f}%.",
         "Banks should display a CBS maintenance warning and recommend deferring non-urgent payments."),
        ("Insight 2", "Salary Day Surge",
         f"Failure rate spikes to {round(pr[pr['day_of_month']>=28]['is_failed'].mean()*100,1):.1f}% on days 28–31 (salary credit period).",
         "Pre-scale server capacity by at least 40% from the 27th of each month."),
        ("Insight 3", "Channel Guidance",
         f"UPI has the highest failure rate while RTGS is the most reliable. For high-value transfers, RTGS or NEFT is recommended.",
         "Display channel reliability scores to users at the point of payment initiation."),
        ("Insight 4", "Worst Combination",
         f"UPI at night fails at {upi_n:.1f}% vs NEFT daytime at {neft_d:.1f}% — a {round(upi_n/neft_d,1) if neft_d else 'N/A'}× difference.",
         "Rate-limit new UPI registrations during maintenance windows and prioritise retries for existing transactions."),
        ("Insight 5", "Error Prioritisation",
         "Bank server timeout has the longest MTTR and is directly actionable through infrastructure investment.",
         "Implement auto-scaling and hot-standby CBS replicas to reduce server timeout failures."),
    ]

    insights_html = ['<div class="insights-grid">']
    odd_count = len(insights) % 2 == 1
    last_index = len(insights) - 1
    for i, (num, title, body, rec) in enumerate(insights):
        span_class = ' span-2' if odd_count and i == last_index else ''
        insights_html.append(
            f'<div class="insight-card{span_class}">'
            f'<div class="insight-num">{num}</div>'
            f'<div class="insight-title">{title}</div>'
            f'<div class="insight-body">{body}</div>'
            f'<div class="insight-rec">→ {rec}</div>'
            '</div>'
        )
    insights_html.append('</div>')
    st.markdown(''.join(insights_html), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: RELIABILITY
# ═══════════════════════════════════════════════════════════════════════════════
elif selected_page_id == "reliability":
    rel = filtered_df.copy()
    sc  = compute_scores(rel)
    page_title("reliability", "Weighted reliability index across all bank × channel combinations")
    st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

    if sc.empty:
        st.info("No data is available for the current filters. Clear or broaden the filters to view reliability results.")
        st.stop()

    avg_sc   = round(sc['score'].mean(), 1)
    top_sc   = sc.iloc[0]
    bot_sc   = sc.iloc[-1]
    at_risk  = int((sc['score'] < 60).sum())

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("Average Score",    f"{avg_sc}",            "Across all combinations"),                      unsafe_allow_html=True)
    with k2: st.markdown(kpi("Top Performer",    top_sc['combo'],        f"Score: {top_sc['score']}"),                    unsafe_allow_html=True)
    with k3: st.markdown(kpi("Lowest Performer", bot_sc['combo'],        f"Score: {bot_sc['score']}"),                    unsafe_allow_html=True)
    with k4: st.markdown(kpi("At-Risk Combos",   str(at_risk),           "Score below 60 — action required"),             unsafe_allow_html=True)

    st.markdown(_sp, unsafe_allow_html=True)

    if at_risk > 0:
        risk_df = sc[sc['score'] < 60][['combo', 'score']].sort_values('score')
        risk_df = risk_df.reset_index(drop=True)
        chip_html = []
        for _, r in risk_df.iterrows():
            chip_html.append(
                f'<span class="rel-chip"><span>{r["combo"]}</span><span class="rel-chip-score">{r["score"]:.1f}</span></span>'
            )

        st.markdown(
            f'''<div class="rel-alert">
                    <div class="rel-alert-title">Risk Alert</div>
                    <div class="rel-alert-meta">{at_risk} combination(s) are below reliability threshold (60).</div>
                    <div class="rel-alert-list">{"".join(chip_html)}</div>
                </div>''',
            unsafe_allow_html=True,
        )

    st.markdown(_sp, unsafe_allow_html=True)
    st.markdown('<div class="ov-table-title">Reliability Leaderboard — All Bank × Channel Combinations</div>', unsafe_allow_html=True)

    def _rank_cell(v, row):
        return f'<strong>#{v}</strong>'
    def _score_cell(v, row):
        return f'<strong style="color:{row["grade_color"]};font-size:1rem">{v}</strong>'
    def _grade_cell(v, row):
        return f'<span class="ov-badge" style="background:{row["grade_bg"]};color:{row["grade_color"]}">{row["grade"]}</span>'
    def _fr_cell(v, row):
        return f'{v:.1f}%'
    def _res_cell(v, row):
        return f'{v:.0f} min'

    tbl = sc.copy()
    tbl.index = tbl.index + 1
    tbl['rank'] = tbl.index

    st.markdown(render_html_table(
        tbl,
        ['rank', 'bank_name', 'payment_channel', 'score', 'grade', 'failure_rate', 'avg_res'],
        ['Rank', 'Bank', 'Channel', 'Score', 'Grade', 'Failure Rate', 'Avg MTTR'],
        {
            'rank': _rank_cell,
            'score': _score_cell,
            'grade': _grade_cell,
            'failure_rate': _fr_cell,
            'avg_res': _res_cell
        }
    ), unsafe_allow_html=True)

    st.markdown(_sp, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('''
        <div class="ov-panel-title" style="display: flex; justify-content: space-between; align-items: center;">
            <span>Reliability Index by Bank + Channel Combination</span>
            <span class="rel-info-icon" style="cursor: pointer; color: #627D98; display: inline-flex; align-items: center; transition: color 0.2s;" title="View Calculation Details" onmouseover="this.style.color='#0f6d6d'" onmouseout="this.style.color='#627D98'">
                <svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="currentColor">
                    <path d="M440-280h80v-240h-80v240Zm40-320q17 0 28.5-11.5T520-640q0-17-11.5-28.5T480-680q-17 0-28.5 11.5T440-640q0 17 11.5 28.5T480-600Zm0 520q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Z"/>
                </svg>
            </span>
        </div>
        ''', unsafe_allow_html=True)
        sc_sorted = sc.sort_values('score', ascending=True)
        colors = [row['grade_color'] for _, row in sc_sorted.iterrows()]
        fig = go.Figure(go.Bar(
            x=sc_sorted['score'], y=sc_sorted['combo'],
            orientation='h', marker_color=colors,
            text=sc_sorted['score'].apply(lambda x: f'{x}'),
            textposition='outside'
        ))
        fig.update_layout(margin=dict(l=10,r=60,t=8,b=10),
                          plot_bgcolor='white', paper_bgcolor='white',
                          xaxis_title='Reliability Score (0–100)', yaxis_title='',
                          showlegend=False, xaxis_range=[0,110])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)
    st.markdown('<div id="rel-calc-section"></div>', unsafe_allow_html=True)

    with st.expander("How the reliability score is calculated", expanded=False):
        st.markdown("""
        The reliability score (0–100) is a weighted composite of three factors:

        | Factor | Weight | Description |
        |--------|--------|-------------|
        | Failure incidence rate | **50%** | Lower failure rate = higher score |
        | Mean Time to Recovery (MTTR) | **30%** | Faster resolution = higher score |
        | Error severity | **20%** | Less severe errors = higher score |

        **Formula:**
        ```
        Score = (100 − norm_failure_rate) × 0.5
              + (100 − norm_resolution_time) × 0.3
              + (100 − norm_severity) × 0.2
        ```

        Each factor is min-max normalised to 0–100 before applying weights.
        Score bands: **Excellent** ≥ 80 · **Good** 60–79 · **At Risk** < 60
        """)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: HEATMAP
# ═══════════════════════════════════════════════════════════════════════════════
elif selected_page_id == "heatmap":
    hm = filtered_df.copy()
    page_title("heatmap", "Full-resolution failure incidence heatmaps — channel × hour and bank × channel")
    st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)
    st.markdown('<style>.js-plotly-plot .legend { pointer-events: none !important; }</style>', unsafe_allow_html=True)

    pivot_ch = hm.pivot_table(values='is_failed', index='payment_channel', columns='hour', aggfunc='mean').mul(100).round(1)
    
    if pivot_ch.empty or pivot_ch.isna().all().all() or pivot_ch.stack().empty:
        wc_label, wc_val, bc_label, bc_val = "N/A", "N/A", "N/A", "N/A"
    else:
        worst_cell = pivot_ch.stack().idxmax()
        best_cell = pivot_ch.stack().idxmin()
        wc_label = f"{worst_cell[0]}, Hr {worst_cell[1]:02d}"
        wc_val = f"{pivot_ch.loc[worst_cell]:.1f}% failure rate"
        bc_label = f"{best_cell[0]}, Hr {best_cell[1]:02d}"
        bc_val = f"{pivot_ch.loc[best_cell]:.1f}% failure rate"

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("Worst Cell", wc_label, wc_val), unsafe_allow_html=True)
    with k2: st.markdown(kpi("Best Cell",  bc_label, bc_val), unsafe_allow_html=True)
    with k3: st.markdown(kpi("Peak Hours",  "22:00 – 01:00", "Bank maintenance window"),  unsafe_allow_html=True)
    with k4: st.markdown(kpi("Channels",    str(pivot_ch.shape[0]), "Rows in heatmap"), unsafe_allow_html=True)

    st.markdown(_sp, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="ov-panel-title">Payment Channel × Hour of Day — Failure Incidence Rate (%)</div>', unsafe_allow_html=True)
        custom_ch = pivot_ch.apply(lambda c: c.map(lambda x: "No Data" if pd.isna(x) else f"{x:.1f}%"))
        text_ch = pivot_ch.apply(lambda c: c.map(lambda x: "" if pd.isna(x) else f"{x:.1f}"))
        fig = px.imshow(pivot_ch,
                        color_continuous_scale=_THEME_SCALE,
                        aspect='auto', zmin=0, zmax=100,
                        labels=dict(x='Hour of Day', y='Payment Channel', color='Failure %'))
        fig.update_traces(
            text=text_ch,
            texttemplate="%{text}",
            customdata=custom_ch,
            hovertemplate=(
                f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Hour</span><br>"
                "<b>%{x}:00</b><br>"
                f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Channel</span><br>"
                "<b>%{y}</b><br>"
                f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Failure</span><br>"
                "<b>%{customdata}</b><extra></extra>"
            )
        )
        fig.update_layout(margin=dict(l=10,r=10,t=8,b=10),
                          plot_bgcolor='white', paper_bgcolor='white',
                          height=320,
                          showlegend=False,
                          annotations=[
                              dict(
                                  text="      ",
                                  xref="paper", yref="paper", x=1.02, y=0.15,
                                  xanchor="left", yanchor="middle", showarrow=False,
                                  xshift=6,
                                  bordercolor="#94A3B8", borderwidth=1.5, bgcolor="white",
                                  font=dict(size=12)
                              ),
                              dict(
                                  text="No Data",
                                  xref="paper", yref="paper", x=1.02, y=0.15,
                                  xanchor="left", yanchor="middle", showarrow=False,
                                  xshift=34,
                                  font=dict(size=14, color="#486581")
                              )
                          ])
        fig.update_coloraxes(colorbar=dict(
            title='Failure %', 
            outlinewidth=1, outlinecolor='#CBD5E1',
            thickness=16, len=0.7, tickfont=dict(size=11), y=0.55, yanchor='middle', x=1.02
        ))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="ov-panel-title">Bank × Payment Channel — Failure Incidence Rate (%)</div>', unsafe_allow_html=True)
        pivot_bk = hm.pivot_table(values='is_failed', index='bank_name', columns='payment_channel', aggfunc='mean').mul(100).round(1)
        custom_bk = pivot_bk.apply(lambda c: c.map(lambda x: "No Data" if pd.isna(x) else f"{x:.1f}%"))
        text_bk = pivot_bk.apply(lambda c: c.map(lambda x: "" if pd.isna(x) else f"{x:.1f}"))
        fig = px.imshow(pivot_bk,
                        color_continuous_scale=_THEME_SCALE,
                        aspect='auto', zmin=0, zmax=100,
                        labels=dict(x='Payment Channel', y='Bank', color='Failure %'))
        fig.update_traces(
            text=text_bk,
            texttemplate="%{text}",
            customdata=custom_bk,
            hovertemplate=(
                f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Bank</span><br>"
                "<b>%{y}</b><br>"
                f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Channel</span><br>"
                "<b>%{x}</b><br>"
                f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Failure</span><br>"
                "<b>%{customdata}</b><extra></extra>"
            )
        )
        fig.update_layout(margin=dict(l=10,r=10,t=8,b=10),
                          plot_bgcolor='white', paper_bgcolor='white',
                          height=280,
                          showlegend=False,
                          annotations=[
                              dict(
                                  text="      ",
                                  xref="paper", yref="paper", x=1.02, y=0.15,
                                  xanchor="left", yanchor="middle", showarrow=False,
                                  xshift=6,
                                  bordercolor="#94A3B8", borderwidth=1.5, bgcolor="white",
                                  font=dict(size=12)
                              ),
                              dict(
                                  text="No Data",
                                  xref="paper", yref="paper", x=1.02, y=0.15,
                                  xanchor="left", yanchor="middle", showarrow=False,
                                  xshift=34,
                                  font=dict(size=14, color="#486581")
                              )
                          ])
        fig.update_coloraxes(colorbar=dict(
            title='Failure %', 
            outlinewidth=1, outlinecolor='#CBD5E1',
            thickness=16, len=0.7, tickfont=dict(size=11), y=0.55, yanchor='middle', x=1.02
        ))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(_sp, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="ov-panel-title">Hour × Day of Month — Failure Incidence Rate (%)</div>', unsafe_allow_html=True)
        pivot_hd = hm.pivot_table(values='is_failed', index='hour', columns='day_of_month', aggfunc='mean').mul(100)
        pivot_hd = pivot_hd.sort_index().sort_index(axis=1)

        hourly_avg = pivot_hd.mean(axis=1)
        daily_avg = pivot_hd.mean(axis=0)
        
        has_hourly = len(hourly_avg) > 0 and not hourly_avg.isna().all()
        peak_hour = int(hourly_avg.idxmax()) if has_hourly else 0
        peak_hour_rate = float(hourly_avg.max()) if has_hourly else 0.0
        
        has_daily = len(daily_avg) > 0 and not daily_avg.isna().all()
        peak_day = int(daily_avg.idxmax()) if has_daily else 1
        peak_day_rate = float(daily_avg.max()) if has_daily else 0.0

        salary_days = [d for d in daily_avg.index if d >= 28]
        normal_days = [d for d in daily_avg.index if d < 28]
        salary_rate = float(daily_avg.loc[salary_days].mean()) if salary_days else 0.0
        normal_rate = float(daily_avg.loc[normal_days].mean()) if normal_days else 0.0
        salary_lift = ((salary_rate - normal_rate) / normal_rate * 100) if normal_rate else 0.0

        night_hours = [h for h in [22, 23, 0, 1] if h in hourly_avg.index]
        day_hours = [h for h in hourly_avg.index if h not in night_hours]
        night_rate = float(hourly_avg.loc[night_hours].mean()) if night_hours else 0.0
        daytime_rate = float(hourly_avg.loc[day_hours].mean()) if day_hours else 0.0

        i1, i2, i3, i4 = st.columns(4)
        with i1:
            st.markdown(kpi("Peak Hour", f"{peak_hour:02d}:00", f"Avg failure: {peak_hour_rate:.1f}%"), unsafe_allow_html=True)
        with i2:
            st.markdown(kpi("Peak Day", f"Day {peak_day}", f"Avg failure: {peak_day_rate:.1f}%"), unsafe_allow_html=True)
        with i3:
            st.markdown(kpi("Night vs Day", f"{night_rate:.1f}%", f"Daytime: {daytime_rate:.1f}%"), unsafe_allow_html=True)
        with i4:
            st.markdown(kpi("Salary Lift", f"{salary_lift:+.1f}%", f"28-31 vs 1-27 days"), unsafe_allow_html=True)

        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

        custom_hd = pivot_hd.apply(lambda c: c.map(lambda x: "No Data" if pd.isna(x) else f"{x:.1f}%"))
        fig = px.imshow(
            pivot_hd.round(1),
            color_continuous_scale=_THEME_SCALE,
            aspect='auto', zmin=0, zmax=100,
            labels=dict(x='Day of Month', y='Hour of Day', color='Failure %'),
        )
        fig.add_vrect(x0=27.5, x1=31.5, fillcolor='rgba(182, 225, 116, 0.18)', line_width=0)
        fig.add_hrect(y0=-0.5, y1=1.5, fillcolor='rgba(73, 170, 126, 0.14)', line_width=0)
        fig.add_hrect(y0=21.5, y1=23.5, fillcolor='rgba(73, 170, 126, 0.14)', line_width=0)
        fig.update_layout(
            margin=dict(l=10, r=10, t=8, b=10),
            plot_bgcolor='white', paper_bgcolor='white',
            height=430,
            showlegend=False,
            annotations=[
                dict(
                    text="      ",
                    xref="paper", yref="paper", x=1.02, y=0.15,
                    xanchor="left", yanchor="middle", showarrow=False,
                    xshift=6,
                    bordercolor="#94A3B8", borderwidth=1.5, bgcolor="white",
                    font=dict(size=12)
                ),
                dict(
                    text="No Data",
                    xref="paper", yref="paper", x=1.02, y=0.15,
                    xanchor="left", yanchor="middle", showarrow=False,
                    xshift=34,
                    font=dict(size=14, color="#486581")
                )
            ]
        )
        fig.update_traces(
            customdata=custom_hd,
            hovertemplate=(
                f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Day</span><br>"
                "<b>%{x}</b><br>"
                f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Hour</span><br>"
                "<b>%{y}:00</b><br>"
                f"<span style='color:{_HOVER_ACCENT}; font-weight:600;'>Failure</span><br>"
                "<b>%{customdata}</b><extra></extra>"
            )
        )
        fig.update_coloraxes(colorbar=dict(
            title='Failure %', 
            outlinewidth=1, outlinecolor='#CBD5E1',
            thickness=16, len=0.75, tickfont=dict(size=11), y=0.58, yanchor='middle', x=1.02
        ))
        st.plotly_chart(fig, use_container_width=True)


