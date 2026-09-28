"""
Stages the shared icon catalog's SVGs into remotion_project/public/icons/ --
Remotion can only serve files that live inside its own public/ dir via
staticFile() (same reason narration WAVs get staged into public/narration/
at render time), unlike ppt_creator's insert_picture() which reads any
filesystem path directly. This is a static asset sync (run when the catalog
changes), not per-request runtime code.

Usage: python sync_to_video_creator.py
"""
import shutil
from pathlib import Path

ICONS_DIR = Path(__file__).resolve().parent
PUBLIC_ICONS_DIR = ICONS_DIR.parent / "video_creator" / "remotion_project" / "public" / "icons"


def main():
    for provider_dir in ICONS_DIR.iterdir():
        svg_dir = provider_dir / "svg"
        if not svg_dir.is_dir():
            continue
        dest = PUBLIC_ICONS_DIR / provider_dir.name
        dest.mkdir(parents=True, exist_ok=True)
        count = 0
        for svg_file in svg_dir.glob("*.svg"):
            dest_file = dest / svg_file.name
            # OneDrive sometimes marks a previously-synced file read-only --
            # clear that before overwriting instead of letting shutil.copy
            # fail with PermissionError (reproduced directly on a re-sync).
            if dest_file.exists():
                dest_file.chmod(0o666)
            shutil.copy(svg_file, dest_file)
            count += 1
        print(f"{provider_dir.name}: synced {count} SVGs -> {dest}")


if __name__ == "__main__":
    main()
