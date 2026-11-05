"""
test_publish.py

Manual end-to-end test for publish_social.py: reads a REAL caption file from
output_descriptions/ (as the production pipeline does), parses and checks it
with the same code the publisher uses, then posts to whichever platforms you
choose. It skips only the schedule and review checks.

This exercises everything else:
  - the real image file
  - the real caption / alt-text parsing and caption checks (captions.py)
  - the real Cloudflare R2 upload
  - the real Meta and Threads location lookups (when a location is known)
  - the real Facebook / Instagram / Threads posting calls

WARNING: this makes REAL, LIVE, PUBLIC posts. The Facebook, Instagram and
Threads APIs have no sandbox or draft mode. Use content you don't mind being
briefly public, and delete the test posts afterwards.

This is a script, not a pytest test (pytest is told to skip it).

Usage
-----
    # Finds output_descriptions/modeled_Breathable_Baby_Carrier_1.txt to match
    # the image, the same way the pipeline names caption files:
    python test_publish.py --image output_models/modeled_Breathable_Baby_Carrier_1.jpg

    # Point at a specific caption file:
    python test_publish.py --image path/to/photo.jpg --text path/to/caption.txt

    # Only test one or two platforms:
    python test_publish.py --image path/to/photo.jpg --platforms facebook threads

    # Set the geotag yourself (otherwise taken from the image's schedule file,
    # then from the caption's "Location Tag:" line):
    python test_publish.py --image path/to/photo.jpg --location "Miami, USA"

    # Show the parsed caption, alt text, location and checks WITHOUT posting:
    python test_publish.py --image path/to/photo.jpg --dry-run
"""

import argparse
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from captions import THREADS_MAX_CHARS, caption_problems, extract_caption, post_length
from publish_social import (
    CAPTIONS_DIR,
    REQUIRED_ENV,
    SCHEDULE_DIR,
    get_meta_location_id,
    get_threads_location_id,
    post_to_facebook,
    post_to_instagram_feed,
    post_to_threads,
    upload_to_public_url,
)

__test__ = False  # keeps pytest from collecting this live-posting script

load_dotenv()


def check_env_vars() -> bool:
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        print("❌ Missing required environment variables (check your .env file):")
        for v in missing:
            print(f"   - {v}")
        return False
    print("✅ All required environment variables are set.")
    return True


def find_location(image_path: Path, raw_text: str) -> tuple[str | None, str]:
    """Return (location, where it came from): the image's schedule file first,
    then the caption's 'Location Tag:' line."""
    if SCHEDULE_DIR.is_dir():
        for path in SCHEDULE_DIR.glob("*.json"):
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if entry.get("image") == image_path.name and entry.get("city"):
                return f"{entry['city']}, {entry['country']}", f"schedule file {path.name}"
    m = re.search(r"^\s*Location\s*Tag\s*:\s*(.+)$", raw_text.replace("**", ""), re.M | re.I)
    if m:
        return m.group(1).strip(), "the caption's Location Tag line"
    return None, "nowhere (posting without a geotag)"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True, help="Path to a local image file to test-post.")
    parser.add_argument(
        "--text",
        default=None,
        help="Path to the matching caption .txt file. If omitted, uses "
             "output_descriptions/<image_stem>.txt, the name the pipeline gives caption files.",
    )
    parser.add_argument("--location", default=None, help='Geotag to use, e.g. "Miami, USA".')
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
        help="Parse and print the caption, alt text, location and checks, but don't upload or post anything.",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"❌ Image not found: {image_path}")
        return

    text_path = Path(args.text) if args.text else CAPTIONS_DIR / f"{image_path.stem}.txt"
    if not text_path.exists():
        print(f"❌ Caption file not found: {text_path}")
        print("   Pass --text explicitly if it isn't in output_descriptions/.")
        return

    print(f"=== Reading caption file: {text_path} ===")
    raw_text = text_path.read_text(encoding="utf-8")
    caption, alt_text = extract_caption(raw_text)

    if args.location:
        location_name, source = args.location, "--location"
    else:
        location_name, source = find_location(image_path, raw_text)

    print("\n=== Parsed post data ===")
    print(f"  Location     : {location_name or '(none)'}  (from {source})")
    print(f"  Alt text     : {alt_text or '(none)'}")
    print(f"  Length       : {post_length(caption)}/{THREADS_MAX_CHARS} characters")
    print(f"  Caption      :\n{caption}\n")

    # The same check the publisher runs before posting.
    problems = caption_problems(raw_text, require_alt_text=False)
    if problems:
        print("❌ The publisher would refuse this caption:")
        for p in problems:
            print(f"   - {p}")
        print("   Fix the caption file before testing.")
        return
    print("✅ Caption passes the publisher's checks.")

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
        print(f"❌ Cloudflare R2 upload failed; check your R2 environment variables. Error: {e}")
        return

    results = {}

    if "facebook" in args.platforms:
        print("\n=== Testing Facebook ===")
        results["facebook"] = post_to_facebook(image_url, caption)

    if "instagram" in args.platforms:
        print("\n=== Testing Instagram Feed ===")
        meta_loc_id = get_meta_location_id(location_name) if location_name else None
        results["instagram"] = post_to_instagram_feed(image_url, caption, alt_text, meta_loc_id)

    if "threads" in args.platforms:
        print("\n=== Testing Threads ===")
        threads_loc_id = get_threads_location_id(location_name) if location_name else None
        results["threads"] = post_to_threads(image_url, caption, alt_text, location_id=threads_loc_id)

    print("\n" + "=" * 40)
    print("RESULTS")
    print("=" * 40)
    for platform, ok in results.items():
        print(f"  {platform:12s}: {'✅ SUCCESS' if ok else '❌ FAILED'}")

    if not all(results.values()):
        print("\nCheck the error messages printed above each failed platform for details "
              "(e.g. invalid or expired token, wrong Page/User ID, missing permissions).")
    else:
        print("\nAll tested platforms succeeded. Remember to delete these test posts from each app.")


if __name__ == "__main__":
    main()
