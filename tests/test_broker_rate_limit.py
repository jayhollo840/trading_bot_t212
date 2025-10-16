import requests
import pytest

from broker import Broker, RateLimitError


def test_req_raises_rate_limit(monkeypatch):
    """Broker._req surfaces rate limit responses with retry metadata."""
    monkeypatch.setattr(Broker, "_load_metadata", lambda self: None)
    broker_instance = Broker()

    response = requests.Response()
    response.status_code = 429
    response.headers["Retry-After"] = "7"
    response._content = b""
    response.url = f"{broker_instance.base_url}/test"
    response.reason = "Too Many Requests"

    def fake_request(method, url, json=None, timeout=None):
        return response

    monkeypatch.setattr(broker_instance.session, "request", fake_request)

    with pytest.raises(RateLimitError) as excinfo:
        broker_instance._req("GET", "/test")

    assert excinfo.value.retry_after == 7.0
