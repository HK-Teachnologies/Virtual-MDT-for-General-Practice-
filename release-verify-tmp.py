"""Live release-gate probe (throwaway). Usage:
  python release-verify-tmp.py setup   # release D visits, approve items, prepare overall
  python release-verify-tmp.py portal <otp-code>  # release overall, read my-summary
"""
import json
import subprocess
import sys
import time

TMP = "C:/Windows/Temp"
RESOLVE = ["--resolve", "localhost:443:127.0.0.1"]
PATIENT_D = "9b7ed0c9-526a-4494-9c57-50884c61a307"
EMAIL = "demo-d@example.com"


def curl(*args):
    p = subprocess.run(
        ["curl.exe", "-s", "-k", *RESOLVE, *args],
        capture_output=True, text=True, timeout=120,
    )
    try:
        return json.loads(p.stdout)
    except ValueError:
        return p.stdout


def api(method, path, token=None, json_body=None):
    args = [f"https://localhost{path}"]
    if token:
        args += ["-H", f"Authorization: Bearer {token}"]
    if json_body is not None:
        f = f"{TMP}/mdt-body.json"
        with open(f, "w") as fh:
            json.dump(json_body, fh)
        args += ["-H", "Content-Type: application/json", "--data", f"@{f}"]
    if method != "GET":
        args += ["-X", method]
    return curl(*args)


# login is form-encoded:
p = subprocess.run(
    ["curl.exe", "-s", "-k", *RESOLVE, "https://localhost/api/auth/login",
     "-d", "username=admin@me.com&password=pass123"],
    capture_output=True, text=True, timeout=60)
stok = json.loads(p.stdout)["access_token"]

if sys.argv[1] == "setup":
    rec = api("GET", f"/api/patients/{PATIENT_D}", token=stok)
    for v in rec["visits"]:
        r = api("POST", f"/api/patients/visits/{v['id']}/release", token=stok)
        print("release visit", v["visit_date"], r.get("summary_status"),
              r.get("released_by_name"))
    runs = api("GET", f"/api/mdt/patients/{PATIENT_D}/runs", token=stok)
    ready = [r for r in runs if r["status"] == "ready"]
    print("ready runs:", len(ready))
    run = ready[0]
    for item in run["items"]:
        if item["status"] not in ("approved", "edited"):
            api("PATCH", f"/api/mdt/items/{item['id']}",
                token=stok, json_body={"status": "approved"})
    print("items approved")
    prep = api("POST", f"/api/mdt/runs/{run['id']}/patient-summary", token=stok)
    print("prepare:", prep.get("queued"), prep["run"].get("patient_summary", {}).get("en", "")[:60])
    for _ in range(30):
        time.sleep(10)
        cur = api("GET", f"/api/mdt/runs/{run['id']}", token=stok)
        if cur.get("patient_summary", {}).get("en"):
            print("overall draft:", cur["patient_summary"]["en"][:200])
            print("RUN", run["id"])
            break
    else:
        print("TIMEOUT waiting for overall draft")
    api("POST", "/api/patient-auth/request", json_body={"identifier": EMAIL})
    print("OTP requested")
elif sys.argv[1] == "portal":
    code = sys.argv[2]
    v = api("POST", "/api/patient-auth/verify",
            json_body={"identifier": EMAIL, "code": code})
    ptok = v["access_token"]
    s = api("GET", "/api/patient-auth/my-summary", token=ptok)
    print("overall:", json.dumps(s["summary"], ensure_ascii=False)[:300])
    print("overall by:", s["summary_released_by_name"], s["summary_released_at"])
    for x in s["visits"]:
        print(x["date"], "ready=", x["ready"], "by=", x["released_by_name"],
              (x["en"] or "[preparing]")[:100])
