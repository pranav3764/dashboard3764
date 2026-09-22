"""
app.py  —  streamlit run c:\\nifty\\app.py
 
Layout — 5 rows, each: [ Table | Strangle | Chart ]

  Row 1 — NIFTY   Current Expiry  (w1)
  Row 2 — SENSEX  Current Expiry  (w1)
  Row 3 — BANK NIFTY Current Month (w1)
  Row 4 — NIFTY   Next Expiry     (w2)
  Row 5 — SENSEX  Next Expiry     (w2)

Greeks panel appears when a strike row is clicked (auto-refreshes every 1 s).
"""
 
import json
import time
import threading
import http.server
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
 
DATA_FILE             = r"C:\Users\Victus\Downloads\Dashboard_1\live_data.json"
STRADDLE_HISTORY_FILE = r"C:\Users\Victus\Downloads\Dashboard_1\straddle_history.json"
OTM_LEVELS = 7


if "selected_data" not in st.session_state:
    st.session_state.selected_data = None
if "greeks_panel" not in st.session_state:
    # dict: strike, instrument, week, ce, pe, ce_iv, pe_iv,
    #       ce_greeks, pe_greeks, net_greeks  — or None
    st.session_state.greeks_panel = None

if "show_greeks_dialog" not in st.session_state:
    st.session_state.show_greeks_dialog = False
# Track which strike+instrument+week was last dismissed via X
if "dismissed_key" not in st.session_state:
    st.session_state.dismissed_key = None
# Was the dialog open on the previous rerun?
if "dialog_was_open" not in st.session_state:
    st.session_state.dialog_was_open = False
if "pause_updates" not in st.session_state:
    st.session_state.pause_updates = False

if "pause_until" not in st.session_state:
    st.session_state.pause_until = 0



# ── Detect X click ───────────────────────────────────────────────────────────
# While paused, st.stop() prevents any automatic reruns.
# The ONLY way a rerun happens during pause is when the user clicks X.
# So: if we were paused AND dialog_was_open last rerun → X was clicked.
if st.session_state.pause_updates and st.session_state.dialog_was_open:
    panel = st.session_state.greeks_panel
    if panel:
        st.session_state.dismissed_key = (
            panel.get("instrument"),
            panel.get("strike"),
            panel.get("week"),
        )
    st.session_state.greeks_panel = None
    st.session_state.show_greeks_dialog = False
    # ── Resume live updates immediately ──────────────────────────────────────
    st.session_state.pause_updates = False
    st.session_state.pause_until = 0
st.session_state.dialog_was_open = False  # reset; show_greeks_dialog() sets it True

st.set_page_config(
    page_title="NIFTY / SENSEX Live Options",
    layout="wide",
    page_icon="📈",
)
 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Bebas+Neue&display=swap');
 
html, body, [class*="css"], .stApp {
    background-color: #090d18 !important;
    color: #dde4f0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding-top: 150px;   /* 🔥 ADD THIS */
    padding-bottom: 20px;
}
 
/* ── Remove whitespace inside dataframe containers ── */
[data-testid="stDataFrame"] > div,
[data-testid="stDataFrame"] iframe { overflow: hidden !important; }
[data-testid="stDataFrame"] { margin-bottom: 0 !important; padding-bottom: 0 !important; }
[data-testid="stDataFrame"] > div > div { overflow: hidden !important; }
 
/* Hide dataframe toolbar */
button[title="Download"] { display:none !important; }
 
/* ── Responsive ── */
@media (max-width: 1400px) {
    html, body, [class*="css"], .stApp { font-size: 16px !important; }
    .ohlc-row    { font-size: 0.62rem !important; gap: 8px !important; }
    .straddle-ltp-val { font-size: 0.85rem !important; }
    .s-key { font-size: 0.62rem !important; }
    .s-val { font-size: 0.72rem !important; }
    .sec-hdr, .sec-hdr-w2 { font-size: 1.1rem !important; }
    .otm-hdr, .otm-hdr-w2 { font-size: 0.75rem !important; }
    .info-row    { font-size: 0.7rem !important; }
    .info-lbl    { font-size: 0.65rem !important; }
}
 
