"""
Video/Audio Parsing Agent — extracts audio (and, for video, periodic
keyframes) with ffmpeg, transcribes the audio locally with faster-whisper (no
AWS/S3 required), then asks Claude (via the Claude Code CLI, on Bedrock) to
synthesize the transcript + keyframe images into a structured summary.

Requires the system `ffmpeg`/`ffprobe` binaries to be installed separately —
this script checks for them and fails with a clear message rather than a
confusing crash if they're missing.

Usage:
    python run.py <media.mp4|media.mp3> [--out summary.md] [--keyframe-interval 30]
                   [--whisper-model base] [--question "..."]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.claude_cli import run_claude

# On a network behind a corporate TLS-inspecting proxy (e.g. Zscaler), the
# first-run download of Whisper's model weights from huggingface.co fails
# cert verification against Python's default CA bundle. If this machine has
# the proxy's root CA exported (same fix already needed for npm elsewhere in
# this project), trust it for these downloads too. No-op everywhere else.
_CORP_CA_BUNDLE = Path.home() / "certs" / "zscaler-root.pem"
if _CORP_CA_BUNDLE.exists():
    os.environ.setdefault("SSL_CERT_FILE", str(_CORP_CA_BUNDLE))
    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(_CORP_CA_BUNDLE))

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

SYSTEM_PROMPT = """You are the Video/Audio Parsing Agent. You are given a
timestamped speech transcript and, if the source was a video, a set of
keyframe images taken at regular intervals. Read the keyframe images (if any)
and produce a structured summary: main topics discussed, a timeline of
notable moments (timestamp + description, referencing what's visible on
screen for video), and — if a question was asked — a direct answer citing
timestamps. Respond in well-structured Markdown."""


def check_ffmpeg():
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            sys.exit(
                f"`{binary}` not found on PATH. Install ffmpeg (https://ffmpeg.org/download.html) "
                "and ensure it's on PATH before running this agent."
            )


def has_video_stream(path: Path) -> bool:
    if path.suffix.lower() not in VIDEO_EXTS:
        return False
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=index",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return bool(out.stdout.strip())
    except Exception:
        return path.suffix.lower() in VIDEO_EXTS


def extract_audio(path: Path, out_wav: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(out_wav)],
        capture_output=True, text=True, check=True,
    )


def extract_keyframes(path: Path, out_dir: Path, interval: int) -> list[str]:
    pattern = out_dir / "keyframe_%04d.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-vf", f"fps=1/{interval}", str(pattern)],
        capture_output=True, text=True, check=True,
    )
    frames = sorted(out_dir.glob("keyframe_*.jpg"))
    return [str(f) for f in frames]


def transcribe(wav_path: Path, model_size: str) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper not installed. Run: pip install -r ../requirements.txt")

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(wav_path))
    return [{"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()} for s in segments]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--out")
    ap.add_argument("--keyframe-interval", type=int, default=30)
    ap.add_argument("--whisper-model", default="base")
    ap.add_argument("--question")
    args = ap.parse_args()

    check_ffmpeg()
    path = Path(args.media).resolve()
    if not path.exists():
        sys.exit(f"File not found: {path}")

    is_video = has_video_stream(path)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        wav_path = tmp_dir / "audio.wav"
        print("Extracting audio...")
        extract_audio(path, wav_path)

        keyframes = []
        if is_video:
            print(f"Extracting keyframes every {args.keyframe_interval}s...")
            keyframes = extract_keyframes(path, tmp_dir, args.keyframe_interval)

        print(f"Transcribing with faster-whisper ({args.whisper_model})...")
        transcript = transcribe(wav_path, args.whisper_model)

        transcript_path = path.with_suffix(".transcript.json")
        transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        print(f"Wrote transcript to {transcript_path}")

        prompt_parts = [f"TRANSCRIPT (timestamped, seconds):\n{json.dumps(transcript, indent=2)}"]
        if keyframes:
            prompt_parts.append(
                f"\nKEYFRAME IMAGES (one every {args.keyframe_interval}s, in order): "
                + ", ".join(keyframes)
            )
        if args.question:
            prompt_parts.append(f"\nQuestion: {args.question}")

        result = run_claude(
            "\n".join(prompt_parts), system_prompt=SYSTEM_PROMPT,
            allowed_tools=["Read"], cwd=str(tmp_dir),
        )
        summary = result["result"]

        out_path = Path(args.out) if args.out else path.with_suffix(".summary.md")
        out_path.write_text(summary, encoding="utf-8")

    print(f"Wrote summary to {out_path}")


if __name__ == "__main__":
    main()
