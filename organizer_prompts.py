"""
organizer_prompts.py

Randomized prompts for the two stroller organizers:
  - Baby Stroller Organizer (BSO): black, flap lid, fold-down mesh net and a
    detachable shoulder strap
  - Gray Stroller Organizer (GSO): heather gray, open top, built-in cup sleeves

Every call draws a new person (gender, age, ethnicity, build, hair, outfit),
setting, light, camera angle, pose, stroller, child and set of items packed
inside, so posts don't repeat the same posed, front-on shot. The black organizer
is sometimes shown worn as a crossbody bag, since it comes with a shoulder strap.

It uses the `random` module, so --seed in generate_product_images.py still makes
runs reproducible.

Preview a few prompts without calling Gemini:
    python organizer_prompts.py
"""

from __future__ import annotations

import logging
import random

log = logging.getLogger("product_image_gen")

ORGANIZER_PRODUCTS = {"Baby Stroller Organizer", "Gray Stroller Organizer"}

# Share of black-organizer images that show it worn crossbody instead of on a
# stroller. The gray one has no shoulder strap, so it is always on a stroller.
CROSSBODY_CHANCE = 0.3
# Relative weights for the model's gender (3:2 = about 60% women, 40% men).
GENDER_WEIGHTS = {"woman": 3, "man": 2}
# Ages are drawn between these, most often near the middle value.
AGE_MIN, AGE_PEAK, AGE_MAX = 22, 33, 56

# --------------------------------------------------------------------------- #
# The products (taken from the reference photos)
# --------------------------------------------------------------------------- #
PRODUCT_DESCRIPTIONS = {
    "Baby Stroller Organizer": (
        "THE PRODUCT (copy it exactly from the reference images):\n"
        "A black stroller organizer made of smooth, durable black polyester, with slim black piping along its "
        "edges. It is a long, low box, roughly twice as wide as it is tall, and its top edge rises slightly at "
        "both ends.\n"
        "- Top: a soft rectangular flap lid in the middle, edged with piping and closed with hook-and-loop, covers "
        "the center compartment. At each end of the lid is an open compartment where a bottle or cup stands upright.\n"
        "- Front (the side that faces the person pushing): a small black mesh pocket near one end, and a wide, "
        "flat slip pocket with a piped opening across the rest of the front.\n"
        "- A large black mesh net panel is attached at the front. It can be flipped down over the front to make a "
        "big open net pouch for soft toys or a jacket; when not in use it sits folded below the organizer's "
        "bottom edge.\n"
        "- Ends: exactly one black hook-and-loop strap at each end, which wraps around the handlebar and fastens "
        "into a loop. A small D-ring near each top corner is where the optional shoulder strap clips on.\n"
        "- Optional shoulder strap: plain black webbing with a black plastic swivel snap hook at each end.\n"
        "- There are NO cup holders, pouches or pockets hanging off the two ends."
    ),
    "Gray Stroller Organizer": (
        "THE PRODUCT (copy it exactly from the reference images):\n"
        "A heather-gray stroller organizer: a long, low box, roughly twice as wide as it is tall, made of soft "
        "salt-and-pepper heather-gray polyester, with black binding along the top rim and black trim on the "
        "pocket openings.\n"
        "- Top: fully open, with NO lid or flap. The inside is lined in black, with a round, padded cup sleeve "
        "built in at each end, the main space between them, and a zippered pocket on the inside back wall.\n"
        "- Front (the side that faces the person pushing): a wide, flat slip pocket with a black-trimmed opening, "
        "and beside it a black mesh pocket about the size of a phone.\n"
        "- Ends: exactly one black hook-and-loop strap at each end, which wraps around the handlebar and fastens "
        "into a loop.\n"
        "- There are NO cup holders, pouches or pockets on the outside of the ends, no shoulder strap, and no "
        "extra loops or rings. The two cup sleeves are inside the organizer only."
    ),
}

