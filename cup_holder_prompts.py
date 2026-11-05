"""
cup_holder_prompts.py

Builds a new randomized scene prompt for the stroller cup holder products every
time it is called, so batches stop repeating the same side-profile park shot.

Random choices are paired so each scene stays logical:
  - setting -> lighting -> climate -> clothing
  - mount position -> who can reach it -> drink, tray contents, baby action
  - every camera angle faces the organizer's outer side, so the clamp stays hidden
  - the Arabic (Saudi Arabia / UAE) post uses a Gulf Arab guardian in Gulf
    locations, in modern everyday clothes with no head covering or traditional dress
"""

import logging
import random

log = logging.getLogger("product_image_gen")

# --------------------------------------------------------------------------- #
# Product designs (design only; the scene is built separately)
# --------------------------------------------------------------------------- #
_UNIVERSAL_SHAPE = (
    "a two-compartment stroller organizer: on one side a deep round cup holder with a flexible rubber collar "
    "around its rim, four small rubber grip tabs inside, and a narrow vertical slot cut into its outer wall for a "
    "cup handle; on the other side a deep rounded-rectangle snack bin; both joined by one flat top rim."
)

CUP_HOLDER_PRODUCTS = {
    "Gray stroller cup holder": {
        "description": (
            f"The product is {_UNIVERSAL_SHAPE} The body is matte black plastic; the rubber collar and grip "
            "tabs are light grey. Its visible surfaces are smooth, with no knobs or buttons."
        ),
    },
    "Blue Stroller Cup Holder": {
        # Same one-piece body as the gray version; only the collar color differs.
        "description": (
            f"The product is {_UNIVERSAL_SHAPE} The body is black plastic; the rubber collar around the cup "
            "holder's rim is a bright royal blue. Its visible surfaces are smooth, with no knobs or buttons."
        ),
    },
    "Green stroller cup holder": {
        # Same one-piece body again; only the collar color differs. Match the shade
        # of green to the reference photos if it looks off.
        "description": (
            f"The product is {_UNIVERSAL_SHAPE} The body is black plastic; the rubber collar around the cup "
            "holder's rim is green. Its visible surfaces are smooth, with no knobs or buttons."
        ),
    },
    "Detachable Cup Holder": {
        "tray": "snack tray",  # what the prompt calls the snack compartment
        # A different design: a separate caged cup holder with a small tray clipped to its side.
        "description": (
            "The product is a matte black plastic stroller cup holder with a detachable snack tray. The cup "
            "holder is a tall cylinder: its upper part is a solid cup whose rim rises into two tall rounded points "
            "on opposite sides, like cat ears, with a deep U-shaped dip between them at the front and back; its "
            "lower part is an open cage of evenly spaced vertical ribs with rounded arch cut-outs near the base, "
            "so the drink shows through the gaps. A small round button sits on the side of the solid upper part. "
            "A small rounded-rectangle snack tray with a thin rolled rim is clipped flush against one side of the "
            "cup holder, its top edge roughly level with the dip in the holder's rim. The tray is much shallower "
            "than the cup holder and is a separate clip-on piece, not molded into it."
        ),
    },
}

# --------------------------------------------------------------------------- #
# Scene pools
# --------------------------------------------------------------------------- #
ETHNICITIES = [
    "East Asian", "South Asian", "Southeast Asian", "Black", "Latino",
    "Middle Eastern", "white", "mixed-race", "Pacific Islander",
]

# (place, lighting, climate). Climate decides the clothing below.
SETTINGS = [
    ("a city sidewalk outside a café with empty outdoor tables", "soft morning sunlight", "mild"),
    ("a seaside boardwalk with the ocean behind", "warm golden-hour light", "warm"),
    ("a marina pier lined with sailboats", "clear midday sun", "warm"),
    ("a palm-lined waterfront promenade", "bright late-morning sun", "warm"),
    ("a cherry-blossom walkway", "bright, soft spring daylight", "mild"),
    ("a quiet cobblestone old-town square", "late-afternoon sun", "mild"),
    ("a riverside path with a footbridge in the distance", "soft early-evening light", "mild"),
    ("a tree-lined suburban street covered in autumn leaves", "soft overcast light", "cool"),
    ("a city plaza in front of a modern museum", "cool overcast daylight", "cool"),
    ("a cleared park path with snow banks on either side", "crisp, bright winter sun", "cold"),
    ("an indoor shopping mall concourse with glass storefronts", "bright, even indoor lighting", "indoor"),
    ("a botanical garden glasshouse full of tropical plants", "filtered daylight through the glass roof", "indoor"),
    ("an airport terminal beside floor-to-ceiling windows", "natural window light", "indoor"),
]

