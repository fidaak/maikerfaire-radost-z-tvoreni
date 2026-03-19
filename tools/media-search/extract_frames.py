"""
Extract keyframes from video files for CLIP indexing.

Uses ffmpeg to pull I-frames (keyframes) from videos, saving them as JPEGs.
Output filenames encode the source video so the indexer can track origin.

Usage:
    python extract_frames.py <video_or_folder> [--output keyframes/] [--max-frames 50] [--min-interval 2]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from tqdm import tqdm

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mts", ".3gp"}
KEYFRAME_MARKER = "__keyframe__"


def find_videos(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            return [path]
        return []
    videos = []
    for root, _dirs, files in os.walk(path):
        for f in files:
            if Path(f).suffix.lower() in VIDEO_EXTENSIONS:
                videos.append(Path(root) / f)
    return videos


def get_video_duration(video_path: Path) -> float | None:
    """Get video duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def extract_keyframes(
    video_path: Path,
    output_dir: Path,
    max_frames: int,
    min_interval: float,
) -> list[Path]:
    """Extract I-frames from a video, return list of saved frame paths."""
    # Build a safe filename prefix from the video path
    safe_name = video_path.stem.replace(" ", "_")
    prefix = f"{safe_name}{KEYFRAME_MARKER}"

    frame_dir = output_dir / safe_name
    frame_dir.mkdir(parents=True, exist_ok=True)

    # Strategy: extract keyframes using ffmpeg select filter
    # select='eq(pict_type,I)' picks only I-frames
    # fps filter ensures minimum interval between frames
    filter_str = f"select='eq(pict_type,I)',fps=1/{max(min_interval, 0.5)}"

    output_pattern = str(frame_dir / f"{prefix}%04d.jpg")

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", filter_str,
        "-vsync", "vfr",
        "-frames:v", str(max_frames),
        "-q:v", "2",  # JPEG quality (2 = high)
        output_pattern,
    ]

    try:
        subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        print(f"  Warning: ffmpeg timed out for {video_path.name}")
    except FileNotFoundError:
        print("Error: ffmpeg not found. Install ffmpeg and ensure it's on PATH.", file=sys.stderr)
        sys.exit(1)

    # Collect extracted frames
    frames = sorted(frame_dir.glob(f"{prefix}*.jpg"))
    return frames


def main():
    parser = argparse.ArgumentParser(description="Extract keyframes from videos for CLIP indexing")
    parser.add_argument("path", help="Video file or folder containing videos")
    parser.add_argument("--output", default="keyframes", help="Output directory for extracted frames (default: keyframes/)")
    parser.add_argument("--max-frames", type=int, default=50, help="Max keyframes per video (default: 50)")
    parser.add_argument("--min-interval", type=float, default=2.0, help="Minimum seconds between frames (default: 2.0)")
    args = parser.parse_args()

    source = Path(args.path).resolve()
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    videos = find_videos(source)
    if not videos:
        print(f"No video files found in {source}")
        return

    print(f"Found {len(videos)} video(s)")
    total_frames = 0

    for video in tqdm(videos, desc="Processing videos"):
        duration = get_video_duration(video)
        dur_str = f" ({duration:.0f}s)" if duration else ""
        print(f"\n  {video.name}{dur_str}")

        frames = extract_keyframes(video, output_dir, args.max_frames, args.min_interval)
        print(f"  → {len(frames)} keyframes extracted")
        total_frames += len(frames)

    print(f"\nDone. {total_frames} total keyframes in {output_dir}")
    print(f"Now run:  python index.py {output_dir}")


if __name__ == "__main__":
    main()
