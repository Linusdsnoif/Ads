"""
tips_posts.py

Parenting-tips infographic posts: 2 a month, on the 1st and 3rd Wednesday.

The text for every topic is written out here instead of generated, so each tip
is accurate and short enough for the image model to spell correctly. After an
image is made, Gemini reads its text back and it is compared word by word with
what was asked for. A garbled image is regenerated (up to 3 tries), and the
result of the check is shown in the review summary.

Add, edit or remove topics in TIPS_TOPICS; the rotation uses them in turn.
Keep headings to 1-4 words and lines to about 7 words, use "and" instead of "&",
and set "product" to a key of PRODUCT_LINKS in generate_product_images.py.
"""

import logging
import re

log = logging.getLogger("product_image_gen")

# Style reference image(s) go in "<base folder>/Parenting Tips/". Optional.
TIPS_FOLDER = "Parenting Tips"

TIPS_TOPICS = [
    {
        "title": "Baby Carrier Selecting Tips",
        "subtitle": "Find the right fit for you and your baby",
        "tips": [
            ("Safety First", "Check the weight limit"),
            ("Prioritize Comfort", "Look for padded straps"),
            ("Adjustable Fit", "Adjusts as your baby grows"),
            ("Easy to Clean", "Choose machine washable fabric"),
            ("Breathable Fabric", "Helps prevent overheating"),
            ("Right Size", "Match your baby's age and size"),
        ],
        "illustration": "a smiling parent wearing a baby in a soft structured baby carrier",
        "product": "Gray Baby Carrier",
        "shop_name": "All Season Baby Carrier",
    },
    {
        "title": "Safe Babywearing Checklist",
        "subtitle": "Keep your little one snug and secure",
        "tips": [
            ("Tight", "Snug straps with no slack"),
            ("In View", "Always see your baby's face"),
            ("Close to Kiss", "Baby's head near your chin"),
            ("Chin Off Chest", "Keep the airway open"),
            ("Supported Back", "Hold baby in a natural position"),
            ("Check Often", "Readjust as your baby moves"),
        ],
        "illustration": "a parent wearing a baby in a light mesh carrier, the baby's face clearly visible",
        "product": "Breathable Baby CarrierM",
        "shop_name": "Mesh Baby Carrier",
    },
    {
        "title": "Stress-Free Nail Care",
        "subtitle": "Gentle care for tiny fingers",
        "tips": [
            ("Calm Moments", "Try while your baby sleeps"),
            ("After Bath Time", "Nails are softer and easier"),
            ("Good Lighting", "See every tiny edge"),
            ("Go Slowly", "One nail at a time"),
            ("Hold Gently", "Press the fingertip away from the nail"),
            ("Make It Routine", "Check nails a few times a week"),
        ],
        "illustration": "a parent gently filing a sleeping baby's tiny fingernails",
        "product": "Baby Nail File",
        "shop_name": "Baby Nail File",
    },
    {
        "title": "Stroller Walk Essentials",
        "subtitle": "Pack smart for easy outings",
        "tips": [
            ("Buckle Up", "Use the harness every time"),
            ("Brakes On", "Lock the wheels when you stop"),
            ("Shade and Layers", "Canopy up, dress for the weather"),
            ("Snacks Within Reach", "Keep drinks and snacks handy"),
            ("Balanced Load", "Follow your stroller's weight limits"),
            ("Spare Supplies", "Diapers, wipes and a spare outfit"),
        ],
        "illustration": "a parent pushing a stroller along a leafy path",
        "product": "Gray Stroller Organizer",
        "shop_name": "Durable Stroller Organizer",
    },
    {
        "title": "Pumping Made Easier",
        "subtitle": "Small habits for busy moms",
        "tips": [
            ("Stay Hydrated", "Keep water within reach"),
            ("Get Comfortable", "Relax your shoulders and breathe"),
            ("Right Fit", "Use the correct flange size"),
            ("Keep It Clean", "Wash pump parts after each use"),
            ("Label and Store", "Date every bottle or bag"),
            ("Find a Rhythm", "Pump at regular times"),
        ],
        "illustration": "a relaxed mother sitting in a cozy armchair with a glass of water",
        "product": "Breast Pumps",
        "shop_name": "Electric Hands-Free Breast Pump",
    },
    {
        "title": "Traveling with a Baby",
        "subtitle": "Plan ahead and travel lighter",
        "tips": [
            ("Wear Your Baby", "Hands free through busy terminals"),
            ("Snacks Ready", "Keep favorites easy to grab"),
            ("Dress in Layers", "Ready for any temperature"),
            ("Plan Breaks", "Time for feeds and stretches"),
            ("Comfort Item", "Bring a familiar toy or blanket"),
            ("Documents Together", "Keep them in one pouch"),
        ],
        "illustration": "a parent wearing a baby in a carrier while pulling a small suitcase",
        "product": "Breathable Baby Carrier",
        "shop_name": "All Season Baby Carrier",
    },
    {
        "title": "Summer Outings with Baby",
        "subtitle": "Stay cool, safe and happy",
        "tips": [
            ("Seek Shade", "Skip the strong midday sun"),
            ("Sun Hat", "Protect face, ears and neck"),
            ("Light Layers", "Loose, breathable cotton clothes"),
            ("Feed Often", "Offer extra feeds in the heat"),
            ("Car Safety", "Never leave baby in a parked car"),
            ("Check Often", "Watch for flushed, sweaty skin"),
        ],
        "illustration": "a parent and a baby in a sun hat resting in the shade of a tree",
        "product": "Breathable Baby CarrierM",
        "shop_name": "Mesh Baby Carrier",
    },
    {
        "title": "Self-Care for New Moms",
        "subtitle": "Looking after you matters too",
        "tips": [
            ("Rest When You Can", "Nap while your baby naps"),
            ("Eat Well", "Keep easy, nourishing snacks nearby"),
            ("Accept Help", "Let others share the load"),
            ("Move Gently", "Short walks once your doctor says OK"),
            ("Me Time", "Ten quiet minutes just for you"),
            ("Talk It Out", "Share how you are feeling"),
        ],
        "illustration": "a mother relaxing on a sofa with a cup of tea",
        "product": "LED Beauty Mask",
        "shop_name": "LED Beauty Mask",
    },
    {
        "title": "Baby Sitting Practice",
        "subtitle": "Support your baby's growing strength",
        "tips": [
            ("Floor Only", "Never on tables, beds or water"),
            ("Head Control First", "Wait until baby holds their head steady"),
            ("Stay Close", "Always supervise your baby"),
            ("Short Sessions", "A few minutes at a time"),
            ("Tummy Time Too", "Builds neck and core strength"),
            ("Play Together", "Toys at your baby's eye level"),
        ],
        "illustration": "a happy baby sitting in a soft floor seat on a play mat with a toy",
        "product": "Inflatable Baby Seat",
        "shop_name": "Inflatable Baby Seat",
    },
    {
        "title": "Hands-Free Parenting Hacks",
        "subtitle": "Get more done, together",
        "tips": [
            ("Wear Your Baby", "Do chores with baby close"),
            ("Prep Ahead", "Pack the bag the night before"),
            ("Snack Station", "Keep snacks in one spot"),
            ("Easy Containers", "Pick lids you can open one handed"),
            ("Supply Baskets", "Essentials ready in every room"),
            ("Ask for Help", "Share the load with others"),
        ],
        "illustration": "a parent wearing a baby in a carrier while watering plants at home",
        "product": "Gray Baby Carrier",
        "shop_name": "All Season Baby Carrier",
    },
    {
        "title": "Diaper Bag Checklist",
        "subtitle": "Never leave home unprepared",
        "tips": [
            ("Diapers and Wipes", "Pack a few extra"),
            ("Spare Outfit", "For baby, and maybe you"),
            ("Feeding Kit", "Bottle, milk or snacks"),
            ("Burp Cloth", "For quick cleanups"),
            ("Changing Pad", "A clean spot anywhere"),
            ("Hand Sanitizer", "Clean hands on the go"),
        ],
        "illustration": "an open bag neatly packed with diapers, a bottle and a small toy",
        "product": "Baby Stroller Organizer",
        "shop_name": "Versatile Stroller Organizer",
    },
    {
        "title": "Healthy Nails for the Family",
        "subtitle": "Simple habits for neat nails",
        "tips": [
            ("Trim Straight Across", "Helps prevent ingrown toenails"),
            ("Smooth the Edges", "File away any rough spots"),
            ("Clean Tools", "Wipe them after every use"),
            ("Moisturize", "Nails and cuticles love it"),
            ("Hands Off", "Avoid biting or picking nails"),
            ("Weekly Check", "Spot problems early"),
        ],
        "illustration": "a parent and a child smiling and showing their neat, clean hands",
        "product": "Automatic Nail Clipper",
        "shop_name": "Electric Nail Clipper",
    },
    {
        "title": "Snack Time on the Go",
        "subtitle": "Less mess, happier outings",
        "tips": [
            ("Spill Proof Cups", "Less mess on the move"),
            ("Small Portions", "Easy for little hands"),
            ("Soft Bites", "Cut food into small, soft pieces"),
            ("Wipes Ready", "Clean hands, happy baby"),
            ("Seated Snacking", "Eat only while sitting upright"),
            ("Stay Close", "Always supervise snack time"),
        ],
        "illustration": "a toddler in a stroller holding a sippy cup next to a small snack tray",
        "product": "Detachable Cup Holder",
        "shop_name": "Detachable Stroller Cup Holder",
    },
]

