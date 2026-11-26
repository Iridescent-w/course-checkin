import importlib.util
import json
import os
import sys
import tempfile
import unittest
import threading
import hashlib
import hmac
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TEMP_STATE = tempfile.TemporaryDirectory()
os.environ["COURSE_STATE_DIR"] = TEMP_STATE.name
os.environ["COURSE_BASE_URL"] = "http://course.test"
spec = importlib.util.spec_from_file_location("course_checkin", ROOT / "course_checkin.py")
client = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = client
spec.loader.exec_module(client)


class ApiRequestTests(unittest.TestCase):
    def test_login_response_is_parsed(self):
        response = BytesIO(b'{"code":200,"data":{"token":"example"}}')
        with patch.object(client.urllib.request, "urlopen", return_value=response) as open_url:
            result = client.api_request("POST", "/auth/login", {"student_no": "demo", "password": "demo"})

        self.assertEqual(result["data"]["token"], "example")
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "http://course.test/api/auth/login")
        self.assertEqual(json.loads(request.data), {"student_no": "demo", "password": "demo"})

    def test_signed_request_has_expected_hmac_header(self):
        response = BytesIO(b'{"code":200,"data":{}}')
        with patch.object(client.urllib.request, "urlopen", return_value=response) as open_url:
            client.api_request("POST", "/attendance/check-in", {"status": "在校"}, "token", "key")

        request = open_url.call_args.args[0]
        timestamp = request.get_header("X-timestamp")
        nonce = request.get_header("X-nonce")
        canonical = f"POST\n/api/attendance/check-in\n\n{timestamp}\n{nonce}"
        expected = hmac.new(b"key", canonical.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(request.get_header("X-sign"), expected)
        self.assertEqual(request.get_header("Authorization"), "Bearer token")

    def test_full_flow_against_local_server_and_duplicate_guard(self):
        calls = []
        today = datetime.now().astimezone().date().isoformat()

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append(self.path)
                if self.path == "/api/auth/login":
                    valid = body == {"student_no": "demo", "password": "demo"}
                    data = {"token": "test-token", "sign_key": "test-key"}
                else:
                    canonical = (
                        f"POST\n{self.path}\n\n{self.headers['X-Timestamp']}"
                        f"\n{self.headers['X-Nonce']}"
                    )
                    expected = hmac.new(b"test-key", canonical.encode(), hashlib.sha256).hexdigest()
                    valid = (
                        self.path == "/api/attendance/check-in"
                        and self.headers.get("X-Sign") == expected
                        and self.headers.get("Authorization") == "Bearer test-token"
                        and body == {"status": "在校"}
                    )
                    data = {"attendance_date": today}
                payload = json.dumps({"code": 200 if valid else 400, "data": data}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as state:
                marker = Path(state) / "last_successful_date.txt"
                with patch.object(client, "SERVER_URL", f"http://127.0.0.1:{server.server_port}"), \
                     patch.object(client, "SUCCESS_MARKER", marker), \
                     patch.object(client, "LOG_PATH", Path(state) / "test.log"), \
                     patch.dict(os.environ, {"COURSE_STUDENT_NO": "demo", "COURSE_PASSWORD": "demo"}):
                    client.main()
                    self.assertEqual(marker.read_text(encoding="utf-8").strip(), today)
                    client.main()
                    self.assertEqual(calls, ["/api/auth/login", "/api/attendance/check-in"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
