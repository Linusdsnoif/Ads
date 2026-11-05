"""
product_scenes.py

Randomized prompts for the products that don't have their own prompt module:
Automatic Nail Clipper, Baby Nail File, Baby Sculpting Device, Breast Pumps,
Inflatable Baby Seat and LED Beauty Mask.

How the prompts are built:
  - FIXED per product: the product description and how it is used. That's what
    keeps the product accurate, so it is never randomized.
  - PER PRODUCT: pools of settings, poses and camera angles written for that
    product, so any combination makes sense for it (the seat's logo always faces
    the camera, the sculpting device is always seen side-on, and so on).
  - SHARED: people (ethnicity, build, hair, outfit), light and photo style, so
    every product draws from the same range of models.

It uses the `random` module, so --seed in generate_product_images.py still makes
runs reproducible.

Preview prompts without calling Gemini:
    python product_scenes.py                      # one of each product
    python product_scenes.py "LED Beauty Mask"    # one product, normal and Arabic
"""

from __future__ import annotations

import logging
import random
import sys

log = logging.getLogger("product_image_gen")

# =========================================================================== #
# Shared pools
# =========================================================================== #
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

HAIR = {
    "woman": ["long hair in loose waves", "hair in a sleek low bun", "a short pixie cut",
              "shoulder-length natural curls", "hair in a high ponytail", "a blunt chin-length bob",
              "long braids tied back", "hair in a messy top knot", "hair pulled back with a soft headband",
              "straight hair tucked behind the ears"],
    "man": ["a short fade", "tousled medium-length hair", "neatly side-parted hair", "a shaved head",
            "short natural curls", "hair tied back in a small bun", "close-cropped hair"],
}
GULF_HAIR = {
    "woman": ["long dark hair worn loose", "hair in a sleek low ponytail", "soft shoulder-length waves",
              "hair in a neat high bun", "long hair in loose curls", "a glossy blowout"],
    "man": ["short dark hair, neatly styled", "a short fade", "slicked-back dark hair", "short wavy hair"],
}
FACIAL_HAIR = ["no facial hair", "light stubble", "a short, neat beard", "a full, well-groomed beard"]
GULF_FACIAL_HAIR = ["a neatly trimmed beard", "a short, groomed beard", "light stubble", "a well-shaped full beard"]

COLORS = ["oatmeal", "sage green", "dusty pink", "soft grey", "cream", "navy", "terracotta", "lavender",
          "camel", "white", "charcoal", "sky blue", "butter yellow", "olive"]