# Used only for the Arabic (Saudi Arabia / UAE) post.
GULF_SETTINGS = [
    ("a palm-lined waterfront corniche promenade", "warm late-afternoon sun", "gulf"),
    ("a modern shopping mall atrium with marble floors", "bright, even indoor lighting", "gulf"),
    ("a landscaped city park with palm trees and a fountain", "golden-hour light", "gulf"),
    ("a café terrace on a palm-lined boulevard", "soft morning sun", "gulf"),
    ("a modern airport terminal with sweeping white architecture", "natural window light", "gulf"),
]

OUTFITS = {
    # Gulf posts: modern everyday clothes, no head covering or traditional dress.
    "gulf": {
        "adult": ["a loose linen shirt and light trousers", "a long-sleeved cotton top and wide-leg trousers",
                  "a lightweight knit top and tailored trousers"],
        "baby": ["a short-sleeved cotton romper", "a light long-sleeved bodysuit"],
    },
    "warm": {
        "adult": ["a linen shirt and light trousers", "a T-shirt and shorts",
                  "a short-sleeved shirt and linen shorts", "a short-sleeved polo and chinos"],
        "baby": ["a cotton romper and a sun hat", "a short-sleeved bodysuit and a bucket hat",
                 "a sleeveless romper"],
    },
    "mild": {
        "adult": ["a denim jacket over a T-shirt", "a light knit sweater and jeans",
                  "a light trench coat", "an overshirt and chinos"],
        "baby": ["a long-sleeved bodysuit and soft pants", "a light cardigan and leggings", "a cotton jumpsuit"],
    },
    "cool": {
        "adult": ["a wool coat and a scarf", "a quilted jacket and jeans", "a chunky knit sweater and a long coat"],
        "baby": ["a knit sweater and a beanie", "a fleece jumpsuit and a knit hat"],
    },
    "cold": {
        "adult": ["a puffer jacket, a scarf and a knit hat", "a long wool coat and a beanie"],
        "baby": ["a padded snowsuit and a knit hat", "a fleece-lined snowsuit with a hood"],
    },
    "indoor": {
        "adult": ["a casual sweater and jeans", "a knit polo and tailored trousers",
                  "a hoodie and joggers", "a button-up shirt and chinos"],
        "baby": ["a long-sleeved bodysuit", "a cotton romper", "a soft knit set"],
    },
}

# (canopy, frame). Delete all but the first entry to lock in the grey/silver look.
STROLLER_LOOKS = [
    ("grey", "silver"),
    ("light grey", "silver"),
    ("charcoal", "matte black"),
    ("navy", "matte black"),
    ("sand-beige", "champagne-gold"),
    ("olive-green", "matte black"),
]

# All of these see the organizer's outer face, so the clamp behind it stays hidden.
CAMERAS = [
    "Classic side profile at waist height, medium distance; the guardian enters the frame from the side, "
    "visible from the head to mid-thigh.",
    "Three-quarter front view from the organizer's side, camera at the baby's eye level; the guardian is "
    "visible from the waist up behind the stroller.",
    "Three-quarter rear view from behind and beside the guardian at shoulder height, looking past them toward "
    "the stroller; the guardian's face is in partial profile.",
    "Close-up with shallow depth of field, camera at the organizer's own height: the organizer is large and "
    "sharp in the foreground, the baby and guardian softly blurred behind it.",
    "Wide eye-level shot from the front-side diagonal, the whole stroller and guardian in frame with the "
    "setting visible around them.",
]

GUARDIAN_ACTIONS = [
    "walking slowly and smiling down at the baby",
    "pausing mid-stroll and laughing with the baby",
    "walking with a relaxed smile, looking ahead",
    "standing still and leaning slightly forward to talk to the baby",
]

BABY_ACTIONS = [
    "looking curiously toward the camera",
    "smiling and pointing at something off-frame",
    "laughing up at the guardian",
    "holding a small soft toy in both hands",
    "gazing around at the surroundings, calm and content",
]
# Only used when the organizer is mounted within the baby's reach.
BABY_REACH_ACTIONS = [
    "reaching into the snack bin to pick up a snack",
    "holding a snack just taken from the snack bin",
    "resting one hand on the drink in the cup holder",
]

BABY_DRINKS = [
    "a baby bottle of milk with a clear cap",
    "a sippy cup",
    "a small stainless-steel kids' water bottle",
    "a clear water bottle with a straw lid",
]
PARENT_DRINKS = [
    "a lidded iced coffee in a clear cup with a straw",
    "an insulated coffee tumbler",
    "a reusable water bottle",
]
BABY_SNACKS = [
    "puffs", "O-shaped cereal", "blueberries", "yogurt melts",
    "freeze-dried strawberries", "small cheese crackers", "teething wafers", "rice-cake pieces",
]
PARENT_ITEMS = ["a phone and a set of keys", "sunglasses and a set of keys"]

