"""Unit tests for the startup wait-for-dependency retry logic.

Covers the shared ``retry_with_backoff`` helper plus its use in
``ESKeywordSearch.setup`` (via a fake ``elasticsearch`` module, so no live
cluster is needed). All sleeps are stubbed, so the tests run instantly.
"""

import sys
import types

import pytest

from src.utils.helpers import retry_with_backoff


class _Flaky:
    """Callable that raises ``exc`` for the first ``fail_times`` calls."""

    def __init__(self, fail_times: int, exc: Exception, result: str = "ok"):
        self.fail_times = fail_times
        self.exc = exc
        self.result = result
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc
        return self.result


class TestRetryWithBackoff:
    def test_returns_immediately_on_success(self):
        func = _Flaky(fail_times=0, exc=ConnectionError())
        slept: list[float] = []
        out = retry_with_backoff(func, retry_on=(ConnectionError,), sleep=slept.append)
        assert out == "ok"
        assert func.calls == 1
        assert slept == []  # never waited

    def test_retries_then_succeeds(self):
        func = _Flaky(fail_times=3, exc=ConnectionError("nope"))
        slept: list[float] = []
        out = retry_with_backoff(
            func,
            retry_on=(ConnectionError,),
            base_delay=1.0,
            max_delay=5.0,
            sleep=slept.append,
        )
        assert out == "ok"
        assert func.calls == 4
        # Exponential backoff, capped at max_delay: 1, 2, 4.
        assert slept == [1.0, 2.0, 4.0]

    def test_raises_after_max_attempts(self):
        func = _Flaky(fail_times=99, exc=ConnectionError("down"))
        with pytest.raises(ConnectionError, match="down"):
            retry_with_backoff(
                func,
                retry_on=(ConnectionError,),
                max_attempts=3,
                sleep=lambda _d: None,
            )
        assert func.calls == 3  # exactly max_attempts, no extra

    def test_does_not_catch_other_exceptions(self):
        def boom() -> str:
            raise ValueError("unexpected")

        with pytest.raises(ValueError, match="unexpected"):
            retry_with_backoff(boom, retry_on=(ConnectionError,), sleep=lambda _d: None)


class _FakeIndices:
    def __init__(self):
        self.created = False

    def exists(self, index):
        return False

    def create(self, index, settings, mappings):
        self.created = True


class _FakeESClient:
    """Fake elasticsearch.Elasticsearch: fails ping until ``ready_after`` tries."""

    _attempts = 0
    ready_after = 0

    def __init__(self, *args, **kwargs):
        self.indices = _FakeIndices()

    def ping(self):
        type(self)._attempts += 1
        return type(self)._attempts > type(self).ready_after


@pytest.fixture
def fake_elasticsearch(monkeypatch):
    """Inject a fake ``elasticsearch`` module so setup() needs no real cluster."""
    _FakeESClient._attempts = 0
    module = types.ModuleType("elasticsearch")
    module.Elasticsearch = _FakeESClient
    monkeypatch.setitem(sys.modules, "elasticsearch", module)
    return _FakeESClient


class TestESKeywordSearchSetupRetry:
    def test_setup_waits_for_cluster(self, fake_elasticsearch):
        fake_elasticsearch.ready_after = 2  # unreachable for the first 2 pings

        from src.retrieval.es_keyword_search import ESKeywordSearch

        es = ESKeywordSearch(url="http://elasticsearch:9200")
        es.setup(base_delay=0.0)  # base_delay=0 -> retries with no real delay

        assert es.client is not None
        assert es.client.indices.created is True

    def test_setup_raises_after_exhausting_attempts(self, fake_elasticsearch):
        fake_elasticsearch.ready_after = 999  # never reachable

        from src.retrieval.es_keyword_search import ESKeywordSearch

        es = ESKeywordSearch(url="http://elasticsearch:9200")
        with pytest.raises(ConnectionError, match="not reachable"):
            es.setup(max_attempts=3, base_delay=0.0)