# Outfit contexts: "home" (casual at home), "selfcare" (robes, pajamas),
# "nursing" (fitted tops for the breast pump) and "outdoor". {c} becomes a random color.
OUTFITS = {
    "home": {
        "woman": ["a {c} knit sweater and relaxed jeans", "a {c} linen shirt and soft lounge pants",
                  "an oversized {c} T-shirt and leggings", "a {c} cotton lounge set",
                  "a {c} cardigan over a white T-shirt"],
        "man": ["a {c} crew-neck sweater and chinos", "a {c} henley and joggers", "a {c} linen shirt and jeans",
                "a plain {c} T-shirt and lounge pants", "a {c} hoodie and jeans"],
    },
    "selfcare": {
        "woman": ["a {c} waffle-knit robe", "{c} silk pajamas", "a {c} knit lounge set",
                  "a {c} ribbed tank top under an open cardigan", "a {c} cotton pajama shirt"],
        "man": ["a {c} waffle-knit robe", "a {c} pajama set", "a {c} T-shirt and lounge pants"],
    },
    "nursing": {
        "woman": ["a fitted {c} ribbed tank top", "a fitted {c} crew-neck T-shirt",
                  "a fitted {c} nursing camisole under an open cardigan", "a fitted {c} scoop-neck top",
                  "a fitted {c} long-sleeve henley"],
    },
    "outdoor": {
        "woman": ["a {c} linen shirt and wide-leg trousers", "a {c} sundress and sandals",
                  "a striped T-shirt and {c} shorts", "a {c} light knit top and jeans"],
        "man": ["a {c} short-sleeve linen shirt and chinos", "a {c} polo shirt and shorts",
                "a plain {c} T-shirt and light trousers"],
    },
}
GULF_OUTFITS = {
    "home": {
        "woman": ["a {c} long-sleeve knit top and wide-leg trousers", "a {c} long-sleeve linen shirt and soft trousers",
                  "a {c} long-sleeve lounge set", "a long {c} cardigan over a long-sleeve top and trousers"],
        "man": ["a {c} knit polo and chinos", "a {c} linen shirt and trousers",
                "a {c} long-sleeve T-shirt and lounge pants"],
    },
    "selfcare": {
        "woman": ["a long {c} satin robe", "{c} long-sleeve silk pajamas", "a {c} long-sleeve knit lounge set"],
        "man": ["a {c} pajama set", "a {c} long-sleeve T-shirt and lounge pants"],
    },
    "nursing": {
        "woman": ["a fitted {c} long-sleeve ribbed top", "a fitted {c} long-sleeve knit top under an open cardigan",
                  "a fitted {c} long-sleeve henley"],
    },
    "outdoor": {
        "woman": ["a {c} long-sleeve linen shirt dress", "a {c} flowing blouse with wide-leg trousers",
                  "a {c} long-sleeve top and a long skirt"],
        "man": ["a {c} short-sleeve linen shirt and chinos", "a {c} polo shirt and tailored trousers"],
    },
}

BABY_HAIR = ["soft, wispy hair", "a full head of dark curls", "fine, barely-there fuzz", "straight light-brown hair",
             "tiny tight curls", "soft black hair"]
BABY_COLORS = ["pastel yellow", "mint", "soft white", "pale pink", "light blue", "oatmeal", "sage", "lavender"]
BABY_OUTFITS = ["a {c} cotton bodysuit", "a {c} knitted romper", "a {c} striped onesie", "a {c} sleepsuit",
                "a {c} linen romper"]

INDOOR_LIGHT = ["soft natural window light", "warm morning sun through sheer curtains", "bright, even daylight",
                "warm lamplight mixed with soft daylight", "soft, diffused late-afternoon light"]
OUTDOOR_LIGHT = ["soft morning sun", "bright, clean daylight", "warm golden-hour light", "soft dappled shade"]

PHOTO_STYLES = ["clean, bright commercial look", "warm, film-like editorial tones",
                "candid, documentary-style moment with natural imperfections", "soft, airy pastel color grading"]

EXPRESSIONS = ["a warm, natural smile", "a relaxed, content smile", "a soft laugh, caught mid-moment",
               "a calm, peaceful expression", "a bright, open smile"]

COMMON_RULES = [
    "Every face is new and unique; do not reuse any face or person from the reference images.",
    "Use the reference images only for the product's design. Ignore their text, icons, labels, layout, "
    "people and backgrounds.",
    "No mirrors or reflections that show a second copy of a person or the product.",
    "All bodies follow normal human anatomy, and every hand belongs to a visible arm.",
    "If any details pull in different directions, keep the setting and camera angle and adapt the pose so it "
    "looks natural.",
    "Photorealistic, natural skin texture and real material detail: a real photo, not a 3D render.",
]
GULF_RULE = (
    "Every adult is a Gulf Arab of Saudi or Emirati appearance with uncovered, casually styled hair, in modern "
    "everyday clothes: no hijab or other head covering, and no traditional dress (no abaya, thobe or ghutra)."
)


# =========================================================================== #
# Shared helpers
# =========================================================================== #
def _cap(text: str) -> str:
    return text[0].upper() + text[1:]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _pick_gender(weights: dict[str, int]) -> str:
    return random.choices(list(weights), weights=list(weights.values()))[0]


