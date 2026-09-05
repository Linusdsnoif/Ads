"""
generate_product_images.py

Generates AI lifestyle/commercial photos for randomly selected products using
the Gemini image model, given local reference product photos.

Produces 4 images per run:
  - 3 images in a generic, casual setting (using each product's tailored prompt)
  - 1 image of a 4th, distinct product styled for an Arabic-region audience,
    with demonstrators in modest/strict traditional dress (abaya + headscarf
    for women, thawb for men) and a Middle-Eastern-appropriate setting.

Setup
-----
    pip install google-genai pillow

    # Set your API key as an environment variable (do NOT hardcode it):
    export GOOGLE_API_KEY="your-key-here"        # macOS/Linux
    setx GOOGLE_API_KEY "your-key-here"           # Windows (new shell needed after)

Usage
-----
    python generate_product_images.py
    python generate_product_images.py --base-folder "Product images" --output-folder output_models
    python generate_product_images.py --num-casual 3 --seed 42
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import getpass
import time
from io import BytesIO
from pathlib import Path

from PIL import Image
from google.genai import Client, types
from dotenv import load_dotenv

load_dotenv()
# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("product_image_gen")

# --------------------------------------------------------------------------- #
# Static configuration
# --------------------------------------------------------------------------- #
MODEL_NAME = "gemini-3.1-flash-image"

PRODUCT_LIST = [
    "Automatic Nail Clipper(ENC)",
    "Baby Nail File(BNF)",
    "Baby Sculpting Device(BSM)",
    "Baby Stroller Organizer(BSO)",
    "Blue Stroller Cup Holder(Btray)",
    "Breast Pumps(BP)",
    "Breathable Baby Carrier(BBC)",
    "Breathable Baby CarrierM(BCM)",
    "Detachable Cup Holder(DCH)",
    "Gray Baby Carrier(GBC)",
    "Gray stroller cup holder(Gtray)",
    "Gray Stroller Organizer(GSO)",
    "Inflatable Baby Seat(IBS)",
    "LED Beauty Mask(LBM)",
]

COLOR_AGE_PAIRS = [
    {"color": "purple", "age": "an infant between 0 and 12 months old"},
    {"color": "yellow", "age": "a toddler between 1 and 3 years old"},
    {"color": "pink", "age": "a young child between 3 and 6 years old"},
    {"color": "grey", "age": "a baby for a polishing session"},
]

# Shared closing instructions appended to every prompt, matching the notebook's
# original fallback/default guidance (kept so every product benefits from it,
# not just ones missing a custom entry).
GLOBAL_GUIDANCE = (
    "Carefully analyze all reference images, and double check the output image to make sure it fits the prompt and product designs."
    "Ensure the guardians are random ethnicies and faces. No repeat faces from reference images."
    "Ensure the interaction between the demonstrator and the products fits logic and physics. "
    "If the product is a cup holder, do not show the clamp in the image; make sure it's hidden and parallel to the "
    "side handle, and make sure there is only one stroller in the image."
    "If the product is a Baby Carrier or Inflatable Seat, double check the brand logo LUFFCABO, and the baby must "
    "face outward and look at the camera, and ensure the baby is sitting properly in the product. "
    "If the product is the Automatic Nail Clipper, ensure the device is middle-finger long. "
    "If the product is the Baby Sculpting Device, ensure there are only five white buttons embedded within the black screen. "
    "Please generate the image carefully with details such as sizing and color matching. "
    "Ensure there is only one guardian in the image at a time, and all body features should stay normal and fit human anatomy. Guardians should only have 2 hands in the frame."
)

# Instructions layered on top of a product's normal prompt to produce the
# Arabic-region / strict-dress-code variant.
ARABIC_DRESS_CODE_OVERRIDE = (
    "\n\nREGIONAL STYLING OVERRIDE (Arabian Gulf market, strict modest dress code):\n"
    "Change ONLY the demonstrator's clothing, ethnicity/styling, and the background setting to fit a conservative "
    "Gulf Arab household — do NOT change the product's design, color, shape, logo, or placement described above.\n"
    "- If the demonstrator is a woman: she wears a traditional Saudi-style abaya — a long, loose, full-length black "
    "outer cloak worn over her regular clothes — paired with a matching headscarf (hijab) that covers her hair. "
    "Only her face and hands are visible. No form-fitting or short clothing.\n"
    "- If the demonstrator is a man: he wears a thawb — a long-sleeved, ankle-length white or softly colored robe "
    "(traditional Gulf Arab dress) — and may wear a simple white or checkered head covering.\n"
    "- The demonstrator should be of Middle Eastern / Arab appearance.\n"
    "- The setting should read as an upscale Gulf Arab home or family space: warm neutral or gold-toned decor, "
    "majlis-style low seating, arabesque or geometric patterned textiles or wall art, soft warm lighting.\n"
    "- Keep the same product interaction, framing, and photorealistic commercial quality described above; this is "
    "purely a wardrobe- and setting-region change, not a different scene concept."
)

# --------------------------------------------------------------------------- #
# Per-product prompts (unchanged from the notebook, aside from the
# `{chosen_color}` / `{chosen_age}` templating being resolved once up front)
# --------------------------------------------------------------------------- #
def build_custom_prompts(chosen_color: str, chosen_age: str) -> dict[str, str]:
    return {
        "Automatic Nail Clipper": (
            "Expert lifestyle product photographer, tasked with a photorealistic, natural lifestyle portrait of an adult using an ultra-compact electronic automatic nail care device." 
            "The device is extremely compact and small. Demonstrator can easily hold it using thumb and index finger." 
            "Refer carefully to the form factor in the reference images, specifically the integrated, non-protruding circular grooming slot on the top surface." 
            "The scene features a smiling male or female, aged 20 to 60 of random ethnicities, in a softly lit, warm residential setting, such as a cozy home vanity, a clean natural-light bathroom, or a comfortable bedroom seating area." 
            "The camera framing captures the person's face, upper body, and both hands in a natural, relaxed posture, with varied hairstyles and casual clothing styles suitable for the setting." 
            "The demonstrator is holding the tiny device delicately with the person's fingers, demonstrating its use by gently placing the person's opposite fingertip against the smooth styling surface." 
            "The device has a smooth, contoured, silver-grey and black body with NO protruding lever parts," 
            "featuring an integrated circular grooming area and clear window on the top face and also two circular grey button at at the center of the device." 
            "The background features a soft, diffused aesthetic with a shallow depth of field, keeping the focus on the person's interaction and natural smile." 
            "High-quality photorealistic lighting on the device, smooth skin, and perfectly manicured nails. NO Brand Logo or Brand Text." 
            "Strictly follow the product design from references."
            "The demonstrator should only have 2 hands in the frame"
        ),
        "Baby Nail File": (
            f"""
            You are an expert product photographer. Create a luxurious, soft-focus lifestyle commercial image of a gentle electric baby nail file being used by a smiling adult guardian on a child aged {chosen_age}'s tiny finger.
            Ensure the Baby nail file is being used on the child's own finger.
            Ensure there are no partial guardian or ghost in the frame. No hands coming out of nowhere.
            There should only be one guardian and one baby in the image. 
            The background should be a minimalist, modern nursery setting with clean lines, Scandinavian design, or warm pastel tones, featuring various plush textiles. 
            Soft, diffuse natural light, close-up details on the file's material, photorealistic, 8k. 
            The product body is entirely yellow with a perfectly smooth, seamless body and flush edges. 
            The top surface nail file is a circular flat disc, and the very top surface color is strictly {chosen_color}, and it is being used gently to trim the child's nail. 
            The device features only a simple duck graphic. 
            Crucially, the entire image surface is clean and completely free of any text, brand names, or logos.
            The guardian should have only 2 hands.
            The baby should have only 2 hands.
            """
        ),
        "Baby Sculpting Device": (
            f"""
            A professional commercial product photograph in a luxury setting, rendered in ultra-realistic 8k resolution with shallow depth of field and soft ambient indoor lighting in gentle pastel tones. 
            The scene is a clean changing station countertop with varying marble patterns, and features a smiling woman, of random ethnicities and ages from young adult to mid-30s, well-seated. 
            She is holding the single, only baby facial sculpting device in the entire scene against her cheek, jawline, or under her eye to demonstrate its use.
            The device is straight vertical and not bendable at all. It should remain a straight vertical device in the frame.
            Ensure the product matches the form from the reference image.
            It has a single, dark, circular display face on top. 
            Crucially, embedded within this dark display screen, there is a distinct curved array of exactly 5 white, arc-shaped control buttons. 
            The device is held with the top display vertical to the bottom.
            On the countertop in the foreground, among the crystal-clear reflections, a curated collection of high-end baby accessories (such as a wooden brush, organic muslin cloths, a single boutique lotion bottle, and a different colored storage pouch) is arranged, without any additional freestanding devices. 
            There are absolutely no brand logos or text on the device, the woman, or any accessories. 
            There is no baby face image on the device. 
            There is only one single device in the whole frame, and it is in the woman's hand.
            **Carefully reference the images, and ensure there are absolutely only FIVE buttons on top of the circular display screen**
            The demonstrator should have only 2 hands.
            """
        ),
        "Baby Stroller Organizer": (
            "You are an expert product photographer"
            "Collect all reference images and analyze them carefully then you shoot generate a"
            "premium commercial placement shot of a sophisticated, durable fabric baby stroller organizer attached "
            "to the leather-wrapped handle of an expensive urban stroller. The organizer is packed with organized "
            "baby essentials (bottles, wipes, small toys). Blurred background of a chic metropolitan cafe patio,"
            "bright daylight, commercial quality, sharp detail focus."
            "Create a unique image that generate a unique scenario fitting the product"
            "Generate new things that being put in the organizer, do not put the same thing always in the stroller organizer"
            "The demonstrator should be either a woman or man **of diverse ethnicities and across a broad age range (e.g., from young adult to mid-50s)"
            "**NO Brand Logo or Brand Text needed on the image**"
            "**Strictly follow the product design from references**"
            "**There are no pocket or pouch cup holder on both sides, strictly follow the designs from the reference images**"
            "The demonstrator should have only 2 hands."
        ),
        "Blue Stroller Cup Holder": (
            "A photorealistic, medium-distance side-profile photograph of a random age (age 20 to 40) and Arabic Regions mom pushing a luxury stroller. Only 1 guardian should be in the frame." 
            "No other partial guardian should appear." 
            "Ensure the cup holder is in the frame." 
            "The gurdianc should be either a man or woman and fully visible in the frame, walking and smiling, with her hands on the stroller handle." 
            "The stroller has a grey fabric canopy and a silver metal frame." 
            "Cup holder center should securely attached to the stroller handle frame, parallel to the frame, is the black plastic double-section cup holder and snack tray unit." 
            "The camera angle captures the side profile of the unit, which is entirely smooth and unbranded on this visible surface, with zero text, zero logos, and zero protruding parts, knobs, or visible clamps;" 
            "The attachment clamp is completely hidden behind the unit." 
            "The cup holder holds a baby water bottle and the tray section is filled with the random snacks)." 
            "Bright daylight illuminates the scene."
            "Ensure there is only one stroller in the shot"
        ),
        "Breast Pumps": (
            "You are an expert product photographer"
            "A smiling woman, age 25 to 35 of diverse ethnicities, is seated on a comfortable bed in a peaceful,"
            "minimalist bedroom with soft morning window daylight. She is wearing a soft grey ribbed tank top with a modern, ergonomic, wireless breast pump discreetly" 
            "tucked inside the neckline of her top, demonstrating its wearable, hands-free design." 
            "She has one hand gently resting near the pump with a natural, peaceful expression. Warm neutral tones, photorealistic, 8k resolution, highly detailed."
            "**NO Brand Logo or Brand Text needed on the image**"
            "Create a unique image that generate a unique scenario fitting the product"
            "**Strictly follow the product design from references**"
            "**Ensure you have the breast pumps placed on top of the breasts with correct position and inside and covered by the tops**"
            "The breast pumps has a circular black screens on top displaying time with four white buttons featuring different features"
            "The demonstrator should only have 2 hands"
        ),
        "Breathable Baby Carrier(BBC)": (
            f"""Role & Style: You are an expert product photographer. 
            There should strictly only has one baby and a guardian in the frame.
            Generate a single, vibrant, dynamic high-end commercial lifestyle photograph. Do not generate multiple angles; it should only contain one shot.
            Subject & Scene: The image features exactly one guardian and one baby. The guardian should either be a smiling woman or a man, aged 25-40, of random ethnicity, comfortably wearing an ergonomic baby carrier. 
            The setting should be a random lifestyle scenario where the carrier is naturally needed, such as a sunny outdoor farmers market, a supermarket, at home, or a park. 
            The guardian should have a casual hairstyle and clothing style suitable for the chosen setting. 
            The guardian should do a natural, casual posture that fits the scenario to show the convenience of the product.
            **The Baby must face outward and look at directly at the camera and looks just fine, and make sure the baby is sitting in the baby carrier**
            Product Design (Strictly follow this): The baby carrier's main body is made of a smooth, solid black nylon/canvas material—do not make the entire carrier mesh, and a storiage zipper bag on the right side of the waist belt.
            The top head-support panel is folded down, showing a smooth light gray exterior, and revealing a small rounded breathable light gray mesh below the fold panel.
            The shoulder straps and thick waist belt are black. 
            **The fastening loop connecting the main panel to the shoulder straps must be white connecting black buckles.**
            Branding: The brand logo must be perfectly legible and clearly seen in white color and not in white square frames. It should just naturally paste on the product. 
            The logo consists of a anchor symbol positioned directly above the text "LUFFCABO".
            This logo must be accurately placed in two specific locations: small brand logo centered on the smooth white beneath the round breathable mesh panel size at (1.5cm x 1.5cm), and very tiny logo at the corner of the side storage zipper bag on the waist belt (0.5cm x 0.5cm) without in any frame, naturally paste on the product. 
            Carefully reference the reference images to make sure the product design is identical.
            Make sure the text LUFFCABO is spelled correctly. Ensure the scene is random and fitted for the product use
            The guardian should have only 2 hands.
            The baby should have only 2 hands.
            """
        ),
        "Breathable Baby CarrierM(BCM)": (
            "You are an expert product photographer. Collect all reference images and analyze them carefully." 
            "Generate a natural-light, heartwarming commercial lifestyle photograph featuring a smiling woman or a man with a range of 25-40 ages, of random ethnicity." 
            "The image features exactly one guardian and one baby."
            "**The Baby must face outward and look at directly at the camera**"
            "The guardian is a smiling woman or man, aged 25-40, of random ethnicity, comfortably wearing an ergonomic baby carrier."
            "The guardian should do some casual posture that fits the scenario to show the convenience of the product."
            "The setting should be a random lifestyle scenario where the carrier is naturally needed, such as an outdoor street, supermarket,at a lovely home setting, or a park." 
            "The camera framing captures her upper body and both hands in a natural, relaxed posture." 
            "The guardian should have a hairstyle and clothing style suitable for the chosen setting."
            "The camera framing captures her upper body and her hands, which are positioned naturally and relaxed at the guardian's sides supporting the baby." 
            "The high-resolution details showcase the intricate mesh material of a specific light grey and white structured ergonomic, premium breathable baby carrier." 
            "The carrier is in an outward-facing configuration, and the baby, awake and looking at the camera, wears a light-colored onesie. Strictly follow the specific product design seen in the references." 
            "A single, distinct square brand logo patch is central to the lower part of the carrier, featuring a detailed anchor icon at the top and the text 'LUFFCABO' clearly and correctly displayed below the anchor within the same square border." 
            "This setting is a place where the Breathable Baby Carrier is needed. This is a single, direct shot."
            "**Ensure the brand logo text is legibly and correctly displayed as 'LUFFCABO'.**"
            "The guardian should have only 2 hands."
            "The baby should have only 2 hands."
        ),
        "Detachable Cup Holder": (
            "A photorealistic, medium-distance side-profile photograph of a smiling woman or man with random age (age 20 to 40) and ethnicites(any color) pushing a luxury stroller with a baby sitting in the stroller." 
            "Only 1 guardian should be in the frame. No other partial guardian should appear. Ensure the cup holder is in the frame." 
            "The guardian is fully visible in the frame, walking and smiling, with her hands on the stroller handle." 
            "The stroller has a grey fabric canopy and a silver metal frame." 
            "Cup Holder center should securely attached to the stroller handle frame, parallel to the frame, is the black plastic double-section cup holder and snack tray unit." 
            "The camera angle captures the side profile of the unit, which is entirely smooth and unbranded on this visible surface, with zero text, zero logos, and zero protruding parts, knobs, or visible clamps;" 
            "the attachment clamp is completely hidden behind the unit. The cup holder holds a baby water bottle and the tray section is filled with the random snacks)." 
            "Bright daylight illuminates the scene."
            "Ensure there is only one stroller in the shot"
            "The guardian should have only 2 hands."
            "The baby should have only 2 hands."
        ),
        "Gray Baby Carrier": (
            f"""Role & Style: You are an expert product photographer. 
            There should strictly only has one baby and a guardian in the frame.
            Generate a single, vibrant, dynamic high-end commercial lifestyle photograph. 
            Do not generate multiple angles; it should only contain one shot.
            Subject & Scene: The image features exactly one guardian and one baby. 
            The guardian is a smiling woman or man, aged 25-40, of diverse ethnicity, comfortably wearing an ergonomic baby carrier. 
            The setting should be a random lifestyle scenario where the carrier is naturally needed, such as a sunny outdoor farmers market, a supermarket, at home or a park. 
            The guardian should have a casual hairstyle and clothing style suitable for the chosen setting. 
            The guardian should do a natural, casual posture that fits the scenario to show the convenience of the product.
            **The Baby must face outward and look at directly at the camera and looks just fine, and make sure the baby is sitting in the baby carrier**
            Product Design (Strictly follow this): The baby carrier's main body is made of a smooth, solid light gray nylon/canvas material—do not make the entire carrier mesh, and a storiage zipper bag on the right side of the waist belt.
            The top head-support panel is folded down, showing a smooth light gray exterior, and revealing a small rounded breathable light gray mesh below the fold panel.
            The shoulder straps and thick waist belt are solid light gray. 
            The fastening loop connecting the main panel to the shoulder straps must be light gray connecting black circular buckles.
            Branding: The brand logo must be perfectly legible and clearly seen in light gray color and not in white square frames. It should just naturally paste on the product. 
            The logo consists of a anchor symbol positioned directly above the text "LUFFCABO".
            This logo must be accurately placed in two specific locations: small brand logo centered on the smooth light gray beneath the round breathable mesh panel size at (1.5cm x 1.5cm), and very tiny logo at the corner of the side storage zipper bag on the waist belt (0.5cm x 0.5cm) without in any frame, naturally paste on the product. 
            Carefully reference the reference images to make sure the product design is identical.
            Make sure the text LUFFCABO is spelled correctly.
            The guardian should have only 2 hands.
            The baby should have only 2 hands.
            """
        ),
        "Gray stroller cup holder": (
            "A photorealistic, medium-distance side-profile photograph of a smiling man or woman random age (age 20 to 40) and ethnicites(any color) pushing a luxury stroller with a baby sitting inside the stroller." 
            "Only 1 guardian should be fully visible in the frame. No other partial guardian should appear." 
            "Ensure the cup holder is in the frame." 
            "The guardian is partially visible, walking and smiling, with the person's hands on the stroller handle." 
            "The stroller has a grey fabric canopy and a silver metal frame." 
            "Cup Holder center should securely attached to the stroller handle frame, parallel to the frame, is the black plastic double-section cup holder and snack tray unit." 
            "The camera angle captures the side profile of the unit, which is entirely smooth and unbranded on this visible surface, with zero text, zero logos, and zero protruding parts, knobs, or visible clamps;" 
            "the attachment clamp is completely hidden behind the unit. The cup holder holds a baby water bottle and the tray section is filled with the random snacks)." 
            "Bright daylight illuminates the scene."
            "Ensure there is only one stroller in the shot"
            "The guardian should have only 2 hands."
            "The baby should have only 2 hands."
        ),
        "Gray Stroller Organizer": (
            "You are an expert product photographer"
            "Collect all reference images and analyze them carefully then you shoot generate a"
            "premium commercial placement shot of a sophisticated, durable fabric baby stroller organizer attached "
            "to the leather-wrapped handle of an expensive urban stroller. The organizer is packed with organized "
            "baby essentials (bottles, wipes, small toys). Blurred background of a chic metropolitan cafe patio,"
            "bright daylight, commercial quality, sharp detail focus."
            "Create a unique image that generate a unique scenario fitting the product"
            "Generate new things that being put in the organizer, do not put the same thing always in the stroller organizer"
            "The demonstrator should be a smiling man or woman **of diverse ethnicities and across a broad age range (e.g., from young adult to mid-50s)"
            "**NO Brand Logo or Brand Text needed on the image**"
            "**Strictly follow the product design from references**"
            "There are no cup holder on sides, strictly follow the designs from the reference images"
            "The demonstrator should have only 2 hands."
        ),
        "Inflatable Baby Seat": (
            "You are an expert product photographer"
            "Collect all reference images and analyze them carefully then you shoot generate"
            "a warm, inviting commercial lifestyle shot of an inflatable baby seat resting safely on a soft living room rug. "
            "Natural ambient sunlight, cheerful modern home interior, crisp textures, sharp focus, 8k resolution." 
            "The primary logo on the inflatable seat must be rendered clearly and visible."
            "Nice to have baby playfully sitting on it and behaving some random happy faces or emotions and possibly holding some toys"
            "The logo LUFFCABO with an anchor on top is needed to be shown on the product in the black color"
            "**The Brand logo must be clearly seen, LUFFCABO and an anchor on top need to be clearly seen**"
            "Please create a high resolution image and make sure"
            "Create the image at place where the Breathable Baby Carrier is needed"
            "Create a unique image that generate a unique scenario fitting the product"
            "Strictly follow the product design from references"
            "Ensure the gurdian does not goes through the inflatable baby seat, has the guardian around the baby"
            "Double check the logo text LUFFCABO"
            "The guardian should have only 2 hands."
            "The baby should have only 2 hands."
        ),
        "LED Beauty Mask": (
            "You are an expert product photographer"
            "Collect all reference images and analyze them carefully then you shoot generate a"
            "luxury cosmetic product commercial photograph featuring a sleek, multi-layered LED beauty mask. The mask is "
            "displayed on a polished marble vanity top in a high-end modern bathroom. Soft, diffuse light, close-up details "
            "on the LED arrays within the material, photorealistic, 8k."
            "The output image should purely just an LED mask put on the demonstrator face without any effect"
            "Have a women **of diverse ethnicities and across a broad age range (e.g., from young adult to mid-40s) holding it or putting on their face is the best"
            "**NO Brand Logo or Brand Text needed on the image**"
            "Create a unique image that generate a unique scenario fitting the product"
            "Strictly follow the product design from references"
            "There should only have one woman in the frame"
            "The demonstrator should have only 2 hands."
        ),
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def clean_key(product_name: str) -> str:
    """Strip the trailing '(ABC)' code suffix from a product folder name."""
    return product_name.split("(")[0].strip()


def load_reference_images(product_dir: Path) -> list[Image.Image]:
    """Load every image file found in a product's reference folder."""
    images: list[Image.Image] = []
    if not product_dir.is_dir():
        log.warning("Product folder not found: %s", product_dir)
        return images

    for f in sorted(product_dir.iterdir()):
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        try:
            images.append(Image.open(f))
        except Exception as e:
            log.warning("Skipping unreadable image %s: %s", f.name, e)
    return images