# --------------------------------------------------------------------------- #
# Settings and light
# --------------------------------------------------------------------------- #
# (place, season, indoor). Season picks the outfit: "warm", "cool", "cold" or "any".
WEST_SETTINGS = [
    ("a sunny city café terrace with bistro chairs and potted olive trees", "warm", False),
    ("a leafy park path in autumn, golden leaves on the ground", "cool", False),
    ("a busy weekend farmers market, produce stalls softly blurred behind", "warm", False),
    ("a seaside boardwalk with the ocean and a pale sky behind", "warm", False),
    ("a snowy old-town street with glowing shop windows", "cold", False),
    ("a bright, modern airport terminal with tall windows", "any", True),
    ("a glass-roofed shopping arcade", "any", True),
    ("a botanical garden path lined with flowering shrubs in spring", "warm", False),
    ("a cobblestone side street with pastel-colored buildings", "warm", False),
    ("a quiet suburban sidewalk with front gardens", "any", False),
    ("a lakeside promenade with willow trees", "warm", False),
    ("a riverside city path with a bridge in the distance", "cool", False),
    ("a zoo walkway with leafy enclosures blurred behind", "warm", False),
    ("the bright entryway of a family home, front door open, just about to head out", "any", True),
    ("a modern train station platform, a train softly blurred behind", "any", True),
    ("a sunny park lawn, the stroller parked beside a picnic blanket", "warm", False),
    ("a modern museum plaza with a fountain and clean stone paving", "any", False),
    ("a cozy café interior with big windows and plants", "any", True),
    ("a mountain-town main street in early autumn", "cool", False),
    ("a palm-lined beachfront path", "warm", False),
]

# (place, indoor). Saudi Arabia / UAE posts.
GULF_SETTINGS = [
    ("a palm-lined corniche promenade along the Gulf waterfront", False),
    ("a marina walkway with sleek yachts and glass towers softly blurred behind", False),
    ("the airy atrium of a modern shopping mall with polished floors and skylights", True),
    ("a shaded modern boulevard with palm trees and contemporary sandstone buildings", False),
    ("a landscaped city park with lawns, palms and a fountain", False),
    ("an upscale café terrace with palm planters and misting fans", False),
    ("a bright, modern airport terminal with tall windows", True),
    ("a restored historic quarter with coral-stone buildings and carved wooden balconies", False),
    ("the marble entrance hall of a modern villa, just about to head out", True),
    ("a waterfront family park with a curving walkway", False),
]

OUTDOOR_LIGHT = [
    "soft morning sun",
    "bright, clean daylight",
    "warm golden-hour light",
    "soft overcast light",
    "late-afternoon backlight with a gentle glow around the hair",
]
GULF_OUTDOOR_LIGHT = [
    "warm golden-hour light",
    "soft evening light just after sunset, city lights starting to glow",
    "bright, clean morning sun",
    "soft late-afternoon light",
]
INDOOR_LIGHT = [
    "soft natural window light",
    "bright, even daylight from skylights or large windows",
    "warm ambient light mixed with daylight",
]

PHOTO_STYLES = [
    "clean, bright commercial look",
    "warm, film-like editorial tones",
    "candid, documentary-style moment with natural imperfections",
    "soft, airy pastel color grading",
]

# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #
ETHNICITIES = [
    "of East Asian descent", "of South Asian descent", "of Southeast Asian descent",
    "Black, of West African descent", "Black, of Caribbean descent", "of East African descent",
    "of Northern European descent", "of Mediterranean descent", "of Eastern European descent",
    "of Latin American descent", "of Middle Eastern descent", "of Pacific Islander descent",
    "of mixed heritage",
]

BUILDS = {
    "woman": ["a slim build", "an athletic build", "an average build", "a curvy build",
              "a tall, lean frame", "a petite frame"],
    "man": ["a slim build", "an athletic build", "an average build", "a broad, solid build",
            "a tall, lean frame"],
}