def _person(gender: str, ages: tuple[int, int, int], context: str, arabic: bool) -> str:
    """One adult. `ages` is (youngest, most common, oldest)."""
    low, peak, high = ages
    age = round(random.triangular(low, high, peak))
    if arabic:
        who, hair, facial = ("a Gulf Arab of Saudi or Emirati appearance", random.choice(GULF_HAIR[gender]),
                             random.choice(GULF_FACIAL_HAIR))
        outfit = random.choice(GULF_OUTFITS[context][gender])
    else:
        who, hair, facial = random.choice(ETHNICITIES), random.choice(HAIR[gender]), random.choice(FACIAL_HAIR)
        outfit = random.choice(OUTFITS[context][gender])
    looks = f"{hair} and {facial}" if gender == "man" else hair
    outfit = outfit.format(c=random.choice(COLORS))
    return (f"One {gender}, about {age} years old, {who}, with {random.choice(BUILDS[gender])}, {looks}, "
            f"wearing {outfit}.")


def _child(age_text: str, arabic: bool, with_adult: bool = True) -> str:
    outfit = random.choice(BABY_OUTFITS).format(c=random.choice(BABY_COLORS))
    text = f"The child is {age_text}, with {random.choice(BABY_HAIR)}, wearing {outfit}."
    if arabic:
        text += " The child is Gulf Arab."
    elif with_adult:
        text += " The child looks like the adult's own child."
    return text


def _setting(place: str, indoor: bool, arabic: bool) -> str:
    light = random.choice(INDOOR_LIGHT if indoor else OUTDOOR_LIGHT)
    text = f"THE SETTING:\n{_cap(place)}, in {light}."
    if arabic:
        text += " Style it as it would look in Saudi Arabia or the UAE today."
    return text


def _camera(angle: str) -> str:
    return f"CAMERA:\n{angle} Style: {random.choice(PHOTO_STYLES)}."


# Each product builder returns (sections, product rules, short summary for the log).

# =========================================================================== #
# Automatic Nail Clipper
# =========================================================================== #
CLIPPER_PRODUCT = (
    "THE PRODUCT (copy it exactly from the reference images):\n"
    "An ultra-compact electronic automatic nail clipper, about as long as a middle finger and small enough to hold "
    "between thumb and index finger. Its smooth, contoured body is silver-grey and black, with NO protruding lever "
    "or moving parts. The top face has an integrated, non-protruding circular grooming slot with a clear window, "
    "and two circular grey buttons at the center of the device."
)
CLIPPER_USE = (
    "HOW IT IS USED:\n"
    "The person holds the tiny device delicately between the thumb and fingers of one hand and gently places a "
    "fingertip of the other hand against the circular grooming slot. Both hands are in front of the body and "
    "clearly visible."
)
CLIPPER_SETTINGS = [
    ("a softly lit home vanity table with a few skincare bottles", True),
    ("a clean, bright bathroom with light from a frosted window", True),
    ("a comfortable bedroom armchair beside a window with sheer curtains", True),
    ("a living room sofa with a knit throw and a mug of tea on the side table", True),
    ("a sunny kitchen table in the morning, a coffee cup nearby", True),
    ("a home office desk during a break, laptop closed", True),
    ("a hotel room armchair by a large window, a suitcase softly blurred behind", True),
    ("a balcony chair surrounded by potted plants", False),
    ("a reading nook with bookshelves", True),
    ("the edge of a neatly made bed with linen bedding", True),
    ("a garden patio chair", False),
]
CLIPPER_ANGLES = [
    "Medium close-up at chest height, straight on, framing the face, shoulders and both hands. 85mm look, "
    "shallow depth of field.",
    "Three-quarter view from slightly to one side, the hands raised in front of the chest so the device and the "
    "face are both sharp. 50mm look.",
    "Slightly high angle, as if from someone standing nearby, looking down at the hands while the person looks "
    "up and smiles. 35mm look.",
    "Close side-angle shot at hand height: the hands and device sharp in the foreground, the smiling face a little "
    "softer behind. 50mm look.",
    "Relaxed seated portrait from the waist up, the person leaning back comfortably with the hands in front of the "
    "body. 50mm look.",
]
CLIPPER_GAZES = ["smiling at the camera", "smiling down at their fingertips", "glancing up from their hands with a smile"]


