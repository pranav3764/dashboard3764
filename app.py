# app.py
import os
import json
from datetime import datetime,timezone
from flask import Flask, redirect, request, url_for, render_template_string
from kiteconnect import KiteConnect
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("KITE_API_KEY")
print(API_KEY)
API_SECRET = os.getenv("KITE_API_SECRET")
REDIRECT_URL = os.getenv("REDIRECT_URL")  # must match app console
TOKEN_FILE = "token_store.json"

if not API_KEY or not API_SECRET or not REDIRECT_URL:
    raise RuntimeError("Set KITE_API_KEY, KITE_API_SECRET and FLASK_REDIRECT_URL in .env")

kite = KiteConnect(api_key=API_KEY)
app = Flask(__name__)

INDEX_HTML = """
<h2>Kite Connect Auth</h2>
<ul>
  <li><a href="{{ login_url }}" target="_blank">Open Kite Login (new tab)</a></li>
  <li>After login you'll be redirected to: <code>{{ redirect_url }}</code></li>
  <li>Callback will auto-exchange request_token and save access_token to <b>token_store.json</b></li>
</ul>
"""

@app.route("/")
def index():
    login_url = kite.login_url()
    return render_template_string(INDEX_HTML, login_url=login_url, redirect_url=REDIRECT_URL)

@app.route("/callback")
def callback():
    # This route receives ?request_token=xxxxx&status=success
    req_token = request.args.get("request_token")
    status = request.args.get("status")
    if status != "success" or not req_token:
        return "Login failed or missing request_token", 400

    try:
        # Exchange request_token -> access_token (server-side only)
        data = kite.generate_session(req_token, api_secret=API_SECRET)
        # print('data')
        print(data)
        access_token = data.get("access_token")
        # refresh_token=data.get('refresh_token')
        if not access_token:
            return f"Failed to generate access token: {data}", 500
        # if not refresh_token:
        #     return f"Failed to generate access token: {data}", 500

        # Save token and metadata
        stored = {
            "api_key": API_KEY,
            "access_token": access_token,
        #    "login_time": data.get("login_time") or datetime.now(timezone.utc).isoformat(),
             "login_time": data.get("login_time").isoformat() if data.get("login_time") else datetime.now(timezone.utc).isoformat(),
            # "refresh_token":refresh_token,
            "user_id": data.get("user_id"),
            # "raw": data  # helpful debug info (don't commit)
        }
        with open(TOKEN_FILE, "w") as f:
            json.dump(stored, f, indent=2)

        # Set token in kite instance for this process (optional)
        kite.set_access_token(access_token)

        return f"Access token saved successfully. You can close this page. (user_id: {stored.get('user_id')})"
    except Exception as e:
        return f"Error generating session: {repr(e)}", 500

if __name__ == "__main__":
    # Run locally: flask server that will capture request_token and exchange it.
    # Start this, then open http://127.0.0.1:5000/ and click login.
    app.run(host="0.0.0.0", port=5000, debug=False)
