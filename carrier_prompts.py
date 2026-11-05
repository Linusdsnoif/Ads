"""
carrier_prompts.py

Builds a new randomized scene prompt for the three baby carriers every time it
is called. Setting, activity, guardian, clothing, baby and camera all vary,
while each carrier's design description stays fixed and matches its reference
photos.

Choices are paired so each scene stays logical:
  - every setting has its own lighting, climate and activities that fit it
  - every activity says exactly what BOTH of the guardian's hands are doing, so
    the model never has a spare hand to hide (a hidden hand usually comes out as
    a missing one)
  - activities are ones a real parent can do with a baby facing outward: nothing
    that needs the arms to reach around the baby, and nothing the baby's legs
    would bump into (shopping carts, desks, sinks, counters)
  - climate decides clothing, and the guardian's clothing always contrasts with
    the carrier so its outline and logo stay visible
  - babies are 6-15 months old, old enough to face outward with steady head control
  - the Arabic (Gulf) variant uses a Gulf Arab guardian in Gulf locations, in
    modern everyday clothes with no head covering or traditional dress
"""

import logging
import random

log = logging.getLogger("product_image_gen")

# --------------------------------------------------------------------------- #
# Product designs (design only; the scene is built separately)
# --------------------------------------------------------------------------- #
# Gray Baby Carrier and Breathable Baby Carrier are the same hip-seat carrier
# in two colorways, so they share how the baby sits in it.
_HIP_SEAT_FIT = (
    "The baby faces outward, its back against the guardian's chest, and sits securely on the hip seat. The "
    "folded head flap sits just under the baby's chin, the baby's arms come out over the sides of the panel, and "
    "the legs hang naturally through the leg openings."
)