def resolve_prompt(product_name: str, custom_prompts: dict[str, str]) -> str:
    """Get the tailored prompt for a product, falling back to a generic one."""
    base_key = clean_key(product_name)
    return custom_prompts.get(
        base_key,
        f"Professional commercial advertising photography of a parent using a {base_key}. {GLOBAL_GUIDANCE}",
    )


def next_output_index(output_folder: Path, clean_name: str) -> int:
    """Find the next free numeric suffix for a product's output filename."""
    existing = []
    prefix = f"modeled_{clean_name}_"
    for f in output_folder.iterdir():
        if f.name.startswith(prefix) and f.suffix == ".jpg":
            try:
                existing.append(int(f.stem.rsplit("_", 1)[-1]))
            except ValueError:
                pass
    return max(existing) + 1 if existing else 1


def generate_image(
    client: Client,
    ref_images: list[Image.Image],
    prompt_text: str,
    max_retries: int = 10,
) -> Image.Image | None:
    """Call the Gemini image model with retries; return a PIL image or None."""
    contents = ref_images + [
        f"{prompt_text} Use the provided reference images to understand the exact product "
        "(shape, color, logo, material) and generate ONE single best-quality, 8k resolution, and most polished "
        "commercial lifestyle photograph of it. Do not generate multiple images — return only one. "
        "There will be no human check after you finish generating, so make sure you always generate the best "
        "quality that fits the description. Please generate the image carefully with details such as sizing and "
        "color matching."
    ]

    for attempt in range(1, max_retries + 1):
        try:
            log.info("Requesting render via %s (attempt %d/%d)...", MODEL_NAME, attempt, max_retries)
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    temperature=0.50,
                    top_p=0.95,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                        ),
                    ],
                ),
            )

            if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                raise RuntimeError(f"API returned an empty response (finish_reason={reason}); likely safety-blocked.")

            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    return Image.open(BytesIO(part.inline_data.data))

            raise RuntimeError("No image data returned in response.")

        except Exception as e:
            log.warning("Attempt %d failed: %s", attempt, e)
            if attempt < max_retries:
                wait_time = 3 * attempt
                log.info("Cooling down %ds before retrying...", wait_time)
                time.sleep(wait_time)
            else:
                log.error("Giving up after %d attempts.", max_retries)

    return None


