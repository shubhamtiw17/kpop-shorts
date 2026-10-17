"""Extend the Instagram token by another 60 days and save it to GitHub Secrets.
Run on your Mac:  python3 renew_ig.py
The current token must still be valid (renew before it expires).
The newest token is kept in ~/.ksm_ig_token so next time you don't need to paste it."""
import getpass, os, subprocess, requests

store = os.path.expanduser("~/.ksm_ig_token")
token = open(store).read().strip() if os.path.exists(store) else \
    getpass.getpass("Paste your current IG token (hidden): ").strip()

r = requests.get("https://graph.instagram.com/refresh_access_token",
                 params={"grant_type": "ig_refresh_token", "access_token": token}).json()
if "access_token" not in r:
    raise SystemExit(f"Refresh failed: {r.get('error', r)}\n"
                     "If the token already expired, generate a new one in the Meta app "
                     "(API setup with Instagram login -> Generate token), then delete "
                     f"{store} and run this again.")

new = r["access_token"]
subprocess.run(["gh", "secret", "set", "IG_TOKEN", "-R", "shubhamtiw17/kpop-shorts",
                "--body", new], check=True)
with open(store, "w") as f:
    f.write(new)
os.chmod(store, 0o600)
print(f"IG_TOKEN updated on GitHub. Valid for {r.get('expires_in', 5184000) // 86400} days.")
