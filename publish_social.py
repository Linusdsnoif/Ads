"""
publish_social.py: runs hourly from GitHub Actions.

Posts are driven by output_schedule/<batch_id>_<slot>.json (written by
generate_product_images.py), NOT by scanning output_models/. A post goes out
only when ALL of these are true:
  * its JSON says "review": "approved"
  * the current time is at/after its scheduled_utc (7:00 AM local in its city)
  * it is no more than PUBLISH_GRACE_HOURS late (default 6)

Because each post has an absolute date, next week's Tuesday post can never be
mixed up with this week's. An image with no schedule JSON is never posted.
"""
import os
import sys
import time
import json
import re
import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

import boto3
from botocore.config import Config

# ==========================================
# 1. CREDENTIALS & CONFIG
# ==========================================
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
IG_USER_ID = os.environ.get("IG_USER_ID")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID")

R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
R2_PUBLIC_URL = (os.environ.get("R2_PUBLIC_URL") or "").rstrip("/")

GRACE_HOURS = float(os.environ.get("PUBLISH_GRACE_HOURS", "6"))
PLATFORMS = ["facebook", "instagram_feed", "threads"]
MAX_ATTEMPTS = 3

SCHEDULE_DIR = Path("output_schedule")
IMAGES_DIR = Path("output_models")
CAPTIONS_DIR = Path("output_descriptions")

REQUIRED_ENV = [
    "META_ACCESS_TOKEN", "FB_PAGE_ID", "IG_USER_ID", "THREADS_ACCESS_TOKEN", "THREADS_USER_ID",
    "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "R2_PUBLIC_URL",
]

_r2_client = None


def r2():
    global _r2_client
    if _r2_client is None:
        _r2_client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
        )
    return _r2_client


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def extract_caption(raw_text: str) -> tuple[str, str]:
    """Pull the caption and alt text out of the Gemini output. Tolerates **bold** labels."""
    text = raw_text.replace("**", "")
    parts = re.split(r"^\s*Caption\s*:\s*", text, maxsplit=1, flags=re.M | re.I)
    if len(parts) < 2:
        print("     ⚠️ No 'Caption:' label found; posting the whole text file as the caption.")
        body = text
    else:
        body = parts[1]
    alt_parts = re.split(r"^\s*Alt Text\s*:\s*", body, maxsplit=1, flags=re.M | re.I)
    caption = alt_parts[0].strip()
    alt_text = alt_parts[1].strip() if len(alt_parts) == 2 else ""
    return caption, alt_text


def upload_to_public_url(local_image_path: Path) -> str:
    """Uploads an image to Cloudflare R2 and returns a permanent public URL."""
    print(f"Uploading {local_image_path.name} to Cloudflare R2...")
    object_name = f"posts/{int(time.time())}_{local_image_path.name}"
    try:
        r2().upload_file(
            str(local_image_path), R2_BUCKET_NAME, object_name,
            ExtraArgs={"ContentType": "image/jpeg"},
        )
    except Exception as e:
        raise RuntimeError(f"Cloudflare R2 upload failed: {e}")
    public_url = f"{R2_PUBLIC_URL}/{object_name}"
    print(f"  -> Upload successful! Permanent URL: {public_url}")
    return public_url


def get_meta_location_id(location_name: str):
    if location_name == "UTC":
        return None

    # Strip out the country name to help Meta's search engine
    search_query = location_name.split(",")[0].strip()
    print(f"  -> Searching Meta for location ID using query: '{search_query}'")
    
    url = "https://graph.facebook.com/v19.0/pages/search"
    params = {"q": search_query, "fields": "id,name,location", "access_token": META_ACCESS_TOKEN}

    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        if "data" in data:
            for place in data["data"]:
                if "location" in place: # Must have a physical address to work on IG
                    print(f"     ✅ Found Meta Place: {place.get('name')} (ID: {place['id']})")
                    return place["id"]

        print(f"     ⚠️ No verified Meta Place found for '{search_query}'. Posting without geotag.")
        return None
    except Exception as e:
        print(f"     ❌ Location search failed: {e}")
        return None
 


