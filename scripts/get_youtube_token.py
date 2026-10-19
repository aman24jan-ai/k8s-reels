"""Run ONCE on your Mac to get the YouTube refresh token.

    pip install google-auth-oauthlib
    python scripts/get_youtube_token.py client_secret.json

A browser opens; sign in with the Google account that owns your YouTube channel.
Copy the three printed values into GitHub -> Settings -> Secrets and variables -> Actions.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

path = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
flow = InstalledAppFlow.from_client_secrets_file(
    path, scopes=["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
info = json.load(open(path))
client = info.get("installed") or info.get("web")
print("\nYT_CLIENT_ID     =", client["client_id"])
print("YT_CLIENT_SECRET =", client["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