TIPS_CLOSING = (
    "Generate ONE single finished infographic image, sharp and high resolution. Do not generate multiple images; "
    "return only one. Before returning it, check every word in the image against the TEXT list and fix any "
    "misspelling."
)


def find_tips_topic(title: str) -> dict | None:
    return next((t for t in TIPS_TOPICS if t["title"] == title), None)


def tips_text_lines(topic: dict) -> list[str]:
    lines = [topic["title"], topic["subtitle"]]
    for heading, line in topic["tips"]:
        lines += [heading, line]
    return lines


def build_tips_image_prompt(topic: dict, has_style_reference: bool) -> str:
    cards = "\n".join(
        f'Card {i}: heading "{heading}", line "{line}"' for i, (heading, line) in enumerate(topic["tips"], start=1)
    )
    style_note = (
        "The reference image shows the visual style to match: its colors, layout, card shapes, icon style and "
        "illustration style. Do NOT copy any of its words, its title or its illustration; use only the text below.\n\n"
        if has_style_reference else ""
    )
    return (
        "You are an expert social media graphic designer. Design ONE clean, modern parenting-tips infographic "
        "for Instagram, as a vertical 4:5 portrait.\n"
        f"{style_note}"
        "STYLE: a soft cream background; a calm palette of sage green and warm peach with dark green-black text; "
        "flat vector illustration with simple rounded shapes; rounded cards; generous spacing; an elegant bold "
        "serif for the title and a clean, highly legible sans-serif for everything else.\n\n"
        "LAYOUT, top to bottom:\n"
        "1. A large rounded sage-green banner holding the title in big dark letters and the subtitle in smaller "
        f"letters below it, with a small flat illustration of {topic['illustration']} beside the banner.\n"
        "2. Six rounded peach cards in two columns of three. Each card has a simple line icon in a white circle "
        "that matches its tip, a bold heading, and one short line of text under the heading.\n\n"
        "TEXT (use exactly this text, each item exactly once, and no other text anywhere):\n"
        f'Title: "{topic["title"]}"\n'
        f'Subtitle: "{topic["subtitle"]}"\n'
        f"{cards}\n\n"
        "RULES: spell every word exactly as written above; never break a word across two lines; all text is large, "
        "sharp and easy to read on a phone; no extra text of any kind (no captions, bullet lists, numbers, dates, "
        "logos, brand names, watermarks or signatures); the illustration and icons contain no letters; any person "
        "drawn has a simple friendly face and normal anatomy."
    )