def process_product(
    client: Client,
    base_folder: Path,
    output_folder: Path,
    product_name: str,
    custom_prompts: dict[str, str],
    arabic_variant: bool,
    max_retries: int,
) -> Path | None:
    """Generate and save one image for one product. Returns the output path, or None on failure."""
    product_dir = base_folder / product_name
    base_key = clean_key(product_name)

    log.info("=" * 60)
    log.info(
        "Processing: %s%s",
        product_name,
        "  [ARABIC / MODEST DRESS VARIANT]" if arabic_variant else "  [casual variant]",
    )

    ref_images = load_reference_images(product_dir)
    if not ref_images:
        log.warning("No usable reference images for %s. Skipping.\n", product_name)
        return None
    log.info("Loaded %d reference image(s).", len(ref_images))

    prompt_text = resolve_prompt(product_name, custom_prompts)
    if arabic_variant:
        prompt_text += ARABIC_DRESS_CODE_OVERRIDE

    generated_image = generate_image(client, ref_images, prompt_text, max_retries=max_retries)
    if generated_image is None:
        log.error("Failed to generate an image for %s.\n", product_name)
        return None

    clean_name = base_key.replace(" ", "_")
    if arabic_variant:
        clean_name += "_ARABIC"

    output_folder.mkdir(parents=True, exist_ok=True)
    index = next_output_index(output_folder, clean_name)
    output_path = output_folder / f"modeled_{clean_name}_{index}.jpg"

    generated_image.convert("RGB").save(output_path, "JPEG")
    log.info("Saved: %s\n", output_path)
    return output_path


