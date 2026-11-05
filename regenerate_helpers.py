"""
regenerate_helpers.py

Redo ONE slot of a weekly batch, either with a new AI image or with your own
photo, keeping the SAME product, day, city, country, language and posting time.
Every slot's target is stored in output_schedule/<batch_id>_<slot>.json, so
there is nothing to retype.

Slots: sun (Saudi/UAE), tue (USA), wed (parenting tips, 1st and 3rd week of the
month), thu (Europe), sat (UK/Australia)
batch_id = the date of the Sunday the batch starts on, e.g. 2026-10-11

Your own photo instead of the AI image (easiest way)
----------------------------------------------------
1. Name the photo after its slot: tue.jpg (the next Tuesday post that hasn't gone
   out yet), or batch + slot: 2026-11-08_tue.jpg. JPG, PNG or WEBP.
2. Upload it to the manual_uploads/ folder on GitHub (Add file > Upload files).
3. The "Use Manual Image" workflow runs by itself: it crops the photo to
   1080x1350, writes the caption for that slot's city and language, removes
   the rejected AI image, and marks the slot "approved", so it posts on schedule.

Command line
------------
    python regenerate_helpers.py --list                          # show latest batch
    python regenerate_helpers.py --slot tue                      # new AI image for Tuesday (latest batch)
    python regenerate_helpers.py --batch 2026-10-11 --slot thu
    python regenerate_helpers.py --slot sat --caption-only       # keep image, redo caption
    python regenerate_helpers.py --slot tue --manual my_photo.jpg   # your own photo, next upcoming Tuesday
    python regenerate_helpers.py --scan-manual                   # attach every photo in manual_uploads/

Add --keep-pending to leave your own photo at "pending" instead of "approved".
Or run the "Regenerate Slot" GitHub workflow, which does the same and commits.

Notebook
--------
    from regenerate_helpers import regenerate_slot, use_manual_image
    regenerate_slot("2026-10-11", "tue")
    use_manual_image("2026-10-11", "tue", Path("my_photo.jpg"))

If you run it locally, `git pull` first and commit + push afterwards; the
publisher only sees what is in the repository.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import random
import re
import sys
from pathlib import Path

from google.genai import Client
from PIL import Image, ImageOps

from generate_product_images import (
    CAPTION_DIR,
    COLOR_AGE_PAIRS,
    SCHEDULE_DIR,
    build_custom_prompts,
    clean_key,
    fit_to_output_size,
    generate_caption,
    generate_tips_caption,
    load_schedule,
    process_product,
    process_tips,
    product_link_for,
    save_schedule,
    schedule_path,
)
from tips_posts import find_tips_topic

log = logging.getLogger("product_image_gen")

PLATFORMS = ["facebook", "instagram_feed", "threads"]
SLOT_KEYS = ["sun", "tue", "wed", "thu", "sat"]
MANUAL_DIR = Path("manual_uploads")
MANUAL_NAME = re.compile(r"^(?:(\d{4}-\d{2}-\d{2})_)?(sun|tue|wed|thu|sat)$", re.I)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def latest_batch_id() -> str | None:
    ids = sorted({p.name.split("_")[0] for p in SCHEDULE_DIR.glob("*.json")})
    return ids[-1] if ids else None


def upcoming_batch_id(slot: str) -> str | None:
    """The batch whose `slot` post is the next one still waiting to go out."""
    waiting = []
    for path in SCHEDULE_DIR.glob(f"*_{slot}.json"):
        entry = load_schedule(path)
        if not (entry["publish"]["done"] or entry["publish"]["missed"]):
            waiting.append((entry["scheduled_utc"], entry["batch_id"]))
    return min(waiting)[1] if waiting else None


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
        extra = f" | text check {e['text_check']}" if e.get("post_type") == "tips" else ""
        print(f"  {e['slot']:>3} | {e['product_name']:<34} | {e['city']}, {e['country']:<20} | "
              f"{e['scheduled_local'][:16]} | {e['image'] or '(no image)'} | {state}{extra}")


def _can_replace(entry: dict, path: Path) -> bool:
    pub = entry["publish"]
    if pub["done"]:
        log.error(f"{path.name} was already posted at {pub['posted_at']}. Not changing it.")
        return False
    if any(pub[p] for p in PLATFORMS):
        log.error(f"{path.name} is already live on some platforms "
                  f"({[p for p in PLATFORMS if pub[p]]}); a new image would mismatch. Not changing it.")
        return False
    sched = datetime.datetime.fromisoformat(entry["scheduled_utc"])
    if datetime.datetime.now(datetime.timezone.utc) >= sched:
        log.warning(f"⚠️ Slot {entry['slot']} was due at {entry['scheduled_local']}, which has passed. "
                    f"Edit scheduled_local/scheduled_utc in {path.name} if you want it posted later.")
    return True


def _target(entry: dict) -> dict:
    return {k: entry[k] for k in ("day", "city", "country", "language")}


def _write_caption(entry: dict, img_path: Path, client: Client) -> Path | None:
    """Caption for the slot's own city/language: a product caption, or a tips caption for tips posts."""
    if entry.get("post_type") == "tips":
        topic = find_tips_topic(entry.get("tips_topic", ""))
        if topic is None:
            log.error(f"Tips topic '{entry.get('tips_topic')}' is no longer in TIPS_TOPICS; can't write its caption.")
            return None
        return generate_tips_caption(img_path, client, _target(entry), topic)
    base_key = clean_key(entry["product_name"])
    return generate_caption(img_path, client, _target(entry), base_key, product_link_for(base_key))


