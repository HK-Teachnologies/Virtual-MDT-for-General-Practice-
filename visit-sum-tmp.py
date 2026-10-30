"""Live decoupling probe (throwaway): fresh patient + visit, no brief.
Usage: python visit-sum-tmp.py
Prints the portal my-summary once the worker-written visit line lands.
"""
import json
import subprocess
import sys
import time

TMP = "C:/Windows/Temp"
RESOLVE = ["--resolve", "localhost:443:127.0.0.1"]
EMAIL = "nodebrief@example.com"


def curl(*args):
    p = subprocess.run(
        ["curl.exe", "-s", "-k", *RESOLVE, *args],
        capture_output=True, text=True, timeout=120,
    )
    try:
        return json.loads(p.stdout)
    except ValueError:
        return p.stdout


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


stok = api("POST", "/api/auth/login",
           form={"username": "admin@me.com", "password": "pass123"})["access_token"]
pat = api("POST", "/api/patients", token=stok,
          json_body={"full_name": "No Brief Patient", "email": EMAIL})
pid = pat["id"]
print("patient:", pid)
visit = api("POST", f"/api/patients/{pid}/visits", token=stok, form={
    "notes": "Fever and sore throat for one day. No difficulty breathing.",
    "visit_date": "2026-10-29",
})
print("visit created, summary inline:", visit.get("patient_summary"))
vid = visit["id"]
for _ in range(18):
    time.sleep(10)
    rec = api("GET", f"/api/patients/{pid}", token=stok)
    v = [x for x in rec["visits"] if x["id"] == vid][0]
    if v["patient_summary"].get("en"):
        print("worker summary:", json.dumps(v["patient_summary"], ensure_ascii=False))
        break
else:
    print("TIMEOUT waiting for worker summary")
    sys.exit(1)

api("POST", "/api/patient-auth/request", json_body={"identifier": EMAIL})
print("OTP requested — read it from: docker logs virtual-mdt-backend-1 --since 2m")