def get_threads_location_id(location_name: str):
    if location_name == "UTC":
        return None

    search_query = location_name.split(",")[0].strip()
    print(f"  -> Searching Threads for location ID using query: '{search_query}'")

    url = "https://graph.threads.net/v1.0/location_search"
    params = {"q": search_query, "access_token": THREADS_ACCESS_TOKEN}

    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        results = data.get("data", [])
        if results:
            best = results[0]
            print(f"     ✅ Found Threads location: {best.get('name')} (ID: {best['id']})")
            return str(best["id"])
            
        print(f"     ⚠️ No Threads location found. Posting without geotag.")
        return None
    except Exception as e:
        print(f"     ❌ Threads location search failed: {e}")
        return None


# ==========================================
# 3. CONTAINER POLLING & PUBLISHING
# ==========================================
def poll_container_status(container_id: str, platform: str, token: str, max_retries: int = 6) -> bool:
    """Actively polls Meta's servers until the image is 100% processed."""
    print(f"     ⏳ Polling {platform} container status...")
    base_url = "https://graph.facebook.com/v19.0" if platform == "IG" else "https://graph.threads.net/v1.0"
    url = f"{base_url}/{container_id}"
    params = {"fields": "status_code" if platform == "IG" else "status", "access_token": token}

    for attempt in range(max_retries):
        time.sleep(10)
        try:
            res = requests.get(url, params=params, timeout=30).json()
            status = res.get("status_code" if platform == "IG" else "status", "UNKNOWN")

            if status == "FINISHED":
                print(f"     ✅ Container {container_id} is FINISHED and ready!")
                return True
            elif status in ["ERROR", "EXPIRED"]:
                print(f"     ❌ Container failed processing with status: {status}")
                return False
            else:
                print(f"       - Status: {status}... waiting.")
        except Exception as e:
            print(f"     ⚠️ Polling error: {e}")

    print("     ❌ Container processing timed out.")
    return False


# Each publisher function now RETURNS True/False instead of only printing,
# so the caller can decide whether it's safe to delete the source files.

def post_to_facebook(image_url: str, caption: str) -> bool:
    print("  -> Posting to Facebook Page...")
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
    payload = {"url": image_url, "message": caption, "access_token": META_ACCESS_TOKEN}
    try:
        response = requests.post(url, data=payload, timeout=30)
        if response.status_code == 200:
            print("     ✅ Facebook Post Successful!")
            return True
        print(f"     ❌ Facebook Error: {response.json()}")
        return False
    except Exception as e:
        print(f"     ❌ Facebook request failed: {e}")
        return False


def post_to_instagram_feed(image_url: str, caption: str, alt_text: str, location_id: str) -> bool:
    print("  -> Posting to Instagram Feed...")
    container_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media"
    container_payload = {"image_url": image_url, "caption": caption, "access_token": META_ACCESS_TOKEN}

    if alt_text:
        container_payload["accessibility_caption"] = alt_text
    if location_id:
        container_payload["location_id"] = location_id

    try:
        container_res = requests.post(container_url, data=container_payload, timeout=30).json()
    except Exception as e:
        print(f"     ❌ IG Container request failed: {e}")
        return False

    if "id" not in container_res:
        print(f"     ❌ IG Container Error: {container_res}")
        return False

    container_id = container_res["id"]
    if not poll_container_status(container_id, "IG", META_ACCESS_TOKEN):
        return False

    publish_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish"
    publish_payload = {"creation_id": container_id, "access_token": META_ACCESS_TOKEN}
    try:
        pub_res = requests.post(publish_url, data=publish_payload, timeout=30)
        if pub_res.status_code == 200:
            print("     ✅ Instagram Feed Post Successful!")
            return True
        print(f"     ❌ IG Publish Error: {pub_res.json()}")
        return False
    except Exception as e:
        print(f"     ❌ IG Publish request failed: {e}")
        return False


def post_to_threads(image_url: str, caption: str, alt_text: str, location_id: str = None) -> bool:
    print("  -> Posting to Threads...")
    container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    container_payload = {"media_type": "IMAGE", "image_url": image_url, "text": caption,
                          "access_token": THREADS_ACCESS_TOKEN}

    if alt_text:
        container_payload["alt_text"] = alt_text
    if location_id:
        container_payload["location_id"] = location_id

    try:
        container_res = requests.post(container_url, data=container_payload, timeout=30).json()
    except Exception as e:
        print(f"     ❌ Threads Container request failed: {e}")
        return False

    if "id" not in container_res:
        print(f"     ❌ Threads Container Error: {container_res}")
        return False

    container_id = container_res["id"]
    if not poll_container_status(container_id, "Threads", THREADS_ACCESS_TOKEN):
        return False

    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    publish_payload = {"creation_id": container_id, "access_token": THREADS_ACCESS_TOKEN}
    try:
        pub_res = requests.post(publish_url, data=publish_payload, timeout=30)
        if pub_res.status_code == 200:
            print("     ✅ Threads Post Successful!")
            return True
        print(f"     ❌ Threads Publish Error: {pub_res.json()}")
        return False
    except Exception as e:
        print(f"     ❌ Threads Publish request failed: {e}")
        return False


# ==========================================
# 4. MAIN ORCHESTRATOR
# ==========================================
def save_entry(path: Path, entry: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2, ensure_ascii=False)


def publish_due_posts() -> int:
    print("=== Starting Social Publisher Hourly Check ===")

    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f"❌ Missing environment variables: {missing}. Add them as repository secrets.")
        return 1

    if not SCHEDULE_DIR.exists():
        print("No output_schedule/ folder yet. Nothing to do.")
        return 0

    now = datetime.datetime.now(datetime.timezone.utc)
    posted_any = False

    for path in sorted(SCHEDULE_DIR.glob("*.json")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ Could not read {path.name}: {e}")
            continue

        pub = entry["publish"]
        label = f"{path.stem} [{entry['product_name']} -> {entry['city']}, {entry['country']}]"

        if pub.get("done") or pub.get("stopped") or pub.get("missed"):
            continue

        sched = datetime.datetime.fromisoformat(entry["scheduled_utc"])
        if now < sched:
            hrs = (sched - now).total_seconds() / 3600
            print(f"{label}: due {entry['scheduled_local'][:16]} local ({hrs:.0f}h), review={entry['review']}")
            continue

        if now > sched + datetime.timedelta(hours=GRACE_HOURS):
            pub["missed"] = True
            save_entry(path, entry)
            print(f"🛑 {label}: MISSED its window (review={entry['review']}, "
                  f"posted so far={[p for p in PLATFORMS if pub[p]]}). Not posting. "
                  f"To post it anyway, set a new scheduled_utc and missed=false.")
            continue

        if entry["review"] != "approved":
            print(f"⏸️  {label}: due now but review={entry['review']}. Waiting for approval "
                  f"(window closes {GRACE_HOURS:.0f}h after 7 AM local).")
            continue

        img_path = IMAGES_DIR / (entry["image"] or "")
        txt_path = CAPTIONS_DIR / (entry["caption"] or "")
        if not entry["image"] or not img_path.is_file() or not entry["caption"] or not txt_path.is_file():
            print(f"❌ {label}: approved but image/caption file is missing. Skipping.")
            continue

        caption, alt_text = extract_caption(txt_path.read_text(encoding="utf-8"))
        location_name = f"{entry['city']}, {entry['country']}"
        pending = [p for p in PLATFORMS if not pub[p]]
        pub["attempts"] += 1
        posted_any = True
        print(f"\n--- Posting {label}. Pending: {pending} (attempt {pub['attempts']}/{MAX_ATTEMPTS}) ---")

        try:
            public_image_url = upload_to_public_url(img_path)
            if "facebook" in pending:
                pub["facebook"] = post_to_facebook(public_image_url, caption)
            if "instagram_feed" in pending:
                pub["instagram_feed"] = post_to_instagram_feed(
                    public_image_url, caption, alt_text, location_id=get_meta_location_id(location_name))
            if "threads" in pending:
                pub["threads"] = post_to_threads(
                    public_image_url, caption, alt_text, location_id=get_threads_location_id(location_name))
        except Exception as e:
            print(f"     ❌ Error while posting: {e}")

        if all(pub[p] for p in PLATFORMS):
            pub["done"] = True
            pub["posted_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            img_path.unlink(missing_ok=True)
            txt_path.unlink(missing_ok=True)
            print(f"     ✅ All platforms succeeded. Deleted {img_path.name} and {txt_path.name}; "
                  f"{path.name} kept as a record.")
        elif pub["attempts"] >= MAX_ATTEMPTS:
            pub["stopped"] = True
            print(f"     🛑 Still failing on {[p for p in PLATFORMS if not pub[p]]} after {MAX_ATTEMPTS} "
                  f"attempts. Stopped; files kept for manual review.")
        else:
            print(f"     ⏳ Still failing on {[p for p in PLATFORMS if not pub[p]]}; will retry next hour.")

        save_entry(path, entry)
        time.sleep(15)

    if not posted_any:
        print("\nNothing due to post this hour.")
    return 0


if __name__ == "__main__":
    sys.exit(publish_due_posts())
