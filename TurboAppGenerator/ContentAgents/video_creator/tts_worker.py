"""Standalone worker: synthesizes exactly one WAV via pyttsx3 (Windows
SAPI5/COM), invoked as its own subprocess -- never imported and called
in-process. pyttsx3's SAPI5 binding has strict COM thread-affinity
requirements; calling it from anything other than a process's own main
thread (e.g. a background worker thread, which is exactly how a live
server's workflow runner executes -- see server.py's
threading.Thread(target=_execute_workflow_run)) reliably hangs forever with
no error and no way to time out (reproduced directly: a real workflow run
sat stuck on "Recording narration..." for 48+ minutes with zero further
progress). A subprocess always gets a fresh process with its own real main
thread, sidestepping that entirely, and lets the caller (see
synthesize_narration in run.py) enforce a real timeout via
subprocess.run(..., timeout=...) instead of hanging indefinitely.

Usage: python _tts_worker.py <text_file> <voice_name> <out_wav_path>
"""
import sys

import pyttsx3


def main() -> None:
    text_path, voice_name, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    text = open(text_path, "r", encoding="utf-8").read()
    engine = pyttsx3.init()
    try:
        for v in engine.getProperty("voices"):
            if voice_name.lower() in v.name.lower():
                engine.setProperty("voice", v.id)
                break
        engine.save_to_file(text, out_path)
        engine.runAndWait()
    finally:
        engine.stop()


if __name__ == "__main__":
    main()
