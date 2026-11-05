"""
captions.py

Reads and checks the caption files Gemini writes to output_descriptions/.

Used by generate_product_images.py (each caption is checked before it is saved,
and regenerated if it fails) and by publish_social.py (parses the file, and
refuses to post one that is broken). It has no third-party imports, so either
side can use it without pulling in the other's dependencies.
"""

from __future__ import annotations

import re

# Threads rejects posts longer than this. Facebook and Instagram allow more,
# so this is the limit every caption has to fit.
THREADS_MAX_CHARS = 500

_CAPTION_LABEL = re.compile(r"^\s*Caption\s*:\s*", re.M | re.I)
_ALT_LABEL = re.compile(r"^\s*Alt[\s\-]*Text\s*:\s*", re.M | re.I)


def extract_caption(raw_text: str) -> tuple[str, str]:
    """Return (caption, alt_text) from a caption file.

    Tolerates **bold** labels and 'Alt Text:' / 'Alt-text:' / 'AltText:' spellings.
    With no 'Caption:' label the whole text comes back as the caption;
    caption_problems() reports that, so it is never posted that way.
    """
    text = raw_text.replace("**", "")
    parts = _CAPTION_LABEL.split(text, maxsplit=1)
    body = parts[1] if len(parts) == 2 else text
    alt_parts = _ALT_LABEL.split(body, maxsplit=1)
    caption = alt_parts[0].strip()
    alt_text = alt_parts[1].strip() if len(alt_parts) == 2 else ""
    return caption, alt_text


def post_length(text: str) -> int:
    """Length with each emoji counted as 2 characters (UTF-16 code units).

    That is the stricter of the usual ways of counting characters, so the check
    errs on the safe side whichever way a platform counts.
    """
    return len(text.encode("utf-16-le")) // 2


def caption_problems(
    raw_text: str | None,
    product_link: str | None = None,
    require_alt_text: bool = True,
) -> list[str]:
    """List what is wrong with a caption file's text. An empty list means it is fine to post."""
    if not raw_text or not raw_text.strip():
        return ["the text is empty"]

    problems = []
    if not _CAPTION_LABEL.search(raw_text.replace("**", "")):
        problems.append("there is no 'Caption:' label, so the header lines would be posted too")

    caption, alt_text = extract_caption(raw_text)
    if require_alt_text and not alt_text:
        problems.append("there is no 'Alt Text:' section")

    length = post_length(caption)
    if length > THREADS_MAX_CHARS:
        problems.append(f"the caption is {length} characters, over Threads' limit of {THREADS_MAX_CHARS}")

    if product_link and product_link not in caption:
        problems.append(f"the caption does not contain the product link {product_link}")

    return problems
