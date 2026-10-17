"""Renew the YouTube refresh token and save it straight to GitHub Secrets.
Run weekly on your Mac:  python3 renew_yt.py
Needs client_secret.json in this folder and `gh auth login` done once."""
import subprocess
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", ["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
if not creds.refresh_token:
    raise SystemExit("No refresh token returned. Remove 'KSM Uploader' at "
                     "myaccount.google.com/permissions and run again.")
subprocess.run(["gh", "secret", "set", "YT_REFRESH_TOKEN", "-R", "shubhamtiw17/kpop-shorts",
                "--body", creds.refresh_token], check=True)
print("YT_REFRESH_TOKEN updated on GitHub. Valid for 7 days.")