@media (max-width: 1100px) {
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1),
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {
        min-width: 48% !important; flex: 1 1 48% !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) {
        min-width: 100% !important; flex: 1 1 100% !important; margin-top: 18px !important;
    }
}
@media (max-width: 680px) {
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        min-width: 100% !important; flex: 1 1 100% !important; margin-top: 14px !important;
    }
    .ticker-bar { flex-wrap: wrap; }
    .ticker-item { min-width: 48%; border-right: none !important; padding: 6px 10px; }
    .ticker-item:nth-child(odd) { border-right: 1px solid #1a2f55 !important; }
    .ticker-item:nth-child(1), .ticker-item:nth-child(2) { border-bottom: 1px solid #1a2f55; }
}
.stApp {
    overflow: visible !important;
}
/* ── Ticker bar ── */
.ticker-bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 9999;

    width: 100%;
    max-width: 100vw;

    background: linear-gradient(90deg,#0d1830,#0a1528 60%,#0d1830);
    border-bottom:1px solid #1a2f55;
    padding:12px 20px;
    justify-content: space-between;
    
    display: flex;
    align-items: stretch;
    gap: 0;
    
    transform: translateZ(1);
    -webkit-transform: translateZ(0);
    will-change: transform;
    backface-visibility: hidden;
    -webkit-backface-visibility: hidden;
    isolation: isolate;
}
.ticker-item { display:flex; flex-direction:column; gap:2px; flex:1 1 0; padding:0 18px; }
.ticker-item:not(:last-child) { border-right:1px solid #1a2f55; }
.ticker-name { font-size:0.7rem; letter-spacing:0.18em; text-transform:uppercase; color:#ff8c00; margin-bottom:3px}
.ticker-ltp  { font-family:'Bebas Neue',sans-serif; font-size:1.5rem; letter-spacing:0.06em; line-height:1; color:#e8f0ff; }
.ticker-meta { font-size:0.7rem; display:flex; align-items:center; gap:8px; }
.pct-up   { color:#22dd88; font-weight:700; }
.pct-down { color:#ee5555; font-weight:700; }
.pct-na   { color:#5a7aaa; }
.ohlc-row { display:flex; gap:15px; margin-top:3px; font-size:0.70rem; flex-wrap:wrap;}
.ohlc-lbl { color:#AAAAAA; margin-right:3px }
.ohlc-val-high { color:#22dd88; font-weight:600; }
.ohlc-val-low  { color:#ee5555; font-weight:600; }
.ohlc-val-open { color:#f0c040; font-weight:600; }
.ohlc-val-pc   { color:#7a8aaa; font-weight:600; }
                
/* ── Ticker bar — lives on document.body, outside Streamlit's React root ── */
#__nifty_ticker__ {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 99999;
    width: 100%;
}

#__nifty_ticker__ .ticker-bar {
    display: flex;
    align-items: stretch;
    gap: 0;
    justify-content: space-between;
    width: 100%;
    max-width: 100vw;
    font-family:Bebas Neue',sans-serif;
    background: linear-gradient(90deg, #0d1830, #0a1528 60%, #0d1830);
    border-bottom: 1px solid #1a2f55;
    padding: 12px 20px;
    box-sizing: border-box;
    /* GPU compositing — no paint on scroll */
    transform: translateZ(0);
    will-change: transform;
    backface-visibility: hidden;
    isolation: isolate;
}
 
/* ── Section headers ── */
.sec-hdr {
    font-family:'Bebas Neue',sans-serif; font-size:1.5rem; letter-spacing:0.08em;
    padding:4px 10px; border-left:4px solid #f0c040;
    background:#0e1828; color:#e8d080; margin-bottom:3px;
}
.sec-hdr-w2 {
    font-family:'Bebas Neue',sans-serif; font-size:1.5rem; letter-spacing:0.08em;
    padding:4px 10px; border-left:4px solid #f0c040;
    background:#0e1828; color:#e8d080; margin-bottom:3px;
}
 
/* ── Straddle OHLC bar ── */
.straddle-bar {
    display:flex; align-items:center; gap:0;
    background:#07111f; border:1px solid #152840;
    border-radius:5px; padding:4px 10px; margin-bottom:4px; flex-wrap:wrap;
}
.straddle-lbl { font-size:0.65rem; color:#AAAAAA; letter-spacing:0.14em; text-transform:uppercase; margin-right:8px; white-space:nowrap; }
.straddle-ltp-val { font-family:'Bebas Neue',sans-serif; font-size:1rem; color:#AAAAAA; letter-spacing:0.05em; margin-right:7px; }
.straddle-divider { width:1px; height:16px; background:#152840; margin:0 8px; flex-shrink:0; }
.s-item { display:flex; align-items:center; gap:3px; }
.s-key  { font-size:0.7rem; color:#3a5878; letter-spacing:0.10em; }
.s-val  { font-size:0.8rem; font-weight:700; }
.s-open { color:#f0c040; }
.s-high { color:#22dd88; }
.s-low  { color:#ee5555; }
.s-pc   { color:#7a8aaa; }
 
/* ── Info row ── */
.info-row { display:flex; align-items:center; flex-wrap:wrap; gap:5px; padding:3px 2px; margin-bottom:4px; font-size:0.8rem; }
.info-item { display:flex; align-items:baseline; gap:3px; }
.info-lbl  { color:#AAAAAA; font-size:0.75rem; letter-spacing:0.10em; text-transform:uppercase; margin-right:3px}
.info-val  { color:#b8ddf8; font-weight:700; }
.fut-val   { color:#a8c8f0; }
.syn-val   { color:#f0d060; font-weight:700; }
.info-sep  { color:#1a3050; font-size:0.78rem; }
.info-time { margin-left:auto; color:#AAAAAA; font-size:0.8rem; }
            

 
/* ── OTM strangle headers ── */
.otm-hdr {
    background:#0c1c38; color:#6aa8d8; font-size:0.9rem; font-weight:700;
    padding:5px 10px; border-left:3px solid #2060a0; margin-bottom:3px; letter-spacing:0.04em;
}
.otm-hdr-w2 {
    background:#081828; color:#4a88a8; font-size:0.80rem; font-weight:700;
    padding:5px 10px; border-left:3px solid #184860; margin-bottom:3px; letter-spacing:0.04em;
}
 
/* ── Selects ── */
div[data-baseweb="select"] > div {
    background:#0c1c38 !important; border-color:#1a3660 !important;
    color:#6aa8d8 !important; font-family:'JetBrains Mono',monospace !important; font-size:0.82rem !important;
}
div[data-baseweb="select"] svg { fill:#6aa8d8 !important; }
                                
/* ── Zero gap between stacked column rows inside a container ── */
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) {
    gap: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}
.no-gap-container > div {
    gap: 0 !important;
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}
 
/* ── Greeks Panel ── */
.greeks-panel {
    background: linear-gradient(135deg, #0a1828 0%, #0d1e35 100%);
    border: 1px solid #1e3a5a;
    border-radius: 8px;
    padding: 10px 14px;
    font-family: 'JetBrains Mono', monospace;
}
.greeks-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.1rem;
    letter-spacing: 0.10em;
    color: #f0c040;
    margin-bottom: 6px;
    border-bottom: 1px solid #1e3a5a;
    padding-bottom: 4px;
}
.greeks-subtitle {
    font-size: 0.62rem;
    color: #5a7aaa;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 3px;
    margin-top: 4px;
}
.greeks-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 3px 6px;
    margin-bottom: 2px;
}
.greek-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: #070f1e;
    border-radius: 4px;
    padding: 3px 4px;
    border: 1px solid #122040;
}
.greek-lbl { font-size: 0.55rem; color: #3a5878; letter-spacing: 0.10em; text-transform: uppercase; }
.greek-val { font-size: 0.74rem; font-weight: 700; }
.greek-ce  { color: #22dd88; }
.greek-pe  { color: #ee5555; }
.greek-net { color: #f0c040; }
.iv-row {
    display: flex; gap: 6px; justify-content: center; margin-bottom: 5px;
}
.iv-badge {
    display: flex; align-items: center; gap: 4px;
    background: #070f1e; border-radius: 4px; padding: 3px 10px;
    border: 1px solid #122040;
}
.iv-lbl { font-size: 0.60rem; color: #3a5878; letter-spacing: 0.10em; }
.iv-val { font-size: 0.80rem; font-weight: 700; }
.greeks-col-hdr {
    text-align: center; font-size: 0.58rem; letter-spacing: 0.12em;
    font-weight: 700; padding-bottom: 2px;
}
.greeks-close-hint { font-size: 0.55rem; color: #1e3050; text-align: right; margin-top: 4px; }
 
/* ── Header ── */
.main-title { font-family:'Bebas Neue',sans-serif; font-size:2.5rem; letter-spacing:0.10em; color:#f0c040; line-height:1; }
.sub-title  { font-size:0.8rem; color:#AAAAAA; letter-spacing:0.18em; text-transform:uppercase; }
.status-live {
    display:inline-block; background:#061510; border:1px solid #1a7a3a; color:#22dd88;
    border-radius:20px; padding:3px 14px; font-size:0.76rem; letter-spacing:0.14em;
    text-transform:uppercase; animation:blink 2s infinite;
}
.status-wait {
    display:inline-block; background:#160e00; border:1px solid #7a5500; color:#ddaa22;
    border-radius:20px; padding:3px 14px; font-size:0.76rem; letter-spacing:0.14em; text-transform:uppercase;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.35} }

/* ── Force dark background on ALL iframes (dataframes) ── */
iframe {
    background-color: #090d18 !important;
    color-scheme: dark !important;
}

/* ── Streamlit dataframe wrapper ── */
[data-testid="stDataFrame"] > div > div > iframe {
    background: #090d18 !important;
}

/* ── Dropdown / popover menus (baseweb) ── */
[data-baseweb="popover"],
[data-baseweb="menu"],
[role="listbox"],
ul[role="listbox"] {
    background-color: #0c1c38 !important;
    border: 1px solid #1a3660 !important;
    color: #6aa8d8 !important;
}
[role="option"] {
    background-color: #0c1c38 !important;
    color: #a8c8e8 !important;
}
[role="option"]:hover,
[aria-selected="true"] {
    background-color: #152e5a !important;
    color: #e8f0ff !important;
}

/* ── Stray white backgrounds from Streamlit containers ── */
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="column"],
[data-testid="stColumn"],
.stColumn > div,
div[class*="css"] {
    background-color: transparent !important;
}

/* ── Expander / details ── */
details, summary,
[data-testid="stExpander"] {
    background-color: #090d18 !important;
    border-color: #1a2f55 !important;
    color: #dde4f0 !important;
}

/* ── Tooltip / overlay backgrounds ── */
[data-baseweb="tooltip"] > div,
[data-baseweb="card"] {
    background-color: #0d1830 !important;
    border: 1px solid #1a2f55 !important;
    color: #dde4f0 !important;
}

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #090d18; }
::-webkit-scrollbar-thumb { background: #1a2f55; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2a4f7a; }

/* ── ATM change annotation ── */
.atm-change-tag {
    display: inline-block;
    background: #1a1000;
    border: 1px solid #f0c04055;
    color: #f0c040;
    font-size: 0.65rem;
    border-radius: 4px;
    padding: 1px 7px;
    margin: 2px 3px;
    font-family: 'JetBrains Mono', monospace;
}
/* 🔥 REMOVE WHITE CONTAINER BEHIND TABLE */
[data-testid="stDataFrame"] > div {
    background-color: #090d18 !important;
}

[data-testid="stDataFrame"] > div > div {
    background-color: #090d18 !important;
}

/* Also fix inner table wrapper */
[data-testid="stDataFrame"] table {
    background-color: #090d18 !important;
}
/* 🔥 Force ALL table headers (including Greeks) */
[data-testid="stDataFrame"] thead th {
    background-color: #0c1c38 !important;
    color: #e8f0ff !important;
}
</style>
""", unsafe_allow_html=True)
 
 
# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read()

        if not content.strip():
            return {}, None

        return json.loads(content), None

    except Exception as e:
        return {}, str(e)


def load_straddle_chart_series(series_key: str):
    """
    Load one unified series (e.g. "nifty_w1") from straddle_history.json.
    Returns list of {time, price, atm_strike} dicts, or [] on any error.
    The series is already a continuous record across ATM changes.
    """

    try:
        with open(STRADDLE_HISTORY_FILE, "r") as f:
            content = f.read()

        if not content.strip():
            return []

        data = json.loads(content)
        return data.get(series_key, [])

    except Exception:
        return []
    # try:
    #     with open(STRADDLE_HISTORY_FILE, "r") as f:
    #         data = json.load(f)
    #     return data.get(series_key, [])
    # except Exception:
    #     return []
 
def fmt(val, decimals=2):
    if val is None:            return "—"
    if isinstance(val, float): return f"{val:.{decimals}f}"
    if isinstance(val, int):   return str(val)
    return str(val)
 
def fmt_k(val):
    if val is None: return "—"
    try:   return f"{int(val):,}"
    except: return str(val)
 
def fmt_price(val):
    if val is None: return "—"
    try:   return f"{float(val):,.2f}"
    except: return str(val)
 
def sfmt(v):
    if v is None: return "—"
    try: return f"{float(v):,.2f}"
    except: return "—"
 
def gfmt(v, decimals=4):
    """Format a greek value; returns '—' for None."""
    if v is None: return "—"
    try: return f"{float(v):.{decimals}f}"
    except: return "—"
 
 
# ─── Pandas styler helpers ─────────────────────────────────────────────────────
def style_options_table(df, atm_strike):
    styles = []
    for i, row in df.iterrows():
        if row["_strike_raw"] == atm_strike:
            s = ["background-color:#26200a; color:#f5d020; font-weight:bold"] * len(df.columns)
        elif i % 2 == 0:
            s = ["background-color:#0d1624; color:#dde4f0"] * len(df.columns)
        else:
            s = ["background-color:#0a1018; color:#dde4f0"] * len(df.columns)
        styles.append(s)
    return pd.DataFrame(styles, index=df.index, columns=df.columns)
 
def style_otm_table(df):
    styles = []
    for i, row in df.iterrows():
        if row["_is_mid"]:
            s = ["background-color:#112440; color:#90c8f0; font-weight:bold"] * (len(df.columns) - 1)
            s += ["background-color:#112440; color:#f0c040; font-weight:bold"]
        else:
            s = ["background-color:#0c1828; color:#6880a0"] * len(df.columns)
        styles.append(s)
    return pd.DataFrame(styles, index=df.index, columns=df.columns)
 
TABLE_STYLES = [
    {"selector": "th", "props": [
        ("background-color", "#0c1c38 !important"),
        ("color", "#e8f0ff !important"),
        ("font-weight", "700"),
        ("text-align", "center"),
        ("font-family", "JetBrains Mono,monospace"),
        ("font-size", "13px"),
        ("padding", "4px 5px"),
        ("border-bottom", "1px solid #1a2f55"),
    ]},
    {"selector": "td", "props": [
        ("text-align","center"), ("font-family","JetBrains Mono,monospace"),
        ("font-size","12px"), ("padding","4px 5px"),
        ("border-bottom","1px solid #0d1624"),
    ]},
    {"selector": "table", "props": [("width","100%"), ("border-collapse","collapse")]},
]
 
OTM_TABLE_STYLES = [
    {"selector": "th", "props": [
        ("background-color", "#0c1c38 !important"),
        ("color", "#e8f0ff !important"),
        ("font-weight", "700"),
        ("text-align", "center"),
        ("font-family", "JetBrains Mono,monospace"),
        ("font-size", "12px"),
        ("padding", "3px 4px"),
    ]},
    {"selector": "td", "props": [
        ("text-align","center"), ("font-family","JetBrains Mono,monospace"),
        ("font-size","11px"), ("padding","3px 4px"),
        ("border-bottom","1px solid #0a1420"),
    ]},
    {"selector": "table", "props": [("width","100%"), ("border-collapse","collapse")]},
]
 
 
# ─── Ticker bar ───────────────────────────────────────────────────────────────
def build_ticker_bar_html(ticker_bar):
    """Build the ticker bar HTML string (pure function, no st calls)."""
    def item_html(label, info, show_ohlc=True):
        spot = info.get("spot")
        pct  = info.get("pct_change")
        o    = info.get("open")
        h    = info.get("high")
        l    = info.get("low")
        pc   = info.get("day_prev_close")
        ltp_str = fmt_price(spot)
        abs_chg = round(spot - pc, 2) if isinstance(spot, (int, float)) and isinstance(pc, (int, float)) else None

        if pct is None:
            chg_html = '<span class="pct-na">— %</span>' if show_ohlc else ""
        elif pct >= 0:
            abs_str  = f"+{abs_chg:,.2f} " if abs_chg is not None else ""
            chg_html = f'<span class="pct-up">▲ {abs_str}({pct:+.2f}%)</span>' if show_ohlc else ""
        else:
            abs_str  = f"{abs_chg:,.2f} " if abs_chg is not None else ""
            chg_html = f'<span class="pct-down">▼ {abs_str}({pct:.2f}%)</span>' if show_ohlc else ""

        ohlc_html = (
            f'<div class="ohlc-row">'
            f'<span><span class="ohlc-lbl">O </span><span class="ohlc-val-open">{fmt_price(o)}</span></span>'
            f'<span><span class="ohlc-lbl">H </span><span class="ohlc-val-high">{fmt_price(h)}</span></span>'
            f'<span><span class="ohlc-lbl">L </span><span class="ohlc-val-low">{fmt_price(l)}</span></span>'
            f'<span><span class="ohlc-lbl">PC </span><span class="ohlc-val-pc">{fmt_price(pc)}</span></span>'
            f'</div>'
        ) if show_ohlc else ""
        return (
            f'<div class="ticker-item">'
            f'<span class="ticker-name">{label}</span>'
            f'<span class="ticker-ltp">{ltp_str}</span>'
            f'<div class="ticker-meta">{chg_html}</div>'
            f'{ohlc_html}'
            f'</div>'
        )

    return (
        f'<div class="ticker-bar">'
        f'{item_html("NIFTY 50",   ticker_bar.get("nifty",     {}))}'
        f'{item_html("SENSEX",      ticker_bar.get("sensex",    {}))}'
        f'{item_html("BANK NIFTY", ticker_bar.get("banknifty", {}))}'
        f'{item_html("INDIA VIX",  ticker_bar.get("indiavix",  {}), show_ohlc=False)}'
        f'</div>'
    )


@st.fragment(run_every=1)
def ticker_fragment():
    """
    Injects the ticker bar directly into the parent window's <body>,
    completely outside Streamlit's React tree — zero flicker on rerun.
    """
    import streamlit.components.v1 as components

    data, _ = load_data()
    if not data:
        return

    ticker_bar = data.get("ticker_bar", {})
    html       = build_ticker_bar_html(ticker_bar)

    # Escape backticks and backslashes so the string is safe inside a JS template literal
    js_safe = html.replace("\\", "\\\\").replace("`", "\\`")

    components.html(
        f"""
        <script>
        (function() {{
            var bar = window.parent.document.getElementById('__nifty_ticker__');
            if (!bar) {{
                bar = window.parent.document.createElement('div');
                bar.id = '__nifty_ticker__';
                window.parent.document.body.prepend(bar);
            }}
            bar.innerHTML = `{js_safe}`;
        }})();
        </script>
        """,
        height=0,
        scrolling=False,
    )


def render_ticker_bar(ticker_bar):
    """Render the ticker bar using a stable st.empty() placeholder to prevent flicker."""
    new_html = build_ticker_bar_html(ticker_bar)

    # Only update the DOM when the HTML actually changes (avoids flicker on identical data)
    if "ticker_bar_html" not in st.session_state:
        st.session_state.ticker_bar_html = ""

    if "ticker_placeholder" not in st.session_state:
        st.session_state.ticker_placeholder = st.empty()

    if new_html != st.session_state.ticker_bar_html:
        st.session_state.ticker_bar_html = new_html
        st.session_state.ticker_placeholder.markdown(new_html, unsafe_allow_html=True)
    else:
        # Re-render with same HTML to keep placeholder alive across reruns
        st.session_state.ticker_placeholder.markdown(new_html, unsafe_allow_html=True)


# ─── Straddle OHLC bar ────────────────────────────────────────────────────────
def render_straddle_bar(s):
    st.markdown(
        f'<div class="straddle-bar">'
        f'<span class="straddle-lbl">Straddle</span>'
        f'<span class="straddle-ltp-val">{sfmt(s.get("ltp"))}</span>'
        f'<div class="straddle-divider"></div>'
        f'<div class="s-item"><span class="s-key">O&nbsp;</span><span class="s-val s-open">{sfmt(s.get("open"))}</span></div>'
        f'<div class="straddle-divider"></div>'
        f'<div class="s-item"><span class="s-key">H&nbsp;</span><span class="s-val s-high">{sfmt(s.get("high"))}</span></div>'
        f'<div class="straddle-divider"></div>'
        f'<div class="s-item"><span class="s-key">L&nbsp;</span><span class="s-val s-low">{sfmt(s.get("low"))}</span></div>'
        f'<div class="straddle-divider"></div>'
        f'<div class="s-item"><span class="s-key">PC&nbsp;</span><span class="s-val s-pc">{sfmt(s.get("prev_close"))}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
 
 
# ─── Info row (spot / fut / syn fut) ─────────────────────────────────────────
def render_info_row(state):
    st.markdown(
        f'<div class="info-row">'
        f'<span class="info-item"><span class="info-lbl">Spot</span>'
        f'<span class="info-val">{fmt_price(state.get("spot_close"))}</span></span>'
        f'<span class="info-sep">·</span>'
        f'<span class="info-item"><span class="info-lbl">Fut</span>'
        f'<span class="info-val fut-val">{fmt_price(state.get("fut_close"))}</span></span>'
        f'<span class="info-sep">·</span>'
        f'<span class="info-item"><span class="info-lbl">Syn Fut</span>'
        f'<span class="info-val syn-val">{fmt_price(state.get("synthetic_future"))}</span></span>'
        f'<span class="info-time">⏱ {state.get("updated_at","—")}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
 
 
# ─── Greeks panel ─────────────────────────────────────────────────────────────
def render_greeks_panel(panel):
    if panel is None:
        st.markdown(
            '<div class="greeks-panel" style="opacity:0.4;text-align:center;padding:20px 14px;">'
            '<div class="greeks-title">OPTION GREEKS</div>'
            '<div style="font-size:0.72rem;color:#3a5878;margin-top:0px;line-height:1.6;">'
            'Click any strike row<br>in the NIFTY or SENSEX<br>table to view greeks'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    strike = panel.get("strike")
    inst   = panel.get("instrument", "")
    week   = panel.get("week", "")

    ce_g   = panel.get("ce_greeks") or {}
    pe_g   = panel.get("pe_greeks") or {}
    net_g  = panel.get("net_greeks") or {}


    def greek_cells(ce_val, pe_val, net_val, dec=4):
        """Return three <div class='greek-item'> cells: CE / PE / NET."""
        return (
            f'<div class="greek-item">'
            f'<span class="greek-lbl">CE</span>'
            f'<span class="greek-val greek-ce">{gfmt(ce_val, dec)}</span>'
            f'</div>'
            f'<div class="greek-item">'
            f'<span class="greek-lbl">PE</span>'
            f'<span class="greek-val greek-pe">{gfmt(pe_val, dec)}</span>'
            f'</div>'
            f'<div class="greek-item">'
            f'<span class="greek-lbl">NET</span>'
            f'<span class="greek-val greek-net">{gfmt(net_val, dec)}</span>'
            f'</div>'
        )

    html = (
        f'<div class="greeks-panel">'
        f'<div class="greeks-title">'
        f'{inst} &nbsp;{fmt_k(strike)}'
        f'<span style="font-size:0.7rem;color:#5a7aaa;margin-left:8px;">{week.upper()}</span>'
        f'</div>'
        f'<div class="iv-row">'
        f'<div class="iv-badge">'
        f'<span class="iv-lbl">CE&nbsp;IV&nbsp;</span>'
        f'<span class="iv-val greek-ce">{gfmt(ce_iv, 2) if ce_iv is not None else "—"}%</span>'
        f'</div>'
        f'<div class="iv-badge">'
        f'<span class="iv-lbl">PE&nbsp;IV&nbsp;</span>'
        f'<span class="iv-val greek-pe">{gfmt(pe_iv, 2) if pe_iv is not None else "—"}%</span>'
        f'</div>'
        f'</div>'
        f'<div class="iv-row">'
        f'<div class="iv-badge">'
        f'<span class="iv-lbl">CE&nbsp;LTP&nbsp;</span>'
        f'<span class="iv-val greek-ce">{gfmt(ce_ltp, 2)}</span>'
        f'</div>'
        f'<div class="iv-badge">'
        f'<span class="iv-lbl">PE&nbsp;LTP&nbsp;</span>'
        f'<span class="iv-val greek-pe">{gfmt(pe_ltp, 2)}</span>'
        f'</div>'
        f'</div>'
        f'<div class="greeks-grid" style="margin-bottom:4px;">'
        f'<div class="greeks-col-hdr" style="color:#22dd88;">CALL</div>'
        f'<div class="greeks-col-hdr" style="color:#ee5555;">PUT</div>'
        f'<div class="greeks-col-hdr" style="color:#f0c040;">NET</div>'
        f'</div>'
        f'<div class="greeks-subtitle" style="text-align:center;">DELTA &nbsp;Δ</div>'
        f'<div class="greeks-grid">'
        f'{greek_cells(ce_g.get("delta"), pe_g.get("delta"), net_g.get("delta"), 4)}'
        f'</div>'
        f'<div class="greeks-subtitle" style="text-align:center;">GAMMA &nbsp;Γ</div>'
        f'<div class="greeks-grid">'
        f'{greek_cells(ce_g.get("gamma"), pe_g.get("gamma"), net_g.get("gamma"), 6)}'
        f'</div>'
        f'<div class="greeks-subtitle" style="text-align:center;">THETA &nbsp;Θ &nbsp;/ day</div>'
        f'<div class="greeks-grid">'
        f'{greek_cells(ce_g.get("theta"), pe_g.get("theta"), net_g.get("theta"), 2)}'
        f'</div>'
        f'<div class="greeks-subtitle" style="text-align:center;">VEGA &nbsp;V &nbsp;/ 1%</div>'
        f'<div class="greeks-grid">'
        f'{greek_cells(ce_g.get("vega"), pe_g.get("vega"), net_g.get("vega"), 2)}'
        f'</div>'
        f'<div class="greeks-subtitle" style="text-align:center;">RHO &nbsp;ρ &nbsp;/ 1%</div>'
        f'<div class="greeks-grid">'
        f'{greek_cells(ce_g.get("rho"), pe_g.get("rho"), net_g.get("rho"), 4)}'
        f'</div>'
        f'<div class="greeks-close-hint">auto-refreshes · click another strike to switch</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
    
def render_greeks_table(state, name, week, strike_key):
    rows = state.get(f"options_rows_{week}", [])
    if not rows:
        return

    strike_options = [r["strike"] for r in rows]
    atm_strike     = state.get("atm_strike")

    # ── Strike selector ───────────────────────────────────────────────────────
    col_sel, col_lbl = st.columns([1.6, 2.4])
    with col_sel:
        selected_strike = st.selectbox(
            "Strike",
            options=[None] + strike_options,
            index=0,
            format_func=lambda x: "— select —" if x is None
                else f"{int(x):,}" + (" ★ ATM" if x == atm_strike else ""),
            key=strike_key,
            label_visibility="collapsed",
        )
    with col_lbl:
        label_str = f"{int(selected_strike):,}" if selected_strike else "select a strike"
        st.markdown(
            f'<div style="font-size:0.68rem;color:#5a7aaa;letter-spacing:0.12em;'
            f'text-transform:uppercase;padding-top:8px;">'
            f'Greeks · {name} {week.upper()} · {label_str}</div>',
            unsafe_allow_html=True,
        )

    # ── Build records — HORIZONTAL: 2 data rows (CE, PE), columns = greeks ───
    if selected_strike is None:
        df_g = pd.DataFrame([
            {"":  "CE", "Delta": "—", "Gamma": "—", "Theta": "—", "Vega": "—", "Rho": "—"},
            {"":  "PE", "Delta": "—", "Gamma": "—", "Theta": "—", "Vega": "—", "Rho": "—"},
        ])
    else:
        matched = next((r for r in rows if r["strike"] == selected_strike), None)
        if matched is None:
            return
        ce_g  = matched.get("ce_greeks")  or {}
        pe_g  = matched.get("pe_greeks")  or {}
        df_g = pd.DataFrame([
            {
                "":       "CE",
                
                "Delta":  gfmt(ce_g.get("delta"),       4),
                "Gamma":  gfmt(ce_g.get("gamma"),       6),
                "Theta":  gfmt(ce_g.get("theta"),       2),
                "Vega":   gfmt(ce_g.get("vega"),        2),
                "Rho":    gfmt(ce_g.get("rho"),         4),
            },
            {
                "":       "PE",
                
                "Delta":  gfmt(pe_g.get("delta"),       4),
                "Gamma":  gfmt(pe_g.get("gamma"),       6),
                "Theta":  gfmt(pe_g.get("theta"),       2),
                "Vega":   gfmt(pe_g.get("vega"),        2),
                "Rho":    gfmt(pe_g.get("rho"),         4),
            },
            {
                "":       "NET",
                
                "Delta":  gfmt(ce_g.get("delta")+pe_g.get("delta"),       4),
                "Gamma":  gfmt(ce_g.get("gamma")+pe_g.get("gamma"),       6),
                "Theta":  gfmt(ce_g.get("theta")+pe_g.get("theta"),       2),
                "Vega":   gfmt(ce_g.get("vega")+pe_g.get("vega"),        2),
                "Rho":    gfmt(ce_g.get("rho")+pe_g.get("rho"),         4),
            },
        ])

    GREEKS_TABLE_STYLES = [
        {"selector": "th", "props": [
            ("background-color", "#0c1c38 !important"),
            ("color", "#e8f0ff !important"),
            ("font-weight", "700"),
            ("text-align", "center"),
        ]},
        {"selector": "td", "props": [
            ("text-align", "center"),
            ("font-family", "JetBrains Mono,monospace"),
            ("font-size", "12px"),
            ("padding", "6px 8px"),
            ("border-bottom", "1px solid #0d1624"),
        ]},
        {"selector": "td:first-child", "props": [
            ("font-weight", "700"),
            ("font-size", "12px"),
            ("letter-spacing", "0.08em"),
            ("padding", "6px 10px"),
        ]},
        
        {"selector": "table", "props": [
            ("width", "100%"),
            ("border-collapse", "collapse"),
        ]},
    ]

    def style_greeks_horizontal(df):
        print(df)
        styles = []
        for i, row in df.iterrows():
            is_ce = row[""]
            row_type = row[""]
            if row_type == "CE":    
                row_color  = "#22dd88"
            if row_type == "PE":
                row_color = "#ee5555"
            else:
                row_color = "#22dd88"
            label_style = f"background-color:#070f1e; color:{row_color}; font-weight:700;"
            cell_style  = f"background-color:{'#0d1624' if is_ce else '#0a1018'}; color:{row_color}; font-weight:600;"
            styles.append([label_style] + [cell_style] * (len(df.columns) - 1))
        return pd.DataFrame(styles, index=df.index, columns=df.columns)

    styled_g = (
        df_g.style
        .apply(lambda _: style_greeks_horizontal(df_g), axis=None)
        .hide(axis="index")
        .set_table_styles(GREEKS_TABLE_STYLES)
    )

    st.table(
        styled_g   # exactly 2 data rows + header
    )

@st.dialog("📊 Option Greeks")
def show_greeks_dialog():
    # Mark that the dialog is open this rerun so we can detect X click next rerun
    st.session_state.dialog_was_open = True
    panel = st.session_state.get("greeks_panel")
    render_greeks_panel(panel)
 
 
# ─── Options block (one instrument, one expiry) ───────────────────────────────
def render_options_block(state, name, week, is_w2=False):
    atm_strike = state.get("atm_strike")
    expiry_lbl = state.get("expiry_week1" if week == "w1" else "expiry_week2", "—")
    hdr_class  = "sec-hdr-w2" if is_w2 else "sec-hdr"
 
    st.markdown(
        f'<div class="{hdr_class}">{name} '
        f'<span style="font-size:0.9rem;color:#a0b8d0">EXP: {expiry_lbl}</span></div>',
        unsafe_allow_html=True,
    )
 
    render_straddle_bar(state.get(f"straddle_ohlc_{week}", {}))
 
    # Info row once per instrument — only on the w1 block to avoid repetition
    if not is_w2:
        render_info_row(state)
 
    rows = state.get(f"options_rows_{week}", [])
    if not rows:
        ref = state.get("spot_close") or state.get("fut_close")
        st.warning(f"⏳ No data — ATM={atm_strike}, Ref={fmt_price(ref)}")
        return
 
    records = [
        {
            "_strike_raw": r["strike"],
            "Strike":      fmt_k(r["strike"]) + (" ★" if r["is_atm"] else ""),
            "CE":          fmt(r["ce"]),
            "CE_IV":       fmt(r["ce_iv"]),
            "PE":          fmt(r["pe"]),
            "PE_IV":       fmt(r["pe_iv"]),
            "Sum":         fmt(r["sum"]),
        }
        for r in rows
    ]
    df = pd.DataFrame(records)
    display_cols = ["Strike", "CE", "CE_IV", "PE", "PE_IV", "Sum"]
 
    styled = (
        df[display_cols]
        .style
        .apply(lambda _: style_options_table(df, atm_strike)[display_cols], axis=None)
        .hide(axis="index")
        .set_table_styles(TABLE_STYLES)
    )
 
    # ── Row selection — clicking a row populates the Greeks panel ────────────
    sel_key = f"sel_{name}_{week}"
    event = st.table(
        styled,
       
    )
 
 
# ─── Strangle OHLC bar ───────────────────────────────────────────────────────
def render_strangle_ohlc_bar(s):
    """Render the OHLC bar for a specific strangle (one OTM level)."""
    st.markdown(
        f'<div class="straddle-bar">'
        f'<span class="straddle-ltp-val">{sfmt(s.get("ltp"))}</span>'
        f'<div class="straddle-divider"></div>'
        f'<div class="s-item"><span class="s-key">O&nbsp;</span><span class="s-val s-open">{sfmt(s.get("open"))}</span></div>'
        f'<div class="straddle-divider"></div>'
        f'<div class="s-item"><span class="s-key">H&nbsp;</span><span class="s-val s-high">{sfmt(s.get("high"))}</span></div>'
        f'<div class="straddle-divider"></div>'
        f'<div class="s-item"><span class="s-key">L&nbsp;</span><span class="s-val s-low">{sfmt(s.get("low"))}</span></div>'
        f'<div class="straddle-divider"></div>'
        f'<div class="s-item"><span class="s-key">PC&nbsp;</span><span class="s-val s-pc">{sfmt(s.get("prev_close"))}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
 
 
# ─── OTM strangle block (one instrument, one expiry) ─────────────────────────
def render_otm_block(state, name, otm_level_key, week, is_w2=False, target_height=470):
    atm_strike = state.get("atm_strike")
    expiry_lbl = state.get("expiry_week1" if week == "w1" else "expiry_week2", "—")
    hdr_class  = "otm-hdr-w2" if is_w2 else "otm-hdr"

    st.markdown(
        f'<div class="{hdr_class}">Strangle · {expiry_lbl} — ATM: {fmt_k(atm_strike)}</div>',
        unsafe_allow_html=True,
    )

    level = st.selectbox(
        "OTM Level",
        options=list(range(1, OTM_LEVELS + 1)),
        format_func=lambda x: f"OTM {x}",
        key=otm_level_key,
        label_visibility="collapsed",
    )

    strangle_ohlc_all = state.get(f"strangle_ohlc_{week}", {})
    strangle_ohlc_lvl = strangle_ohlc_all.get(str(level), {})
    render_strangle_ohlc_bar(strangle_ohlc_lvl)

    rows = state.get(f"otm_levels_{week}", {}).get(str(level), [])
    if not rows:
        st.warning("⏳ No OTM data yet")
        return

    records = [
        {
            "_is_mid":   r.get("is_mid", False),
            "CE Strike": fmt_k(r["ce_strike"]),
            "CE LTP":    fmt(r["ce_ltp"]),
            "PE Strike": fmt_k(r["pe_strike"]),
            "PE LTP":    fmt(r["pe_ltp"]),
            "Sum":       fmt(r["sum"]),
        }
        for r in rows
    ]
    df = pd.DataFrame(records)
    display_cols = ["CE Strike", "CE LTP", "PE Strike", "PE LTP", "Sum"]

    styled = (
        df[display_cols]
        .style
        .apply(lambda _: style_otm_table(df)[display_cols], axis=None)
        .hide(axis="index")
        .set_table_styles(OTM_TABLE_STYLES)
    )

    # ── Header ~28px + selectbox ~38px + OHLC bar ~36px + padding ~10px ──────
    OVERHEAD = 112
    natural_height  = (len(records) + 1) * 35 + 3
    remaining_height = target_height - OVERHEAD
    table_height     = max(natural_height, remaining_height)

    st.table(
        styled
    )


# ─── Straddle chart ───────────────────────────────────────────────────────────
def render_straddle_chart(series_key: str, label: str):
    """
    Render an ATM straddle price vs time line chart for one index (w1).

    Reads the unified series from straddle_history.json — each point has:
        {time: "HH:MM:SS", price: float, atm_strike: int}

    The series is continuous across ATM changes (feed.py tracks which strike
    was live at each moment).  ATM change moments are shown as annotations
    below the chart.
    """
    points = load_straddle_chart_series(series_key)

    if not points:
        st.info(f"No {label} data yet — waiting for feed…")
        return

    # Build DataFrame
    df = pd.DataFrame(points)
    df["time"] = pd.to_datetime(df["time"], format="%H:%M:%S", errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time")

    # ── Filter: only show data from 09:15:00 onwards ──────────────────────────
    market_open = df["time"].dt.normalize() + pd.Timedelta(hours=9, minutes=15)
    df = df[df["time"] >= market_open]

    if df.empty:
        st.info(f"No valid {label} data yet")
        return

    # ── Stats ─────────────────────────────────────────────────────────────────
    latest     = df["price"].iloc[-1]
    open_price = df["price"].iloc[0]
    high_price = df["price"].max()
    low_price  = df["price"].min()
    chg        = round(latest - open_price, 2)
    chg_pct    = round(chg / open_price * 100, 2) if open_price else 0
    cur_strike = df["atm_strike"].iloc[-1]

    sign   = "+" if chg >= 0 else ""
    colour = "green" if chg >= 0 else "red"

    # Current ATM strike badge + stats row
    stats_html = (
        f'<div style="display:flex;gap:20px;align-items:baseline;flex-wrap:wrap;'
        f'font-family:JetBrains Mono,monospace;font-size:0.78rem;margin-bottom:6px;">'
        f'<span style="color:#f0c040;font-weight:700;font-size:0.9rem;">'
        f'ATM {int(cur_strike):,}</span>'
        f'<span style="color:#60a5fa;">LTP {latest:,.2f}</span>'
        f'<span style="color:#f0c040;">O {open_price:,.2f}</span>'
        f'<span style="color:#22dd88;">H {high_price:,.2f}</span>'
        f'<span style="color:#ee5555;">L {low_price:,.2f}</span>'
        f'<span style="color:{"#22dd88" if chg >= 0 else "#ee5555"};">'
        f'{sign}{chg:,.2f} ({sign}{chg_pct:.2f}%)</span>'
        f'</div>'
    )
    st.markdown(stats_html, unsafe_allow_html=True)

  
    import plotly.graph_objects as go

    def plot_straddle(df, title):
        if df.empty:
            st.write("No data")
            return

        has_spot = "spot" in df.columns and df["spot"].notna().any()

        # ── ATM price axis range ──────────────────────────────────────────────
        p_min = df["price"].min()
        p_max = df["price"].max()
        p_pad = max((p_max - p_min) * 0.12, 1)

        fig = go.Figure()

        # ── Trace 1: ATM Straddle Price (right Y-axis) ────────────────────────
        fig.add_trace(go.Scatter(
            x=df["time"],
            y=df["price"],
            mode="lines",
            name="ATM Price",
            yaxis="y2",
            line=dict(color="#3b82f6", width=2),
            hovertemplate="%{x|%H:%M:%S}<br>ATM Price: %{y:,.2f}<extra></extra>",
        ))

        # ── Trace 2: Spot Price (left Y-axis) ────────────────────────────────
        if has_spot:
            s_min = df["spot"].min()
            s_max = df["spot"].max()
            s_pad = max((s_max - s_min) * 0.12, 1)

            

            # Prev-close dashed line (open spot) on left axis
            open_spot = df["spot"].iloc[0]
            fig.add_hline(
                y=open_spot,
                line=dict(color="#6b7280", width=1, dash="dash"),
                annotation_text=f"PC {open_spot:,.2f}",
                annotation_position="right",
                annotation_font=dict(color="#9ca3af", size=10),
            )

            yaxis1 = dict(
                title=dict(text="Spot Price", font=dict(color="#fb923c", size=11)),
                tickfont=dict(color="#fb923c", size=10),
                range=[s_min - s_pad, s_max + s_pad],
                showgrid=True,
                gridcolor="#1e3a4a",
                gridwidth=1,
                zeroline=False,
                tickformat=",",
                side="left",
            )
        else:
            yaxis1 = dict(visible=False)

        fig.update_layout(
            height=370,
            margin=dict(l=60, r=70, t=28, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0d1b2a",
            font=dict(color="#cbd5e1", size=10),
            hovermode="x unified",
            dragmode="pan",
            uirevision="fixed",
            legend=dict(
                orientation="h",
                x=0, y=1.08,
                font=dict(size=10),
                bgcolor="rgba(0,0,0,0)",
            ),

            # ── Left Y-axis: Spot ─────────────────────────────────────────────
            yaxis=yaxis1,

            # ── Right Y-axis: ATM Price ───────────────────────────────────────
            yaxis2=dict(
                title=dict(text="ATM Price", font=dict(color="#f87171", size=11)),
                tickfont=dict(color="#3b82f6", size=10),
                range=[p_min - p_pad, p_max + p_pad],
                showgrid=False,
                zeroline=False,
                side="right",
                tickformat=",",
                overlaying="y",
            ),

            xaxis=dict(
                showgrid=False,
                tickformat="%H:%M",
                tickfont=dict(size=10),
                rangeslider=dict(visible=False),
            ),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"chart_{series_key}",
            config={"scrollZoom": True, "displayModeBar": False},
        )

    plot_straddle(df, label)

    # ── ATM change annotations ────────────────────────────────────────────────
    # Find rows where atm_strike changed from the previous row
    # atm_series = df["atm_strike"].tolist()
    # time_series = df["time"].dt.strftime("%H:%M:%S").tolist()
    # changes = []
    # for i in range(1, len(atm_series)):
    #     if atm_series[i] != atm_series[i - 1]:
    #         changes.append({
    #             "time":  time_series[i],
    #             "from":  atm_series[i - 1],
    #             "to":    atm_series[i],
    #         })

    # if changes:
    #     tags_html = "".join(
    #         f'<span class="atm-change-tag">⇄ {c["time"]} &nbsp;'
    #         f'{int(c["from"]):,} → {int(c["to"]):,}</span>'
    #         for c in changes
    #     )
    #     st.markdown(
    #         f'<div style="margin-top:4px;font-size:0.7rem;color:#64748b;">'
    #         f'<span style="color:#5a7aaa;margin-right:6px;">ATM changes:</span>'
    #         f'{tags_html}</div>',
    #         unsafe_allow_html=True,
    #     )
    # else:
    #     st.markdown(
    #         '<div style="font-size:0.7rem;color:#334155;margin-top:2px;">'
    #         'No ATM changes recorded today</div>',
    #         unsafe_allow_html=True,
    #     )


# ─── Load + render ────────────────────────────────────────────────────────────
# ── Ticker bar: rendered as a @st.fragment(run_every=1) so it refreshes
#    independently and the rest of the page DOM is never torn down for it.
ticker_fragment()

data, err = load_data()

# ── Refresh greeks panel with latest live data BEFORE rendering ───────────────
if data and st.session_state.greeks_panel is not None and not st.session_state.pause_updates:
    gp            = st.session_state.greeks_panel
    nifty_st      = data.get("nifty",     {})
    sensex_st     = data.get("sensex",    {})
    banknifty_st  = data.get("banknifty", {})
    instrument    = gp.get("instrument")
    if instrument == "NIFTY":
        inst_state = nifty_st
    elif instrument == "SENSEX":
        inst_state = sensex_st
    else:
        inst_state = banknifty_st
    week_key   = gp.get("week", "w1")
    strike_val = gp.get("strike")
    for r in inst_state.get(f"options_rows_{week_key}", []):
        if r["strike"] == strike_val:
            st.session_state.greeks_panel = {
                "strike":     r["strike"],
                "instrument": gp["instrument"],
                "week":       week_key,
                "ce":         r.get("ce"),
                "pe":         r.get("pe"),
                "ce_iv":      r.get("ce_iv"),
                "pe_iv":      r.get("pe_iv"),
                "ce_greeks":  r.get("ce_greeks"),
                "pe_greeks":  r.get("pe_greeks"),
                "net_greeks": r.get("net_greeks"),
            }
            break


# ── Header row: title | status badge ─────────────────────────────────────────
tc1, tc2 = st.columns([3, 1])
with tc1:
    st.markdown('<div class="main-title">NIFTY, SENSEX &amp; BANK NIFTY LIVE OPTIONS</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Real-time · 1-second refresh · Spot price</div>', unsafe_allow_html=True)
with tc2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<span class="status-live">⬤ Live</span>' if data
        else '<span class="status-wait">⬤ Waiting</span>',
        unsafe_allow_html=True,
    )
 
if err:
    st.error(f"⚠️ {err}")
    time.sleep(2)
    st.rerun()
elif data is None:
    time.sleep(0.5)
    st.rerun()
else:
    ticker_bar      = data.get("ticker_bar",   {})
    nifty_state     = data.get("nifty",        {})
    sensex_state    = data.get("sensex",       {})
    banknifty_state = data.get("banknifty",    {})
 
    # ─────────────────────────────────────────────────────────────────────────
    # Layout: 5 rows, each = [ Table | Strangle | Chart ]
    # Row 1 — NIFTY   current expiry (w1)
    # Row 2 — SENSEX  current expiry (w1)
    # Row 3 — BANK NIFTY current month (w1)
    # Row 4 — NIFTY   next expiry    (w2)
    # Row 5 — SENSEX  next expiry    (w2)
    # ─────────────────────────────────────────────────────────────────────────

    _ROWS = [
        # (state,            name,          week, is_w2, series_key,        label_color)
        (nifty_state,     "NIFTY",       "w1", False, "nifty_w1",     "#60a5fa"),
        (sensex_state,    "SENSEX",      "w1", False, "sensex_w1",    "#c084fc"),
        (banknifty_state, "BANK NIFTY",  "w1", False, "banknifty_w1", "#fb923c"),
        (nifty_state,     "NIFTY",       "w2", True,  "nifty_w2",     "#60a5fa"),
        (sensex_state,    "SENSEX",      "w2", True,  "sensex_w2",    "#c084fc"),
    ]

    for idx, (state, name, week, is_w2, series_key, lbl_color) in enumerate(_ROWS):

        if idx > 0:
            st.markdown(
                "<hr style='border:1px solid #1a2f40; margin:18px 0 10px 0'>",
                unsafe_allow_html=True,
            )

        if name == "BANK NIFTY":
            row_label = "BANK NIFTY — Current Month Expiry"
        elif is_w2:
            row_label = f"{name} — Next Expiry"
        else:
            row_label = f"{name} — Current Expiry"

        st.markdown(
            f'<div style="font-family:Bebas Neue,sans-serif;font-size:1.15rem;'
            f'letter-spacing:0.1em;color:{lbl_color};margin-bottom:0px;">'
            f'{row_label}</div>',
            unsafe_allow_html=True,
        )

        otm_key    = f"otm_{name.lower().replace(' ', '')}_{week}_{idx}"
        strike_key = f"greeks_strike_{name}_{week}"

        col_left, col_right = st.columns([2.2, 3.8], gap="small")

        with col_left:
            render_options_block(state, name, week, is_w2=is_w2)

        with col_right:
            # OTM + Chart side by side at the top
            col_otm, col_chart = st.columns([2, 2], gap="small")
            with col_otm:
                render_otm_block(state, name, otm_key, week, is_w2=is_w2, target_height=340)
                render_greeks_table(state, name, week, strike_key)
            with col_chart:
                render_straddle_chart(series_key, f"{name} {week.upper()}")

            # Greeks table immediately below, full width of col_right
            # st.markdown(
            #     '<div style="margin-top:-0px;">',
            #     unsafe_allow_html=True,
            # )
            # render_greeks_table(state, name, week, strike_key)
            # st.markdown('</div>', unsafe_allow_html=True)

    


# ── Greeks dialog ─────────────────────────────────────────────────────────────
if st.session_state.get("show_greeks_dialog", False) and st.session_state.get("greeks_panel") is not None:
    show_greeks_dialog()

if st.session_state.pause_updates:
    remaining = st.session_state.pause_until - time.time()

    if remaining > 0:
        st.stop()
    else:
        st.session_state.pause_updates = False
        st.session_state.pause_until = 0
        time.sleep(1)
        st.rerun()

else:
    # Normal 1 sec refresh
    time.sleep(1)
    st.rerun()