CARRIER_PRODUCTS = {
    "Gray Baby Carrier": {
        "design": (
            "PRODUCT DESIGN (copy exactly from the reference images): a hip-seat baby carrier in a soft two-tone gray.\n"
            "- Main body: smooth, matte, warm light taupe-gray canvas (about #B3ACAE). This is the color of the "
            "shoulder straps, the front panel and the hip seat.\n"
            "- Shoulder straps: wide, thick, padded straps covered entirely in the same smooth, solid taupe-gray "
            "canvas, with matching taupe-gray edges; each strap is one uniform color across its full width and "
            "length. On each strap, a round black snap button is joined by a short black elastic loop to a second "
            "black snap button fastened at the top corner of the head flap.\n"
            "- Head flap: folded down across the top of the front panel as a wide, rounded, padded roll of smooth "
            "cool blue-gray fabric (about #A5A8B5), slightly bluer and darker than the main body.\n"
            "- Zip panel: directly below the head flap, a smooth taupe-gray panel closed by a light-gray zipper that "
            "curves down one side and along its bottom edge. It is a roll-up breathable panel shown zipped shut, so "
            "no mesh shows here.\n"
            "- Front panel: below the zip panel, smooth taupe-gray fabric that narrows to a soft pointed tip between "
            "the baby's legs. At each leg opening sits a padded, wing-shaped cushion of dark charcoal 3D mesh "
            "(about #6E727C).\n"
            "- Hip seat: a tall, firm, padded taupe-gray waist belt, about as tall as a hand is long, worn around the "
            "guardian's waist directly under the baby. The center front of the hip seat, directly below the baby, "
            "is plain, smooth taupe-gray fabric.\n"
            "- Storage pouch: a taupe-gray zippered pouch built into the hip seat on the guardian's right hip (the "
            "viewer's left), on the side of the waist well away from the center, with its zipper running "
            "horizontally along its top edge.\n"
            "- Dark accents: the charcoal leg cushions, black snap buttons and elastic loops, and dark charcoal "
            "(about #3A3A3C) webbing adjusters and buckles. Apart from the leg cushions, every visible surface is "
            "smooth, solid canvas.\n"
            "- Branding: a small anchor symbol directly above the word \"LUFFCABO\", printed in muted slate "
            "blue-gray directly onto the taupe fabric, with the fabric visible all around it. Logo 1 is centered on "
            "the front panel just below the zip panel, about the size of the baby's palm. Logo 2 is very small, in "
            "the lower front corner of the storage pouch."
        ),
        "fit": _HIP_SEAT_FIT,
        # Clothing colors that stand out against taupe-gray.
        "top_colors": ["navy", "white", "olive green", "terracotta", "denim blue", "burgundy", "mustard yellow"],
        "checks": [
            "The shoulder straps are solid smooth taupe-gray from edge to edge.",
            "Below the head flap is a zipped-shut taupe panel, not a mesh window.",
            "The storage pouch is on the guardian's right hip, and the center front of the hip seat is plain.",
            "\"LUFFCABO\" is spelled correctly.",
        ],
    },
    "Breathable Baby Carrier": {
        "design": (
            "PRODUCT DESIGN (copy exactly from the reference images): a hip-seat baby carrier that is solid black "
            "all over.\n"
            "- Main body: smooth, matte black canvas. The shoulder straps, head flap, front panel, leg cushions and "
            "hip seat are all black.\n"
            "- Shoulder straps: wide, thick, padded black straps. Near the top of the front panel, each strap has two "
            "round black snap buttons with silver rims, joined by a short, narrow light-gray tab; one button sits on "
            "the strap and the other on the top corner of the head flap.\n"
            "- Head flap: folded down across the top of the front panel as a wide, rounded, padded black roll.\n"
            "- Zip panel: directly below the head flap, a smooth black panel closed by a black zipper that curves "
            "down one side and along its bottom edge. It is a roll-up breathable panel shown zipped shut.\n"
            "- Front panel: below the zip panel, smooth black fabric that narrows between the baby's legs, with "
            "padded black mesh cushions at the leg openings.\n"
            "- Hip seat: a tall, firm, padded black waist belt worn directly under the baby; its center front is "
            "plain black fabric.\n"
            "- Storage pouch: a black zippered pouch built into the hip seat on the guardian's right hip (the "
            "viewer's left), with its zipper along its top edge.\n"
            "- Accents: black webbing and black buckles. The only non-black details are the silver button rims, the "
            "two light-gray tabs and the white logos.\n"
            "- Branding: a small white anchor symbol directly above the word \"LUFFCABO\", screen-printed directly "
            "on the black fabric, with black fabric visible all around it. Logo 1 is centered on the front panel "
            "just below the zip panel, about the width of the baby's palm. Logo 2 is very small, in the lower "
            "corner of the storage pouch."
        ),
        "fit": _HIP_SEAT_FIT,
        # Clothing colors that stand out against black.
        "top_colors": ["white", "cream", "light blue", "sage green", "camel", "blush pink", "light gray"],
        "checks": [
            "Every part of the carrier is black except the silver button rims, the two light-gray tabs and the "
            "white logos.",
            "Below the head flap is a zipped-shut black panel, not a mesh window.",
            "The storage pouch is on the guardian's right hip.",
            "\"LUFFCABO\" is spelled correctly.",
        ],
    },
    "Breathable Baby CarrierM": {
        "design": (
            "PRODUCT DESIGN (copy exactly from the reference images): a soft, structured baby carrier made almost "
            "entirely of breathable 3D air mesh, light gray-white with a honeycomb pattern of small gray oval "
            "perforations.\n"
            "- Mesh: the shoulder straps, the front panel and the waist belt are all this same light air mesh.\n"
            "- Head support: a padded band of smooth medium-gray fabric folded across the top of the front panel.\n"
            "- Front panel: light air mesh with a slightly raised rounded-rectangle pad in its center. It narrows "
            "between the baby's legs, where padded, wing-shaped leg cushions of smooth medium-gray fabric frame each "
            "leg opening.\n"
            "- Shoulder straps: wide, padded mesh straps lined with medium-gray fabric on the underside. At chest "
            "height, each has a light-gray plastic sliding buckle on medium-gray webbing.\n"
            "- Side straps: medium-gray webbing with light-gray plastic buckles joins the sides of the front panel "
            "to the waist belt.\n"
            "- Waist belt: a tall, wide, padded belt of the same air mesh, with gray webbing adjusters and a "
            "light-gray buckle.\n"
            "- Branding: exactly one logo, a small square black woven patch on the lower center of the front panel, "
            "with a white anchor icon above the white word \"LUFFCABO\", both inside the patch. There are no other "
            "logos or text."
        ),
        "fit": (
            "The baby faces outward, its back against the guardian's chest. The gray head-support band sits just "
            "under the baby's chin, the baby's arms come out over the sides of the panel, and the legs hang "
            "naturally through the leg openings, framed by the gray leg cushions."
        ),
        # Clothing colors that stand out against light gray-white mesh.
        "top_colors": ["navy", "black", "olive green", "rust", "denim blue", "burgundy", "forest green"],
        "checks": [
            "The carrier is light gray-white air mesh with medium-gray accents; it is not dark and not solid fabric.",
            "There is exactly one black square logo patch, reading \"LUFFCABO\" correctly.",
        ],
    },
}