WEST_HAIR = {
    "woman": ["long hair in loose waves", "hair in a sleek low bun", "a short pixie cut",
              "shoulder-length natural curls", "hair in a high ponytail", "a blunt chin-length bob",
              "long braids tied back", "hair in a messy top knot", "straight hair tucked behind the ears"],
    "man": ["a short fade", "tousled medium-length hair", "neatly side-parted hair", "a shaved head",
            "short natural curls", "hair tied back in a small bun", "close-cropped hair"],
}
GULF_HAIR = {
    "woman": ["long dark hair worn loose", "hair in a sleek low ponytail", "soft shoulder-length waves",
              "hair in a neat high bun", "long hair in loose curls", "a glossy blowout"],
    "man": ["short dark hair, neatly styled", "a short fade", "slicked-back dark hair", "short wavy hair"],
}
WEST_FACIAL_HAIR = ["no facial hair", "light stubble", "a short, neat beard", "a full, well-groomed beard"]
GULF_FACIAL_HAIR = ["a neatly trimmed beard", "a short, groomed beard", "light stubble", "a well-shaped full beard"]

WEST_OUTFITS = {
    "woman": {
        "warm": ["a breezy linen shirt tucked into wide-leg trousers", "a striped T-shirt and light-wash jeans",
                 "a floral midi sundress and white sneakers", "a ribbed tank top under an open oversized shirt with shorts",
                 "a fitted zip-up athleisure top and leggings"],
        "cool": ["a camel trench coat over a knit sweater and jeans", "a chunky cardigan, a turtleneck and straight trousers",
                 "a denim jacket over a hoodie and joggers", "a quilted vest over a long-sleeve top and jeans"],
        "cold": ["a long wool coat, a knit scarf and ankle boots", "a puffer jacket, a beanie and knit gloves",
                 "a teddy coat over a turtleneck and dark jeans"],
    },
    "man": {
        "warm": ["a short-sleeve linen shirt and chinos", "a plain T-shirt and denim shorts",
                 "a polo shirt and light trousers", "a henley and joggers"],
        "cool": ["a bomber jacket over a hoodie and jeans", "a flannel overshirt and jeans",
                 "a knit sweater and chinos", "a field jacket over a T-shirt"],
        "cold": ["a navy wool peacoat and a scarf", "a puffer jacket and a knit beanie",
                 "a shearling-collar jacket, jeans and boots"],
    },
}
GULF_OUTFITS = {
    "woman": ["a long-sleeve linen shirt dress with a belt", "a flowing silk blouse with wide-leg trousers",
              "a light knit top with a long pleated skirt", "a tailored blazer over a long-sleeve top and straight trousers",
              "a long-sleeve wrap midi dress", "a long-sleeve cotton tunic over slim trousers"],
    "man": ["a short-sleeve linen shirt and chinos", "a polo shirt and tailored trousers",
            "an overshirt over a plain T-shirt and dark jeans", "a knit polo and linen trousers",
            "a crisp white shirt with rolled sleeves and navy chinos"],
}

# None means no accessory. The cap is skipped for Gulf posts (no head covering).
ACCESSORIES = {
    "woman": [None, None, "a slim watch", "small gold hoop earrings", "thin-framed glasses", "a delicate necklace"],
    "man": [None, None, "a leather-strap watch", "thin-framed glasses", "a plain baseball cap with no logo"],
}

EXPRESSIONS = ["a warm, natural smile", "a relaxed half-smile", "an easy laugh, caught mid-moment",
               "a calm, content expression", "a bright, open smile"]

# --------------------------------------------------------------------------- #
# Strollers, camera angles and poses
# --------------------------------------------------------------------------- #
# (description, all-black) - all-black strollers are skipped for the black organizer, for contrast.
STROLLERS = [
    ("a premium stroller with a cognac leather-wrapped handlebar, a polished silver frame and a heather-gray seat", False),
    ("a sleek stroller with a black faux-leather handlebar, a matte black frame and a charcoal seat", True),
    ("a stroller with a champagne-gold frame, a tan leather handlebar and a cream seat", False),
    ("a stroller with a white frame, a light-brown leather handlebar and a sand-beige seat", False),
    ("a modern stroller with a dark-gray frame, a black foam handlebar and an olive-green seat", False),
    ("a three-wheel jogging stroller with a padded black handlebar and a navy seat", False),
    ("a stroller with a gunmetal frame, a dark-brown leather handlebar and a dusty-blue seat", False),
]