def _clipper(arabic: bool):
    gender = _pick_gender({"woman": 1, "man": 1})
    place, indoor = random.choice(CLIPPER_SETTINGS)
    person = (f"THE PERSON:\n{_person(gender, (20, 34, 60), 'home', arabic)} Expression: "
              f"{random.choice(EXPRESSIONS)}, {random.choice(CLIPPER_GAZES)}. Nails are clean, neat and nicely manicured.")
    rules = [
        "Exactly one person, with exactly two hands and five fingers on each.",
        "Only one device in the image, and it is in the person's hand.",
        "No brand logos or text on the device or anywhere else.",
    ]
    return [CLIPPER_PRODUCT, CLIPPER_USE, person, _setting(place, indoor, arabic),
            _camera(random.choice(CLIPPER_ANGLES))], rules, f"{gender} | {place}"


# =========================================================================== #
# Baby Nail File
# =========================================================================== #
# The disc color matches the file head made for that age.
NAIL_FILE_PAIRS = [
    {"color": "purple", "age": "an infant between 0 and 12 months old"},
    {"color": "yellow", "age": "a toddler between 1 and 3 years old"},
    {"color": "pink", "age": "a young child between 3 and 6 years old"},
    {"color": "grey", "age": "a baby between 6 and 18 months old, during a gentle polishing session"},
]
# (place, indoor, pose that must go with it or None)
NAIL_FILE_SETTINGS = [
    ("a minimalist Scandinavian nursery with light wood furniture and plush textiles", True, None),
    ("a warm pastel nursery with a knitted blanket and soft toys on a shelf", True, None),
    ("a sunlit living room sofa with linen cushions", True, None),
    ("a rocking chair by a nursery window with sheer curtains", True, None),
    ("a large bed with crisp white linen and fluffy pillows", True, None),
    ("a padded changing table with folded muslin cloths", True, None),
    ("a cushioned window seat in the morning", True, None),
    ("a soft play mat on the living room floor", True, None),
    ("a cozy bedroom just after bath time, the child wrapped in a hooded towel", True, None),
    ("a calm nursery at nap time, the child resting drowsily in the crib", True,
     "The guardian leans over the crib rail, steadying the tiny hand with one hand and filing with the other "
     "while the child rests."),
]
NAIL_FILE_POSES = [
    "The child sits on the guardian's lap, leaning back against their chest; the guardian holds the tiny hand "
    "steady with one hand and files with the other.",
    "The child lies on their back on a soft surface; the guardian sits or kneels beside them, holds the tiny hand "
    "steady with one hand and files with the other.",
    "The guardian cradles the child in one arm, using that hand to steady the tiny fingers, and files with the "
    "other hand.",
    "The child sits facing the guardian, who holds the tiny hand steady with one hand and files with the other.",
]
NAIL_FILE_ANGLES = [
    "Close-up from the side at the child's eye level: the hands and file sharp in the foreground, both faces "
    "softly visible. 85mm look.",
    "Over the guardian's shoulder, looking down at the tiny hand, the file and the child's face. 50mm look.",
    "Three-quarter medium shot showing both faces and the hands, the guardian smiling. 50mm look.",
    "Slightly high angle looking down at the pair, the hands and file in the center of the frame. 35mm look.",
    "Low, intimate angle from beside the child, looking slightly up at the guardian's smiling face, the hands in "
    "the foreground. 35mm look.",
]


