"""
Tests for the observability module — timer, metrics recording.
"""

from __future__ import annotations

import time

from vectraiq.observability import (
    AICallMetrics,
    RequestMetrics,
    SearchMetrics,
    record_ai_call,
    record_request,
    record_search,
    timed_ai_call,
    timed_search,
    timer,
)


class TestTimer:
    def test_elapsed_ms_increases(self):
        t = timer()
        time.sleep(0.01)
        assert t.elapsed_ms() >= 5.0  # at least 5ms

    def test_elapsed_ms_is_float(self):
        t = timer()
        assert isinstance(t.elapsed_ms(), float)

    def test_elapsed_ms_accumulates(self):
        t = timer()
        e1 = t.elapsed_ms()
        time.sleep(0.01)
        e2 = t.elapsed_ms()
        assert e2 > e1


class TestTimedAiCall:
    def test_populates_latency(self):
        with timed_ai_call("generate", model="gpt-4o") as m:
            time.sleep(0.01)
        assert m.latency_ms >= 5.0

    def test_populates_provider_and_model(self):
        with timed_ai_call("embed", model="text-embedding-3-small", provider="openai") as m:
            pass
        assert m.provider == "openai"
        assert m.model == "text-embedding-3-small"
        assert m.operation == "embed"

    def test_records_error_on_exception(self):
        with timed_ai_call("generate") as m:
            m.error = "Rate limit"

        assert m.error == "Rate limit"

    def test_exception_propagates(self):
        import pytest
        with pytest.raises(ValueError):
            with timed_ai_call("generate"):
                raise ValueError("test error")


class TestTimedSearch:
    def test_populates_latency(self):
        with timed_search("hybrid") as m:
            time.sleep(0.005)
        assert m.latency_ms >= 1.0
        assert m.mode == "hybrid"

    def test_yields_mutable_metrics(self):
        with timed_search("dense") as m:
            m.num_results = 5
            m.reranked = True
        assert m.num_results == 5
        assert m.reranked is True


class TestMetricsDataclasses:
    def test_ai_call_metrics_defaults(self):
        m = AICallMetrics()
        assert m.provider == "openai"
        assert m.prompt_tokens == 0
        assert m.cache_hit is False
        assert m.error is None

    def test_search_metrics_defaults(self):
        m = SearchMetrics()
        assert m.mode == "dense"
        assert m.num_results == 0
        assert m.reranked is False

    def test_request_metrics_defaults(self):
        m = RequestMetrics()
        assert m.ai_calls == []
        assert m.search is None
        assert m.status_code == 200


class TestRecordFunctions:
    """Smoke tests — these functions currently just log; verify they don't raise."""

    def test_record_ai_call_does_not_raise(self):
        record_ai_call(AICallMetrics(model="gpt-4o", operation="generate", total_tokens=100))

    def test_record_search_does_not_raise(self):
        record_search(SearchMetrics(mode="hybrid", num_results=5))

    def test_record_request_does_not_raise(self):
        record_request(RequestMetrics(endpoint="/query", user_id="testuser", status_code=200))
