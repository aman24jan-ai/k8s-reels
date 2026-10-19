"""Post a Reel with the free Instagram Graph API (resumable upload, no file hosting needed).

Works with an Instagram Business/Creator account connected to a Facebook Page.
"""
import os
import time

import requests

API = os.environ.get("IG_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{API}"


def _check(r: requests.Response) -> dict:
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Instagram API error: {data}")
    return data


def upload(video_path: str, caption: str) -> str:
    user_id = os.environ["IG_USER_ID"]
    token = os.environ["IG_ACCESS_TOKEN"]

    # 1. create a resumable REELS container
    c = _check(requests.post(f"{GRAPH}/{user_id}/media", data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200],
        "share_to_feed": "true", "access_token": token}, timeout=60))
    container = c["id"]

    # 2. send the video bytes straight from this machine
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        r = requests.post(f"https://rupload.facebook.com/ig-api-upload/{API}/{container}",
                          headers={"Authorization": f"OAuth {token}", "offset": "0",
                                   "file_size": str(size)}, data=f, timeout=300)
    _check(r)

    # 3. wait for Instagram to finish processing
    for _ in range(60):
        st = _check(requests.get(f"{GRAPH}/{container}", params={
            "fields": "status_code,status", "access_token": token}, timeout=30))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram processing failed: {st}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram processing timed out")

    # 4. publish
    pub = _check(requests.post(f"{GRAPH}/{user_id}/media_publish", data={
        "creation_id": container, "access_token": token}, timeout=60))
    return pub["id"]
