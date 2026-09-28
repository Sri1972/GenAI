# ContentAgents test harness (UI)

A minimal FastAPI + plain HTML page for manually testing all six agents —
pick an agent, fill in its inputs, click Run, see the output (and, for
`ppt_creator`, download the generated `.pptx`).

Each request runs the agent's real standalone `run.py` as a subprocess —
the same code path any external workflow would use — so what works here
works from automation too.

## Run
```bash
pip install -r ../requirements.txt
python server.py
```
Then open http://localhost:8420

## Notes
- Uploaded files are saved to `uploads/` with a random prefix; clean that
  folder out periodically, it's not auto-purged.
- `media_parser` requires `ffmpeg` on the server's PATH — the endpoint
  returns a clear error in the UI if it's missing, rather than hanging.
- `site_crawler`'s `max_pages` defaults to 20 here (vs. 200 in the CLI) to
  keep test runs fast; raise it for a fuller crawl.
