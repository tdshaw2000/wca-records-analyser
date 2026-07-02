"""A small time-to-live cache for memoising expensive lookups."""


def ttl_cached(ttl_seconds, clock):
    """Memoise a function's result per argument for ``ttl_seconds``.

    ``clock`` is a no-argument callable returning the current time in seconds; it
    is injected so expiry can be driven deterministically in tests. A cached value
    is reused while the clock reads before its expiry, and recomputed once reached.
    """

    def decorate(function):
        expiry_and_value_by_arguments = {}

        def cached(*arguments):
            now = clock()
            cached_entry = expiry_and_value_by_arguments.get(arguments)
            if cached_entry is not None and now < cached_entry[0]:
                return cached_entry[1]
            value = function(*arguments)
            expiry_and_value_by_arguments[arguments] = (now + ttl_seconds, value)
            return value

        return cached

    return decorate
