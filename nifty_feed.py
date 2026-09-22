# # instruments.py
# """
# Run this script once before starting feed.py to generate nifty_sensex_instruments.json

# It saves:
#   - Futures (nearest expiry)
#   - options_week1  →  nearest/current-week expiry options
#   - options_week2  →  next-week expiry options

# Usage:
#     python c:\\nifty\\instruments.py
# """

# import os
# import json
# from datetime import datetime
# from kiteconnect import KiteConnect
# from dotenv import load_dotenv

# load_dotenv(dotenv_path=r'C:\Users\Tanav Mehra\Documents\Internship MasterTrust\PROJECTS\Dashboard_1\.env', override=True)

# API_KEY    = os.getenv("KITE_API_KEY")
# TOKEN_FILE = r"C:\Users\Tanav Mehra\Documents\Internship MasterTrust\PROJECTS\Dashboard_1\token_store.json"
# OUT_FILE   = r"C:\Users\Tanav Mehra\Documents\Internship MasterTrust\PROJECTS\Dashboard_1\nifty_sensex_instruments.json"

# # How many strikes around ATM to keep (reduces file size)
# # Set to None to keep all strikes
# STRIKE_FILTER_RANGE = 6000   # keep strikes within ±6000 of a rough ATM
# # Rough ATM estimates just for filtering — doesn't need to be exact
# NIFTY_APPROX_SPOT  = 24000
# SENSEX_APPROX_SPOT = 78000


# def load_token():
#     with open(TOKEN_FILE, "r") as f:
#         return json.load(f)


# def filter_instruments(instruments, symbol_name, exchange):
#     """Return all FUT and OPT contracts for the given symbol."""
#     seg_fut = f"{exchange}-FUT"
#     seg_opt = f"{exchange}-OPT"
#     fut = [i for i in instruments
#            if i["segment"] == seg_fut and i["name"] == symbol_name]
#     opt = [i for i in instruments
#            if i["segment"] == seg_opt and i["name"] == symbol_name]
#     return fut, opt


# def get_nearest_futures(futures_list):
#     """Return the single nearest-expiry futures contract."""
#     if not futures_list:
#         return []
#     sorted_fut = sorted(futures_list, key=lambda x: x["expiry"])
#     nearest_expiry = sorted_fut[0]["expiry"]
#     return [f for f in sorted_fut if f["expiry"] == nearest_expiry]


# def get_two_expiry_options(options_list, approx_spot, strike_range):
#     """
#     Returns (week1_opts, week2_opts):
#       week1 = options for the nearest (current-week) expiry
#       week2 = options for the second-nearest (next-week) expiry

#     Also filters strikes to ±strike_range around approx_spot to keep
#     the JSON file small and subscription count manageable.
#     """
#     if not options_list:
#         return [], []

#     # Get all unique expiries sorted ascending
#     expiries = sorted(set(o["expiry"] for o in options_list))

#     if len(expiries) < 1:
#         return [], []

#     expiry_w1 = expiries[0]
#     expiry_w2 = expiries[1] if len(expiries) > 1 else None

#     def filter_by_expiry_and_strike(exp):
#         if exp is None:
#             return []
#         opts = [o for o in options_list if o["expiry"] == exp]
#         if strike_range and approx_spot:
#             opts = [
#                 o for o in opts
#                 if abs(o["strike"] - approx_spot) <= strike_range
#             ]
#         return opts

#     week1 = filter_by_expiry_and_strike(expiry_w1)
#     week2 = filter_by_expiry_and_strike(expiry_w2)

#     return week1, week2


# def print_summary(name, fut, w1, w2):
#     exp_w1 = w1[0]["expiry"] if w1 else "—"
#     exp_w2 = w2[0]["expiry"] if w2 else "—"
#     print(f"\n{'─'*50}")
#     print(f"  {name}")
#     print(f"{'─'*50}")
#     print(f"  Futures      : {len(fut)} contract(s)  expiry={fut[0]['expiry'] if fut else '—'}")
#     print(f"  Week 1 opts  : {len(w1)} contracts     expiry={exp_w1}")
#     print(f"  Week 2 opts  : {len(w2)} contracts     expiry={exp_w2}")

#     print(f"\n  Sample NIFTY futures tokens:")
#     for f in fut[:3]:
#         print(f"    {f['tradingsymbol']:<30} token={f['instrument_token']}  expiry={f['expiry']}")

#     if w1:
#         print(f"\n  Sample Week1 option tokens (first 4):")
#         for o in w1[:4]:
#             print(f"    {o['tradingsymbol']:<35} token={o['instrument_token']}  strike={o['strike']}  type={o['instrument_type']}")

