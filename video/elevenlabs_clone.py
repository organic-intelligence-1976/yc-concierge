"""Create an ElevenLabs Instant Voice Clone of Reza from existing narration recordings.

Feeds 4 different takes (~65 seconds total) for variety in pitch / pacing.
Prints the new voice_id to stdout so we can wire it into elevenlabs_gen.py.
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["ELEVENLABS_API_KEY"]
CLIPS = Path(__file__).parent / "clips"

# Picked for variety: different segments, different pacing, all clean speech.
SAMPLE_FILES = [
    "Union Iron Works Historic District - Building 105 (Forge Shop).m4a",   # sponsor flex — 20.9s
    "Y Combinator22.m4a",                                                    # card narration — 16.4s
    "Union Iron Works Historic District - Building 105 (Forge Shop) 2.m4a", # sign-off attempt — 16.5s
    "last.m4a",                                                              # updated sign-off — 11.3s
]


def main():
    files = []
    for fn in SAMPLE_FILES:
        path = CLIPS / fn
        if not path.exists():
            print(f"  missing: {path}")
            continue
        files.append(("files", (fn, open(path, "rb"), "audio/mp4")))
        print(f"  + {fn}")

    if not files:
        raise SystemExit("no samples found")

    resp = requests.post(
        "https://api.elevenlabs.io/v1/voices/add",
        headers={"xi-api-key": API_KEY},
        data={
            "name": "Reza Jamei",
            "description": (
                "Cloned from Reza Jamei's narration recordings for the YC-Concierge "
                "hackathon demo. Use for first-person product narration."
            ),
            "labels": '{"accent":"slight non-native","gender":"male","use_case":"narration","language":"english"}',
            "remove_background_noise": "true",
        },
        files=files,
        timeout=120,
    )

    if resp.status_code != 200:
        print(f"FAILED: HTTP {resp.status_code}")
        print(resp.text[:500])
        raise SystemExit(1)

    voice_id = resp.json().get("voice_id")
    print()
    print(f"✓ Created voice — voice_id = {voice_id}")
    print()
    print("Save this in .env as REZA_VOICE_ID, then re-run elevenlabs_gen.py.")


if __name__ == "__main__":
    main()