COMMON_CHECKS = [
    "The guardian's whole face is visible in the frame.",
    "Follow each of the guardian's sleeves to its end: each ends in a visible hand with five fingers, doing "
    "exactly what HANDS describes. No arm fades out, stops at the baby, or disappears behind the baby or carrier.",
    "The baby faces outward and looks toward the camera.",
    "There is exactly one guardian and one baby, both with normal anatomy.",
]

# --------------------------------------------------------------------------- #
# Scene pools
# --------------------------------------------------------------------------- #
ETHNICITIES = [
    "East Asian", "South Asian", "Southeast Asian", "Black", "Latino",
    "Middle Eastern", "white", "mixed-race", "Pacific Islander",
]

# Where the guardian's second hand goes when the activity only uses one. Each
# position is natural for a parent carrying an outward-facing baby, easy for the
# camera to see, and clear of the front logo.
OTHER_HAND = [
    "the other hand rests lightly on the outside of the baby's knee, at the side of the carrier",
    "the other hand gently holds one of the baby's feet",
    "the other hand holds the shoulder strap at chest height, beside the baby's shoulder",
    "the other hand rests on the side of the carrier's waist belt, clear of any logo",
    "the other arm hangs relaxed at the guardian's side, the hand open and visible",
]

# (place, lighting, climate, [(activity, hands)]). `hands` says what both hands
# do; "{other}" is filled from OTHER_HAND. Activities keep the baby's legs clear
# of furniture and keep hot drinks and sharp objects away from the baby.
SETTINGS = [
    ("a bright grocery store produce aisle", "even, bright store lighting", "indoor", [
        ("choosing an apple from the produce display",
         "one hand picks up an apple from the display, and {other}"),
        ("carrying a shopping basket along the aisle",
         "one hand carries a small shopping basket down at the side, and {other}"),
    ]),
    ("an open-air farmers market", "soft morning sunlight", "mild", [
        ("browsing a crate of fresh peaches",
         "one hand holds up a peach to look at it, and {other}"),
        ("carrying a paper bag of vegetables",
         "one arm holds a paper bag of vegetables against the guardian's side, away from the baby, and {other}"),
    ]),
    ("a cozy home kitchen", "warm morning light from a window", "indoor", [
        ("testing the warmth of a baby bottle",
         "one hand holds a baby bottle and tips a drop onto the inside of the other wrist, both hands held out "
         "to the side of the baby"),
        ("taking a carton of milk from the open fridge door",
         "one hand lifts the carton from the fridge door, and {other}"),
    ]),
    ("a sunny home office with plants and a wooden desk", "soft natural window light", "indoor", [
        ("standing beside the desk, reading a printed document",
         "one hand holds the document out to the side, and {other}"),
        ("watering a small plant on the desk",
         "one hand tips a small watering can over the plant, and {other}"),
    ]),
    ("a living room with a sofa and soft rugs", "soft afternoon light", "indoor", [
        ("standing by the window, pointing outside for the baby",
         "one hand points out of the window, and {other}"),
        ("showing the baby a soft toy",
         "one hand holds a soft toy out to the side where the baby can see it, and {other}"),
    ]),
    ("a quiet bookstore aisle with wooden shelves", "warm indoor light", "indoor", [
        ("browsing a book",
         "one hand holds the open book out to the side, and {other}"),
    ]),
    ("a bright art gallery with abstract paintings on white walls", "soft gallery lighting", "indoor", [
        ("standing in front of a painting, showing it to the baby",
         "one hand points toward the painting, and {other}"),
    ]),
    ("an airport terminal beside floor-to-ceiling windows", "natural window light", "indoor", [
        ("walking while pulling a carry-on suitcase",
         "one hand pulls the suitcase by its handle, slightly behind, and {other}"),
    ]),
    ("a tree-lined city sidewalk", "soft overcast light", "mild", [
        ("walking and glancing down at the baby",
         "one hand carries a tote bag by its handles down at the side, and {other}"),
        ("walking with a takeaway coffee",
         "one hand holds a lidded takeaway coffee out to the side, away from the baby, and {other}"),
    ]),
    ("a forest walking trail", "dappled sunlight through the trees", "mild", [
        ("walking along the trail",
         "one hand holds a small water bottle down at the side, and {other}"),
    ]),
    ("a botanical garden path among flowering bushes", "bright spring daylight", "mild", [
        ("pausing to show the baby the flowers",
         "one hand gently lifts a flower on a nearby bush toward the baby, and {other}"),
    ]),
    ("a seaside boardwalk", "warm golden-hour light", "warm", [
        ("walking along the boardwalk",
         "one hand holds a pair of sunglasses down at the side, and {other}"),
        ("standing at the railing looking out to sea",
         "one hand rests on the railing beside the guardian, and {other}"),
    ]),
    ("a sunny backyard garden", "warm afternoon light", "warm", [
        ("watering potted plants",
         "one hand tips a small watering can over a pot, out to the side, and {other}"),
    ]),
    ("an outdoor winter market with string lights", "the warm glow of string lights at dusk", "cold", [
        ("holding a cup of hot cocoa",
         "one hand holds a lidded cup of hot cocoa out to the side, away from the baby, and {other}"),
    ]),
    ("a snowy residential street", "crisp, bright winter sun", "cold", [
        ("walking along the cleared sidewalk",
         "one gloved hand carries a small paper shopping bag down at the side, and {other}"),
    ]),
]

