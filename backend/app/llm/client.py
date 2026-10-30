"""Single model access layer: text, vision, audio transcription, embeddings.

Everything goes through LiteLLM's OpenAI-compatible interface so the
provider (Meta API, OpenAI, a self-hosted LiteLLM proxy, ...) is just
configuration. ``LLM_PROVIDER=echo`` returns deterministic canned output
for tests and offline development — it never touches the network.
"""

import base64
import json
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


def _api_key() -> str:
    return settings.llm_api_key or settings.meta_api_key


def _litellm_kwargs() -> dict:
    kw: dict = {}
    if _api_key():
        kw["api_key"] = _api_key()
    if settings.llm_api_base:
        kw["api_base"] = settings.llm_api_base
    return kw


# Deterministic canned outputs keyed by prompt kind (echo provider).
_ECHO = {
    "plan": {
        "specialties": ["HIV care", "Cardiology"],
        "queries": ["antiretroviral therapy adherence", "management of hypertension in adults"],
        "reasoning": "Echo plan.",
    },
    "draft": {
        "specialties": ["HIV care", "Cardiology"],
        "items": [
            {"specialty": "HIV care", "concern": "Review ART adherence against recorded visits.",
             "question": "When was the last viral load?", "citation": "Visit notes on file",
             "source_type": "patient_record", "urgent": False},
            {"specialty": "Cardiology", "concern": "Blood pressure above target at recent visits.",
             "question": "Has treatment been intensified?", "citation": "Visit notes on file",
             "source_type": "patient_record", "urgent": False},
        ],
        "interactions": [
            {"drugs": ["Drug A", "Drug B"], "concern": "Echo interaction for tests.",
             "citation": "Visit notes on file", "source_type": "patient_record"},
        ],
        "overdue_checks": [
            {"check": "Kidney function", "last_done": "not on record",
             "citation": "Visit notes on file", "source_type": "patient_record"},
        ],
    },
    # No "selfcheck" fixture: point ids only exist at run time, so echo
    # mode generates a keep verdict per id in code (see mdt/tasks.py).
    "visit_summary": {
        "en": "Echo visit summary.",
        "sw": "Muhtasari wa echo wa ziara.",
        "lg": "Echo okusumulula kwa IPS.",
    },
    "question_i18n": {
        "en": "Echo question.",
        "sw": "Swali la echo.",
        "lg": "Ekibuuzo kya echo.",
    },
    "answer_i18n": {
        "en": "Echo answer.",
        "sw": "Jibu la echo.",
        "lg": "Eddamu lya echo.",
    },
    "translate_en": {
        "en": "Echo transcription in English.",
    },
}


def complete_json(
    *, system: str, user: str, kind: str, max_tokens: int = 8000, retries: int = 1
) -> dict:
    # Generous budget: reasoning models spend hundreds of tokens thinking
    # before emitting; too small a cap ends the turn with empty content
    # (finish_reason=length) before any JSON appears.
    """Chat completion parsed as JSON. ``kind`` selects the echo fixture."""
    if settings.llm_provider == "echo":
        return json.loads(json.dumps(_ECHO[kind]))
    import litellm

    last_error = "unknown error"
    for attempt in range(retries + 1):
        try:
            resp = litellm.completion(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                **_litellm_kwargs(),
            )
            choice = resp.choices[0]
            content = choice.message.content
            if not content:
                last_error = (
                    f"empty content (finish_reason={choice.finish_reason})"
                )
                continue
            return json.loads(content)
        except Exception as exc:
            last_error = str(exc)[:300]
    raise LLMError(f"completion failed after {retries + 1} attempt(s): {last_error}")


def describe_image(path: str, mime: str, instruction: str) -> str:
    """Vision read of a photo (handwritten notes, lab slip, patient-held book)."""
    if settings.llm_provider == "echo":
        return f"Echo transcription of {Path(path).name} — verify against the photo."
    import litellm

    raw = base64.b64encode(Path(path).read_bytes()).decode()
    try:
        resp = litellm.completion(
            model=settings.llm_vision_model or settings.llm_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime or 'image/jpeg'};base64,{raw}"},
                        },
                    ],
                }
            ],
            max_tokens=2000,
            **_litellm_kwargs(),
        )
    except Exception as exc:
        raise LLMError(f"vision read failed: {exc}") from exc
    return resp.choices[0].message.content or ""


def transcribe_to_english(path: str) -> tuple[str, str]:
    """Speech-to-text plus translation: Luganda/Swahili/English speech in,
    (original transcript, plain English text) out. The original is kept so
    bilingual staff can check the translation. Audio is transcription fuel
    only — callers must not serve the file to users."""
    from app.llm.prompts import TRANSLATE_ENGLISH_SYSTEM

    if settings.llm_provider == "echo":
        return ("Echo transcript.", "Echo transcription in English.")
    text = transcribe_audio(path).strip()
    if not text:
        return ("", "")
    raw = complete_json(
        system=TRANSLATE_ENGLISH_SYSTEM, user=text, kind="translate_en"
    )
    return (text, str(raw.get("en", "")).strip())


