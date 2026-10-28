import glob
import json

import httpx

from app.core.config import settings

key = settings.llm_api_key or settings.meta_api_key
wav = sorted(glob.glob("/code/uploads/*consult.wav"))[0]
data = open(wav, "rb").read()
print("wav bytes:", len(data))
request = {"mode": "PUSH_TO_TALK", "model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV"}
resp = httpx.post(
    "https://api.meta.ai/v1/asr/transcribe",
    headers={"Authorization": f"Bearer {key}"},
    files={
        "request": (None, json.dumps(request), "application/json"),
        "audio": ("consult.wav", data, "audio/wav"),
    },
    timeout=180.0,
)
print("status:", resp.status_code)
print("body:", resp.text[:500])