def _nail_file(arabic: bool):
    pair = random.choice(NAIL_FILE_PAIRS)
    gender = _pick_gender({"woman": 3, "man": 2})
    place, indoor, fixed_pose = random.choice(NAIL_FILE_SETTINGS)
    product = (
        "THE PRODUCT (copy it exactly from the reference images):\n"
        "A gentle electric baby nail file. The body is entirely yellow, perfectly smooth and seamless, with flush "
        "edges, and features only a simple duck graphic. The filing head on top is a flat circular disc, and its "
        f"very top surface is strictly {pair['color']}."
    )
    use = (
        "HOW IT IS USED:\n"
        f"{fixed_pose or random.choice(NAIL_FILE_POSES)} The disc touches the edge of the child's own fingernail, "
        "gently. Adapt the pose to what a child of this age can safely do: a young infant lies down or is held "
        "and never sits unsupported."
    )
    people = (f"THE PEOPLE:\nThe guardian: {_person(gender, (20, 31, 60), 'home', arabic)} Expression: "
              f"{random.choice(EXPRESSIONS)}. {_child(pair['age'], arabic)}")
    rules = [
        "Exactly one guardian and one child, with no partial people, ghost figures or hands coming in from out of frame.",
        "The guardian has exactly two hands and the child exactly two hands, with five fingers each.",
        "Only one nail file in the image.",
        "No text, brand names or logos anywhere; the device shows only the simple duck graphic.",
    ]
    return [product, use, people, _setting(place, indoor, arabic),
            _camera(random.choice(NAIL_FILE_ANGLES))], rules, f"{pair['color']} | {gender} | {place}"


# =========================================================================== #
# Baby Sculpting Device
# =========================================================================== #
SCULPT_PRODUCT = (
    "THE PRODUCT (copy its shape exactly from the reference images):\n"
    "A compact, palm-sized facial sculpting device shaped like a mushroom or a doorknob lying on its side. It has "
    "NO handle, NO stick, NO long grip and is NOT a wand or paddle.\n"
    "It has three parts, in a straight line:\n"
    "1. FRONT: a large, smooth, glossy white convex dome. This dome is the part that touches the skin.\n"
    "2. MIDDLE: a short, narrow white neck connecting the dome to the back. This neck is the only place she holds it.\n"
    "3. BACK: a smaller flat circular face made of glossy black, with exactly FIVE white arc-shaped segment buttons "
    "arranged in a curved row around its edge.\n"
    "The dome is noticeably wider than the black back face. The whole device is no longer than her hand."
)
SCULPT_USE = (
    "HOW IT IS HELD:\n"
    "She holds it between her thumb and fingers by the narrow neck, with the white dome pressed against her cheek "
    "or jawline. The device points sideways, away from her face, so the camera sees it from the side: the white "
    "dome against her skin and the black face with the five white buttons at the outer end. She is seated "
    "comfortably."
)
SCULPT_SETTINGS = [
    ("a polished marble changing-station countertop", True),
    ("a marble bathroom vanity", True),
    ("a bedroom dressing table with soft linen curtains behind", True),
    ("the edge of a neatly made bed, a small tray on the duvet", True),
    ("a calm nursery armchair, a crib softly blurred behind", True),
    ("a living room sofa beside a side table", True),
    ("a sunlit window seat with cushions", True),
    ("a spa-like bathroom with stone, wood and green plants", True),
]
SCULPT_PROPS = ["a wooden baby brush", "folded organic muslin cloths", "a single plain lotion bottle",
                "a small {c} storage pouch", "a cup of herbal tea", "a soft rolled towel",
                "a sprig of eucalyptus in a small vase", "a small wooden tray", "a tiny knitted baby hat"]
SCULPT_ANGLES = [
    "Medium close-up at eye level, her face turned slightly so the device on her near cheek is seen side-on. 85mm look.",
    "Three-quarter profile at eye level, the device side-on against her jawline. 50mm look.",
    "Waist-up shot of her seated, the foreground surface and its items softly blurred at the bottom of the frame. "
    "50mm look.",
    "Slightly high angle from the side, looking down a little at her face and the device. 35mm look.",
    "Close portrait from the chest up, the device and her hand sharp against a softly blurred background. 85mm look.",
]
SCULPT_GAZES = ["smiling at the camera", "eyes softly closed, relaxed", "smiling off to the side"]