def generate_descriptions(saved_paths: list[Path], client: Client):
    log.info("=" * 60)
    log.info("Starting automated social media description generation...")
    
    output_folder = Path("output_descriptions")
    output_folder.mkdir(parents=True, exist_ok=True)

    # Clean up old txt files for a fresh batch
    for old_file in output_folder.glob("*.txt"):
        old_file.unlink()
    log.info(f"Cleared old files from '{output_folder}'.")

    PRODUCT_LINKS = {
        "Automatic Nail Clipper": "https://luffcabo.com/products/electric-nail-clipper",
        "Baby Nail File": "https://luffcabo.com/products/baby-nail-file",
        "Baby Sculpting Device": "https://luffcabo.com/products/body-sculpting-machine",
        "Baby Stroller Organizer": "https://luffcabo.com/products/versatile-stroller-organizer",
        "Blue Stroller Cup Holder": "https://luffcabo.com/products/universal-stroller-cup-holder",
        "Breast Pumps": "https://luffcabo.com/products/electric-hands-free-breast-pump",
        "Breathable Baby Carrier": "https://luffcabo.com/products/all-season-baby-carrier",
        "Breathable Baby CarrierM": "https://luffcabo.com/products/luffcabo-mesh-baby-carrier",
        "Detachable Cup Holder": "https://luffcabo.com/products/detachable-stroller-cup-holder",
        "Gray Baby Carrier": "https://luffcabo.com/products/all-season-baby-carrier?variant=41562902167648",
        "Gray stroller cup holder": "https://luffcabo.com/products/universal-stroller-cup-holder",
        "Gray Stroller Organizer": "https://luffcabo.com/products/durable-stroller-organizer",
        "Inflatable Baby Seat": "https://luffcabo.com/products/inflatable-baby-seat",
        "LED Beauty Mask": "https://luffcabo.com/products/led-beauty-mask"  
    }

    # Configuration Pools
    post_1_pool = {"country": "USA", "cities": ["Los Angeles", "Seattle", "New York", "Chicago", "Miami", "San Francisco", "Austin", "Denver"], "language": "English", "day": "Tuesday"}
    post_2_pool = [
        {"country": "Saudi Arabia", "cities": ["Riyadh", "Jeddah", "Mecca", "Medina"], "language": "Arabic", "day": "Sunday"},
        {"country": "United Arab Emirates", "cities": ["Dubai", "Abu Dhabi", "Sharjah"], "language": "Arabic", "day": "Sunday"}
    ]
    post_3_options = [
        {"country": "UK", "cities": ["London", "Manchester", "Edinburgh", "Birmingham", "Bristol"], "language": "English", "day": "Saturday"},
        {"country": "Australia", "cities": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"], "language": "English", "day": "Saturday"}
    ]

    post_4_options = [
        {"country": "France", "cities": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Bordeaux"], "language": "French", "day": "Thursday"},
        {"country": "Germany", "cities": ["Berlin", "Munich", "Frankfurt", "Hamburg", "Cologne", "Stuttgart"], "language": "German", "day": "Thursday"},
        {"country": "Sweden", "cities": ["Stockholm", "Gothenburg", "Malmö"], "language": "Swedish", "day": "Thursday"},
        {"country": "Netherlands", "cities": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht"], "language": "Dutch", "day": "Thursday"},
        {"country": "Italy", "cities": ["Rome", "Milan", "Naples", "Turin", "Florence"], "language": "Italian", "day": "Thursday"},
        {"country": "Belgium", "cities": ["Brussels", "Antwerp", "Ghent", "Liege"], "language": "French", "day": "Thursday"}
    ]

    casual_count = 0

    for i, img_path in enumerate(saved_paths):
        # 1. Parse the generated file name cleanly
        raw_name = img_path.stem  # e.g., modeled_Baby_Nail_File_ARABIC_1
        
        if raw_name.startswith("modeled_"):
            raw_name = raw_name[len("modeled_"):]
            
        name_parts = raw_name.split('_')
        
        # Remove the numeric index at the end
        if name_parts[-1].isdigit():
            name_parts = name_parts[:-1]
            
        # Detect if it's the Arabic variant and remove the tag
        is_arabic = False
        if len(name_parts) > 0 and name_parts[-1] == "ARABIC":
            is_arabic = True
            name_parts = name_parts[:-1]
            
        base_clean_key = " ".join(name_parts)
        
        # Link resolution
        product_link = PRODUCT_LINKS.get(
            base_clean_key,
            f"https://luffcabo.com/products/{base_clean_key.lower().replace(' ', '-')}"
        )

        # 2. DETERMINE AUDIENCE CONFIGURATION
        if is_arabic:
            # Arabic image always pulls from post_2_pool (Saudi Arabia / UAE)
            selection = random.choice(post_2_pool)
            country = selection["country"]
            lang = selection["language"]
            day = selection["day"]
            city = random.choice(selection["cities"])
        else:
            # Distribute the 3 casual images across the 3 remaining pools
            if casual_count == 0:
                country = post_1_pool["country"]
                lang = post_1_pool["language"]
                day = post_1_pool["day"]
                city = random.choice(post_1_pool["cities"])
            elif casual_count == 1:
                selection = random.choice(post_3_options)
                country = selection["country"]
                lang = selection["language"]
                day = selection["day"]
                city = random.choice(selection["cities"])
            else:
                selection = random.choice(post_4_options)
                country = selection["country"]
                lang = selection["language"]
                day = selection["day"]
                city = random.choice(selection["cities"])
            
            casual_count += 1

        log.info(f"Generating caption for: {img_path.name}")
        log.info(f"Targeting: {lang} | {city}, {country} | {day} 7:00 AM")
        
        try:
            img = Image.open(img_path)
        except Exception as e:
            log.error(f"Skipping unreadable image {img_path.name}: {e}")
            continue

        text_prompt = f"""
        Act as a 'Social Media Post Caption' creator and SEO Specialist for LUFFCABO. Your goal is to generate an engaging, attractive, and search-optimized caption and alt text for this single image.

        Analyze the attached image of the '{base_clean_key}'.

        TARGET CONFIGURATION FOR THIS POST:
        - Location: {city}, {country}
        - Schedule: {day}, 7:00 AM Local Time
        - Language: {lang}

        === Behaviors and Rules ===

        1. Caption Composition:
           a) Write a short, engaging paragraph in a 'fun, chill, and attractive' tone that highlights the lifestyle or product appeal.
           b) Incorporate highly Amazon & Google-search-recommended product keywords naturally within the text.
           c) Mandatory Inclusion: You must include the exact phrase (translated organically into {lang}): 'Explore it Now: {product_link}'. The URL must remain exactly as provided.
           d) Hashtags: Conclude with exactly 5 hashtags in this exact format:
              - #LUFFCABO
              - # [1 English core keyword for {base_clean_key}]
              - # [1 Core keyword in {lang}]
              - # [1 Broader lifestyle/product keyword in {lang}]
              - # [1 Broader lifestyle/product keyword in {lang}]
           e) Length: The ENTIRE caption must be strictly under 500 characters.

        2. Alt Text Creation:
           a) Write a concise, descriptive sentence for the alt text field in {lang}.
           b) Seamlessly embed high-ranking Amazon & Google search product keywords.
           c) Focus on clarity for visually impaired users while maintaining SEO benefits.
           d) CRITICAL: NEVER use a period at the end of the alt text.

        3. Language and Style:
           a) Write the entire post (except the English hashtag and URL) strictly in {lang}.
           b) Maintain a consistent brand voice: approachable, trendy, inviting, enthusiastic but relaxed ('chill').
           c) Use emojis where appropriate to enhance the 'fun' vibe.
           d) Keep the content concise and optimized for quick scrolling on social feeds.

        Format your output EXACTLY like this:

        Location Tag: {city}, {country}
        Schedule: {day} 7:00 AM Local Time
        Language: {lang}

        Caption:
        [Your caption here]
        [The 5 Hashtags based on the rule]

        Alt Text:
        [Your alt text here]
        """

        max_manual_retries = 3
        for attempt in range(1, max_manual_retries + 1):
            try:
                log.info(f"  - Requesting text via Gemini (Attempt {attempt}/{max_manual_retries})...")
                response = client.models.generate_content(
                    model='gemini-3.5-flash', # Or replace with your specific string if needed
                    contents=[text_prompt, img]
                )
                
                description = response.text
                
                safe_country = country.replace(" ", "")
                txt_filename = f"desc_{img_path.stem}_{lang}_{safe_country}.txt"
                txt_output_path = output_folder / txt_filename
                
                with open(txt_output_path, "w", encoding="utf-8") as text_file:
                    text_file.write(description)
                    
                log.info(f"  - Saved caption to: {txt_output_path}")
                break # Break out of retry loop on success
                
            except Exception as e:
                log.warning(f"  ⚠️ Attempt {attempt} failed: {e}")
                if attempt < max_manual_retries:
                    sleep_time = attempt * 5 
                    time.sleep(sleep_time)
                else:
                    log.error(f"  ❌ All manual retry attempts exhausted for {img_path.name}.")

 
# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-folder", default="Product images", help="Folder containing per-product reference image subfolders.")
    parser.add_argument("--output-folder", default="output_models", help="Folder to save generated images into.")
    parser.add_argument("--num-casual", type=int, default=3, help="How many casual-setting products/images to generate.")
    parser.add_argument("--no-arabic", action="store_true", help="Skip the 4th, Arabic/modest-dress image.")
    parser.add_argument("--max-retries", type=int, default=10, help="Max retries per image generation call.")
    parser.add_argument("--cooldown", type=float, default=8.0, help="Seconds to sleep between products.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed, for reproducible product selection.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        try:
            api_key = getpass.getpass("Enter your Google API key (input hidden): ").strip()
        except Exception:
            api_key = input("Enter your Google API key: ").strip()

    if not api_key:
        log.error("No API key provided. Set GOOGLE_API_KEY or enter it when prompted.")
        return 1

    client = Client(api_key=api_key)

    base_folder = Path(args.base_folder)
    output_folder = Path(args.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # Calculate total distinct products needed (3 casual + 1 Arabic = 4)
    total_needed = args.num_casual + (0 if args.no_arabic else 1)
    if total_needed > len(PRODUCT_LIST):
        log.error("Requested %d distinct products but only %d are defined.", total_needed, len(PRODUCT_LIST))
        return 1

    # Grab 4 UNIQUE products from the list
    selected_products = random.sample(PRODUCT_LIST, total_needed)
    
    # Assign the first 3 to casual, and the 4th to Arabic
    casual_products = selected_products[: args.num_casual]
    arabic_product = None if args.no_arabic else selected_products[args.num_casual]

    color_age = random.choice(COLOR_AGE_PAIRS)
    custom_prompts = build_custom_prompts(color_age["color"], color_age["age"])

    log.info("Selected 3 distinct casual products: %s", casual_products)
    if arabic_product:
        log.info("Selected 1 distinct Arabic/modest-dress product: %s", arabic_product)

    saved_paths: list[Path] = []

    # 1. Process the 3 unique products for casual images (1 image each)
    for i, product_name in enumerate(casual_products, start=1):
        path = process_product(
            client, base_folder, output_folder, product_name, custom_prompts,
            arabic_variant=False, max_retries=args.max_retries,
        )
        if path:
            saved_paths.append(path)
        
        # Cooldown between different products
        if i < len(casual_products) or arabic_product:
            log.info("Cooling down %.0fs before the next product...\n", args.cooldown)
            time.sleep(args.cooldown)

    # 2. Process the 4th unique product for the Arabic image (1 image)
    if arabic_product:
        path = process_product(
            client, base_folder, output_folder, arabic_product, custom_prompts,
            arabic_variant=True, max_retries=args.max_retries,
        )
        if path:
            saved_paths.append(path)

    log.info("=" * 60)
    log.info("Done. %d/%d image(s) generated successfully.", len(saved_paths), total_needed)
    for p in saved_paths:
        log.info("  - %s", p)

    if saved_paths:
        generate_descriptions(saved_paths, client)
        
    return 0 if len(saved_paths) == total_needed else 2

if __name__ == "__main__":
    sys.exit(main())
