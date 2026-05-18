"""Generate AI narration via ElevenLabs to replace the human voice tracks.

Keeps the real AgentPhone call audio (clips/call_audio.wav) untouched.
Each segment is saved as clips/narr_NN_ai.mp3 for the build pipeline to pick up.
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["ELEVENLABS_API_KEY"]
CLIPS = Path(__file__).parent / "clips"

# Voice ID — defaults to Reza's cloned voice if available, otherwise Brian (stock).
VOICE_ID = os.environ.get("REZA_VOICE_ID", "nPczCjzI2devNBz1zQrb")
MODEL = "eleven_v3"  # most expressive — supports inline emotion / pacing tags

# Each segment has context-specific audio tags so v3 styles delivery per scene.
SEGMENTS = {
    "narr_01_ai.mp3":
        "[warm] Meet YC-Concierge — an autonomous agent you reach by voice, text, or "
        "email to get a chore done. [confident] It quotes a price, takes payment "
        "through Stripe, and delivers the result. [intrigued] Today's vertical: "
        "personalized birthday cards.",

    "narr_02_ai.mp3":
        "Here's the demo. [excited] I'm going to call the agent and ask it to send a "
        "birthday card to my friend Reza — but I don't know his email. "
        "[curious] Watch what happens.",

    "narr_04_ai.mp3":
        "[surprised] Notice what just happened. The agent misheard my friend's name "
        "as Reza Jermaine. [confident] But because it has live web access through "
        "Browser Use, it searched on its own and recovered the right email.",

    "narr_05_ai.mp3":
        "It texts me back a Stripe Checkout link. [confident] Real Stripe, real test "
        "card, one dollar. [satisfied] The moment payment confirms, the agent ships "
        "the card.",

    "narr_06_ai.mp3":
        "[proud] Claude picks an on-brand design, writes a personalized message in "
        "the tone I asked for, and delivers it. [triumphant] Total time from phone "
        "call to card in my friend's inbox: under a minute.",

    "narr_07_ai.mp3":
        "[confident] Calls, texts, and emails — one agent, many channels. AgentPhone "
        "handles voice and messaging. AgentMail handles email. Browser Use does the "
        "live web lookup. Stripe handles payment. And Claude runs on AWS Bedrock.",

    "narr_08_ai.mp3":
        "[warm] YC-Concierge. By Reza Jamei, Maria Reiling, and Lara Hoyem. "
        "[proud] Built for Call My Agent at Y-C, May 2026.",
}


def synth(filename, text):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    resp = requests.post(
        url,
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": MODEL,
            "voice_settings": {
                "stability": 0.5,         # let it vary — more emotional range
                "similarity_boost": 0.8,  # stay close to the cloned voice's character
                "style": 0.6,             # more expressive
                "use_speaker_boost": True,
            },
        },
        timeout=60,
    )
    if resp.status_code != 200:
        print(f"  FAILED {filename}: HTTP {resp.status_code} {resp.text[:200]}")
        return False
    out = CLIPS / filename
    out.write_bytes(resp.content)
    print(f"  ✓ {filename}  ({len(resp.content) / 1024:.1f} KB)")
    return True


if __name__ == "__main__":
    total_chars = sum(len(v) for v in SEGMENTS.values())
    print(f"Generating {len(SEGMENTS)} segments ({total_chars} chars) via Brian voice...")
    print()
    for fn, text in SEGMENTS.items():
        synth(fn, text)
