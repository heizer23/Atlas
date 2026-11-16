"""App-local provider adapter and AI response parsing (EGR1, KEY1, VAL1).

Reads the environment per call (no module-level secret copy), never logs request/response bodies or the key,
never follows redirects, refuses any host outside COACH_ALLOWED_HOSTS before connecting. Single provider
(Anthropic Messages-style); deliberately not a reusable gateway.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.config import (
    COACH_ALLOWED_HOSTS, COACH_API_URL_DEFAULT, COACH_HTTP_TIMEOUT_S, COACH_MAX_TOKENS, COACH_PROMPT_VERSION_DEFAULT,
)

ANTHROPIC_VERSION = "2023-06-01"
_VERSION_RE = re.compile(r"^v[0-9]+$")
_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


class ProviderError(Exception):
    """Network/TLS/timeout/redirect/non-200/prompt_missing; host-not-allowed is defensive only. Short code, no content."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class InvalidAiResponse(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ProviderConfig:
    def __init__(self, api_key: Optional[str], model: Optional[str], url: str, prompt_version: str):
        self.api_key = api_key or None
        self.model = model or None
        self.url = url
        self.prompt_version = prompt_version

    def destination_host(self) -> Optional[str]:
        return urlparse(self.url).hostname

    def configured(self) -> bool:
        """key and model set, https, host in the allow-list (otherwise AI_NOT_CONFIGURED; no call, no call row)."""
        parsed = urlparse(self.url)
        return bool(self.api_key and self.model and parsed.scheme == "https" and parsed.hostname in COACH_ALLOWED_HOSTS)

    def __repr__(self) -> str:  # never show the key
        return f"ProviderConfig(model={self.model!r}, url={self.url!r}, key_set={bool(self.api_key)})"


def provider_config() -> ProviderConfig:
    env = os.environ
    version = (env.get("RUNNINGTRACKER_COACH_PROMPT_VERSION") or "").strip()
    if not _VERSION_RE.match(version):
        version = COACH_PROMPT_VERSION_DEFAULT
    return ProviderConfig(
        (env.get("RUNNINGTRACKER_COACH_API_KEY") or "").strip(),
        (env.get("RUNNINGTRACKER_COACH_MODEL") or "").strip(),
        (env.get("RUNNINGTRACKER_COACH_API_URL") or "").strip() or COACH_API_URL_DEFAULT,
        version,
    )


def load_prompt(version: str) -> str:
    if not _VERSION_RE.match(version):
        raise ProviderError("prompt_missing")
    try:
        return (_PROMPT_DIR / f"coach_prompt_{version}.md").read_text(encoding="utf-8")
    except OSError:
        raise ProviderError("prompt_missing")


def call_provider(cfg: ProviderConfig, system: str, user_json: str,
                  transport: Optional[httpx.BaseTransport] = None) -> str:
    """One HTTPS POST; returns the text of the first text content block. `transport` is the test seam."""
    if not cfg.configured():
        raise ProviderError("host_not_allowed")  # defensive: the route checks configured() first
    body = {"model": cfg.model, "max_tokens": COACH_MAX_TOKENS, "system": system,
            "messages": [{"role": "user", "content": user_json}]}
    headers = {"x-api-key": cfg.api_key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    try:
        with httpx.Client(timeout=COACH_HTTP_TIMEOUT_S, follow_redirects=False, transport=transport) as client:
            resp = client.post(cfg.url, headers=headers, content=json.dumps(body))
    except httpx.TimeoutException:
        raise ProviderError("timeout")
    except httpx.HTTPError:
        raise ProviderError("network")
    if resp.status_code != 200:
        raise ProviderError(f"http_{resp.status_code}")
    try:
        blocks = resp.json()["content"]
        return next(b["text"] for b in blocks if b.get("type") == "text")
    except (ValueError, KeyError, TypeError, StopIteration):
        raise ProviderError("bad_envelope")


class CoachAiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment: str = Field(min_length=1, max_length=1500)
    previous_recommendation_effect: Optional[str] = Field(None, max_length=600)
    profile_updates: list[dict] = Field(default_factory=list, max_length=10)
    next_session: Optional[dict] = None


_FENCE = re.compile(r"^```[a-zA-Z]*\s*\n(.*)\n```$", re.DOTALL)


def parse_ai_response(text: str) -> CoachAiResponse:
    """Strips one optional markdown code fence, parses one JSON object, validates (VAL1)."""
    t = (text or "").strip()
    m = _FENCE.match(t)
    if m:
        t = m.group(1).strip()
    try:
        raw = json.loads(t)
    except ValueError:
        raise InvalidAiResponse("not_json")
    if not isinstance(raw, dict):
        raise InvalidAiResponse("not_object")
    try:
        resp = CoachAiResponse.model_validate(raw)
    except ValidationError:
        raise InvalidAiResponse("shape")
    if not resp.assessment.strip():
        raise InvalidAiResponse("empty_assessment")
    return resp
