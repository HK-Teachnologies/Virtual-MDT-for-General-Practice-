"""Live portal E2E probe (throwaway): drives curl.exe from Python to avoid
PowerShell quoting issues. Usage:
  python portal-e2e-tmp.py request-otp
  python portal-e2e-tmp.py answer <otp-code>
"""
import json
import subprocess
import sys
import tempfile
import time

TMP = tempfile.gettempdir()
RESOLVE = ["--resolve", "localhost:443:127.0.0.1"]
PATIENT_ID = "9b7ed0c9-526a-4494-9c57-50884c61a307"
Q1 = "24e54fa5-9d47-43cd-b5b1-d1f0ef85b403"
Q2 = "571458f8-4ee8-4950-b12c-79b5e4e22892"
EMAIL = "demo-d@example.com"
TONE = "C:/Users/hakim/AppData/LocalLow/muse-shell-sandbox-01a17cb6-dc76-7671-b74a-e3513bdc33f2/tone.wav"


def curl(*args):
    p = subprocess.run(
        ["curl.exe", "-s", "-k", *RESOLVE, *args],
        capture_output=True, text=True, timeout=180,
    )
    try:
        return json.loads(p.stdout)
    except ValueError:
        return p.stdout


def auth(email="admin@me.com", password="pass123"):
    body = curl(
        "https://localhost/api/auth/login",
        "-d", f"username={email}&password={password}",
    )
    return body["access_token"]


def api(method, path, token=None, json_body=None, form=None):
    args = [f"https://localhost{path}"]
    if token:
        args += ["-H", f"Authorization: Bearer {token}"]
    if json_body is not None:
        f = f"{TMP}/mdt-body.json"
        with open(f, "w") as fh:
            json.dump(json_body, fh)
        args += ["-H", "Content-Type: application/json", "--data", f"@{f}"]
    elif form:
        for k, v in form.items():
            args += ["-F", f"{k}={v}"]
    if method != "GET":
        args += ["-X", method]
    return curl(*args)


if sys.argv[1] == "request-otp":
    print(api("POST", "/api/patient-auth/request", json_body={"identifier": EMAIL}))
elif sys.argv[1] == "answer":
    code = sys.argv[2]
    ptok = api("POST", "/api/patient-auth/verify",
               json_body={"identifier": EMAIL, "code": code})["access_token"]
    print("verified ok")
    print("answer Q1:", api(
        "POST", f"/api/followups/{Q1}/answer", token=ptok,
        form={"text": "The headache is gone but I still feel hot in the evening."},
    ))
    print("answer Q2 voice:", api(
        "POST", f"/api/followups/{Q2}/answer", token=ptok,
        form={"audio": f"@{TONE};type=audio/wav"},
    ))
    for _ in range(24):
        time.sleep(10)
        mine = api("GET", "/api/followups/mine", token=ptok)
        q2 = [q for q in mine if q["id"] == Q2][0]
        print("q2 poll:", q2["status"], repr(q2["answer_text"][:80]))
        if q2["status"] == "answered":
            break
    stok = auth()
    thread = api("GET", f"/api/followups/for-patient/{PATIENT_ID}", token=stok)
    print("staff thread:", json.dumps(thread, indent=1)[:1500])
    raw = subprocess.run(
        ["curl.exe", "-s", "-k", *RESOLVE, f"https://localhost/api/followups/{Q2}/audio",
         "-H", f"Authorization: Bearer {stok}", "-o", f"{TMP}/mdt-ans.wav", "-w", "%{size_download}"],
        capture_output=True, text=True, timeout=60,
    )
    print("staff audio bytes:", raw.stdout)