MOUNTS = {
    "handle": {
        "where": "the side tube of the push handle, on the side of the stroller facing the camera, just below "
                 "the guardian's hand, where the guardian can reach it",
        "drinks": BABY_DRINKS + PARENT_DRINKS,
        "extra_fills": PARENT_ITEMS,
        "baby_actions": BABY_ACTIONS,  # out of the baby's reach here
    },
    "seat": {
        "where": "the side frame tube beside the baby's seat, on the side of the stroller facing the camera, "
                 "at armrest height where the baby can reach it",
        "drinks": BABY_DRINKS,
        "extra_fills": [],
        "baby_actions": BABY_ACTIONS + BABY_REACH_ACTIONS,
    },
}


# --------------------------------------------------------------------------- #
# Builder
# --------------------------------------------------------------------------- #
def _tray_fill(extra_fills: list[str]) -> str:
    if extra_fills and random.random() < 0.25:
        return random.choice(extra_fills)
    return " and ".join(random.sample(BABY_SNACKS, random.choice([1, 2])))


def build_cup_holder_prompt(product_key: str, arabic: bool = False) -> str:
    """Return a new randomized prompt for one of the cup holder products."""
    spec = CUP_HOLDER_PRODUCTS[product_key]
    mount_key = random.choice(list(MOUNTS))
    mount = MOUNTS[mount_key]
    place, light, climate = random.choice(GULF_SETTINGS if arabic else SETTINGS)
    camera = random.choice(CAMERAS)
    canopy, frame = random.choice(STROLLER_LOOKS)
    outfits = OUTFITS[climate]

    age, gender, outfit = random.randint(20, 40), random.choice(["man", "woman"]), random.choice(outfits["adult"])
    if arabic:
        guardian = (
            f"a {age}-year-old Gulf Arab {gender} of Saudi or Emirati appearance, with uncovered, casually styled "
            f"hair (no hijab or other head covering, and no traditional dress), wearing {outfit},"
        )
    else:
        guardian = (
            f"a {age}-year-old {random.choice(spec.get('ethnicities', ETHNICITIES))} {gender} wearing {outfit}"
        )
    baby = f"a {random.randint(9, 24)}-month-old baby wearing {random.choice(outfits['baby'])}"
    drink = random.choice(mount["drinks"])
    fill = _tray_fill(mount["extra_fills"])

    log.info("Cup holder scene: %s | %s | %s mount | %s | %s | %s",
             "Gulf" if arabic else "casual", place, mount_key, camera.split(",")[0], drink, fill)

    prompt = (
        "You are an expert lifestyle product photographer. Create ONE photorealistic commercial photograph.\n"
        "The reference images show the product's design only. Copy the product exactly, but do NOT copy the "
        "backgrounds, strollers, people, props or camera angles in them; this is a new scene.\n\n"
        f"CAMERA: {camera}\n"
        f"SETTING: {place}, in {light}. The background is softly out of focus.\n\n"
        f"PEOPLE: {guardian} is {random.choice(GUARDIAN_ACTIONS)}, with both hands on the stroller handlebar. "
        f"In the stroller, {baby}, who plausibly looks like the guardian's own child, sits upright, buckled "
        f"into the harness, {random.choice(mount['baby_actions'])}.\n\n"
        f"STROLLER: a modern luxury stroller; its fabric canopy is {canopy} and its frame is {frame}. All four wheels "
        "rest on the ground with soft contact shadows.\n\n"
        f"PRODUCT: {spec['description']} The organizer is clamped to {mount['where']}. Although that tube is angled, the "
        "organizer sits perfectly level with the ground, so the drink stands upright and nothing spills. The "
        "mounting clamp is on the side facing the stroller tube and is hidden from the camera. There is no text "
        "or logo on the organizer or on anything in it, including snack wrappers. "
        f"The cup holder holds {drink}; the snack bin holds {fill}, resting naturally inside and not overflowing. "
        "The organizer is at realistic scale (the cup holder fits a single baby bottle), sharp, in focus, and "
        "nothing blocks the camera's view of it.\n\n"
        "REALISM: one consistent light direction, with matching shadows on the people, stroller and product. "
        "Clothing suits the weather and location.\n\n"
        "CONSTRAINTS: exactly one adult and one baby, each with two arms and two hands with five fingers; exactly "
        "one stroller; no other people, extra hands or partial figures anywhere in the frame."
    )
    return prompt.replace("snack bin", spec.get("tray", "snack bin"))


if __name__ == "__main__":
    # Quick preview: python cup_holder_prompts.py
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for key in CUP_HOLDER_PRODUCTS:
        print(f"\n===== {key} =====\n{build_cup_holder_prompt(key)}")
