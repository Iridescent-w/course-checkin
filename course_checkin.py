import hashlib
import hmac
import json
import os
import secrets
import string
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


SERVER_URL = os.environ.get("COURSE_BASE_URL", "").rstrip("/")
STATE_DIR = Path(os.environ.get("COURSE_STATE_DIR", Path(__file__).parent))
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = STATE_DIR / "course_checkin.log"
SUCCESS_MARKER = STATE_DIR / "last_successful_date.txt"
CURRENT_STAGE = "startup"


def log(message):
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(f"{stamp} {message}\n")


def api_request(method, path, payload=None, token=None, sign_key=None):
    if not SERVER_URL:
        raise RuntimeError("Set COURSE_BASE_URL to the course test server origin")

    body = None if payload is None else json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    referer_path = "/login" if path == "/auth/login" else "/group/today"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": SERVER_URL,
        "Referer": SERVER_URL + referer_path,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/158.0.0.0 Safari/537.36"
        ),
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if sign_key:
        timestamp = str(int(time.time() * 1000))
        nonce = "".join(
            secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12)
        )
        canonical = f"{method.upper()}\n/api{path}\n\n{timestamp}\n{nonce}"
        signature = hmac.new(
            sign_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        headers.update(
            {"X-Timestamp": timestamp, "X-Nonce": nonce, "X-Sign": signature}
        )

    request = urllib.request.Request(
        SERVER_URL + "/api" + path,
        data=body,
        headers=headers,
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        try:
            response_data = json.loads(error.read().decode("utf-8", errors="replace"))
            message = response_data.get("message", f"HTTP {error.code}")
        except (ValueError, AttributeError):
            message = f"HTTP {error.code}"
        raise RuntimeError(str(message)) from None

    try:
        result = json.loads(raw.decode("utf-8"))
    except ValueError as error:
        raise RuntimeError("Server returned invalid JSON") from error
    if not isinstance(result, dict) or result.get("code") != 200:
        message = (
            result.get("message", "Request failed")
            if isinstance(result, dict)
            else "Request failed"
        )
        raise RuntimeError(str(message))
    return result


def main():
    global CURRENT_STAGE
    today = datetime.now().astimezone().date().isoformat()
    if SUCCESS_MARKER.exists() and SUCCESS_MARKER.read_text(encoding="utf-8").strip() == today:
        print(f"Skipped: today's submission is already recorded ({today}).")
        return

    student_no = os.environ.get("COURSE_STUDENT_NO", "")
    password = os.environ.get("COURSE_PASSWORD", "")
    if not student_no or not password:
        raise RuntimeError("Course account credentials are not configured")

    CURRENT_STAGE = "login"
    login = api_request(
        "POST",
        "/auth/login",
        {"student_no": student_no, "password": password},
    )
    login_data = login.get("data") or {}
    token = login_data.get("token")
    sign_key = login_data.get("sign_key")
    if not token or not sign_key:
        raise RuntimeError("Login response did not include token and sign_key")

    CURRENT_STAGE = "check-in submission"
    result = api_request(
        "POST",
        "/attendance/check-in",
        {"status": "在校"},
        token,
        sign_key,
    )
    attendance = result.get("data") or {}
    attendance_date = attendance.get("attendance_date")
    if attendance_date != today:
        raise RuntimeError("Response did not confirm today's submission")

    SUCCESS_MARKER.write_text(f"{attendance_date}\n", encoding="utf-8")
    message = str(result.get("message", "success"))
    log(f"SUCCESS date={attendance_date} message={message}")
    print(f"Submission completed: {attendance_date}; {message}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        log(f"FAILURE stage={CURRENT_STAGE} {type(error).__name__}: {error}")
        print(f"Submission failed: {error}", file=sys.stderr)
        sys.exit(1)
