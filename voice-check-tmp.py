"""Live voice-answer probe (throwaway). Usage:
  python voice-check-tmp.py <otp-code> <followup-id>
Prints the raw answer response, then checks disk + endpoints.
"""
import json
import subprocess
import sys

RESOLVE = ["--resolve", "localhost:443:127.0.0.1"]
TONE = "C:/Users/hakim/AppData/LocalLow/muse-shell-sandbox-01a17cb6-dc76-7671-b74a-e3513bdc33f2/tone.wav"


def curl(*args):
    p = subprocess.run(
        ["curl.exe", "-s", "-k", *RESOLVE, *args],
        capture_output=True, text=True, timeout=120,
    )
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"_raw": p.stdout[:300]}


code, qid = sys.argv[1], sys.argv[2]
open("C:/Windows/Temp/mdt-v.json", "w").write(
    json.dumps({"identifier": "demo-d@example.com", "code": code})
)
ptok = curl(
    "https://localhost/api/patient-auth/verify",
    "-H", "Content-Type: application/json",
    "--data", "@C:/Windows/Temp/mdt-v.json",
)["access_token"]
pauth = ["-H", "Authorization: Bearer " + ptok]
print("answer:", json.dumps(curl(
    f"https://localhost/api/followups/{qid}/answer",
    *pauth, "-F", f"audio=@{TONE};type=audio/wav",
)))
