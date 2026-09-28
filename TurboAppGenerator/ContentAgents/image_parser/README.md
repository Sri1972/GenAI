# Image Parsing Agent

Hands an image straight to Claude's native vision (via the Claude Code CLI on
Bedrock) to describe it or extract structured data from it.

## Standalone usage
```bash
python run.py chart.png --instruction "Extract the exact values plotted in this chart" --format json
```

## As a Claude Code subagent
`Agent({ subagent_type: "image-parser", prompt: "Read screenshot.png and transcribe every line of text on it" })`

## Notes
- No OCR library needed — Claude reads the image file directly via its
  built-in vision support.
- Images wider/taller than `--max-dim` (default 2000px) are downsized to a
  temp copy first to control token cost; the original file is never modified.
