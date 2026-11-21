#!/usr/bin/env python3
"""Throwaway stand-in for POST /api/triage. Stdlib only, makes no LLM calls.

Serves contracts/triage_response.example.json with the ticket echoed back, so the
stress runner and the UI's failure states can be tried without the real backend.

    python3 stress/fake_server.py --port 8765                  # dry run for run_stress.py
    python3 stress/fake_server.py --port 8000 --mode hang      # UI timeout state (Vite proxies :8000)

Modes (switch at runtime: curl -X POST localhost:8765/__mode -d '{"mode":"slow"}'):
    ok         example contract, input echoed, language guessed (default)
    slow       like ok, after --delay seconds (slow retrieval / LLM)
    hang       never answers (UI 30 s timeout)
    error      500 {"error": {...}}
    malformed  200 with a body that is not JSON
    partial    200 JSON missing `classification` and `draft`
    drift      200 JSON with an off-vocabulary label and a citation not in precedents
    drop       closes the socket without answering (backend killed mid-request)
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

EXAMPLE = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "triage_response.example.json"
)
MODES = ("ok", "slow", "hang", "error", "malformed", "partial", "drift", "drop")
DE_HINT = re.compile(
    r"[äöüß]|\b(?:und|nicht|bitte|wir|ist|der|die|das|seit)\b", re.IGNORECASE
)

STATE: dict[str, Any] = {"mode": "ok", "delay": 8.0}
LOCK = threading.Lock()


DRAFTS = {
    "en": (
        "Thank you for reporting this. We have passed your ticket to our on-call "
        "engineer. In a similar case [TKT-01842], rolling back the gateway firmware "
        "and reissuing client certificates restored the service for the customer."
    ),
    "de": (
        "Vielen Dank für Ihre Nachricht. Wir haben Ihr Anliegen an unseren "
        "Bereitschaftsdienst weitergeleitet. In einem ähnlichen Fall [TKT-01842] "
        "konnte das Problem durch ein Zurücksetzen der Firmware gelöst werden."
    ),
}


def build_response(subject: str | None, body: str) -> dict[str, Any]:
    """The example contract with the ticket echoed and a holding-reply draft.

    Deliberately dumb: every ticket comes back as the same escalated VPN incident,
    so the dry run shows both passing and failing checks.
    """
    resp = copy.deepcopy(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    lang = "de" if len(DE_HINT.findall(f"{subject or ''} {body}")) >= 2 else "en"
    resp["request_id"] = f"req_{uuid.uuid4().hex[:6]}"
    resp["input"].update(subject=subject, body=body, language_detected=lang)
    resp["input"].setdefault("language_supported", True)
    resp["draft"] = {"language": lang, "text": DRAFTS[lang], "citations": ["TKT-01842"]}
    return resp


class Handler(BaseHTTPRequestHandler):
    server_version = "SentinelDeskFake/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter default log
        print(f"[fake] {self.command} {self.path} {fmt % args}")

    def _send(self, status: int, payload: Any, raw: bytes | None = None) -> None:
        data = raw if raw is not None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: int, code: str, message: str) -> None:
        self._send(status, {"error": {"code": code, "message": message}})

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length).decode("utf-8") or "null")

    def do_GET(self) -> None:
        if self.path == "/api/health":
            with LOCK:
                mode = STATE["mode"]
            stages = {
                s: {"mode": "fake", "ready": True} for s in ("classify", "generate")
            }
            self._send(200, {"status": "ok", "stages": stages, "fake_mode": mode})
        else:
            self._error(404, "NOT_FOUND", self.path)

    def do_POST(self) -> None:
        if self.path == "/__mode":
            try:
                mode = self._read_json().get("mode")
            except (json.JSONDecodeError, AttributeError):
                mode = None
            if mode not in MODES:
                self._error(422, "INVALID_REQUEST", f"mode must be one of {MODES}")
                return
            with LOCK:
                STATE["mode"] = mode
            self._send(200, {"mode": mode})
            return
        if self.path != "/api/triage":
            self._error(404, "NOT_FOUND", self.path)
            return
        try:
            req = self._read_json()
        except json.JSONDecodeError:
            self._error(422, "INVALID_REQUEST", "body is not JSON")
            return
        if not isinstance(req, dict) or not isinstance(req.get("body"), str):
            self._error(422, "INVALID_REQUEST", "body: field required")
            return
        body, subject = req["body"], req.get("subject")
        if not body.strip():
            self._error(422, "EMPTY_BODY", "Ticket body must not be empty.")
            return
        if len(body) > 20_000:
            self._error(
                422, "BODY_TOO_LONG", "Ticket body is longer than 20000 characters."
            )
            return
        if subject and len(subject) > 500:
            self._error(
                422, "SUBJECT_TOO_LONG", "Subject is longer than 500 characters."
            )
            return
        if isinstance(subject, str) and not subject.strip():
            subject = None

        with LOCK:
            mode, delay = STATE["mode"], STATE["delay"]
        start = time.perf_counter()
        if mode == "hang":
            time.sleep(3600)
        if mode == "drop":
            self.close_connection = True
            self.connection.close()
            return
        if mode == "slow":
            time.sleep(delay)
        else:
            time.sleep(0.05)  # a little realism for latency percentiles
        if mode == "error":
            self._error(
                500, "UPSTREAM_UNAVAILABLE", "The generator did not respond (fake)."
            )
            return
        if mode == "malformed":
            self._send(200, None, raw=b"<html>502 Bad Gateway</html>")
            return
        resp = build_response(subject, body)
        if mode == "partial":
            del resp["classification"], resp["draft"]
        if mode == "drift":
            resp["classification"]["priority"]["label"] = "critical"
            resp["draft"]["text"] += " See also [TKT-99999]."
        resp["latency_ms"]["total"] = round((time.perf_counter() - start) * 1000)
        self._send(200, resp)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--mode", choices=MODES, default="ok")
    p.add_argument("--delay", type=float, default=8.0, help="seconds, for --mode slow")
    args = p.parse_args()
    STATE.update(mode=args.mode, delay=args.delay)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[fake] listening on http://127.0.0.1:{args.port} mode={args.mode}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
