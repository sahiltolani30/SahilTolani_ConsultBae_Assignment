"""
start_with_tunnel.py
--------------------
Starts the Flask bridge API and opens an ngrok tunnel.
Run this ONE script — it prints the public URL to paste into n8n.

Usage:
  cd SahilTolani_ConsultBae_Assignment
  python3 start_with_tunnel.py [--authtoken YOUR_TOKEN]

If you have an ngrok account, pass --authtoken.
Without a token, ngrok gives a temporary URL (works fine for demo).
"""
import sys
import os
import time
import threading
import argparse

# ── parse optional authtoken ───────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--authtoken", default=None, help="ngrok authtoken (optional)")
args, _ = parser.parse_known_args()

# ── configure pyngrok to use our downloaded binary ─────────────────
from pyngrok import conf, ngrok as pyngrok

NGROK_BIN = "/tmp/ngrok_bin_arm/ngrok"
if os.path.exists(NGROK_BIN):
    conf.get_default().ngrok_path = NGROK_BIN

if args.authtoken:
    conf.get_default().auth_token = args.authtoken

# ── start Flask in a background thread ────────────────────────────
PORT = 5001

def run_flask():
    # Silence Flask startup noise
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    sys.path.insert(0, os.path.dirname(__file__))
    from audio_app.app import app
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
time.sleep(2)  # wait for Flask to start

# ── open ngrok tunnel ──────────────────────────────────────────────
print("\n🚀 Opening tunnel to localhost:5001 ...")
try:
    tunnel = pyngrok.connect(PORT, bind_tls=True)
    public_url = tunnel.public_url
except Exception as e:
    print(f"❌ Tunnel failed: {e}")
    print("\n📝 If you see 'authtoken required', go to https://dashboard.ngrok.com/signup")
    print("   then run:  python3 start_with_tunnel.py --authtoken YOUR_TOKEN_HERE")
    sys.exit(1)

# ── print instructions ─────────────────────────────────────────────
print("\n" + "="*60)
print("✅ FLASK + TUNNEL RUNNING")
print("="*60)
print(f"\n🌐 Public URL:  {public_url}")
print(f"\n📋 Copy this URL → paste into n8n as FLASK_API_URL")
print(f"\n🔍 Test it now:")
print(f"   curl '{public_url}/api/health'")
print(f"   curl '{public_url}/api/candidates?untagged=true'")
print("\n⏸  Press Ctrl+C to stop\n")
print("="*60)

# ── keep alive ────────────────────────────────────────────────────
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pyngrok.disconnect(public_url)
    print("\n👋 Tunnel closed.")
