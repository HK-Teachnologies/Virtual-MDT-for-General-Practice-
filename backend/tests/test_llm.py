import httpx
import pytest

from app.core.config import settings
from app.llm import client as llm


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_embed_echo_default():
    assert settings.model_server_url == ""
    vecs = llm.embed(["hello", "world"])
    assert len(vecs) == 2
    assert all(len(v) == settings.llm_embed_dim for v in vecs)


def test_embed_remote(monkeypatch):
    monkeypatch.setattr(settings, "model_server_url", "http://model-server:8000")
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: _Resp({"vectors": [[0.2] * 768]})
    )
    vecs = llm.embed(["hello"])
    assert vecs == [[0.2] * 768]


def test_embed_remote_dim_mismatch(monkeypatch):
    monkeypatch.setattr(settings, "model_server_url", "http://model-server:8000")
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: _Resp({"vectors": [[0.2] * 384]})
    )
    with pytest.raises(llm.LLMError, match="dim"):
        llm.embed(["hello"])


def test_ensure_asr_wav_passthrough(tmp_path):
    import wave

    from app.llm.client import _ensure_asr_wav

    wav = tmp_path / "good.wav"
    with wave.open(str(wav), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(16000)
        fh.writeframes(b"\x00\x00" * 8000)
    assert _ensure_asr_wav(str(wav)) == (str(wav), False)


def test_ensure_asr_wav_rejects_garbage(tmp_path):
    from app.llm.client import LLMError, _ensure_asr_wav

    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio at all")
    try:
        _ensure_asr_wav(str(bad))
        raise AssertionError("should have raised")
    except LLMError as exc:
        assert "conversion failed" in str(exc)


def test_embed_remote_down(monkeypatch):
    monkeypatch.setattr(settings, "model_server_url", "http://model-server:8000")

    def boom(url, **kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(llm.LLMError, match="model server"):
        llm.embed(["hello"])
