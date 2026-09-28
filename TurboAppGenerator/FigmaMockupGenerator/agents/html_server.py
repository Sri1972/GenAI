#!/usr/bin/env python3
"""
Lightweight HTTP server for HTML/CSS/JS Figma prototype projects.
Serves the generated/ directory so each project is at /project-name/
Usage: python html_server.py <output_dir> <port>
"""
import sys
import os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import http.server
import socketserver
from pathlib import Path
from urllib.parse import urlparse


def make_handler(output_path: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(output_path), **kwargs)

        def do_GET(self):
            parsed = urlparse(self.path)
            # Health check — responds instantly, confirms server is alive
            if parsed.path == "/_health":
                body = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            # Serve data files from each project's data/ folder
            # e.g. /my-project/data/teams.json → generated/my-project/data/teams.json
            if "/data/" in parsed.path:
                rel = parsed.path.lstrip("/")
                data_file = output_path / rel
                if data_file.exists() and data_file.suffix == ".json":
                    content = data_file.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
            super().do_GET()

        def end_headers(self):
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

        def log_message(self, *args):
            pass  # silence access log

    return Handler


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: python html_server.py <output_dir> <port>")
        sys.exit(1)
    output_path = Path(args[0]).resolve()
    port = int(args[1])
    handler = make_handler(output_path)
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        httpd.allow_reuse_address = True
        httpd.serve_forever()