#     if w2:
#         print(f"\n  Sample Week2 option tokens (first 4):")
#         for o in w2[:4]:
#             print(f"    {o['tradingsymbol']:<35} token={o['instrument_token']}  strike={o['strike']}  type={o['instrument_type']}")


# def main():
#     token_data   = load_token()
#     access_token = token_data["access_token"]

#     kite = KiteConnect(api_key=API_KEY)
#     kite.set_access_token(access_token)

#     print("⬇️  Fetching NFO instruments …")
#     instruments_nfo = kite.instruments("NFO")
#     print(f"    Got {len(instruments_nfo)} NFO instruments")

#     print("⬇️  Fetching BFO instruments …")
#     instruments_bfo = kite.instruments("BFO")
#     print(f"    Got {len(instruments_bfo)} BFO instruments")

#     # ── NIFTY ────────────────────────────────────────────────────────────────
#     nifty_fut_all, nifty_opt_all = filter_instruments(instruments_nfo, "NIFTY", "NFO")
#     nifty_fut  = get_nearest_futures(nifty_fut_all)
#     nifty_w1, nifty_w2 = get_two_expiry_options(
#         nifty_opt_all, NIFTY_APPROX_SPOT, STRIKE_FILTER_RANGE
#     )
#     print_summary("NIFTY", nifty_fut, nifty_w1, nifty_w2)

#     # ── SENSEX ───────────────────────────────────────────────────────────────
#     sensex_fut_all, sensex_opt_all = filter_instruments(instruments_bfo, "SENSEX", "BFO")
#     sensex_fut  = get_nearest_futures(sensex_fut_all)
#     sensex_w1, sensex_w2 = get_two_expiry_options(
#         sensex_opt_all, SENSEX_APPROX_SPOT, STRIKE_FILTER_RANGE
#     )
#     print_summary("SENSEX", sensex_fut, sensex_w1, sensex_w2)

#     # ── Spot token reminder ───────────────────────────────────────────────────
#     print("\n" + "─"*50)
#     print("  Spot tokens (hardcoded in feed.py — no action needed):")
#     print("    NIFTY  50  →  token 256265  (NSE)")
#     print("    SENSEX     →  token 265     (BSE)")
#     print("─"*50)

#     # ── Save ─────────────────────────────────────────────────────────────────
#     payload = {
#         "nifty": {
#             "futures":        nifty_fut,
#             "options_week1":  nifty_w1,
#             "options_week2":  nifty_w2,
#         },
#         "sensex": {
#             "futures":        sensex_fut,
#             "options_week1":  sensex_w1,
#             "options_week2":  sensex_w2,
#         },
#     }

#     with open(OUT_FILE, "w") as f:
#         json.dump(payload, f, indent=2, default=str)

#     total_tokens = (
#         len(nifty_fut) + len(nifty_w1) + len(nifty_w2) +
#         len(sensex_fut) + len(sensex_w1) + len(sensex_w2) +
#         2   # spot tokens
#     )
#     print(f"\n✅ Saved to {OUT_FILE}")
#     print(f"   Total tokens to subscribe: ~{total_tokens} (+ 2 spot tokens)")
#     print("\n▶  Now run:  python c:\\nifty\\feed.py")


# if __name__ == "__main__":
#     main()



# instruments.py
"""
Run this script once before starting feed.py to generate nifty_sensex_instruments.json

It saves:
  - Futures (nearest expiry)
  - options_week1  →  nearest/current-week expiry options
  - options_week2  →  next-week expiry options

Usage:
    python c:\\nifty\\instruments.py
"""

import os
import json
from datetime import datetime
from kiteconnect import KiteConnect
from dotenv import load_dotenv

load_dotenv(dotenv_path=r'C:\Users\Tanav Mehra\Documents\Internship MasterTrust\PROJECTS\Dashboard_1\.env', override=True)

API_KEY    = os.getenv("KITE_API_KEY")
TOKEN_FILE = r"C:\Users\Tanav Mehra\Documents\Internship MasterTrust\PROJECTS\Dashboard_1\token_store.json"
OUT_FILE   = r"C:\Users\Tanav Mehra\Documents\Internship MasterTrust\PROJECTS\Dashboard_1\nifty_sensex_instruments.json"

