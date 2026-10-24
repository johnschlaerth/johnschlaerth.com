#!/usr/bin/env python3
"""Make local, uncropped web derivatives while retaining the Adobe originals.

Requires Python 3, Pillow, ffmpeg, and ffprobe. Run from any directory:
    python3 scripts/optimize_media.py

The flat JSON mapping is keyed by the original /media/... URL. Stills get 640px
and 1600px WebP bounds (never upscaled); animated GIFs retain their animation,
with large ones encoded to muted looping-compatible MP4. MPO photographs are
treated as photographs, not animations. The HTML renderer decides autoplay /
loop behavior and should honor reduced-motion settings.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
OUTPUT = PUBLIC / "media" / "optimized"
LIMIT = 25 * 1024 * 1024
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff"}


def collect_sources(node, sources):
    if isinstance(node, dict):
        src = node.get("src")
        if isinstance(src, str) and src.startswith("/media/") and Path(src).suffix.lower() in IMAGE_EXTENSIONS:
            sources.add(src)
        for value in node.values():
            collect_sources(value, sources)
    elif isinstance(node, list):
        for value in node:
            collect_sources(value, sources)


def url(path):
    return "/" + path.relative_to(PUBLIC).as_posix()


def decoded_image(path):
    if not path.exists() or path.stat().st_size >= LIMIT:
        return False
    try:
        with Image.open(path) as image:
            image.load()
        return True
    except (OSError, ValueError):
        return False


def write_webp(image, path, bound, quality):
    if not decoded_image(path):
        width, height = image.size
        if width > bound:
            resized = image.resize((bound, max(1, round(height * bound / width))), Image.Resampling.LANCZOS)
        else:
            resized = image.copy()
        temporary = path.with_suffix(".partial.webp")
        # Preserve transparency. ICC profile is retained where supplied; EXIF
        # orientation has already been applied and must not be reintroduced.
        options = {"quality": quality, "method": 6, "exact": True}
        if image.info.get("icc_profile"):
            options["icc_profile"] = image.info["icc_profile"]
        resized.save(temporary, "WEBP", **options)
        if not decoded_image(temporary):
            raise ValueError(f"Invalid or oversized WebP: {temporary}")
        temporary.replace(path)
    with Image.open(path) as result:
        return {"src": url(path), "width": result.width, "height": result.height}


def make_images(src):
    source = PUBLIC / src.lstrip("/")
    if not source.is_file():
        raise FileNotFoundError(f"Missing original {src}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    prefix = digest[:20]
    with Image.open(source) as original:
        animated = original.format == "GIF" and getattr(original, "n_frames", 1) > 1
        frame_count = original.n_frames if animated else 1
        original.seek(0)
        image = ImageOps.exif_transpose(original).convert("RGBA" if "transparency" in original.info or original.mode in {"RGBA", "LA"} else "RGB")
        # Conversion normally carries metadata, but copy explicitly so a future
        # Pillow version does not discard an embedded source color profile.
        if original.info.get("icc_profile"):
            image.info["icc_profile"] = original.info["icc_profile"]
        small = write_webp(image, OUTPUT / f"{prefix}-640.webp", 640, 84)
        large = write_webp(image, OUTPUT / f"{prefix}-1600.webp", 1600, 90)
        variants = [small] if small["width"] == large["width"] else [small, large]
        result = {
            "thumbnail": small["src"],
            "display": src if animated else large["src"],
            "width": image.width,
            "height": image.height,
            "srcset": [] if animated else [{"src": v["src"], "width": v["width"]} for v in variants],
            "full": src,
            "source_sha256": digest,
            "animated": animated,
        }
        if animated:
            result.update({"poster": large["src"], "frames": frame_count})
        return src, result


def probe_video(path):
    completed = subprocess.run([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,nb_read_frames:format=duration", "-of", "json", str(path)
    ], check=True, capture_output=True, text=True)
    value = json.loads(completed.stdout)
    if not value.get("streams"):
        raise ValueError(f"No decoded video stream: {path}")
    return value


def make_video(item):
    src, entry = item
    source = PUBLIC / src.lstrip("/")
    destination = OUTPUT / f"{entry['source_sha256'][:20]}-animation.mp4"
    with Image.open(source) as original:
        durations = []
        for number in range(original.n_frames):
            original.seek(number)
            durations.append(original.info.get("duration", 100))
        source_duration = sum(durations) / 1000
    if not destination.is_file():
        temporary = destination.with_suffix(".partial.mp4")
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ignore_loop", "1", "-i", str(source), "-an",
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2:color=white",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-threads", "2", "-pix_fmt", "yuv420p", "-fps_mode", "passthrough",
            "-enc_time_base", "1:1000", "-video_track_timescale", "1000",
            "-movflags", "+faststart", str(temporary)
        ], check=True, capture_output=True, text=True)
        temporary.replace(destination)
    if destination.stat().st_size >= LIMIT:
        raise ValueError(f"Animation exceeds Cloudflare 25 MiB file limit: {destination}")
    details = probe_video(destination)
    video_stream = details["streams"][0]
    actual_frames = int(video_stream["nb_read_frames"])
    actual_duration = float(details["format"]["duration"])
    if actual_frames != entry["frames"]:
        raise ValueError(f"Animation frame loss: {src}: {entry['frames']} → {actual_frames}")
    # MP4 frame timebase may round the terminal frame by at most 50 ms.
    if not math.isclose(actual_duration, source_duration, abs_tol=.05):
        raise ValueError(f"Animation timing changed: {src}: {source_duration}s → {actual_duration}s")
    # ffprobe -count_frames decodes every frame, and fails/returns fewer frames
    # for an incomplete video. Source hashes and frame counts are kept in JSON.
    entry.update({"video": url(destination), "display": entry["poster"], "duration": actual_duration})
    if source.stat().st_size >= LIMIT:
        entry["full"] = url(destination)
    return src, entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--gif-threshold-mib", type=float, default=5)
    args = parser.parse_args()
    workers = min(4, max(1, args.workers))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    data = json.loads((ROOT / "content" / "site.json").read_text())
    sources = set()
    collect_sources(data, sources)
    mapping = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(make_images, src): src for src in sorted(sources)}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            src, entry = future.result()
            mapping[src] = entry
            if index % 40 == 0 or index == len(sources):
                print(f"Images: {index}/{len(sources)} verified", flush=True)
    animated = [(src, entry) for src, entry in mapping.items()
                if entry["animated"] and (PUBLIC / src.lstrip("/")).stat().st_size > args.gif_threshold_mib * 1024 * 1024]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(2, workers)) as executor:
        for index, (src, entry) in enumerate(executor.map(make_video, animated), 1):
            mapping[src] = entry
            print(f"Animations: {index}/{len(animated)} verified ({entry['frames']} frames, {entry['duration']:.2f}s)", flush=True)
    for src, entry in mapping.items():
        for key in ("thumbnail", "display", "full", "video", "poster"):
            target = entry.get(key)
            if target and (PUBLIC / target.lstrip("/")).stat().st_size >= LIMIT:
                raise ValueError(f"Published {key} would exceed 25 MiB: {target}")
    target = ROOT / "content" / "media-variants.json"
    target.write_text(json.dumps(dict(sorted(mapping.items())), indent=2) + "\n")
    originals = sum((PUBLIC / src.lstrip("/")).stat().st_size for src in sources)
    derivatives = sum(path.stat().st_size for path in OUTPUT.iterdir() if path.is_file())
    thumbs = sum((PUBLIC / entry["thumbnail"].lstrip("/")).stat().st_size for entry in mapping.values())
    print(json.dumps({"images": len(mapping), "gif_to_mp4": len(animated), "original_bytes": originals,
                      "derivative_bytes": derivatives, "all_thumbnail_bytes": thumbs,
                      "mapping": str(target)}, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Media optimization failed: {error}", file=sys.stderr)
        raise