# (short label for the log, full instruction)
STROLLER_ANGLES = [
    ("rear three-quarter",
     "Rear three-quarter view: the camera is behind the stroller and a little to one side, at chest height. "
     "The person stands at the handlebar, turned partly toward the camera, so their face and the organizer's "
     "front pockets are both clearly visible. 50mm look."),
    ("side, walking",
     "Side view at waist height as the person walks; the organizer is seen at an angle from its end, and the "
     "person's face is in profile or three-quarter profile. 35mm look, natural motion."),
    ("over the shoulder",
     "Over-the-shoulder view from just behind and above one of the person's shoulders, looking down at the "
     "handlebar and the organizer; the person's face shows in partial profile as they look down. 35mm look."),
    ("organizer in foreground",
     "Close, waist-level shot from behind the handlebar: the organizer is sharp in the lower part of the frame, "
     "and the person, standing beside the stroller, is visible from the waist up with soft background blur. 50mm look."),
    ("low angle",
     "Low angle from about knee height behind and to one side of the stroller, looking up past the organizer "
     "to the person's face. 35mm look."),
    ("wide environmental",
     "Wide environmental shot from behind and to one side, about 3 to 4 meters away, showing the whole stroller, "
     "the person and the setting; the organizer is still clearly recognizable. 35mm look."),
    ("hands, top-down",
     "High angle from the person's own eye level, looking down at the handlebar: the organizer and what's inside "
     "fill much of the frame, with the person's hands and forearms on or near it. The face is not in this shot. 35mm look."),
    ("telephoto candid",
     "Candid telephoto shot from a few meters behind and to the side, as if unnoticed: the person and the "
     "organizer are sharp and the background melts into soft bokeh. 85mm look."),
]

STROLLER_ACTIONS = [
    "walking and pushing the stroller with both hands on the handlebar",
    "pausing mid-walk, one hand on the handlebar, the other lifting an item out of the organizer",
    "tucking a phone into the front mesh pocket with one hand, the other hand on the handlebar",
    "standing beside the parked stroller with one hand resting on the handlebar",
    "crouching beside the parked stroller to reach into the organizer",
    "dropping an item into the organizer while the other hand holds the handlebar",
    "pushing the stroller one-handed while holding a takeaway coffee in the other hand",
]

STROLLER_GAZES = ["looking toward the camera", "looking down at the child", "glancing down at the organizer",
                  "looking off to the side, unposed"]

CHILD_STATES = [
    "A baby rides in the stroller seat; show them only where this camera angle would naturally see them "
    "(often just the top of their head or a small hand above the seat back).",
    "The canopy is pulled forward over a napping baby, so the baby is not visible.",
    "A toddler sits in the stroller seat, turned to look back and up at the person.",
]

CROSSBODY_ANGLES = [
    ("three-quarter front", "Three-quarter front view at chest height as the person walks toward the camera. 50mm look."),
    ("side profile", "Side profile at waist height, mid-stride. 35mm look."),
    ("medium close-up",
     "Medium close-up from mid-thigh to head, with the organizer sharp at hip level and the face clearly visible. 85mm look."),
    ("low angle", "Low angle from about knee height, looking up past the organizer to the person's face. 35mm look."),
    ("rear three-quarter",
     "Rear three-quarter view as the person glances back over their shoulder toward the camera; the organizer "
     "is worn on the side nearest the camera and is clearly visible. 50mm look."),
]

CROSSBODY_ACTIONS = [
    "walking with one hand resting lightly on the organizer's flap",
    "standing still and lifting the flap to reach inside",
    "walking while holding a takeaway coffee in one hand",
    "walking hand in hand with a toddler beside them",
    "standing still, adjusting the shoulder strap with one hand",
]

CROSSBODY_GAZES = ["looking toward the camera", "glancing down at the organizer", "looking off to the side, unposed"]

# --------------------------------------------------------------------------- #
# What's packed inside
# --------------------------------------------------------------------------- #
CONTENTS = [
    "a soft pack of baby wipes", "a couple of neatly rolled diapers", "a folded muslin swaddle with a small print",
    "a silicone teether", "a wooden teething ring", "a pacifier in a small clear case",
    "a snack cup of puffs with a soft lid", "a small cloth book", "a little plush toy", "a pair of sunglasses",
    "a set of keys", "a small zip pouch", "a squeeze fruit pouch", "a tube of baby sunscreen",
    "a tiny pair of knitted socks", "a folded sun hat", "a travel-size hand sanitizer", "a slim wallet",
    "wireless earbuds in their case",
]
CUP_ITEMS = ["a takeaway coffee cup with a plain sleeve", "a stainless steel water bottle", "a baby bottle",
             "an iced coffee in a clear cup", "a sippy cup"]
