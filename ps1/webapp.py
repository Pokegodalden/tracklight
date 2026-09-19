"""Loopback-only planner. Run with the project .venv: python -m ps1.webapp --port 8767"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from .workspace import RunError, Workspace, decode_upload

WEB = Path(__file__).resolve().parents[1] / "web"
MAX_REQUEST = 9 * 1024 * 1024


class Server(HTTPServer):
    def __init__(self, address):
        if address[0] != "127.0.0.1":
            raise ValueError("This prototype binds only to 127.0.0.1.")
        self.workspace = None
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)
        self.workspace = Workspace()

    def server_close(self):
        super().server_close()
        if self.workspace is not None:
            self.workspace.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send(self, status, data, kind="application/json; charset=utf-8", filename=None):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def allowed_host(self):
        port = self.server.server_port
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self.send(403, {"error": "This app accepts local requests only."})
            return False
        return True

    def do_GET(self):
        if not self.allowed_host():
            return
        path = urlsplit(self.path).path
        try:
            if path in ("/", "/app.js", "/style.css"):
                name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
                content = (WEB / name).read_bytes()
                if name == "index.html":
                    content = content.replace(b"__SESSION_TOKEN__", self.server.token.encode())
                kind = {"index.html": "text/html", "app.js": "text/javascript", "style.css": "text/css"}[name]
                self.send(200, content, kind+"; charset=utf-8")
            elif path == "/api/health":
                self.send(200, {"status": "ready", "scope": "local_step8"})
            elif path.startswith("/api/export/"):
                id = path.removeprefix("/api/export/")
                data, _ = self.server.workspace.export(id)
                self.send(200, data, "application/zip", f"ps1-review-{id[:8]}.zip")
            else:
                self.send(404, {"error": "Not found."})
        except RunError as exc:
            self.send(400, {"error": str(exc), "details": exc.details})
        except Exception:
            self.send(500, {"error": "The operation failed. The displayed run has not been replaced."})

    def do_POST(self):
        if not self.allowed_host():
            return
        origin = self.headers.get("Origin")
        port = self.server.server_port
        if self.headers.get("X-PS1-Token") != self.server.token or (origin is not None and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")):
            self.send(403, {"error": "Reload the local app before submitting a request."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise RunError("Use a JSON request of at most 9 MiB.")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise RunError("Expected a request object.")
            path = urlsplit(self.path).path
            if path == "/api/sample":
                view = self.server.workspace.sample()
            elif path == '/api/runs':
                view = self.server.workspace.summaries()
            elif path == '/api/run':
                view = self.server.workspace.get(body.get('id', ''))['view']
            elif path == '/api/replan':
                seconds = body.get('seconds', 30)
                if type(seconds) not in (int, float) or not 1 <= seconds <= 60:
                    raise RunError('Use a search limit from 1 to 60 seconds.')
                view = self.server.workspace.replan(body.get('id', ''), body.get('version'), body.get('proposal'), seconds=seconds)
            elif path == '/api/rollback':
                view = self.server.workspace.rollback(body.get('id', ''), body.get('version'))
            elif path == '/api/compare':
                view = self.server.workspace.compare(body.get('base_id', ''), body.get('candidate_id', ''))
            elif path == '/api/review':
                view = self.server.workspace.record_review(body.get('id', ''), body.get('version'),
                    body.get('reviewer'), body.get('decision'), body.get('note'), body.get('request_id'))
            elif path == '/api/alternative':
                seconds = body.get('seconds', 30)
                if type(seconds) not in (int, float) or not 1 <= seconds <= 60:
                    raise RunError('The local alternative search supports a time limit of 1..60 seconds.')
                view = self.server.workspace.alternative(body.get('id', ''), body.get('version'), body.get('conflict_id'), seconds)
            elif path == "/api/import":
                view = self.server.workspace.create(decode_upload(body.get("files")), body.get("scenario", "A"), "Uploaded schedule" if len(body.get("files", [])) == 11 else "Uploaded inputs")
            elif path == "/api/generate":
                view = self.server.workspace.generate(body.get("id", ""))
            elif path == '/api/optimise':
                seconds = body.get('seconds',30)
                if type(seconds) not in (int,float) or not 1 <= seconds <= 60:
                    raise RunError('The local web solver supports a time limit of 1..60 seconds.')
                view = self.server.workspace.optimise(body.get('id',''),body.get('scenario'),seconds=seconds)
            else:
                self.send(404, {"error": "Not found."})
                return
            self.send(200, view)
        except (RunError, ValueError, TypeError, KeyError) as exc:
            self.send(400, {"error": str(exc), "details": getattr(exc, "details", None)})
        except Exception:
            self.send(500, {"error": "The operation failed. The displayed run has not been replaced."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    with Server(("127.0.0.1", args.port)) as server:
        print(f"PS1 prototype ready at http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
