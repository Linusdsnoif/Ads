import os
import time
import json
import requests
import base64
import re
import datetime

from zoneinfo import ZoneInfo
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. CREDENTIALS & IDs
# ==========================================
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
IG_USER_ID = os.environ.get("IG_USER_ID")

THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID")

geolocator = Nominatim(user_agent="luffcabo_social_publisher")
tf = TimezoneFinder()


def get_timezone_from_location(location_name: str) -> str:
    """Converts a text string into a timezone string, with rate limit protection."""
    if location_name == "UTC":
        return "UTC"

    try:
        # Rate limit protection for Nominatim (1 req/sec policy)
        time.sleep(1.5)
        location = geolocator.geocode(location_name)
        if location:
            tz_name = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            return tz_name or "UTC"
    except Exception as e:
        print(f"Geocoding error for {location_name}: {e}")
    return "UTC"


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def extract_post_data(raw_text: str):
    day_of_week = "monday"
    location_name = "UTC"

    schedule_match = re.search(r"Schedule:\s*([A-Za-z]+)", raw_text)
    if schedule_match:
        day_of_week = schedule_match.group(1).lower()

    loc_match = re.search(r"Location Tag:\s*(.+)", raw_text)
    if loc_match:
        location_name = loc_match.group(1).strip()

    caption = raw_text
    alt_text = ""
    if "Caption:" in raw_text:
        parts = raw_text.split("Caption:")[1]
        if "Alt Text:" in parts:
            caption = parts.split("Alt Text:")[0].strip()
            alt_text = parts.split("Alt Text:")[1].strip()
        else:
            caption = parts.strip()

    return day_of_week, location_name, caption, alt_text


def upload_to_public_url(local_image_path: Path) -> str:
    print(f"Uploading {local_image_path.name} to ImgBB...")
    imgbb_api_key = os.environ.get("IMGBB_API_KEY")
    if not imgbb_api_key:
        raise ValueError("IMGBB_API_KEY is missing from your .env file.")

    with open(local_image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": imgbb_api_key,
        "image": encoded_string,
        "expiration": 3600  # 1 hour, to survive retries/polling
    }

    response = requests.post(url, data=payload, timeout=30)
    if response.status_code == 200:
        public_url = response.json()["data"]["url"]
        print(f"  -> Upload successful! Temporary URL: {public_url}")
        return public_url
    else:
        raise RuntimeError(f"ImgBB upload failed: {response.text}")


