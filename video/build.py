"""Build the final YC-Concierge demo video.

Pipeline:
  1. Render title cards as PNGs (PIL)
  2. Build each scene as an intermediate 1920x1080 MP4 (ffmpeg)
  3. Concat all scenes into the final video

Run:  .venv/bin/python video/build.py
Output: video/out/yc_concierge_demo.mp4
"""

import json
import os
import shlex
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ─── paths ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
CLIPS = ROOT / "clips"
BUILD = ROOT / "build"
OUT = ROOT / "out"
BUILD.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

# ─── video config ─────────────────────────────────────────────────────────
W, H = 1920, 1080
FPS = 30
BG = "#0a0a0a"  # near-black
VCODEC = ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p"]
ACODEC = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]

# ─── fonts (macOS) ────────────────────────────────────────────────────────
FONT_BOLD = "/System/Library/Fonts/HelveticaNeue.ttc"
FONT_REG = "/System/Library/Fonts/HelveticaNeue.ttc"


def font(size, weight="bold"):
    idx = 1 if weight == "bold" else 0  # ttc indices
    try:
        return ImageFont.truetype(FONT_BOLD, size=size, index=idx)
    except Exception:
        return ImageFont.load_default()


def run(args, check=True):
    """Run ffmpeg/etc., return (rc, stderr_tail)."""
    print("→ ", " ".join(shlex.quote(a) for a in args[:10]) + (" ..." if len(args) > 10 else ""))
    p = subprocess.run(args, capture_output=True, text=True)
    if check and p.returncode != 0:
        print("STDERR:", p.stderr[-1500:])
        raise SystemExit(f"command failed: {' '.join(args[:5])}")
    return p.returncode, p.stderr


def ffprobe_duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    )
    return float(out.decode().strip())


# ═══════════════════════════════════════════════════════════════════════════
# 1. RENDER TITLE / SLIDE PNGs
# ═══════════════════════════════════════════════════════════════════════════