def _sculpt(arabic: bool):
    place, indoor = random.choice(SCULPT_SETTINGS)
    props = [p.format(c=random.choice(COLORS)) for p in random.sample(SCULPT_PROPS, random.randint(3, 4))]
    person = (f"THE PERSON:\n{_person('woman', (22, 29, 36), 'selfcare', arabic)} Expression: "
              f"{random.choice(EXPRESSIONS)}, {random.choice(SCULPT_GAZES)}.")
    foreground = f"IN THE FOREGROUND:\nOn a nearby surface: {_join(props)}, with no other devices."
    rules = [
        "Exactly one woman, with exactly two hands and five fingers on each.",
        "There is only one device in the whole frame, and it is in her hand.",
        "No brand logos or text on the device, the woman or any item, and no face or picture printed on the device.",
    ]
    return [SCULPT_PRODUCT, SCULPT_USE, person, _setting(place, indoor, arabic), foreground,
            _camera(random.choice(SCULPT_ANGLES))], rules, place


# =========================================================================== #
# Breast Pumps
# =========================================================================== #
PUMP_PRODUCT = (
    "THE PRODUCT (copy it exactly from the reference images):\n"
    "A modern, ergonomic, wireless wearable breast pump. Each unit has a circular black screen on top displaying "
    "the time, with four white buttons for its different functions."
)
PUMP_USE = (
    "HOW IT IS WORN:\n"
    "Two pump units sit on top of the breasts in the correct position, inside her bra and covered by her top, "
    "discreetly tucked in at the neckline. It is completely hands-free, with no tubes or cables, so she carries on "
    "with what she's doing."
)
# (place, indoor, what she's doing) - paired, because the activity has to fit the place.
PUMP_SCENES = [
    ("a comfortable bed in a peaceful, minimalist bedroom", True,
     "sitting up against the pillows, one hand resting gently near the pump"),
    ("a home office desk by a window", True, "typing on a laptop with both hands, its screen facing away from the camera"),
    ("a living room sofa with a soft throw", True, "curled up reading a paperback book"),
    ("a bright kitchen counter", True, "pouring herself a cup of tea"),
    ("a nursery armchair, a baby asleep in a bassinet beside her", True,
     "looking over at the sleeping baby with a soft smile"),
    ("a dining table with a vase of fresh flowers", True, "writing in a notebook"),
    ("a balcony lounge chair among potted plants", False, "sipping a glass of water and enjoying the view"),
    ("the end of a neatly made bed", True, "folding tiny baby clothes into a neat stack"),
    ("a sunlit window corner with houseplants", True, "watering a plant with a small watering can"),
    ("a cozy reading nook", True, "holding a warm mug in both hands, gazing out of the window"),
]
PUMP_ANGLES = [
    "Medium shot from the waist up at eye level. 50mm look.",
    "Three-quarter view from slightly to one side, candid, as if she hasn't noticed the camera. 50mm look.",
    "Wider shot showing her within the room, still close enough to see the pump's discreet shape under her top. "
    "35mm look.",
    "Close shot from the chest up, her face and neckline sharp. 85mm look.",
    "Slightly low angle from seated height, looking across at her. 35mm look.",
]


def _pump(arabic: bool):
    place, indoor, activity = random.choice(PUMP_SCENES)
    person = (f"THE PERSON:\n{_person('woman', (25, 30, 36), 'nursing', arabic)} Expression: "
              f"{random.choice(EXPRESSIONS)}. She is {activity}.")
    rules = [
        "Exactly one adult, a woman, with exactly two hands and five fingers on each."
        + (" The only other person is the sleeping baby." if "baby" in place else ""),
        "Exactly two pump units, one on each breast, correctly placed inside her bra and covered by her top.",
        "No brand logos or readable text anywhere; any screen (laptop, phone) faces away or shows nothing readable.",
    ]
    return [PUMP_PRODUCT, PUMP_USE, person, _setting(place, indoor, arabic),
            _camera(random.choice(PUMP_ANGLES))], rules, f"{place} | {activity}"


