"""
YouTube channel lookup and bulk-add tool.

Looks up channel IDs by @handle using the YouTube Data API v3,
then appends any new channels to config/youtube_channels.csv.

Add or remove channels from CHANNELS_TO_ADD below.
"""

import os, csv, time
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

KEY = os.getenv("YOUTUBE_API_KEY")
if not KEY:
    raise SystemExit("Missing YOUTUBE_API_KEY.")

CONFIG = Path("config/youtube_channels.csv")

# ── Channels to look up ────────────────────────────────────────────────────────
# Format: "@handle": "Label_for_CSV"
# Covers: lore/tactics creators, hobby/painting, competitive scene, retail stores

CHANNELS_TO_ADD = {
    # Lore / commentary
    "@AuspexTactics":       "Auspex_Tactics",        # huge tactics/lore, 500k+
    "@Valrak":              "Valrak",                 # 40k news & rumors
    "@MidwinterMinis":      "Midwinter_Minis",        # hobby reviews
    "@ThePaintingPhase":    "Painting_Phase",         # painting tutorials

    # Competitive scene
    "@TheHonestWargamer":   "Honest_Wargamer",        # competitive meta tracking
    "@WinterSEO":           "Winters_SEO",            # tactical gameplay

    # Hobby / painting
    "@DuncanRhodes":        "Duncan_Rhodes",          # legendary painter, ex-GW
    "@goobertown":          "Goobertown_Hobbies",     # painting
    "@SadPandaStudios":     "Sad_Panda_Studios",      # painting/hobby

    # Official / retail adjacent
    "@WarhammerTV":         "Warhammer_TV",           # GW's hobby/tutorial channel

    # Retail stores with YouTube presence
    "@WaylandGames":        "Wayland_Games",          # UK retailer
    "@ElementGames":        "Element_Games",          # UK retailer
}


def lookup_by_handle(handle):
    """Returns (channel_id, title) or (None, None)."""
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={
            "part":      "id,snippet",
            "forHandle": handle.lstrip("@"),
            "key":       KEY,
        },
        timeout=30,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if items:
        return items[0]["id"], items[0]["snippet"]["title"]
    return None, None


# Load existing channels
existing_ids    = set()
existing_labels = set()
with open(CONFIG, newline="") as f:
    for row in csv.DictReader(f):
        existing_ids.add(row["channel_id"].strip())
        existing_labels.add(row["label"].strip())

print(f"Existing channels in config: {len(existing_ids)}\n")

new_channels = []
not_found    = []

for handle, label in CHANNELS_TO_ADD.items():
    print(f"Looking up {handle} ...", end="  ")
    try:
        ch_id, title = lookup_by_handle(handle)
    except Exception as e:
        print(f"ERROR: {e}")
        not_found.append(handle)
        time.sleep(1)
        continue

    if ch_id is None:
        print("NOT FOUND")
        not_found.append(handle)
    elif ch_id in existing_ids:
        print(f"already exists ({label})")
    else:
        print(f"✓  {title}  [{ch_id}]")
        new_channels.append({"label": label, "channel_id": ch_id})

    time.sleep(0.4)

# Append new channels
if new_channels:
    with open(CONFIG, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["label", "channel_id"])
        for ch in new_channels:
            writer.writerow(ch)
    print(f"\n✓ Added {len(new_channels)} new channels to {CONFIG}")
    for ch in new_channels:
        print(f"  {ch['label']}  {ch['channel_id']}")
else:
    print("\nNo new channels to add.")

if not_found:
    print(f"\nNot found ({len(not_found)}): {not_found}")
    print("Check the handles — some may have changed or been renamed.")