# Used only for the Arabic (Saudi Arabia / UAE) post.
GULF_SETTINGS = [
    ("a waterfront corniche promenade lined with palm trees", "warm late-afternoon sun", "gulf", [
        ("walking along the promenade",
         "one hand holds a small water bottle down at the side, and {other}"),
        ("pausing at the railing to look out at the water",
         "one hand rests on the railing beside the guardian, and {other}"),
    ]),
    ("a modern shopping mall atrium with marble floors", "bright, even indoor light", "gulf", [
        ("browsing a shop window",
         "one hand points at something in the window for the baby, and {other}"),
        ("walking while carrying a small shopping bag",
         "one hand carries the shopping bag down at the side, and {other}"),
    ]),
    ("a landscaped city park with palm trees and a fountain", "golden-hour light", "gulf", [
        ("walking along the park path",
         "one hand holds a pair of sunglasses down at the side, and {other}"),
    ]),
    ("a bright modern living room with geometric-patterned cushions and warm gold accents", "soft, warm light", "gulf", [
        ("reading a picture book to the baby",
         "both hands hold a small open picture book out to one side of the baby, angled so the baby can see the "
         "pages, leaving the carrier's front panel uncovered"),
        ("standing by the window, showing the baby the view",
         "one hand points out of the window, and {other}"),
    ]),
    ("a supermarket aisle stocked with dates and fresh produce", "even, bright store lighting", "gulf", [
        ("choosing a box of dates from the shelf",
         "one hand lifts a box of dates from the shelf, and {other}"),
        ("carrying a shopping basket along the aisle",
         "one hand carries a small shopping basket down at the side, and {other}"),
    ]),
    ("a café terrace on a palm-lined boulevard", "soft morning sun", "gulf", [
        ("holding an iced coffee",
         "one hand holds a lidded iced coffee out to the side, away from the baby, and {other}"),
    ]),
    ("a modern airport terminal with sweeping white architecture", "natural window light", "gulf", [
        ("walking while pulling a carry-on suitcase",
         "one hand pulls the suitcase by its handle, slightly behind, and {other}"),
    ]),
]