# How many strikes around ATM to keep (reduces file size)
# Set to None to keep all strikes
STRIKE_FILTER_RANGE = 6000   # keep strikes within ±6000 of a rough ATM
# Rough ATM estimates just for filtering — doesn't need to be exact
NIFTY_APPROX_SPOT     = 24000
SENSEX_APPROX_SPOT    = 78000
BANKNIFTY_APPROX_SPOT = 55000


def load_token():
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)


def filter_instruments(instruments, symbol_name, exchange):
    """Return all FUT and OPT contracts for the given symbol."""
    seg_fut = f"{exchange}-FUT"
    seg_opt = f"{exchange}-OPT"
    fut = [i for i in instruments
           if i["segment"] == seg_fut and i["name"] == symbol_name]
    opt = [i for i in instruments
           if i["segment"] == seg_opt and i["name"] == symbol_name]
    return fut, opt


def get_nearest_futures(futures_list):
    """Return the single nearest-expiry futures contract."""
    if not futures_list:
        return []
    sorted_fut = sorted(futures_list, key=lambda x: x["expiry"])
    nearest_expiry = sorted_fut[0]["expiry"]
    return [f for f in sorted_fut if f["expiry"] == nearest_expiry]


def get_current_month_options(options_list, approx_spot, strike_range):
    """
    Returns options for the current-month expiry only (w1).
    Bank Nifty has weekly expiries — the current-month contract is
    the last Thursday of the current calendar month, which Kite lists
    as the expiry with the highest date still within the current month.
    We pick the LAST expiry of the current calendar month.
    """
    if not options_list:
        return []

    from datetime import date
    today = date.today()
    current_month = today.month
    current_year  = today.year

    # All expiry dates that fall in the current calendar month and are >= today
    expiries_this_month = sorted(set(
        o["expiry"] for o in options_list
        if hasattr(o["expiry"], "month")
           and o["expiry"].month == current_month
           and o["expiry"].year  == current_year
           and o["expiry"] >= today
    ))

    if not expiries_this_month:
        # Fallback: just pick the nearest expiry (handles month-end edge case)
        expiries_this_month = [sorted(set(o["expiry"] for o in options_list))[0]]

    # Current-month contract = last expiry of the current month
    target_expiry = expiries_this_month[-1]

    opts = [o for o in options_list if o["expiry"] == target_expiry]
    if strike_range and approx_spot:
        opts = [o for o in opts if abs(o["strike"] - approx_spot) <= strike_range]
    return opts
    

def get_two_expiry_options(options_list, approx_spot, strike_range):
    """
    Returns (week1_opts, week2_opts):
      week1 = nearest expiry
      week2 = next expiry
    """

    if not options_list:
        return [], []

    expiries = sorted(set(o["expiry"] for o in options_list))

    if len(expiries) < 1:
        return [], []

    expiry_w1 = expiries[0]
    expiry_w2 = expiries[1] if len(expiries) > 1 else None

    def filter_by_expiry_and_strike(exp):
        if exp is None:
            return []
        opts = [o for o in options_list if o["expiry"] == exp]
        if strike_range and approx_spot:
            opts = [
                o for o in opts
                if abs(o["strike"] - approx_spot) <= strike_range
            ]
        return opts

    week1 = filter_by_expiry_and_strike(expiry_w1)
    week2 = filter_by_expiry_and_strike(expiry_w2)

    return week1, week2

def print_summary(name, fut, w1, w2):
    exp_w1 = w1[0]["expiry"] if w1 else "—"
    exp_w2 = w2[0]["expiry"] if w2 else "—"
    print(f"\n{'─'*50}")
    print(f"  {name}")
    print(f"{'─'*50}")
    print(f"  Futures      : {len(fut)} contract(s)  expiry={fut[0]['expiry'] if fut else '—'}")
    print(f"  Week 1 opts  : {len(w1)} contracts     expiry={exp_w1}")
    print(f"  Week 2 opts  : {len(w2)} contracts     expiry={exp_w2}")

    print(f"\n  Sample NIFTY futures tokens:")
    for f in fut[:3]:
        print(f"    {f['tradingsymbol']:<30} token={f['instrument_token']}  expiry={f['expiry']}")

    if w1:
        print(f"\n  Sample Week1 option tokens (first 4):")
        for o in w1[:4]:
            print(f"    {o['tradingsymbol']:<35} token={o['instrument_token']}  strike={o['strike']}  type={o['instrument_type']}")

    if w2:
        print(f"\n  Sample Week2 option tokens (first 4):")
        for o in w2[:4]:
            print(f"    {o['tradingsymbol']:<35} token={o['instrument_token']}  strike={o['strike']}  type={o['instrument_type']}")


