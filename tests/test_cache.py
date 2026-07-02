from wca_records_analyser.cache import ttl_cached

TTL_SECONDS = 3600


class _FakeClock:
    """A hand-cranked clock so cache expiry is deterministic in tests."""

    def __init__(self):
        self._now = 0

    def __call__(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


def _recording_lookup():
    """A lookup that records every argument it is actually invoked with."""
    calls = []

    def lookup(argument):
        calls.append(argument)
        return f"value-for-{argument}"

    lookup.calls = calls
    return lookup


def test_ttl_cached_returns_the_computed_value():
    lookup = ttl_cached(TTL_SECONDS, _FakeClock())(_recording_lookup())

    assert lookup("2007VALK01") == "value-for-2007VALK01"


def test_ttl_cached_reuses_the_value_within_the_ttl():
    clock = _FakeClock()
    underlying = _recording_lookup()
    lookup = ttl_cached(TTL_SECONDS, clock)(underlying)

    lookup("2007VALK01")
    clock.advance(TTL_SECONDS - 1)
    lookup("2007VALK01")

    assert underlying.calls == ["2007VALK01"]


def test_ttl_cached_recomputes_once_the_ttl_has_elapsed():
    clock = _FakeClock()
    underlying = _recording_lookup()
    lookup = ttl_cached(TTL_SECONDS, clock)(underlying)

    lookup("2007VALK01")
    clock.advance(TTL_SECONDS)
    lookup("2007VALK01")

    assert underlying.calls == ["2007VALK01", "2007VALK01"]


def test_ttl_cached_keeps_distinct_arguments_separate():
    clock = _FakeClock()
    underlying = _recording_lookup()
    lookup = ttl_cached(TTL_SECONDS, clock)(underlying)

    lookup("2007VALK01")
    lookup("2015SHAW01")
    lookup("2007VALK01")

    assert underlying.calls == ["2007VALK01", "2015SHAW01"]