# {c} is filled with one of the product's contrast colors.
OUTFITS = {
    "warm": ["{c} linen shirt and light trousers", "{c} T-shirt and shorts", "{c} short-sleeved shirt and chinos"],
    "mild": ["{c} long-sleeved top and jeans", "{c} light sweater and chinos", "{c} button-up shirt and jeans"],
    "indoor": ["{c} T-shirt and jeans", "{c} knit sweater and trousers", "{c} button-up shirt and chinos"],
    "cold": ["{c} wool coat, with the carrier worn over it", "{c} puffer jacket, with the carrier worn over it"],
    # Gulf posts: modern everyday clothes, no head covering or traditional dress.
    # Swap in OUTFITS["warm"] here if you don't want the longer sleeves and trousers.
    "gulf": ["{c} loose linen shirt and light trousers", "{c} long-sleeved cotton top and wide-leg trousers",
             "{c} lightweight knit top and tailored trousers"],
}

BABY_COLORS = ["white", "pale yellow", "mint green", "light pink", "sky blue", "cream"]
BABY_OUTFITS = {
    "warm": ["short-sleeved cotton romper", "sleeveless bodysuit and a sun hat"],
    "mild": ["long-sleeved bodysuit and soft leggings", "striped cotton romper"],
    "indoor": ["long-sleeved bodysuit and soft leggings", "short-sleeved cotton romper"],
    "cold": ["padded snowsuit and a knit hat"],
    "gulf": ["short-sleeved cotton romper", "light long-sleeved bodysuit"],
}
BABY_MOODS = [
    "smiling at the camera",
    "looking at the camera with wide, curious eyes",
    "giggling at the camera",
    "calm and content, gazing at the camera",
]

# Any body turn is toward the viewer's right, which keeps the hip-seat carriers'
# storage pouch (on the guardian's right hip) facing the camera. Every framing
# goes low enough to include both hands.
CAMERAS = [
    "Medium shot from mid-thigh up, camera at chest height, the guardian facing the camera straight on.",
    "Medium shot from mid-thigh up, camera at chest height, the guardian's body turned about 20 degrees toward "
    "the viewer's right.",
    "Shot from the upper thighs up, camera at chest height, a little closer, with a shallow depth of field.",
    "Medium-wide environmental shot from the knees up, with the setting clearly visible around the guardian.",
    "Candid shot from slightly to the side, camera at chest height, the guardian turned about 30 degrees toward "
    "the viewer's right and glancing toward the camera.",
]