def _remove_old_files(old_image: Path | None, old_caption: Path | None, img_path: Path, txt_path: Path | None):
    """Remove the replaced files, only once the replacement exists."""
    if old_image and old_image.exists() and old_image != img_path:
        old_image.unlink()
        log.info(f"Deleted replaced image {old_image.name}")
    if old_caption and old_caption.exists() and (txt_path is None or old_caption != txt_path):
        old_caption.unlink()
        log.info(f"Deleted old caption {old_caption.name}")


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
    if not _can_replace(entry, path):
        return None

    client = client or Client(api_key=os.environ["GOOGLE_API_KEY"])
    old_image = output_models / entry["image"] if entry["image"] else None
    old_caption = CAPTION_DIR / entry["caption"] if entry["caption"] else None

    log.info(f"Regenerating {path.name}: {entry['product_name']}"
             f"{' [ARABIC]' if entry['arabic_variant'] else ''} -> "
             f"{entry['city']}, {entry['country']} ({entry['language']}) {entry['scheduled_local']}")

    if caption_only:
        if not old_image or not old_image.exists():
            log.error("caption_only needs the existing image, but it is missing.")
            return None
        img_path = old_image
    elif entry.get("post_type") == "tips":
        topic = find_tips_topic(entry.get("tips_topic", ""))
        if topic is None:
            log.error(f"Tips topic '{entry.get('tips_topic')}' is no longer in TIPS_TOPICS.")
            return None
        img_path, entry["text_check"] = process_tips(client, base_folder, output_models, topic,
                                                      max_retries=max_retries)
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

    txt_path = _write_caption(entry, img_path, client)
    if not caption_only:
        _remove_old_files(old_image, old_caption, img_path, txt_path)
    elif old_caption and old_caption.exists() and txt_path and old_caption != txt_path:
        old_caption.unlink()

    entry["image"] = img_path.name
    entry["caption"] = txt_path.name if txt_path else None
    entry["review"] = "pending"
    if not caption_only:
        entry["regenerations"] = entry.get("regenerations", 0) + 1
        entry.pop("source", None)
    entry["publish"].update({"attempts": 0, "stopped": False, "missed": False})
    save_schedule(entry)

    if txt_path is None:
        log.error(f"New image {img_path.name} saved, but caption failed. Run again with --caption-only.")
    else:
        log.info(f"✅ Slot {slot} ready for review: {img_path.name} + {txt_path.name}")
    return entry


def use_manual_image(
    batch_id: str,
    slot: str,
    image_path: Path,
    client: Client | None = None,
    output_models: Path = Path("output_models"),
    approve: bool = True,
) -> dict | None:
    """Replace a slot's image with your own photo, then write its caption.

    The photo is cropped to 1080x1350 and saved as output_models/manual_<batch>_<slot>.jpg.
    With approve=True the slot is marked "approved" and posts at its scheduled time.
    A photo taken from manual_uploads/ is removed from there once it is attached.
    """
    path = schedule_path(batch_id, slot)
    if not path.exists():
        log.error(f"No schedule file {path}. Use --list to see available slots.")
        return None
    entry = load_schedule(path)
    if not _can_replace(entry, path):
        return None

    try:
        with Image.open(image_path) as photo:
            photo = ImageOps.exif_transpose(photo)  # respect phone camera rotation
            fitted = fit_to_output_size(photo)
    except Exception as e:
        log.error(f"Could not open {image_path}: {e}")
        return None

    old_image = output_models / entry["image"] if entry["image"] else None
    old_caption = CAPTION_DIR / entry["caption"] if entry["caption"] else None
    output_models.mkdir(parents=True, exist_ok=True)
    img_path = output_models / f"manual_{batch_id}_{slot}.jpg"
    fitted.save(img_path, "JPEG", quality=95, optimize=True)
    log.info(f"Attached your photo {image_path.name} to {path.name} as {img_path.name} (1080x1350).")

    client = client or Client(api_key=os.environ["GOOGLE_API_KEY"])
    txt_path = _write_caption(entry, img_path, client)
    _remove_old_files(old_image, old_caption, img_path, txt_path)

    entry["image"] = img_path.name
    entry["caption"] = txt_path.name if txt_path else None
    entry["source"] = "manual"
    if entry.get("post_type") == "tips":
        entry["text_check"] = "not checked (your own image)"
    entry["review"] = "approved" if (approve and txt_path) else "pending"
    entry["publish"].update({"attempts": 0, "stopped": False, "missed": False})
    save_schedule(entry)

    if image_path.resolve().parent == MANUAL_DIR.resolve():
        image_path.unlink()

    if txt_path is None:
        log.error(f"Your photo is attached, but the caption failed, so the slot stays pending. "
                  f"Run: python regenerate_helpers.py --batch {batch_id} --slot {slot} --caption-only")
    else:
        log.info(f"✅ Slot {slot} ({entry['scheduled_local'][:16]} local) is {entry['review']} "
                 f"with your photo + {txt_path.name}")
    return entry


