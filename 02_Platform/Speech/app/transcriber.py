"""OpenAI transcription call with model fallback. The only module that reads whisper_key."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import Depends

from app.audio import AssembledAudio
from app.config import SpeechSettings, get_settings
from app.errors import SpeechError
from app.vocabulary import Vocabulary, to_form_fields

log = logging.getLogger("speech")
OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"
FALLBACK_STATUSES = (400, 404, 422)  # upstream rejects the model or its parameters


@dataclass
class TranscriptionOutcome:
    text: str
    model_used: str
    fallback_used: bool
    languages: Optional[list]
    api_ms: int


def _lang_codes(langs):
    """Normalize detected languages to list[str]; the API returns either strings or {'code': 'en'} objects."""
    if not isinstance(langs, list):
        return None
    return [x.get("code") if isinstance(x, dict) else str(x) for x in langs if x] or None


class Transcriber:
    def __init__(self, settings: SpeechSettings, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.settings = settings
        self.transport = transport  # test seam (httpx.MockTransport); None = real network

    async def _call(self, client: httpx.AsyncClient, audio: AssembledAudio, model: str, vocab: Vocabulary):
        data: dict = {"model": model, "response_format": "json"}
        for name, value in to_form_fields(model, vocab):  # repeated names become repeated multipart fields
            data.setdefault(name, []).append(value)
        with open(audio.path, "rb") as f:
            files = {"file": (audio.path.name, f.read(), audio.mime_type)}
        return await client.post(OPENAI_URL, data=data, files=files,
                                 headers={"Authorization": f"Bearer {self.settings.whisper_key}"})

    async def transcribe(self, audio: AssembledAudio, vocab: Vocabulary) -> TranscriptionOutcome:
        s = self.settings
        t0 = time.perf_counter()
        fallback_used = False
        model = s.model
        try:
            async with httpx.AsyncClient(timeout=s.upstream_timeout_s, transport=self.transport) as client:
                resp = await self._call(client, audio, model, vocab)
                if resp.status_code in FALLBACK_STATUSES and s.fallback_model and s.fallback_model != s.model:
                    log.warning("primary model rejected status=%s; trying fallback", resp.status_code)
                    model, fallback_used = s.fallback_model, True
                    resp = await self._call(client, audio, model, vocab)
        except httpx.TimeoutException:
            raise SpeechError("TRANSCRIPTION_TIMEOUT", "Transcription request timed out.")
        except httpx.HTTPError as e:
            raise SpeechError("TRANSCRIPTION_FAILED", f"Transcription request failed ({type(e).__name__}).")
        if resp.status_code != 200:
            log.warning("upstream status=%s", resp.status_code)
            raise SpeechError("TRANSCRIPTION_FAILED", f"Transcription upstream returned HTTP {resp.status_code}.")
        try:
            body = resp.json()
            text = str(body.get("text", "")).strip()
        except ValueError:
            raise SpeechError("TRANSCRIPTION_FAILED", "Transcription upstream returned an unreadable response.")
        langs = body.get("languages")
        return TranscriptionOutcome(text=text, model_used=model, fallback_used=fallback_used,
                                    languages=_lang_codes(langs),
                                    api_ms=int((time.perf_counter() - t0) * 1000))


def get_transcriber(settings: SpeechSettings = Depends(get_settings)) -> Transcriber:
    return Transcriber(settings)