# --------------------------------------------------------------------------- #
# Read-back text check
# --------------------------------------------------------------------------- #
_PREAMBLE = re.compile(r"^\s*(here is|here's|the text|transcri)", re.I)


def _words(text: str) -> set[str]:
    text = text.replace("\u2019", "'").replace("\u2018", "'").lower()
    return set(re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text))


def check_tips_text(client, model: str, image, topic: dict) -> dict | None:
    """Have Gemini read the image's text back and compare it with the topic's text.

    Returns {"missing": [...], "unexpected": [...]} (both empty means a perfect match),
    or None if the check itself could not run.
    """
    prompt = (
        "Transcribe every word of text visible in this image exactly as it is written, including any spelling "
        "mistakes, broken words or stray letters. Output only the transcribed text, one line per text block, "
        "with no introduction or commentary."
    )
    try:
        response = client.models.generate_content(model=model, contents=[prompt, image])
        seen_text = "\n".join(l for l in (response.text or "").splitlines() if not _PREAMBLE.match(l))
    except Exception as e:
        log.warning("Could not run the tips text check: %s", e)
        return None

    expected = _words("\n".join(tips_text_lines(topic)))
    seen = _words(seen_text)
    return {
        "missing": sorted(expected - seen),
        "unexpected": sorted(w for w in seen - expected if len(w) > 1),
    }