def scan_manual_uploads(folder: Path = MANUAL_DIR, approve: bool = True) -> int:
    """Attach every photo in manual_uploads/ to the slot in its file name. Returns the number that failed."""
    photos = sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS) \
        if folder.is_dir() else []
    if not photos:
        log.info(f"No photos waiting in {folder}/.")
        return 0

    client, failures, summary = None, 0, []
    for photo in photos:
        match = MANUAL_NAME.match(photo.stem)
        if not match:
            log.error(f"Skipping {photo.name}: name it after its slot, e.g. tue.jpg or 2026-11-08_tue.jpg.")
            summary.append(f"- ❌ `{photo.name}`: name it after its slot, e.g. `tue.jpg` or `2026-11-08_tue.jpg`")
            failures += 1
            continue
        slot = match.group(2).lower()
        batch_id = match.group(1) or upcoming_batch_id(slot)
        if not batch_id:
            log.error(f"Skipping {photo.name}: no upcoming '{slot}' post is waiting to go out.")
            summary.append(f"- ❌ `{photo.name}`: no upcoming `{slot}` post found")
            failures += 1
            continue

        client = client or Client(api_key=os.environ["GOOGLE_API_KEY"])
        entry = use_manual_image(batch_id, slot, photo, client=client, approve=approve)
        if entry is None or not entry["caption"]:
            failures += 1
            summary.append(f"- ❌ `{photo.name}` -> {batch_id} {slot}: failed (see the log)")
            continue
        caption = (CAPTION_DIR / entry["caption"]).read_text(encoding="utf-8").strip()
        summary.append(
            f"- ✅ `{photo.name}` -> **{batch_id} {slot}** ({entry['product_name']}, {entry['city']}), "
            f"posts {entry['scheduled_local'][:16]} local, review = **{entry['review']}**\n\n"
            f"  <details><summary>Caption</summary>\n\n```\n{caption}\n```\n</details>\n"
        )

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("## Your photos\n\n" + "\n".join(summary) + "\n")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate one slot of a weekly batch, or use your own photo.")
    parser.add_argument("--batch", help="Batch id (Sunday date, e.g. 2026-10-11). Defaults to the latest batch "
                                        "(with --manual: the next upcoming post for the slot).")
    parser.add_argument("--slot", choices=SLOT_KEYS)
    parser.add_argument("--caption-only", action="store_true", help="Keep the image, regenerate only the caption.")
    parser.add_argument("--manual", type=Path, help="Use this photo for the slot instead of an AI image.")
    parser.add_argument("--scan-manual", action="store_true",
                        help="Attach every photo in manual_uploads/ (named like tue.jpg or 2026-11-08_tue.jpg).")
    parser.add_argument("--keep-pending", action="store_true",
                        help="Leave your own photo at review=pending instead of approving it.")
    parser.add_argument("--list", action="store_true", help="List the slots in the batch and exit.")
    parser.add_argument("--max-retries", type=int, default=10)
    args = parser.parse_args()

    if args.scan_manual:
        return 0 if scan_manual_uploads(approve=not args.keep_pending) == 0 else 2

    if args.manual:
        if not args.slot:
            print("--manual needs --slot.")
            return 1
        batch_id = args.batch or upcoming_batch_id(args.slot)
        if not batch_id:
            print(f"No upcoming '{args.slot}' post found. Pass --batch.")
            return 1
        entry = use_manual_image(batch_id, args.slot, args.manual, approve=not args.keep_pending)
        return 0 if entry and entry["caption"] else 2

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
