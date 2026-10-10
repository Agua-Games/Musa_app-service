"""HTTP client for the MUSA dynamic API, used by the beta personas (ADR 0014).

Personas reach the product exactly like the curator's admin UI: plain HTTP
against `musa-build serve`, bearer token obtained via /auth/login. No builder
internals are called from persona actions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests


@dataclass
class ApiResponse:
    status: int
    body: object  # parsed JSON body, or None when the response has no JSON
    latency_ms: float

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class ApiClient:
    """One curator session against a running `musa-build serve` instance."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self.token: str | None = None

    # -- transport ------------------------------------------------------
    def request(self, method: str, path: str, *, auth: bool = False, json=None,
                timeout: float | None = None) -> ApiResponse:
        headers = {}
        if auth:
            if not self.token:
                raise RuntimeError("auth=True requested before login()")
            headers["Authorization"] = f"Bearer {self.token}"
        t0 = time.perf_counter()
        # NOTE: health polling right after boot must use a SHORT timeout —
        # on Windows, a connect raced against the listener bind can wedge in
        # the kernel for the full timeout instead of failing fast.
        res = self._session.request(
            method, self.base_url + path, headers=headers, json=json,
            timeout=timeout if timeout is not None else self.timeout,
        )
        latency = (time.perf_counter() - t0) * 1000
        try:
            body = res.json()
        except ValueError:
            body = None
        return ApiResponse(res.status_code, body, latency)

    # -- endpoints (the curator's real vocabulary) ----------------------
    def login(self, email: str, password: str) -> ApiResponse:
        res = self.request("POST", "/auth/login", json={"email": email, "password": password})
        if res.ok:
            self.token = res.body["token"]
        return res

    def health(self, *, timeout: float | None = None) -> ApiResponse:
        return self.request("GET", "/health", timeout=timeout)

    def schema(self) -> ApiResponse:
        return self.request("GET", "/schema")

    def collections(self, *, auth: bool = False) -> ApiResponse:
        return self.request("GET", "/collections", auth=auth)

    def collection_items(self, collection_id: str, *, include_drafts: bool = False,
                         auth: bool = False) -> ApiResponse:
        path = f"/collections/{collection_id}/items"
        if include_drafts:
            path += "?include_drafts=1"
        return self.request("GET", path, auth=auth)

    def item(self, asset_id: str, *, auth: bool = False) -> ApiResponse:
        return self.request("GET", f"/items/{asset_id}", auth=auth)

    def create_collection(self, collection_id: str, title: str, **extra) -> ApiResponse:
        return self.request(
            "POST", "/collections", auth=True,
            json={"id": collection_id, "title": title, **extra},
        )

    def save_item(self, card_or_patch: dict) -> ApiResponse:
        """Create (full card, born draft) or patch ({asset_id, ...fields})."""
        return self.request("POST", "/items", auth=True, json=card_or_patch)

    def search(self, q: str) -> ApiResponse:
        return self.request("GET", f"/search?q={requests.utils.quote(q)}")