def get_meta_location_id(location_name: str):
    """Searches Meta and strictly verifies the result is a physical location."""
    if location_name == "UTC":
        return None

    print(f"  -> Searching Meta for location ID: {location_name}")
    url = "https://graph.facebook.com/v19.0/pages/search"
    params = {
        "q": location_name,
        "fields": "id,name,location",
        "access_token": META_ACCESS_TOKEN
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()

        if "data" in data:
            valid_places = [place for place in data["data"] if "location" in place]
            if valid_places:
                best_match = valid_places[0]
                print(f"     ✅ Found valid Meta Place: {best_match.get('name')} (ID: {best_match['id']})")
                return best_match["id"]

        print(f"     ⚠️ No verified Meta Place found for '{location_name}'. Posting without geotag.")
        return None

    except Exception as e:
        print(f"     ❌ Location search failed: {e}")
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


PLATFORMS = ["facebook", "instagram_feed", "threads"]
MAX_ATTEMPTS = 3  # after this many attempt-rounds without full success, stop retrying


def status_path_for(status_folder: Path, base_name: str) -> Path:
    return status_folder / f"{base_name}.json"


def load_status(status_folder: Path, base_name: str) -> dict:
    """Loads which platforms already succeeded for this post, plus retry bookkeeping."""
    path = status_path_for(status_folder, base_name)
    default = {p: False for p in PLATFORMS}
    default["attempts"] = 0
    default["stopped"] = False

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(default)
            for p in PLATFORMS:
                merged[p] = bool(data.get(p, False))
            merged["attempts"] = int(data.get("attempts", 0))
            merged["stopped"] = bool(data.get("stopped", False))
            return merged
        except Exception as e:
            print(f"     ⚠️ Could not read status file for {base_name}, starting fresh: {e}")
    return default


def save_status(status_folder: Path, base_name: str, status: dict):
    status_folder.mkdir(exist_ok=True)
    path = status_path_for(status_folder, base_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)


def clear_status(status_folder: Path, base_name: str):
    path = status_path_for(status_folder, base_name)
    if path.exists():
        path.unlink()


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


def post_to_threads(image_url: str, caption: str, alt_text: str) -> bool:
    print("  -> Posting to Threads...")
    container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    container_payload = {"media_type": "IMAGE", "image_url": image_url, "text": caption,
                          "access_token": THREADS_ACCESS_TOKEN}

    if alt_text:
        container_payload["alt_text"] = alt_text

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
def publish_for_today():
    print("=== Starting Social Publisher Hourly Check ===")

    images_folder = Path("output_models")
    text_folder = Path("output_descriptions")
    status_folder = Path("output_status")  # sidecar per-post platform status, for retries

    if not images_folder.exists() or not text_folder.exists():
        print("Required folders do not exist yet. Exiting.")
        return

    valid_extensions = {".jpg", ".jpeg", ".png"}
    images = [p for p in images_folder.iterdir() if p.suffix.lower() in valid_extensions]

    if not images:
        print("No images found in output_models/. Exiting.")
        return

    matched_any = False

    for img_path in images:
        base_name = img_path.stem
        # Exact match only: avoids "shirt1" matching "shirt10.txt" via a wildcard glob
        text_path = text_folder / f"{base_name}.txt"

        if not text_path.exists():
            print(f"Skipping {img_path.name} - no matching text file found ({text_path.name}).")
            continue

        with open(text_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        day_of_week, location_name, caption, alt_text = extract_post_data(raw_text)
        target_timezone = get_timezone_from_location(location_name)

        try:
            region_time = datetime.datetime.now(ZoneInfo(target_timezone))
            region_day = region_time.strftime("%A").lower()
            region_hour = region_time.hour

            print(f"Checking {img_path.name} | Target: {location_name} ({target_timezone}) | "
                  f"Local Time: {region_day.capitalize()} {region_hour}:00")

            if region_day == day_of_week and region_hour >= 7:
                matched_any = True

                status = load_status(status_folder, base_name)

                if status["stopped"]:
                    print(f"  -> {img_path.name} already hit the {MAX_ATTEMPTS}-attempt limit. "
                          f"Leaving files in place, not retrying.")
                    continue

                pending = [p for p in PLATFORMS if not status[p]]

                if not pending:
                    # Shouldn't normally happen (files get deleted on full success),
                    # but guards against a stale status file left behind.
                    print(f"  -> {img_path.name} already fully posted per status file. Cleaning up.")
                    img_path.unlink(missing_ok=True)
                    text_path.unlink(missing_ok=True)
                    clear_status(status_folder, base_name)
                    continue

                print(f"\n--- Time to post {img_path.name} for {location_name}. "
                      f"Still pending: {pending} (attempt {status['attempts'] + 1}/{MAX_ATTEMPTS}) ---")

                status["attempts"] += 1

                # Re-upload every run: the ImgBB link expires and a fresh URL is
                # needed whether this is the first attempt or a retry.
                public_image_url = upload_to_public_url(img_path)

                if "facebook" in pending:
                    status["facebook"] = post_to_facebook(public_image_url, caption)

                if "instagram_feed" in pending:
                    meta_location_id = get_meta_location_id(location_name)
                    status["instagram_feed"] = post_to_instagram_feed(
                        public_image_url, caption, alt_text, location_id=meta_location_id
                    )

                if "threads" in pending:
                    status["threads"] = post_to_threads(public_image_url, caption, alt_text)

                print(f"--- Status for {img_path.name}: {status} ---")

                if all(status[p] for p in PLATFORMS):
                    # Only delete the source files once every platform confirms success
                    img_path.unlink()
                    text_path.unlink()
                    clear_status(status_folder, base_name)
                    print(f"     🗑️ All platforms succeeded. Deleted: {img_path.name} and {text_path.name}")
                elif status["attempts"] >= MAX_ATTEMPTS:
                    # Give up on this post: stop retrying, but keep the files
                    # untouched for manual review instead of deleting them.
                    status["stopped"] = True
                    save_status(status_folder, base_name, status)
                    still_failing = [p for p in PLATFORMS if not status[p]]
                    print(f"     🛑 Reached max retries ({MAX_ATTEMPTS}) with {still_failing} still failing. "
                          f"Stopping retries for {img_path.name}; files kept as-is for manual review.")
                else:
                    # Persist progress and leave the source files in place.
                    # The next scheduled run (same day, still within the >=7am
                    # window) will retry only the platforms still marked False.
                    save_status(status_folder, base_name, status)
                    still_failing = [p for p in PLATFORMS if not status[p]]
                    print(f"     ⏳ Still failing on: {still_failing}. "
                          f"Progress saved to {status_folder}/{base_name}.json — "
                          f"will retry automatically on the next run.")

                time.sleep(15)
            else:
                print("  -> Not time yet. Skipping.")

        except Exception as e:
            print(f"Error processing {img_path.name}: {e}")

    if not matched_any:
        print("\nNo product posts were scheduled to run at this hour.")


if __name__ == "__main__":
    publish_for_today()