def render_text_centered(draw, text, y, font_obj, fill="white"):
    bbox = draw.textbbox((0, 0), text, font=font_obj)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((W - tw) // 2, y - bbox[1]), text, font=font_obj, fill=fill)
    return th


def make_title_card():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_title = font(200, "bold")
    f_tag = font(54, "regular")
    f_small = font(28, "regular")

    # Stacked title with accent
    render_text_centered(d, "YC-Concierge", H // 2 - 160, f_title, fill="#ffffff")
    render_text_centered(d, "an agentic concierge that listens, finds, pays, and ships.",
                         H // 2 + 80, f_tag, fill="#a0a0a0")
    render_text_centered(d, "CALL  ·  TEXT  ·  EMAIL", H - 100, f_small, fill="#FF6B6B")

    path = BUILD / "title_open.png"
    img.save(path)
    return path


def make_sponsor_slide():
    """Architecture / sponsor flex slide."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_h1 = font(96, "bold")
    f_h2 = font(54, "bold")
    f_body = font(40, "regular")
    f_note = font(30, "regular")

    render_text_centered(d, "ONE  AGENT,  MANY  CHANNELS", 90, f_h1, fill="#ffffff")

    # Channel pill
    render_text_centered(d, "CALLS  ·  TEXTS  ·  EMAILS",
                         260, f_h2, fill="#FF6B6B")

    # Sponsor list with role
    rows = [
        ("AgentPhone", "voice and text"),
        ("AgentMail",  "email"),
        ("Browser Use", "web lookup"),
        ("Stripe",     "payment"),
        ("Claude",     "on AWS Bedrock"),
    ]
    y = 440
    for name, role in rows:
        # left-aligned name, then role
        line = f"{name}  ·  {role}"
        bbox = d.textbbox((0, 0), line, font=f_body)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        d.text((x, y), name, font=f_body, fill="#ffffff")
        name_bbox = d.textbbox((0, 0), name, font=f_body)
        nw = name_bbox[2] - name_bbox[0]
        d.text((x + nw, y), f"  ·  {role}", font=f_body, fill="#888888")
        y += 80

    render_text_centered(d, "built in one Saturday for Call My Agent",
                         H - 100, f_note, fill="#666666")
    path = BUILD / "sponsor_slide.png"
    img.save(path)
    return path


def make_outro_card():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_title = font(160, "bold")
    f_tag = font(50, "regular")
    f_event = font(36, "regular")
    f_small = font(28, "regular")

    render_text_centered(d, "YC-Concierge", H // 2 - 160, f_title, fill="#ffffff")
    render_text_centered(d, "Birthday cards today.", H // 2 + 30, f_tag, fill="#a0a0a0")
    render_text_centered(d, "Energetic narrators tomorrow.", H // 2 + 90, f_tag, fill="#a0a0a0")
    render_text_centered(d, "CALL MY AGENT HACKATHON  ·  Y-C  ·  MAY 2026",
                         H - 110, f_small, fill="#FF6B6B")

    path = BUILD / "title_close.png"
    img.save(path)
    return path


def make_caption_overlay(text_lines, height=H, accent_color="#FF6B6B"):
    """Render a transparent PNG with lower-third caption text. Used as overlay."""
    img = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f_h = font(56, "bold")
    f_b = font(40, "regular")

    # Box at bottom-left
    pad_x = 80
    pad_y = 60
    box_top = H - 240

    # Draw a rounded-ish dark bar background
    d.rectangle([(0, box_top), (W, H)], fill=(0, 0, 0, 200))

    # Title line
    if text_lines:
        d.text((pad_x, box_top + pad_y - 10), text_lines[0], font=f_h, fill="#ffffff")
    if len(text_lines) > 1:
        d.text((pad_x, box_top + pad_y + 70), text_lines[1], font=f_b, fill=accent_color)

    return img


# ═══════════════════════════════════════════════════════════════════════════
# 2. BUILD INDIVIDUAL SCENES
# ═══════════════════════════════════════════════════════════════════════════

def scene_image_with_audio(image_path, audio_path, out_path, fade_in=0.3, fade_out=0.5):
    """Hold an image for the duration of the audio. 1920x1080."""
    dur = ffprobe_duration(audio_path)
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={BG},"
        f"fade=t=in:st=0:d={fade_in},"
        f"fade=t=out:st={max(0, dur-fade_out):.3f}:d={fade_out},"
        f"fps={FPS}"
    )
    args = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-vf", vf,
        "-t", f"{dur:.3f}",
        *VCODEC, *ACODEC,
        "-shortest",
        str(out_path),
    ]
    run(args)
    return out_path


def scene_image_with_audio_kenburns(image_path, audio_path, out_path,
                                    zoom_from=1.0, zoom_to=1.15,
                                    x_from=0.5, y_from=0.5,
                                    x_to=0.5, y_to=0.5):
    """Image with a Ken Burns slow zoom across the audio duration."""
    dur = ffprobe_duration(audio_path)
    frames = int(dur * FPS)
    # zoompan needs a large input — pre-scale the image, then zoompan
    vf = (
        f"scale=4000:-2:flags=lanczos,"
        f"zoompan=z='if(eq(on,0),{zoom_from},min(zoom+(({zoom_to}-{zoom_from})/{frames}),{zoom_to}))':"
        f"x='iw*({x_from}+({x_to}-{x_from})*on/{frames})-(iw/zoom)/2':"
        f"y='ih*({y_from}+({y_to}-{y_from})*on/{frames})-(ih/zoom)/2':"
        f"d={frames}:s={W}x{H}:fps={FPS},"
        f"fade=t=in:st=0:d=0.3,"
        f"fade=t=out:st={max(0, dur-0.5):.3f}:d=0.5"
    )
    args = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-vf", vf,
        "-t", f"{dur:.3f}",
        *VCODEC, *ACODEC,
        "-shortest",
        str(out_path),
    ]
    run(args)
    return out_path


def scene_video_clip(src, out_path, ss=0, t=None, speed=1.0, audio_path=None, mute_src=True):
    """Trim a portion of a video, optionally speed it up, optionally swap audio."""
    args = ["ffmpeg", "-y"]
    if ss:
        args += ["-ss", f"{ss:.3f}"]
    args += ["-i", str(src)]
    if audio_path:
        args += ["-i", str(audio_path)]
    if t is not None:
        args += ["-t", f"{t:.3f}"]
    # Speed: setpts and atempo (when audio kept) — but we usually replace audio
    if speed != 1.0:
        # Output duration = input_t / speed
        out_t = (t / speed) if t else None
        vf = f"setpts=PTS/{speed},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={BG},fps={FPS}"
        if mute_src:
            args += ["-vf", vf]
        else:
            args += ["-vf", vf, "-af", f"atempo={speed}"]
        if out_t is not None:
            args[-1:-1] = []  # ensure -t already applied via input
    else:
        vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={BG},fps={FPS}"
        args += ["-vf", vf]

    if audio_path:
        args += ["-map", "0:v:0", "-map", "1:a:0"]
    elif mute_src:
        args += ["-an"]

    args += [*VCODEC]
    if audio_path or not mute_src:
        args += [*ACODEC]
    args += ["-shortest", str(out_path)]
    run(args)
    return out_path


def concat_scenes(scene_paths, out_path):
    """Concat using the concat demuxer."""
    listfile = BUILD / "concat_list.txt"
    with open(listfile, "w") as f:
        for s in scene_paths:
            f.write(f"file '{s.resolve()}'\n")
    args = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(listfile),
        "-c", "copy",
        str(out_path),
    ]
    run(args)
    return out_path


# ═══════════════════════════════════════════════════════════════════════════
# 3. ORCHESTRATE
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("Generating title cards...")
    open_card = make_title_card()
    sponsor_slide = make_sponsor_slide()
    close_card = make_outro_card()

    # Extract a clean still of iPhone "Calling..." screen from RPReplay
    iphone_calling_still = BUILD / "iphone_calling.png"
    run(["ffmpeg", "-y", "-ss", "18", "-i", str(CLIPS / "RPReplay_Final1779066552.mov"),
         "-vframes", "1", str(iphone_calling_still)])

    print("\nBuilding scenes...\n")

    scenes = []

    # Scene 1: Opening title with narration 1
    scenes.append(scene_image_with_audio(
        open_card, CLIPS / "narr_01_enhanced.m4a",
        BUILD / "scene_01_title.mp4",
        fade_in=0.5, fade_out=0.3,
    ))

    # Scene 2: iPhone calling screen with narration 2 (setup)
    scenes.append(scene_image_with_audio(
        iphone_calling_still, CLIPS / "narr_02_enhanced.m4a",
        BUILD / "scene_02_setup.mp4",
        fade_in=0.3, fade_out=0.3,
    ))

    # Scene 3: Real call audio over iPhone calling screen — use full 58s call audio
    # (We'll trim it down to the most dramatic 20s in a later iteration)
    scenes.append(scene_image_with_audio(
        iphone_calling_still, CLIPS / "call_audio.wav",
        BUILD / "scene_03_call.mp4",
        fade_in=0.2, fade_out=0.4,
    ))

    # Scene 4: iMessage recovery screenshot with narration 4
    scenes.append(scene_image_with_audio_kenburns(
        CLIPS / "imessage_recovery.png",
        CLIPS / "narr_04_enhanced.m4a",
        BUILD / "scene_04_recovery.mp4",
        zoom_from=1.0, zoom_to=1.25,
        x_from=0.5, y_from=0.4, x_to=0.5, y_to=0.55,
    ))

    # Scene 5: Email proof screenshot — short, captioned, no narration
    # Generate a 5-second beat with the Gmail screenshot
    email_still_audio = BUILD / "silent_5s.m4a"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-t", "5", *ACODEC, str(email_still_audio)])
    scenes.append(scene_image_with_audio(
        CLIPS / "email_inbox.png",
        email_still_audio,
        BUILD / "scene_05_email.mp4",
        fade_in=0.3, fade_out=0.3,
    ))

    # Scene 6+7+8: Stripe + recipient iMessage + card view — concat with narration_06
    # Take pay_and_receive_card.MP4 frames 0-42s, sped up where appropriate
    # For simplicity, use the original speed, full 0-42 range. ~42s, but we'll trim.
    # Cut: 0-15s (Stripe), 25-42s (recipient + card). Skip 15-25s (payment-processing wait).
    # Pace: keep at 1.0x for clarity.
    pay_clip = BUILD / "scene_06_pay.mp4"
    run([
        "ffmpeg", "-y",
        "-i", str(CLIPS / "pay_and_receive_card.MP4"),
        "-vf", f"trim=0:42,setpts=PTS-STARTPTS,scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={BG},fps={FPS}",
        "-an",
        *VCODEC,
        str(pay_clip),
    ])
    # Now overlay narration 6 starting from the card-view moment (~32s into the trimmed clip)
    # Combine: pay_clip (silent video) + narration_06 audio, with the audio starting at offset 32s
    # Actually simpler: keep the pay scene at 42s, layer narration_06 audio starting at 25s (when recipient iMessage hits)
    pay_clip_full = BUILD / "scene_06_pay_full.mp4"
    n6_dur = ffprobe_duration(CLIPS / "narr_06_enhanced.m4a")
    # Pad narration with silence at the start so it begins ~25s in
    n6_padded = BUILD / "narr_06_padded.m4a"
    run([
        "ffmpeg", "-y",
        "-i", str(CLIPS / "narr_06_enhanced.m4a"),
        "-af", "adelay=25000|25000",
        *ACODEC,
        str(n6_padded),
    ])
    # Combine pay_clip video with padded narration audio
    run([
        "ffmpeg", "-y",
        "-i", str(pay_clip),
        "-i", str(n6_padded),
        "-c:v", "copy",
        *ACODEC,
        "-shortest",
        str(pay_clip_full),
    ])
    scenes.append(pay_clip_full)

    # Scene 9: Sponsor slide with narration 7
    scenes.append(scene_image_with_audio(
        sponsor_slide, CLIPS / "narr_07_enhanced.m4a",
        BUILD / "scene_09_sponsors.mp4",
        fade_in=0.3, fade_out=0.3,
    ))

    # Scene 10: Closing title with narration 8
    scenes.append(scene_image_with_audio(
        close_card, CLIPS / "narr_08_enhanced.m4a",
        BUILD / "scene_10_close.mp4",
        fade_in=0.3, fade_out=0.8,
    ))

    print("\nConcatenating final video...\n")
    final = concat_scenes(scenes, OUT / "yc_concierge_demo.mp4")

    print(f"\n✅ Done. Final: {final}")
    dur = ffprobe_duration(final)
    size_mb = os.path.getsize(final) / 1e6
    print(f"   Duration: {dur:.1f}s")
    print(f"   Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
