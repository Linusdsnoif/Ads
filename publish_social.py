import os
import time
import requests
import base64
import re
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. CREDENTIALS & IDs (Loaded from .env)
# ==========================================
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
IG_USER_ID = os.environ.get("IG_USER_ID")

THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID")

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def extract_post_data(raw_text: str):
    """
    Parses the text file to safely extract the scheduled day, 
    location ID, caption, and alt text, ignoring the rest of the metadata.
    """
    day_of_week = "monday" # Default fallback
    location_id = None
    
    # 1. Extract Day of Week (e.g., from "Schedule: Tuesday 7:00 AM")
    schedule_match = re.search(r"Schedule:\s*([A-Za-z]+)", raw_text)
    if schedule_match:
        day_of_week = schedule_match.group(1).lower()

    # 2. Extract Location ID (e.g., from "Location ID: 110970792260962")
    loc_match = re.search(r"Location ID:\s*(\d+)", raw_text)
    if loc_match:
        location_id = loc_match.group(1)

    # 3. Extract Caption and Alt Text
    caption = raw_text
    alt_text = ""
    
    if "Caption:" in raw_text:
        parts = raw_text.split("Caption:")[1]
        if "Alt Text:" in parts:
            caption = parts.split("Alt Text:")[0].strip()
            alt_text = parts.split("Alt Text:")[1].strip()
        else:
            caption = parts.strip()
            
    return day_of_week, location_id, caption, alt_text

def upload_to_public_url(local_image_path: Path) -> str:
    """Uploads a local image to ImgBB and returns the direct public URL."""
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
        "expiration": 600 # Auto-deletes from ImgBB after 10 minutes
    }

    response = requests.post(url, data=payload)
    if response.status_code == 200:
        public_url = response.json()["data"]["url"]
        print(f"  -> Upload successful! Temporary URL: {public_url}")
        return public_url
    else:
        raise RuntimeError(f"ImgBB upload failed: {response.text}")

# ==========================================
# 3. PLATFORM PUBLISHING FUNCTIONS
# ==========================================
def post_to_facebook(image_url: str, caption: str):
    print("  -> Posting to Facebook Page...")
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
    payload = {
        "url": image_url,
        "message": caption,
        "access_token": META_ACCESS_TOKEN
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        print("     ✅ Facebook Post Successful!")
    else:
        print(f"     ❌ Facebook Error: {response.json()}")

def post_to_instagram_feed(image_url: str, caption: str, alt_text: str, location_id: str):
    print("  -> Posting to Instagram Feed...")
    container_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media"
    
    container_payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": META_ACCESS_TOKEN
    }
    # Add optional parameters if they exist
    if alt_text:
        container_payload["accessibility_caption"] = alt_text
    if location_id:
        container_payload["location_id"] = location_id

    container_res = requests.post(container_url, data=container_payload).json()
    if "id" not in container_res:
        print(f"     ❌ IG Container Error: {container_res}")
        return

    container_id = container_res["id"]
    time.sleep(10) # 10 seconds for Meta to securely download the image

    publish_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish"
    publish_payload = {"creation_id": container_id, "access_token": META_ACCESS_TOKEN}
    
    pub_res = requests.post(publish_url, data=publish_payload)
    if pub_res.status_code == 200:
        print("     ✅ Instagram Feed Post Successful!")
    else:
        print(f"     ❌ IG Publish Error: {pub_res.json()}")

def post_to_instagram_story(image_url: str):
    print("  -> Posting to Instagram Story...")
    # NOTE: Stories heavily prefer 9:16 aspect ratio images.
    container_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media"
    container_payload = {
        "image_url": image_url,
        "media_type": "STORIES",
        "access_token": META_ACCESS_TOKEN
    }
    
    container_res = requests.post(container_url, data=container_payload).json()
    if "id" not in container_res:
        print(f"     ❌ IG Story Container Error: {container_res}")
        return

    container_id = container_res["id"]
    time.sleep(10)

    publish_url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish"
    publish_payload = {"creation_id": container_id, "access_token": META_ACCESS_TOKEN}
    
    pub_res = requests.post(publish_url, data=publish_payload)
    if pub_res.status_code == 200:
        print("     ✅ Instagram Story Post Successful!")
    else:
        print(f"     ❌ IG Story Publish Error: {pub_res.json()}")

def post_to_threads(image_url: str, caption: str, alt_text: str):
    print("  -> Posting to Threads...")
    container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    
    container_payload = {
        "media_type": "IMAGE",
        "image_url": image_url,
        "text": caption,
        "access_token": THREADS_ACCESS_TOKEN
    }
    if alt_text:
        container_payload["alt_text"] = alt_text

    container_res = requests.post(container_url, data=container_payload).json()
    if "id" not in container_res:
        print(f"     ❌ Threads Container Error: {container_res}")
        return

    container_id = container_res["id"]
    time.sleep(10)

    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    publish_payload = {"creation_id": container_id, "access_token": THREADS_ACCESS_TOKEN}
    
    pub_res = requests.post(publish_url, data=publish_payload)
    if pub_res.status_code == 200:
        print("     ✅ Threads Post Successful!")
    else:
        print(f"     ❌ Threads Publish Error: {pub_res.json()}")

# ==========================================
# 4. MAIN ORCHESTRATOR (GitHub Actions Ready)
# ==========================================
def publish_for_today():
    # Determine what day it currently is (e.g., 'tuesday')
    today = datetime.datetime.now().strftime("%A").lower()
    print(f"=== Starting Social Publisher | Current Day: {today.capitalize()} ===")
    
    images_folder = Path("output_models")
    text_folder = Path("output_descriptions")
    
    # Check for all standard image types
    image_extensions = ("*.jpg", "*.jpeg", "*.png")
    images = []
    for ext in image_extensions:
        images.extend(images_folder.glob(ext))
        
    if not images:
        print("No images found in output_models/. Exiting.")
        return

    matched_any = False
    
    for img_path in images:
        base_name = img_path.stem
        matching_text_files = list(text_folder.glob(f"desc_{base_name}_*.txt"))
        
        if not matching_text_files:
            continue
            
        with open(matching_text_files[0], "r", encoding="utf-8") as f:
            raw_text = f.read()
            
        # Parse out the data
        day_of_week, location_id, caption, alt_text = extract_post_data(raw_text)
        
        # ONLY publish if the image is scheduled for today
        if day_of_week == today:
            matched_any = True
            print(f"\n--- Broadcasting {img_path.name} ---")
            
            try:
                public_image_url = upload_to_public_url(img_path)
            except Exception as e:
                print(e)
                continue
            
            # Post to all networks
            post_to_facebook(public_image_url, caption)
            post_to_instagram_feed(public_image_url, caption, alt_text, location_id)
            post_to_instagram_story(public_image_url)
            post_to_threads(public_image_url, caption, alt_text)
            
            print(f"--- Finished Broadcasting {img_path.name} ---")
            time.sleep(15) # Safety buffer before posting the next product
            
    if not matched_any:
        print(f"\nNo product posts were scheduled for {today.capitalize()}.")

if __name__ == "__main__":
    publish_for_today()