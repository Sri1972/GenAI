# Video/Audio Parsing Agent

Extracts audio (and, for video, periodic keyframes) with `ffmpeg`,
transcribes locally with `faster-whisper` — no AWS/S3 needed — then asks
Claude to synthesize the transcript + keyframes into a structured summary.

## Prerequisites
- System `ffmpeg`/`ffprobe` binaries on PATH (not a pip package —
  https://ffmpeg.org/download.html). The script checks and fails clearly if
  missing rather than crashing partway through.
- `pip install -r ../requirements.txt` (for `faster-whisper`).

## Standalone usage
```bash
python run.py recording.mp4 --keyframe-interval 30
python run.py call.mp3 --question "What did we agree the deadline was?"
```

## As a Claude Code subagent
`Agent({ subagent_type: "media-parser", prompt: "Summarize recording.mp4 and list every action item mentioned" })`

## Notes
- Claude never "watches" the video directly — the real architecture is
  ffmpeg + faster-whisper doing the transcription/frame-extraction, and
  Claude reasoning over the resulting transcript + keyframe images.
- Upgrade path (not built here): swap in AWS Transcribe once an S3 bucket is
  available, for better accuracy/diarization at scale — `faster-whisper` is
  the local-only default for now.