def describe_check(result: dict | None) -> str:
    if result is None:
        return "not checked"
    if not result["missing"] and not result["unexpected"]:
        return "passed"
    parts = []
    if result["missing"]:
        parts.append("missing " + ", ".join(result["missing"]))
    if result["unexpected"]:
        parts.append("unexpected " + ", ".join(result["unexpected"]))
    return "failed: " + "; ".join(parts)


# --------------------------------------------------------------------------- #
# Caption
# --------------------------------------------------------------------------- #
def build_tips_caption_prompt(topic: dict, target: dict, product_link: str) -> str:
    city, country, lang, day = target["city"], target["country"], target["language"], target["day"]
    tips = "\n".join(f"    - {heading}: {line}" for heading, line in topic["tips"])
    return f"""
    Act as a 'Social Media Post Caption' creator and SEO Specialist for LUFFCABO, a brand of baby and mom products. Your goal is to write an engaging, helpful, and search-optimized caption and alt text for this parenting-tips infographic.

    The attached image is a tips infographic titled '{topic['title']}'. Its six tips are:
{tips}

    TARGET CONFIGURATION FOR THIS POST:
    - Location: {city}, {country}
    - Schedule: {day}, 7:00 AM Local Time
    - Language: {lang}

    === Behaviors and Rules ===

    1. Caption Composition:
       a) Write a short, warm paragraph in a 'fun, chill, and attractive' tone that sums up why these tips matter for parents. Do not add any advice that is not in the tips above.
       b) Invite followers to save the post and share their own tip in the comments.
       c) In one light sentence, mention that the LUFFCABO {topic['shop_name']} can help, and include the exact phrase (translated organically into {lang}): 'Explore it Now: {product_link}'. The URL must remain exactly as provided.
       d) Hashtags: Conclude with exactly 5 hashtags in this exact format:
          - #LUFFCABO
          - #ParentingTips
          - # [1 Core keyword in {lang} for this topic]
          - # [1 Broader parenting keyword in {lang}]
          - # [1 Broader parenting keyword in {lang}]
       e) Length: The ENTIRE caption, hashtags included, must be strictly under 450 characters.

    2. Alt Text Creation:
       a) In {lang}, describe the infographic in one or two sentences and name its six tip headings.
       b) CRITICAL: NEVER use a period at the end of the alt text.

    3. Language and Style:
       a) Write the entire post (except the URL, #LUFFCABO and #ParentingTips) strictly in {lang}.
       b) Use emojis where appropriate to keep it friendly.

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
