"""Run: python app.py. Optional backend: UNIVERSAL_OPTIMIZER_MODULE=my_optimizer."""
import importlib
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from ui import render_page

ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "static"), **kwargs)

    def do_GET(self):
        url = urlsplit(self.path)
        module = os.environ.get("UNIVERSAL_OPTIMIZER_MODULE")
        if url.path == "/api/attractions":
            location = parse_qs(url.query).get("current_location", ["R_1"])[0]
            if location not in {f"R_{number}" for number in range(1, 9)}:
                return self.reply(400, {"error": "Unknown starting location"})
            if not module:
                return self.reply(503, {"error": "Attraction data provider not connected"})
            try:
                data = importlib.import_module(module).get_attractions(location)
                return self.reply(200, {"attractions": data})
            except Exception:
                self.log_error("Attraction provider failed")
                return self.reply(500, {"error": "Attraction data unavailable"})
        if url.path == "/":
            body = render_page(backend_enabled=bool(module)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != "/api/optimize":
            return self.reply(404, {"error": "Endpoint not found"})
        module = os.environ.get("UNIVERSAL_OPTIMIZER_MODULE")
        if not module:
            return self.reply(503, {"error": "Optimizer not connected. Please use demo mode."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > 65536:
                return self.reply(400, {"error": "Invalid request length"})
            payload = json.loads(self.rfile.read(length))
            result = importlib.import_module(module).optimize(payload)
            self.reply(200, result)
        except (ValueError, TypeError):
            self.reply(400, {"error": "Invalid request or response format"})
        except Exception:
            self.log_error("Optimizer failed")
            self.reply(500, {"error": "Optimization service unavailable. Please try again."})

    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Universal Day: http://127.0.0.1:{port}", flush=True)
    try:
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass

