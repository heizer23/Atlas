"""
NumericSeries — LabelEngine HTTP client.

Isolates all httpx usage so routers do not import httpx directly.
Source of truth: Sprint01/20_design/scaffolding.json label_client.py
"""

from __future__ import annotations

import os

import httpx

LABEL_ENGINE_URL = os.environ.get("LABEL_ENGINE_URL", "http://atlas-label-engine:8000")


class LabelClientError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class LabelClient:
    def __init__(self, base_url: str = LABEL_ENGINE_URL) -> None:
        self._base_url = base_url

    def create_label(self, name: str) -> dict:
        """
        POST /api/labels to LabelEngine.
        Returns {id, name} on success.
        Raises LabelClientError on HTTP error or unavailability.
        """
        try:
            with httpx.Client(base_url=self._base_url, timeout=5.0) as client:
                resp = client.post("/api/labels", json={"name": name})
        except httpx.RequestError as exc:
            raise LabelClientError(
                "LABEL_ENGINE_UNAVAILABLE",
                f"LabelEngine unreachable: {exc}",
                status=503,
            ) from exc

        if resp.status_code == 201:
            return resp.json()

        # Handle duplicate name: LabelEngine returns 400 LABEL_DUPLICATE_NAME
        body = resp.json()
        err = body.get("error", {})
        raise LabelClientError(
            code=err.get("code", "LABEL_ENGINE_ERROR"),
            message=err.get("message", "LabelEngine error"),
            status=resp.status_code,
        )

    def search_labels(self, q: str = "") -> list[dict]:
        """
        GET /api/labels?q=<q> from LabelEngine.
        Returns list of {id, name}.
        """
        try:
            with httpx.Client(base_url=self._base_url, timeout=5.0) as client:
                resp = client.get("/api/labels", params={"q": q})
        except httpx.RequestError as exc:
            raise LabelClientError(
                "LABEL_ENGINE_UNAVAILABLE",
                f"LabelEngine unreachable: {exc}",
                status=503,
            ) from exc

        if resp.status_code == 200:
            return resp.json().get("labels", [])

        body = resp.json()
        err = body.get("error", {})
        raise LabelClientError(
            code=err.get("code", "LABEL_ENGINE_ERROR"),
            message=err.get("message", "LabelEngine error"),
            status=resp.status_code,
        )
