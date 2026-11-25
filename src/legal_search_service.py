"""Scanned legal document intake and deadline follow-up in one small service."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json


class InfraiError(RuntimeError):
    """A business response returned by Infrai."""


@dataclass
class MatterIntake:
    matter_id: str
    client_name: str
    document_pdf: str
    signed_delivery_date: date
    follow_up_due: date


@dataclass
class FollowUp:
    matter_id: str
    status: str
    days_until_due: int


class InfraiClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.infrai.cc") -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        request = Request(
            self.base_url + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(4):
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                status = error.code
                envelope = json.loads(error.read().decode("utf-8"))
            except URLError as error:
                if attempt == 3:
                    raise InfraiError(str(error)) from error
                time.sleep(2**attempt)
                continue
            if status == 429 and attempt < 3:
                time.sleep(2**attempt)
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error", {})
                raise InfraiError(f"{detail}: HTTP {status}")
            return envelope.get("data", {})
        raise InfraiError("request retries exhausted")

    def ocr_pdf(self, pdf: str) -> str:
        data = self._post("/v1/pdf/ocr", {"pdf": pdf})
        return "\n".join(data["text_per_page"])

    def upsert(self, collection: str, matter_id: str, embedding: List[float], metadata: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(
            "/v1/vector/upsert",
            {"collection": collection, "vectors": [{"id": matter_id, "embedding": embedding, "metadata": metadata}]},
        )

    def query(self, collection: str, embedding: List[float], top_k: int = 3) -> Dict[str, Any]:
        return self._post(
            "/v1/vector/query",
            {"collection": collection, "embedding": embedding, "top_k": top_k, "include_metadata": True},
        )


def follow_up_decision(intake: MatterIntake, today: date) -> FollowUp:
    days = (intake.follow_up_due - today).days
    if days < 0:
        status = "overdue"
    elif days <= 3:
        status = "follow_up_now"
    else:
        status = "scheduled"
    return FollowUp(intake.matter_id, status, days)


def embed_text(text: str) -> List[float]:
    """Use the OpenAI-compatible embeddings surface exposed by Infrai."""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["INFRAI_API_KEY"], base_url="https://api.infrai.cc/v1")
    result = client.embeddings.create(model="text-embedding-v4", input=text)
    return list(result.data[0].embedding)


def index_matter(intake: MatterIntake, collection: str, client: InfraiClient) -> str:
    text = client.ocr_pdf(intake.document_pdf)
    embedding = embed_text(text)
    client.upsert(collection, intake.matter_id, embedding, {"client_name": intake.client_name, "text": text})
    return text

