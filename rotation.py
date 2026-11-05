"""
rotation.py

Keeps product posts (and parenting-tips topics) in a fair rotation: every item
is posted once, in a shuffled order, before anything repeats. When a new cycle
starts, the items posted most recently go to the back of the new order, so the
same product never appears twice in a row across the cycle boundary.

State lives in state/rotation.json. It must stay OUTSIDE output_schedule/,
because the publisher treats every JSON file in that folder as a post.
"""

import json
import random
from pathlib import Path

STATE_PATH = Path("state/rotation.json")
RECENT_WINDOW = 8    # a new cycle never starts with anything from the last 8 picks (2 weeks)
KEEP_BATCHES = 12    # how many weeks of picks to remember (for --force re-runs)


def load_state(path: Path = STATE_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _queue(state: dict, key: str) -> dict:
    return state.setdefault(key, {"cycle": 0, "remaining": [], "done": [], "recent": []})


def seed_recent(state: dict, key: str, recent: list[str]) -> None:
    """On the very first run, remember what was posted lately (oldest first), so the
    first cycle doesn't open with last week's products."""
    q = _queue(state, key)
    if not (q["remaining"] or q["done"] or q["recent"]):
        q["recent"] = list(recent)[-RECENT_WINDOW:]


def take(state: dict, key: str, pool: list[str], n: int, batch_id: str) -> list[str]:
    """Return the next `n` items from the rotation for this batch and advance it.

    Running the same batch again (generate --force) returns the same picks instead
    of advancing the rotation a second time.
    """
    if n <= 0:
        return []
    if not pool:
        raise ValueError(f"Nothing available to rotate for '{key}'.")

    batches = state.setdefault("batches", {})
    saved = batches.get(batch_id, {}).get(key)
    if saved is not None and len(saved) == n and all(p in pool for p in saved):
        return list(saved)

    q = _queue(state, key)
    in_pool = set(pool)
    q["remaining"] = [p for p in q["remaining"] if p in in_pool]
    # Items added to the pool mid-cycle (e.g. a product that just got its photos)
    # join the current cycle at a random position.
    for p in pool:
        if p not in q["remaining"] and p not in q["done"]:
            q["remaining"].insert(random.randint(0, len(q["remaining"])), p)

    picks: list[str] = []
    while len(picks) < n:
        if not q["remaining"]:
            q["cycle"] += 1
            q["done"] = []
            order = random.sample(pool, len(pool))
            recent = set(q["recent"][-RECENT_WINDOW:]) | set(picks)
            q["remaining"] = [p for p in order if p not in recent] + [p for p in order if p in recent]
        item = q["remaining"].pop(0)
        picks.append(item)
        q["done"].append(item)
        q["recent"] = (q["recent"] + [item])[-RECENT_WINDOW:]

    batches.setdefault(batch_id, {})[key] = picks
    for old in sorted(batches)[:-KEEP_BATCHES]:
        del batches[old]
    return picks
