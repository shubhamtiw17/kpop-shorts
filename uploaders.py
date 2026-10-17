import os, time, requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def upload_youtube(path, title, desc):
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"],
                        client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": f"{title} #shorts"[:100], "description": desc,
                        "categoryId": "10"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    r = yt.videos().insert(part="snippet,status", body=body,
                           media_body=MediaFileUpload(path, resumable=True)).execute()
    return r["id"]


def upload_instagram(video_url, caption):
    """video_url must be public (the queue release asset)."""
    ig, tok = os.environ["IG_USER_ID"], os.environ["IG_TOKEN"]
    base = f"https://graph.instagram.com/v21.0/{ig}"
    c = requests.post(f"{base}/media", data={"media_type": "REELS", "video_url": video_url,
                                             "caption": caption[:2200], "access_token": tok}).json()
    cid = c["id"]
    for _ in range(30):  # wait for IG processing
        s = requests.get(f"https://graph.instagram.com/v21.0/{cid}",
                         params={"fields": "status_code", "access_token": tok}).json()
        if s.get("status_code") == "FINISHED":
            break
        time.sleep(10)
    return requests.post(f"{base}/media_publish",
                         data={"creation_id": cid, "access_token": tok}).json().get("id")