# =========================================================================== #
# Inflatable Baby Seat
# =========================================================================== #
SEAT_PRODUCT = (
    "THE PRODUCT (copy its shape and colors exactly from the reference images):\n"
    "An inflatable baby seat. Its logo, the word LUFFCABO in black with an anchor above it, must be clearly visible "
    "and sharp, spelled exactly L-U-F-F-C-A-B-O."
)
SEAT_SETTINGS = [
    ("a soft rug in a cheerful, modern living room", True),
    ("a nursery play mat with soft toys around", True),
    ("a picnic blanket on a sunny garden lawn", False),
    ("a beach blanket in the shade of a parasol", False),
    ("a wooden patio deck with potted plants", False),
    ("a soft mat on the kitchen floor, breakfast things on the counter behind", True),
    ("a sunny bay-window corner with floor cushions", True),
    ("a blanket at the entrance of a camping tent, trees behind", False),
    ("a bright playroom with wooden toys on low shelves", True),
    ("a classic living room with a patterned rug and armchairs", True),
]
SEAT_BABY_ACTIONS = [
    "holding a soft toy and giggling", "clapping with a big gummy smile", "chewing happily on a silicone teether",
    "reaching toward the camera with curious wide eyes", "holding a stacking cup and babbling",
    "laughing at a soap bubble floating nearby", "shaking a wooden rattle",
    "looking up with a surprised, delighted face",
]
# None = no adult in the shot.
SEAT_ADULT = [
    None, None,
    "kneels beside the seat, off to one side so the logo stays clear, smiling at the baby",
    "sits cross-legged on the ground just behind and to one side of the seat, one hand resting near the baby",
    "is in the soft-focus background, smiling toward the baby",
    "crouches beside the seat, playing peekaboo with the baby",
]
SEAT_ANGLES = [
    "Straight on at the baby's eye level, low to the ground, the logo centered and sharp. 50mm look.",
    "Three-quarter front view from slightly above, as if a parent is standing nearby; the logo is still easy to "
    "read. 35mm look.",
    "Close shot with the baby and seat filling most of the frame and the background melted into bokeh. 85mm look.",
    "Wider front shot showing the setting, with the baby and seat clearly the focus and the logo readable. 35mm look.",
]


def _seat(arabic: bool):
    place, indoor = random.choice(SEAT_SETTINGS)
    adult = random.choice(SEAT_ADULT)
    baby = _child(f"a baby about {random.randint(5, 12)} months old", arabic, with_adult=adult is not None)
    use = (
        "HOW IT IS USED:\n"
        "The seat rests safely and stably on the ground. The baby sits properly in it, upright and supported, "
        f"facing the camera, {random.choice(SEAT_BABY_ACTIONS)}. {baby}"
    )
    if adult:
        gender = _pick_gender({"woman": 3, "man": 2})
        people = (f"THE ADULT:\n{_person(gender, (20, 32, 60), 'home' if indoor else 'outdoor', arabic)} "
                  f"Expression: {random.choice(EXPRESSIONS)}. The adult {adult}.")
    else:
        people = "THE ADULT:\nNo adult in this shot; only the baby."
    rules = [
        "Only one seat and one baby" + (" and one adult." if adult else ", and no adults."),
        "The baby has exactly two hands with five fingers each" + (", and so does the adult." if adult else "."),
        "The LUFFCABO logo and anchor face the camera and are never blocked by the baby's arms, toys or anyone else. "
        "Double check the spelling: LUFFCABO.",
        "No other logos or readable text anywhere.",
    ]
    if adult:
        rules.append("The adult stays around the baby and never passes through the seat.")
    return [SEAT_PRODUCT, use, people, _setting(place, indoor, arabic),
            _camera(random.choice(SEAT_ANGLES))], rules, f"{place} | adult: {'yes' if adult else 'no'}"