NET_ITEMS = ["a soft knitted bunny", "a plush elephant", "a folded baby blanket", "a light jacket folded small",
             "a soft fabric ball", "a small plush bear"]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _person(gender: str, arabic: bool, season: str) -> str:
    age = round(random.triangular(AGE_MIN, AGE_MAX, AGE_PEAK))
    if arabic:
        who = "a Gulf Arab of Saudi or Emirati appearance"
        hair = random.choice(GULF_HAIR[gender])
        facial = random.choice(GULF_FACIAL_HAIR)
        outfit = random.choice(GULF_OUTFITS[gender])
        accessories = [a for a in ACCESSORIES[gender] if not (a and "cap" in a)]
    else:
        who = random.choice(ETHNICITIES)
        hair = random.choice(WEST_HAIR[gender])
        facial = random.choice(WEST_FACIAL_HAIR)
        if season == "any":
            season = random.choice(["warm", "cool"])
        outfit = random.choice(WEST_OUTFITS[gender][season])
        accessories = ACCESSORIES[gender]

    looks = f"{hair} and {facial}" if gender == "man" else hair
    text = (f"One {gender}, about {age} years old, {who}, with {random.choice(BUILDS[gender])} and {looks}, "
            f"wearing {outfit}.")
    accessory = random.choice(accessories)
    if accessory:
        text += f" They also wear {accessory}."
    return text


def _contents(is_black: bool, crossbody: bool, phone_in_action: bool) -> str:
    items = random.sample(CONTENTS, random.randint(3, 5))
    cup = random.choice(CUP_ITEMS)

    if crossbody:
        return (f"The flap lid is closed and the mesh net panel is folded away, with {items[0]} just peeking "
                "out of one of the open end compartments.")

    lines = []
    net_down = False
    if is_black:
        if random.random() < 0.5:
            lines.append(f"The flap lid is folded back, showing what's packed in the middle: {_join(items)}. "
                         f"{cup[0].upper() + cup[1:]} stands upright in one of the end compartments.")
        else:
            lines.append(f"The flap lid is closed. {cup[0].upper() + cup[1:]} stands upright in one end "
                         f"compartment, with {items[0]} peeking out of the other.")
        if random.random() < 0.4:
            net_down = True
            lines.append(f"The mesh net panel is flipped down over the front, holding {random.choice(NET_ITEMS)}, "
                         "so the front pockets are hidden behind it.")
        else:
            lines.append("The mesh net panel is folded away below the organizer.")
    else:
        lines.append(f"The open top shows what's packed inside: {_join(items)}. "
                     f"{cup[0].upper() + cup[1:]} stands in one of the built-in cup sleeves.")

    if not phone_in_action and not net_down and random.random() < 0.5:
        lines.append("A phone is tucked into the front mesh pocket.")
    lines.append("Every item sits inside at a realistic size, and all packaging is plain, with no readable text or logos.")
    return " ".join(lines)