def transcribe_audio(path: str, language: str | None = None) -> str:
    """Speech-to-text for consultation dictation (English or local languages)."""
    if settings.llm_provider == "echo":
        return f"Echo transcript of {Path(path).name} — verify against the audio."
    if settings.llm_transcribe_model.startswith("muse-voice-transcribe"):
        return _transcribe_meta_asr(path)
    import litellm

    kwargs = _litellm_kwargs()
    if language:
        kwargs["language"] = language
    try:
        with Path(path).open("rb") as fh:
            resp = litellm.transcription(
                model=settings.llm_transcribe_model, file=fh, **kwargs
            )
    except Exception as exc:
        raise LLMError(f"transcription failed: {exc}") from exc
    text = resp.get("text") if isinstance(resp, dict) else getattr(resp, "text", "")
    return text or ""


def _ensure_asr_wav(path: str) -> tuple[str, bool]:
    """Voice recordings arrive as phone/browser formats (m4a, webm, mp3);
    the ASR endpoint wants mono s16le WAV at 16 or 24 kHz. Returns the file
    to send plus whether it is a temp copy the caller must delete."""
    import wave

    try:
        with wave.open(str(path), "rb") as wav:
            if (
                wav.getnchannels() == 1
                and wav.getsampwidth() == 2
                and wav.getframerate() in (16000, 24000)
            ):
                return path, False
    except Exception:
        pass
    import os
    import subprocess
    import tempfile

    import imageio_ffmpeg

    fd, converted = tempfile.mkstemp(prefix="asr-", suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-y",
                "-i",
                str(path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-sample_fmt",
                "s16",
                converted,
            ],
            check=True,
            capture_output=True,
        )
    except Exception as exc:
        Path(converted).unlink(missing_ok=True)
        raise LLMError(f"audio conversion failed: {exc}") from exc
    return converted, True


def _transcribe_meta_asr(path: str) -> str:
    """Muse Voice Transcribe via Meta Model API.

    POST {base}/asr/transcribe, multipart with a JSON `request` part and the
    recording as the `audio` part. PUSH_TO_TALK fits single-turn dictation.
    """
    import httpx

    base = (settings.llm_api_base or "https://api.meta.ai/v1").rstrip("/")
    wav_path, is_temp = _ensure_asr_wav(path)
    request = {
        "mode": "PUSH_TO_TALK",
        "model": settings.llm_transcribe_model,
        "audioEncoding": "WAV",
    }
    try:
        raw = Path(wav_path).read_bytes()
        resp = httpx.post(
            base + "/asr/transcribe",
            headers={"Authorization": f"Bearer {_api_key()}"},
            files={
                "request": (None, json.dumps(request), "application/json"),
                "audio": (Path(path).name, raw, "audio/wav"),
            },
            timeout=180.0,
        )
        resp.raise_for_status()
        return resp.json().get("transcript", "")
    except Exception as exc:
        raise LLMError(f"voice transcription failed: {exc}") from exc
    finally:
        if is_temp:
            Path(wav_path).unlink(missing_ok=True)


def embed(texts: list[str]) -> list[list[float]]:
    """Embedding vectors, one per text, of length settings.llm_embed_dim.

    Prefers the local model server when configured (no patient text leaves
    the deployment); otherwise LiteLLM, or deterministic echo output.
    """
    dim = settings.llm_embed_dim
    if settings.model_server_url:
        return _embed_remote(texts, dim)
    if settings.llm_provider == "echo":
        return [[0.1] * dim for _ in texts]
    import litellm

    try:
        resp = litellm.embedding(
            model=settings.llm_embed_model, input=texts, **_litellm_kwargs()
        )
    except Exception as exc:
        raise LLMError(f"embedding failed: {exc}") from exc
    vectors = [list(d["embedding"]) for d in resp.data]
    _check_dims(vectors, dim)
    return vectors


def _check_dims(vectors: list[list[float]], dim: int) -> None:
    for vec in vectors:
        if len(vec) != dim:
            raise LLMError(
                f"embedding dim {len(vec)} != configured {dim}; "
                "set LLM_EMBED_DIM to match the model"
            )


def _embed_remote(texts: list[str], dim: int) -> list[list[float]]:
    import httpx

    url = settings.model_server_url.rstrip("/") + "/embed"
    try:
        resp = httpx.post(url, json={"texts": texts}, timeout=300.0)
        resp.raise_for_status()
        vectors = [list(v) for v in resp.json()["vectors"]]
    except Exception as exc:
        raise LLMError(f"model server embedding failed: {exc}") from exc
    _check_dims(vectors, dim)
    return vectors


def rerank(query: str, texts: list[str]) -> list[int]:
    """Best-first order of document indexes by cross-encoder relevance.

    Calls {model_server_url}/rerank when a model server is configured.
    Without one (echo/tests) — or if the ranker fails — returns the input
    order unchanged, so a down ranker degrades to plain vector search
    instead of breaking the brief.
    """
    if len(texts) <= 1:
        return list(range(len(texts)))
    if settings.llm_provider == "echo" or not settings.model_server_url:
        return list(range(len(texts)))
    import httpx

    try:
        resp = httpx.post(
            settings.model_server_url.rstrip("/") + "/rerank",
            json={"query": query, "documents": texts},
            timeout=300.0,
        )
        resp.raise_for_status()
        scores = resp.json()["scores"]
    except Exception as exc:
        logger.warning("model server rerank failed, keeping vector order: %s", exc)
        return list(range(len(texts)))
    if not isinstance(scores, list) or len(scores) != len(texts):
        logger.warning("model server rerank returned %s scores for %s documents", len(scores) if isinstance(scores, list) else type(scores), len(texts))
        return list(range(len(texts)))
    order = sorted(range(len(texts)), key=lambda i: scores[i], reverse=True)
    return order
