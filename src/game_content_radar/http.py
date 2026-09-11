from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass(slots=True)
class HttpClient:
    timeout: int = 15
    user_agent: str = "game-content-radar/0.1"
    retries: int = 2
    session: requests.Session = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

    def get_json(self, url: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # requests errors + json errors
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.6 * (attempt + 1))
        raise RuntimeError(f"GET JSON failed: {url}: {last_error}")

    def get_text(self, url: str, **kwargs: Any) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout, **kwargs)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or resp.encoding
                return resp.text
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.6 * (attempt + 1))
        raise RuntimeError(f"GET text failed: {url}: {last_error}")