def build_organizer_prompt(base_key: str, arabic: bool = False) -> str:
    """A fresh random scene for one stroller organizer image."""
    if base_key not in ORGANIZER_PRODUCTS:
        raise ValueError(f"Not a stroller organizer: {base_key}")
    is_black = base_key == "Baby Stroller Organizer"
    crossbody = is_black and random.random() < CROSSBODY_CHANCE
    gender = random.choices(list(GENDER_WEIGHTS), weights=list(GENDER_WEIGHTS.values()))[0]

    if arabic:
        place, indoor = random.choice(GULF_SETTINGS)
        season = "warm"
        light = random.choice(INDOOR_LIGHT if indoor else GULF_OUTDOOR_LIGHT)
    else:
        settings = [s for s in WEST_SETTINGS if not (crossbody and "stroller" in s[0])]
        place, season, indoor = random.choice(settings)
        light = random.choice(INDOOR_LIGHT if indoor else OUTDOOR_LIGHT)

    if crossbody:
        angle_label, angle = random.choice(CROSSBODY_ANGLES)
        action = random.choice(CROSSBODY_ACTIONS)
        gaze = random.choice(CROSSBODY_GAZES)
        usage = (
            "HOW IT IS USED IN THIS PHOTO:\n"
            "No stroller in this shot. The organizer is worn as a crossbody bag on its detachable black shoulder "
            "strap, clipped to the D-rings at both top corners, and sits at hip level. The hook-and-loop straps "
            "at each end hang loose or are fastened into small loops."
        )
    else:
        angle_label, angle = random.choice(STROLLER_ANGLES)
        action = random.choice(STROLLER_ACTIONS)
        gaze = random.choice(STROLLER_GAZES)
        strollers = [s for s, all_black in STROLLERS if not (is_black and all_black)]
        child = random.choice(CHILD_STATES)
        child += (" Any child in the shot is Gulf Arab, like the parent." if arabic
                  else " Any child in the shot looks like the person's own child.")
        usage = (
            "HOW IT IS USED IN THIS PHOTO:\n"
            f"The organizer is strapped to the single, continuous handlebar of {random.choice(strollers)}. "
            "It hangs just below the handlebar on the side facing the person pushing, with its front pockets "
            "toward the person and away from the seat, held only by its two end straps. The stroller has a proper "
            "forward-facing seat and a canopy, and must read clearly as a baby stroller, not a walker or a "
            f"shopping cart. {child}"
        )

    rules = [
        "Exactly one adult and one organizer in the image." + ("" if crossbody else " Only one stroller."),
        "The adult has exactly two hands with five fingers each, in natural, anatomically correct poses; "
        "every hand belongs to a visible arm.",
        "No brand logos or readable text anywhere: not on the organizer, stroller, clothes, packaging or signs.",
        "The face is new and unique; do not reuse any face or person from the reference images.",
        "Use the reference images only for the product's design. Ignore their text, icons, labels, layout, "
        "people and backgrounds.",
        "Keep the organizer's color, proportions, pockets and straps exactly as in the references; "
        "do not add or remove any part.",
        "If the camera angle and the pose pull in different directions, keep the camera angle and adjust the "
        "pose so it looks natural.",
        "Photorealistic, natural skin texture and real fabric detail: a real photo, not a 3D render.",
    ]
    if arabic:
        rules.append(
            "The adult is a Gulf Arab of Saudi or Emirati appearance with uncovered, casually styled hair, in "
            "modern everyday clothes: no hijab or other head covering, and no traditional dress (no abaya, "
            "thobe or ghutra)."
        )

    log.info("Organizer scene: %s | %s | %s | %s | %s",
             "crossbody" if crossbody else "stroller", gender, place, angle_label, action)

    return "\n\n".join([
        "You are an expert lifestyle product photographer. Analyze all the reference images carefully, then "
        "create one photorealistic lifestyle photo of this stroller organizer for a social media post. Every "
        "detail below was chosen for this image only: follow it exactly instead of falling back on a standard, "
        "front-on posed shot.",
        PRODUCT_DESCRIPTIONS[base_key],
        usage,
        "THE PERSON:\n"
        f"{_person(gender, arabic, season)} Expression: {random.choice(EXPRESSIONS)}, {gaze}. They are {action}.",
        f"THE SETTING:\n{place[0].upper() + place[1:]}, in {light}.",
        f"CAMERA:\n{angle} Style: {random.choice(PHOTO_STYLES)}.",
        "WHAT'S INSIDE:\n" + _contents(is_black, crossbody, phone_in_action="phone" in action),
        "RULES:\n" + "\n".join(f"- {r}" for r in rules),
    ])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for key in sorted(ORGANIZER_PRODUCTS):
        for arabic in (False, True):
            print("=" * 80)
            print(f"{key}{'  [ARABIC]' if arabic else ''}")
            print("=" * 80)
            print(build_organizer_prompt(key, arabic=arabic))
            print()