def main():
    token_data   = load_token()
    access_token = token_data["access_token"]

    kite = KiteConnect(api_key=API_KEY)
    kite.set_access_token(access_token)

    print("⬇️  Fetching NFO instruments …")
    instruments_nfo = kite.instruments("NFO")
    print(f"    Got {len(instruments_nfo)} NFO instruments")

    print("⬇️  Fetching BFO instruments …")
    instruments_bfo = kite.instruments("BFO")
    print(f"    Got {len(instruments_bfo)} BFO instruments")

    # ── NIFTY ────────────────────────────────────────────────────────────────
    nifty_fut_all, nifty_opt_all = filter_instruments(instruments_nfo, "NIFTY", "NFO")
    nifty_fut  = get_nearest_futures(nifty_fut_all)
    nifty_w1, nifty_w2 = get_two_expiry_options(
        nifty_opt_all, NIFTY_APPROX_SPOT, STRIKE_FILTER_RANGE
    )
    print_summary("NIFTY", nifty_fut, nifty_w1, nifty_w2)

    # ── SENSEX ───────────────────────────────────────────────────────────────
    sensex_fut_all, sensex_opt_all = filter_instruments(instruments_bfo, "SENSEX", "BFO")
    sensex_fut  = get_nearest_futures(sensex_fut_all)
    sensex_w1, sensex_w2 = get_two_expiry_options(
        sensex_opt_all, SENSEX_APPROX_SPOT, STRIKE_FILTER_RANGE
    )
    print_summary("SENSEX", sensex_fut, sensex_w1, sensex_w2)

    # ── BANKNIFTY ─────────────────────────────────────────────────────────────
    banknifty_fut_all, banknifty_opt_all = filter_instruments(instruments_nfo, "BANKNIFTY", "NFO")
    banknifty_fut = get_nearest_futures(banknifty_fut_all)
    banknifty_w1  = get_current_month_options(
        banknifty_opt_all, BANKNIFTY_APPROX_SPOT, STRIKE_FILTER_RANGE
    )

    # Print summary for BANKNIFTY
    exp_w1 = banknifty_w1[0]["expiry"] if banknifty_w1 else "—"
    print(f"\n{'─'*50}")
    print(f"  BANK NIFTY")
    print(f"{'─'*50}")
    print(f"  Futures      : {len(banknifty_fut)} contract(s)  expiry={banknifty_fut[0]['expiry'] if banknifty_fut else '—'}")
    print(f"  Week 1 opts  : {len(banknifty_w1)} contracts     expiry={exp_w1}  (current month)")
    if banknifty_fut:
        print(f"\n  Sample BANKNIFTY futures tokens:")
        for f in banknifty_fut[:3]:
            print(f"    {f['tradingsymbol']:<30} token={f['instrument_token']}  expiry={f['expiry']}")
    if banknifty_w1:
        print(f"\n  Sample Week1 option tokens (first 4):")
        for o in banknifty_w1[:4]:
            print(f"    {o['tradingsymbol']:<35} token={o['instrument_token']}  strike={o['strike']}  type={o['instrument_type']}")
    print("\n" + "─"*50)
    print("  Spot tokens (hardcoded in feed.py — no action needed):")
    print("    NIFTY  50   →  token 256265  (NSE)")
    print("    SENSEX      →  token 265     (BSE)")
    print("    BANK NIFTY  →  token 260105  (NSE)")
    print("─"*50)

    # ── Save ─────────────────────────────────────────────────────────────────
    payload = {
        "nifty": {
            "futures":        nifty_fut,
            "options_week1":  nifty_w1,
            "options_week2":  nifty_w2,
        },
        "sensex": {
            "futures":        sensex_fut,
            "options_week1":  sensex_w1,
            "options_week2":  sensex_w2,
        },
        "banknifty": {
            "futures":        banknifty_fut,
            "options_week1":  banknifty_w1,
        },
    }

    with open(OUT_FILE, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    total_tokens = (
        len(nifty_fut)     + len(nifty_w1)     + len(nifty_w2) +
        len(sensex_fut)    + len(sensex_w1)    + len(sensex_w2) +
        len(banknifty_fut) + len(banknifty_w1) +
        3   # spot tokens (NIFTY, SENSEX, BANKNIFTY)
    )
    print(f"\n✅ Saved to {OUT_FILE}")
    print(f"   Total tokens to subscribe: ~{total_tokens} (+ 3 spot tokens)")
    print("\n▶  Now run:  python c:\\nifty\\feed.py")


if __name__ == "__main__":
    main()