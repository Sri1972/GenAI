# Animated GIFs for video_creator

Drop your own `.gif` files directly into this folder (no subfolders) to make
them available to the `animatedGif` primitive. Nothing is bundled here on
purpose -- most "cool" animated GIFs found online (GIPHY, meme sites, etc.)
have no clear license for embedding in business content, so this kit never
sources or downloads any itself. Only use GIFs you actually have the rights
to use here.

The director (Claude, via `run.py`'s critique loop) is told exactly which
GIFs exist by filename (no extension) each time it plans a video -- it will
never invent a name, and skips `animatedGif` entirely if this folder is
empty or nothing here fits the brief.

Naming: use a short, descriptive filename -- it's exactly what gets shown to
the director as the available name, e.g. `confetti.gif` -> `"confetti"`,
`loading-spinner.gif` -> `"loading-spinner"`.

Files here are synced into `remotion_project/public/gifs/` automatically at
the start of every `generate()`/`generate_series()` call (see `run.py`'s
`_sync_gifs()`) -- no manual step needed after adding or removing a file.
