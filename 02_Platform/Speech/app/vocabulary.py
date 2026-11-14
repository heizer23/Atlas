"""Default vocabulary, per-field override resolution, model-specific parameter mapping."""

import json
from dataclasses import dataclass, field
from typing import Optional

NATIVE_MODEL = "gpt-transcribe"
FALLBACK_PROMPT_MAX_CHARS = 600  # conservative stand-in for the 224-token prompt limit


@dataclass
class Vocabulary:
    prompt: str = ""
    keywords: list = field(default_factory=list)
    languages: list = field(default_factory=lambda: ["en"])


def load_defaults(path: str) -> Vocabulary:
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = {}
    return Vocabulary(
        prompt=str(raw.get("prompt", "")),
        keywords=[str(k) for k in raw.get("keywords", [])],
        languages=[str(x) for x in raw.get("languages", ["en"])],
    )


def resolve(defaults: Vocabulary, prompt: Optional[str], keywords: Optional[list],
            languages: Optional[list]) -> Vocabulary:
    """None keeps the default, empty clears, a value replaces."""
    return Vocabulary(
        prompt=defaults.prompt if prompt is None else prompt,
        keywords=list(defaults.keywords) if keywords is None else list(keywords),
        languages=list(defaults.languages) if languages is None else list(languages),
    )


def to_form_fields(model: str, vocab: Vocabulary) -> list:
    fields = []
    if model == NATIVE_MODEL:
        # Multipart encoding for array fields: repeated field names (see component CLAUDE.md).
        if vocab.prompt:
            fields.append(("prompt", vocab.prompt))
        for k in vocab.keywords:
            fields.append(("keywords", k))
        for lang in vocab.languages:
            fields.append(("languages", lang))
        return fields
    prompt = vocab.prompt
    if vocab.keywords:
        prompt = (prompt + " " if prompt else "") + "Vocabulary: " + ", ".join(vocab.keywords) + "."
    if prompt:
        fields.append(("prompt", prompt[:FALLBACK_PROMPT_MAX_CHARS]))
    if len(vocab.languages) == 1:
        fields.append(("language", vocab.languages[0]))
    return fields
