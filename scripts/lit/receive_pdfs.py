"""Local receiver for open-access PDFs fetched inside the browser (used when Chrome blocks repeated downloads).

Listens on 127.0.0.1 only. Accepts POST /R1234 whose body is a PDF (must start with %PDF, at most 60 MB) and writes it
as sbb-R1234.pdf into the inbox folder; anything else is rejected. Answers CORS / private-network preflights so a page
on a publisher site can post to it. The inbox is then imported with:
  uv run --group analysis python scripts/lit/import_browser_pdfs.py "<how fetched>" <inbox>
Usage: uv run python scripts/lit/receive_pdfs.py <inbox folder> [port]   (stop with Ctrl+C / kill)
"""

import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

INBOX = Path(sys.argv[1])
MAX = 60 * 1024 * 1024


class H(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        m = re.fullmatch(r"/(R\d{4})", self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if 0 < n <= MAX else b""
        ok = bool(m) and body.startswith(b"%PDF")
        if ok:
            (INBOX / f"sbb-{m.group(1)}.pdf").write_bytes(body)
        self.send_response(200 if ok else 400)
        self._cors()
        self.end_headers()
        self.wfile.write(b"ok" if ok else b"rejected")
        print(self.path, len(body), "saved" if ok else "rejected", flush=True)


if __name__ == "__main__":
    INBOX.mkdir(parents=True, exist_ok=True)
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