# =========================================================================== #
# LED Beauty Mask
# =========================================================================== #
MASK_PRODUCT = (
    "THE PRODUCT (copy it exactly from the reference images):\n"
    "A sleek, multi-layered LED beauty mask, with close-up detail of the LED arrays within the material. Show the "
    "mask as it really looks, with no added glow, light beams or special effects."
)
MASK_SETTINGS = [
    ("a polished marble vanity in a high-end modern bathroom", True),
    ("a bed with crisp linen and plenty of pillows", True),
    ("a velvet chaise lounge by a tall window", True),
    ("a living room sofa with a soft throw and a cup of tea on the side table", True),
    ("a calm, spa-like room with stone, wood and green plants", True),
    ("a bedroom reading nook with warm lamplight", True),
    ("a bright, minimalist bedroom in the morning", True),
    ("a balcony daybed at dusk, city lights softly blurred behind", False),
]
# (pose, face visible)
MASK_POSES = [
    ("wearing the mask, leaning back and relaxed, hands resting in her lap", False),
    ("wearing the mask while sitting upright, holding a cup of tea in both hands", False),
    ("wearing the mask while reading a book", False),
    ("holding the mask up in both hands just in front of her face, about to put it on", True),
    ("holding the mask in her lap after a session, her skin fresh and naturally glowing", True),
    ("putting the mask on, settling it into place with both hands", False),
]
MASK_ANGLES = [
    "Three-quarter view at eye level. 50mm look.",
    "Side profile showing the mask's shape and how it sits on the face. 85mm look.",
    "Slightly high angle looking down as she sits or reclines. 35mm look.",
    "Medium close-up from the chest up, the mask's details sharp. 85mm look.",
    "Wider shot showing her in the room, still close enough to see the mask's details. 35mm look.",
]


def _mask(arabic: bool):
    place, indoor = random.choice(MASK_SETTINGS)
    pose, face_visible = random.choice(MASK_POSES)
    mood = (f"Expression: {random.choice(EXPRESSIONS)}, looking at the camera." if face_visible
            else "Her face is covered by the mask; her relaxed posture shows she's enjoying it.")
    person = f"THE PERSON:\n{_person('woman', (22, 32, 46), 'selfcare', arabic)} She is {pose}. {mood}"
    rules = [
        "Exactly one woman, with exactly two hands and five fingers on each.",
        "Only one mask in the image.",
        "No brand logos or text on the mask or anywhere else.",
    ]
    return [MASK_PRODUCT, person, _setting(place, indoor, arabic),
            _camera(random.choice(MASK_ANGLES))], rules, f"{place} | {pose}"


# =========================================================================== #
# Entry point
# =========================================================================== #
BUILDERS = {
    "Automatic Nail Clipper": _clipper,
    "Baby Nail File": _nail_file,
    "Baby Sculpting Device": _sculpt,
    "Breast Pumps": _pump,
    "Inflatable Baby Seat": _seat,
    "LED Beauty Mask": _mask,
}
SCENE_PRODUCTS = set(BUILDERS)


def build_scene_prompt(base_key: str, arabic: bool = False) -> str:
    """A fresh random scene for one product."""
    if base_key not in BUILDERS:
        raise ValueError(f"No scene builder for: {base_key}")
    sections, product_rules, summary = BUILDERS[base_key](arabic)
    rules = product_rules + COMMON_RULES + ([GULF_RULE] if arabic else [])
    log.info("Scene for %s: %s", base_key, summary)
    intro = (
        "You are an expert lifestyle product photographer. Analyze all the reference images carefully, then create "
        "one photorealistic lifestyle photo of this product for a social media post. Every detail below was chosen "
        "for this image only: follow it exactly instead of falling back on a standard posed shot."
    )
    return "\n\n".join([intro, *sections, "RULES:\n" + "\n".join(f"- {r}" for r in rules)])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) > 1:
        cases = [(sys.argv[1], False), (sys.argv[1], True)]
    else:
        cases = [(key, False) for key in BUILDERS]
    for key, arabic in cases:
        print("=" * 80)
        print(f"{key}{'  [ARABIC]' if arabic else ''}")
        print("=" * 80)
        print(build_scene_prompt(key, arabic=arabic))
        print()