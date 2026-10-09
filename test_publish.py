"""
test_publish.py

Full standalone test for publish_social.py: reads a REAL caption file from
output_descriptions/ (same as the production pipeline does), parses it with
the actual extract_post_data() function, then posts to whichever platforms
you choose — bypassing only the day/timezone schedule-matching logic.

This exercises everything except the "is it 7am yet" check:
  - The real image file
  - The real .txt caption/alt-text/location parsing
  - The real ImgBB upload
  - The real Meta location lookup (if the file has a Location Tag)
  - The real Facebook / Instagram / Threads posting calls

⚠️ WARNING: This makes REAL, LIVE, PUBLIC posts. There is no sandbox/draft mode
in the Facebook, Instagram, or Threads Graph APIs. Use content you don't mind
being briefly public, and plan to manually delete the test posts afterward.

Usage
-----
    # Auto-finds output_descriptions/modeled_Breathable_Baby_Carrier_1.txt
    # to match the image, exactly like publish_social.py does:
    python test_publish.py --image output_models/modeled_Breathable_Baby_Carrier_1.jpg

    # Or point at a specific caption file explicitly:
    python test_publish.py --image path/to/photo.jpg --text path/to/caption.txt

    # Only test one or two platforms:
    python test_publish.py --image path/to/photo.jpg --platforms facebook threads

    # See the parsed caption/alt-text/location WITHOUT posting anything:
    python test_publish.py --image path/to/photo.jpg --dry-run
"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv


from publish_social import (
    extract_post_data,
    get_timezone_from_location,
    upload_to_public_url,
    get_meta_location_id,
    get_threads_location_id, 
    post_to_facebook,
    post_to_instagram_feed,
    post_to_threads,
)

load_dotenv()

REQUIRED_ENV_VARS = [
    "META_ACCESS_TOKEN",
    "FB_PAGE_ID",
    "IG_USER_ID",
    "THREADS_ACCESS_TOKEN",
    "THREADS_USER_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ENDPOINT_URL",
    "R2_BUCKET_NAME",
    "R2_PUBLIC_URL",
]


def check_env_vars() -> bool:
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        print("❌ Missing required environment variables (check your .env file):")
        for v in missing:
            print(f"   - {v}")
        return False
    print("✅ All required environment variables are set.")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True, help="Path to a local image file to test-post.")
    parser.add_argument(
        "--text",
        default=None,
        help="Path to the matching caption .txt file. If omitted, looks for "
             "output_descriptions/<image_stem>.txt — the same exact-match lookup "
             "publish_social.py uses in production.",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        choices=["facebook", "instagram", "threads"],
        default=["facebook", "instagram", "threads"],
        help="Which platform(s) to test. Default: all three.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print the caption/alt-text/location/schedule, but don't upload or post anything.",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"❌ Image not found: {image_path}")
        return

    if args.text:
        text_path = Path(args.text)
    else:
        text_path = Path("output_descriptions") / f"{image_path.stem}.txt"

    if not text_path.exists():
        print(f"❌ Caption file not found: {text_path}")
        print("   Pass --text explicitly if it's not sitting next to output_descriptions/.")
        return

    print(f"=== Reading caption file: {text_path} ===")
    raw_text = text_path.read_text(encoding="utf-8")

    day_of_week, location_name, caption, alt_text = extract_post_data(raw_text)

    print("\n=== Parsed post data ===")
    print(f"  Schedule day : {day_of_week}")
    print(f"  Location tag : {location_name}")
    print(f"  Alt text     : {alt_text}")
    print(f"  Caption      :\n{caption}\n")

    if location_name != "UTC":
        print("=== Resolving timezone for location (informational only — not gating this test) ===")
        tz = get_timezone_from_location(location_name)
        print(f"  Resolved timezone: {tz}")

    if args.dry_run:
        print("\n--dry-run set: stopping here, nothing was uploaded or posted.")
        return

    print("\n=== Checking environment variables ===")
    if not check_env_vars():
        return

    print("\n=== Uploading image to Cloudflare R2 ===")
    try:
        image_url = upload_to_public_url(image_path)
    except Exception as e:
        print(f"❌ Cloudflare R2 upload failed — check your R2 environment variables. Error: {e}")
        return

    location_id = None
    if location_name != "UTC":
        print("\n=== Looking up Meta location ===")
        location_id = get_meta_location_id(location_name)

    results = {}

    if "facebook" in args.platforms:
        print("\n=== Testing Facebook ===")
        results["facebook"] = post_to_facebook(image_url, caption)

    if "instagram" in args.platforms:
        print("\n=== Testing Instagram Feed ===")
        results["instagram"] = post_to_instagram_feed(image_url, caption, alt_text, location_id)

    if "threads" in args.platforms:
        print("\n=== Testing Threads ===")
        threads_loc_id = None
        if location_name != "UTC":
            threads_loc_id = get_threads_location_id(location_name)
        
        results["threads"] = post_to_threads(image_url, caption, alt_text, location_id=threads_loc_id)

    print("\n" + "=" * 40)
    print("RESULTS")
    print("=" * 40)
    for platform, ok in results.items():
        print(f"  {platform:12s}: {'✅ SUCCESS' if ok else '❌ FAILED'}")

    if not all(results.values()):
        print("\nCheck the error messages printed above each failed platform for details "
              "(e.g. invalid token, expired token, wrong Page/User ID, missing permissions).")
    else:
        print("\nAll tested platforms succeeded using the REAL caption/alt-text/location. "
              "Remember to manually delete these test posts from each app.")
    
    


if __name__ == "__main__":
    main()