# --------------------------------------------------------------------------- #
# Builder
# --------------------------------------------------------------------------- #
def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def build_carrier_prompt(product_key: str, arabic: bool = False) -> str:
    """Return a new randomized prompt for one of the baby carriers."""
    spec = CARRIER_PRODUCTS[product_key]
    place, light, climate, activities = random.choice(GULF_SETTINGS if arabic else SETTINGS)
    activity, hands = random.choice(activities)
    if "{other}" in hands:
        hands = hands.format(other=random.choice(OTHER_HAND))
    camera = random.choice(CAMERAS)

    top_color = random.choice(spec["top_colors"])
    outfit = f"{_article(top_color)} " + random.choice(OUTFITS[climate]).format(c=top_color)
    baby_color = random.choice(BABY_COLORS)
    baby_outfit = f"{_article(baby_color)} {baby_color} " + random.choice(BABY_OUTFITS[climate])

    age = random.randint(25, 40)
    gender = random.choice(["man", "woman"])
    if arabic:
        guardian = (
            f"a {age}-year-old Gulf Arab {gender} of Saudi or Emirati appearance, with uncovered, casually styled "
            "hair (no hijab or other head covering, and no traditional dress)"
        )
    else:
        guardian = f"a {age}-year-old {random.choice(ETHNICITIES)} {gender}"

    checks = "\n".join(f"{i}. {c}" for i, c in enumerate(spec["checks"] + COMMON_CHECKS, start=1))

    log.info("Carrier scene: %s | %s | %s | %s",
             "Gulf" if arabic else "casual", place, activity, camera.split(",")[0])

    return (
        "You are an expert commercial lifestyle photographer. Create ONE photorealistic photograph: one shot, one "
        "camera angle.\n"
        "The reference images show the exact product. Copy the carrier from them in every detail, but ignore any "
        "circular inset close-ups, labels, arrows, headings or text in them, and do NOT copy their backgrounds, "
        "people, poses or camera angles. The people in the reference photos are only product models: the guardian "
        "and baby must be different people with completely different faces.\n\n"
        f"CAMERA: {camera} There is clear space above the guardian's head, and the guardian's entire face, from "
        "hairline to chin, is inside the frame and in sharp focus. Both of the guardian's hands are inside the "
        "frame.\n"
        f"SETTING: {place}, in {light}. The background is softly out of focus.\n\n"
        f"GUARDIAN: {guardian}, wearing {outfit}, is {activity}, with a warm, natural smile. The {top_color} "
        "clothing contrasts with the carrier, so the carrier's outline and logo stand out clearly.\n\n"
        f"HANDS: {hands[0].upper() + hands[1:]}. Both of the guardian's arms are complete from shoulder to "
        "fingertips, and both hands are fully visible, each joined to its arm at a visible wrist. Neither hand is "
        "tucked behind the baby or the carrier, and neither covers the front logo.\n\n"
        f"BABY: a baby, {random.randint(6, 15)} months old, wearing {baby_outfit}, who plausibly looks like the "
        f"guardian's own child, {random.choice(BABY_MOODS)}. {spec['fit']}\n\n"
        f"{spec['design']}\n\n"
        "REALISM: one consistent light direction with matching shadows; the straps sit naturally on the guardian's "
        "shoulders and the baby's weight looks real; clothing suits the weather and the location. The pose is one "
        "a real parent would hold comfortably: the baby's legs hang freely without pressing against shelves, "
        "furniture or anything else, and nothing hot or sharp is within the baby's reach.\n\n"
        "CONSTRAINTS: exactly one adult and one baby. The guardian has exactly two arms and two hands; the baby has "
        "exactly two arms, two hands, two legs and two feet; every hand has five fingers. No other people, extra "
        "hands or partial figures anywhere in the frame. No text or logos anywhere except the carrier's own "
        "LUFFCABO logos.\n\n"
        f"FINAL CHECK BEFORE OUTPUT:\n{checks}"
    )


if __name__ == "__main__":
    # Quick preview: python carrier_prompts.py
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for key in CARRIER_PRODUCTS:
        print(f"\n===== {key} =====\n{build_carrier_prompt(key)}")
    print(f"\n===== Breathable Baby Carrier (Arabic) =====\n{build_carrier_prompt('Breathable Baby Carrier', arabic=True)}")