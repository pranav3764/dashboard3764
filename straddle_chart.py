
import os
import json
import threading
from datetime import datetime, timedelta, timezone
 
# ── Config ────────────────────────────────────────────────────────────────────
CHART_INTERVAL_SECONDS = 5        # minimum gap between recorded points
MAX_POINTS_PER_SERIES  = 5000     # safety cap (~7 h at 5-second resolution)
 
IST = timezone(timedelta(hours=5, minutes=30))
 
# ── Module-level state ────────────────────────────────────────────────────────
_chart_file   = None              # set by init_chart_history()
_chart_data   = {}                # in-memory mirror of the JSON file
_chart_lock   = threading.Lock()
_last_written = {}                # key → last write timestamp (float)
 
 
# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
 
def init_chart_history(filepath: str) -> None:
    """
    Call once at startup (inside main(), after load_prev_close()).
    Loads today's existing data from disk or creates a fresh structure.
    """
    global _chart_file, _chart_data
 
    _chart_file = filepath
    today = _today_str()
 
    try:
        with open(filepath, "r") as f:
            loaded = json.load(f)
        if loaded.get("date") == today:
            _chart_data = loaded
            counts = {k: len(v) for k, v in loaded.items() if k != "date"}
            print(f"📈 Chart history loaded — {counts}")
        else:
            print(f"📈 Chart history date mismatch ({loaded.get('date')} vs {today}) — resetting")
            _chart_data = _fresh(today)
    except FileNotFoundError:
        print("📈 No chart history file found — starting fresh")
        _chart_data = _fresh(today)
    except Exception as e:
        print(f"⚠️  Chart history load error: {e} — starting fresh")
        _chart_data = _fresh(today)
 
 
def record_chart_point(series_key: str, strike_key: str, price: float) -> None:
    """
    Record one straddle price point for *series_key* (e.g. "nifty_w1").
 
    Parameters
    ──────────
    series_key  : "nifty_w1" or "sensex_w1"
    strike_key  : full key like "nifty_w1_24000"  (used to extract atm_strike)
    price       : combined CE + PE LTP (already a float)
 
    Throttled to at most one point per CHART_INTERVAL_SECONDS.
    Writes to disk atomically after every accepted point.
    """
    if _chart_file is None:
        return  # init_chart_history() not called yet
 
    import time as _time
 
    now_ts = _time.monotonic()
    last   = _last_written.get(series_key, 0.0)
    if now_ts - last < CHART_INTERVAL_SECONDS:
        return  # too soon — skip
 
    # Parse ATM strike from key tail, e.g. "nifty_w1_24000" → 24000
    try:
        atm_strike = int(strike_key.rsplit("_", 1)[-1])
    except (ValueError, IndexError):
        atm_strike = None
 
    now_ist  = datetime.now(IST)
    time_str = now_ist.strftime("%H:%M:%S")
    today    = now_ist.strftime("%Y-%m-%d")
 
    with _chart_lock:
        # Auto-reset on date rollover (shouldn't happen intraday but defensive)
        if _chart_data.get("date") != today:
            _chart_data.clear()
            _chart_data.update(_fresh(today))
 
        series = _chart_data.setdefault(series_key, [])
        series.append({
            "time":       time_str,
            "price":      round(price, 2),
            "atm_strike": atm_strike,
        })
 
        # Trim if over cap
        if len(series) > MAX_POINTS_PER_SERIES:
            _chart_data[series_key] = series[-MAX_POINTS_PER_SERIES:]
 
        _flush_to_disk()
 
    _last_written[series_key] = now_ts
 
 
# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
 
def _today_str() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")
 
 
def _fresh(today: str) -> dict:
    return {"date": today, "nifty_w1": [], "sensex_w1": []}
 
 
def _flush_to_disk() -> None:
    """Atomic write — must be called inside _chart_lock."""
    if not _chart_file:
        return
    try:
        tmp = _chart_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(_chart_data, f)
        os.replace(tmp, _chart_file)
    except Exception as e:
        print(f"⚠️  Chart history write error: {e}")
 