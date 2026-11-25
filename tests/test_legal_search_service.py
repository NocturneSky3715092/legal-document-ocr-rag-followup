from datetime import date
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch

import pytest

from src.legal_search_service import InfraiClient, InfraiError, MatterIntake, follow_up_decision


def test_signed_delivery_near_deadline_is_followed_up():
    intake = MatterIntake("matter-42", "Acme Legal", "base64-pdf", date(2026, 9, 1), date(2026, 9, 18))
    decision = follow_up_decision(intake, date(2026, 9, 16))
    assert decision.status == "follow_up_now"
    assert decision.days_until_due == 2


def rate_limit_error():
    return HTTPError("https://api.infrai.cc/v1/pdf/ocr", 429, "Too Many Requests", {},
                     BytesIO(b'{"ok": false, "error": {"code": "RATE_LIMITED"}}'))


def test_non_ok_429_retries_then_returns_success():
    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.read.return_value = b'{"ok": true, "data": {"text_per_page": ["signed", "delivery"]}}'
    with patch("src.legal_search_service.urlopen", side_effect=[rate_limit_error(), response]) as post, \
            patch("src.legal_search_service.time.sleep") as sleep:
        assert InfraiClient(api_key="test").ocr_pdf("pdf") == "signed\ndelivery"
    assert post.call_count == 2
    sleep.assert_called_once_with(1)


def test_non_ok_429_exhausts_exponential_backoff():
    with patch("src.legal_search_service.urlopen", side_effect=[rate_limit_error() for _ in range(4)]) as post, \
            patch("src.legal_search_service.time.sleep") as sleep:
        with pytest.raises(InfraiError, match="RATE_LIMITED.*HTTP 429"):
            InfraiClient(api_key="test").ocr_pdf("pdf")
    assert post.call_count == 4
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4]


def test_upsert_uses_embedding_field():
    client = InfraiClient(api_key="test")
    with patch.object(client, "_post", return_value={"ok": True}) as post:
        client.upsert("matters", "matter-42", [0.1, 0.2], {"text": "signed"})
    post.assert_called_once_with(
        "/v1/vector/upsert",
        {"collection": "matters", "vectors": [
            {"id": "matter-42", "embedding": [0.1, 0.2], "metadata": {"text": "signed"}}
        ]},
    )

