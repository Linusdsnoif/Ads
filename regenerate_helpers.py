"""
regenerate_helpers.py

Redo ONE rejected (or failed) slot from a weekly batch with the SAME product,
day, city, country, language and posting time. Every slot's target is stored
in output_schedule/<batch_id>_<slot>.json, so there is nothing to retype.

Slots: sun (Arabic, Saudi/UAE), tue (USA), thu (Europe), sat (UK/Australia)
batch_id = the date of the Sunday the batch starts on, e.g. 2026-10-11

Command line
------------
    python regenerate_helpers.py --list                          # show latest batch
    python regenerate_helpers.py --slot tue                      # redo Tuesday in the latest batch
    python regenerate_helpers.py --batch 2026-10-11 --slot thu
    python regenerate_helpers.py --slot sat --caption-only       # keep image, redo caption

Or run the "Regenerate Slot" GitHub workflow, which does the same and commits.

Notebook
--------
    from regenerate_helpers import regenerate_slot
    regenerate_slot("2026-10-11", "tue")

If you run it locally, `git pull` first and commit + push afterwards; the
publisher only sees what is in the repository.

What it does
------------
1. Generates a new image for the same product (and Arabic styling if the slot had it).
2. Writes a caption for the same city/country/language/day.
3. Deletes the rejected image + caption, so they can never be posted.
4. Points the slot's JSON at the new files and resets "review" to "pending",
   so the new image still needs approval.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import random
import sys
from pathlib import Path

from google.genai import Client

from generate_product_images import (
    CAPTION_DIR,
    COLOR_AGE_PAIRS,
    SCHEDULE_DIR,
    build_custom_prompts,
    clean_key,
    generate_caption,
    load_schedule,
    process_product,
    product_link_for,
    save_schedule,
    schedule_path,
)

log = logging.getLogger("product_image_gen")

PLATFORMS = ["facebook", "instagram_feed", "threads"]


def latest_batch_id() -> str | None:
    ids = sorted({p.name.split("_")[0] for p in SCHEDULE_DIR.glob("*.json")})
    return ids[-1] if ids else None


def list_batch(batch_id: str) -> None:
    files = sorted(SCHEDULE_DIR.glob(f"{batch_id}_*.json"))
    if not files:
        print(f"No slots found for batch {batch_id}.")
        return
    print(f"Batch {batch_id}:")
    for p in files:
        e = load_schedule(p)
        pub = e["publish"]
        state = ("posted" if pub["done"] else "missed" if pub["missed"] else "stopped" if pub["stopped"]
                 else f"review={e['review']}")
        print(f"  {e['slot']:>3} | {e['product_name']:<34} | {e['city']}, {e['country']:<20} | "
              f"{e['scheduled_local'][:16]} | {e['image'] or '(no image)'} | {state}")


def regenerate_slot(
    batch_id: str,
    slot: str,
    client: Client | None = None,
    base_folder: Path = Path("Product images"),
    output_models: Path = Path("output_models"),
    caption_only: bool = False,
    max_retries: int = 10,
) -> dict | None:
    """Regenerate one slot in place. Returns the updated schedule entry, or None on failure."""
    path = schedule_path(batch_id, slot)
    if not path.exists():
        log.error(f"No schedule file {path}. Use --list to see available slots.")
        return None

    entry = load_schedule(path)
    pub = entry["publish"]

    if pub["done"]:
        log.error(f"{path.name} was already posted at {pub['posted_at']}. Not regenerating.")
        return None
    if any(pub[p] for p in PLATFORMS):
        log.error(f"{path.name} is already live on some platforms "
                  f"({[p for p in PLATFORMS if pub[p]]}); a new image would mismatch. Not regenerating.")
        return None

    sched = datetime.datetime.fromisoformat(entry["scheduled_utc"])
    if datetime.datetime.now(datetime.timezone.utc) >= sched:
        log.warning(f"⚠️ Slot {slot} was due at {entry['scheduled_local']}, which has passed. "
                    f"Edit scheduled_local/scheduled_utc in {path.name} if you want it posted later.")

    client = client or Client(api_key=os.environ["GOOGLE_API_KEY"])
    target = {k: entry[k] for k in ("day", "city", "country", "language")}
    base_key = clean_key(entry["product_name"])

    old_image = output_models / entry["image"] if entry["image"] else None
    old_caption = CAPTION_DIR / entry["caption"] if entry["caption"] else None

    log.info(f"Regenerating {path.name}: {entry['product_name']}"
             f"{' [ARABIC]' if entry['arabic_variant'] else ''} -> "
             f"{target['city']}, {target['country']} ({target['language']}) {entry['scheduled_local']}")

    if caption_only:
        if not old_image or not old_image.exists():
            log.error("caption_only needs the existing image, but it is missing.")
            return None
        img_path = old_image
    else:
        color_age = random.choice(COLOR_AGE_PAIRS)
        custom_prompts = build_custom_prompts(color_age["color"], color_age["age"])
        img_path = process_product(
            client, base_folder, output_models, entry["product_name"], custom_prompts,
            arabic_variant=entry["arabic_variant"], max_retries=max_retries,
        )
        if img_path is None:
            log.error("Image generation failed. The slot is unchanged (and still not approved).")
            return None

    txt_path = generate_caption(img_path, client, target, base_key, product_link_for(base_key))

    # Remove the rejected files only once the replacement exists.
    if not caption_only and old_image and old_image.exists() and old_image != img_path:
        old_image.unlink()
        log.info(f"Deleted rejected image {old_image.name}")
    if old_caption and old_caption.exists() and (txt_path is None or old_caption != txt_path):
        old_caption.unlink()
        log.info(f"Deleted old caption {old_caption.name}")

    entry["image"] = img_path.name
    entry["caption"] = txt_path.name if txt_path else None
    entry["review"] = "pending"
    if not caption_only:
        entry["regenerations"] = entry.get("regenerations", 0) + 1
    pub.update({"attempts": 0, "stopped": False, "missed": False})
    save_schedule(entry)

    if txt_path is None:
        log.error(f"New image {img_path.name} saved, but caption failed. "
                  f"Run again with --caption-only.")
    else:
        log.info(f"✅ Slot {slot} ready for review: {img_path.name} + {txt_path.name}")
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate one slot of a weekly batch.")
    parser.add_argument("--batch", help="Batch id (Sunday date, e.g. 2026-10-11). Defaults to the latest batch.")
    parser.add_argument("--slot", choices=["sun", "tue", "thu", "sat"])
    parser.add_argument("--caption-only", action="store_true", help="Keep the image, regenerate only the caption.")
    parser.add_argument("--list", action="store_true", help="List the slots in the batch and exit.")
    parser.add_argument("--max-retries", type=int, default=10)
    args = parser.parse_args()

    batch_id = args.batch or latest_batch_id()
    if not batch_id:
        print("No batches found in output_schedule/.")
        return 1

    if args.list or not args.slot:
        list_batch(batch_id)
        return 0 if args.list else 1

    entry = regenerate_slot(batch_id, args.slot, caption_only=args.caption_only, max_retries=args.max_retries)
    return 0 if entry and entry["caption"] else 2


if __name__ == "__main__":
    sys.exit(main())
