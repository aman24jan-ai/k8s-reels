"""Upload a Short to YouTube with the free YouTube Data API (OAuth refresh token)."""
import os
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def upload(video_path: str, title: str, description: str, tags: list[str],
           thumbnail_path: Optional[str] = None) -> str:
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": [t.lstrip("#") for t in tags][:15],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            # Unverified Google Cloud apps can only upload as private until the audit passes
            "privacyStatus": os.environ.get("YT_PRIVACY", "public"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # AI voiceover disclosure
        },
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()

    if thumbnail_path and os.path.exists(thumbnail_path):
        thumb = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
        yt.thumbnails().set(videoId=resp["id"], media_body=thumb).execute()

    return f"https://youtube.com/shorts/{resp['id']}"
