import threading

from wca_records_analyser.concurrency import run_concurrently

WORKER_COUNT = 4
BARRIER_TIMEOUT_SECONDS = 2


def test_run_concurrently_returns_results_in_input_order():
    results = run_concurrently([lambda: 1, lambda: 2, lambda: 3], max_workers=3)

    assert results == [1, 2, 3]


def test_run_concurrently_runs_the_callables_in_parallel():
    # Every task waits on a barrier sized to the whole batch, so it only releases
    # if all tasks are running at once; sequential execution would time out here.
    barrier = threading.Barrier(WORKER_COUNT, timeout=BARRIER_TIMEOUT_SECONDS)

    def task_returning(value):
        def task():
            barrier.wait()
            return value

        return task

    results = run_concurrently(
        [task_returning(value) for value in range(WORKER_COUNT)],
        max_workers=WORKER_COUNT,
    )

    assert sorted(results) == list(range(WORKER_COUNT))


def test_run_concurrently_with_no_callables_returns_an_empty_list():
    assert run_concurrently([], max_workers=3) == []
