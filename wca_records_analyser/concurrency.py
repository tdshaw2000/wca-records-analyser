"""Run independent blocking lookups concurrently."""

from concurrent.futures import ThreadPoolExecutor


def run_concurrently(callables, max_workers):
    """Call each no-arg callable on its own thread, returning results in input order."""
    calls = list(callables)
    if not calls:
        return []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(calls))) as pool:
        return list(pool.map(lambda call: call(), calls))
