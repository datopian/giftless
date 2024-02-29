"""Unit tests for auth.github module."""
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from random import shuffle
from time import sleep
from typing import Any

import giftless.auth.github as gh


def test_ensure_default_lock() -> None:
    lock_getter = gh._ensure_lock()
    lock = lock_getter(None)
    with lock:
        # Is it a RLock or just Lock?
        if lock.acquire(blocking=False):
            lock.release()


def _concurrent_side_effects(
    decorator: Callable[[Callable[..., Any]], Any], thread_cnt: int = 4
) -> tuple[list, list, list]:
    @decorator
    def decorated_method(_ignored_self: Any, index: int) -> int:
        sleep(0.1)
        side_effects[index] = index
        return index

    results: list[int | None] = [None] * thread_cnt
    side_effects: list[int | None] = [None] * thread_cnt
    exceptions: list[Exception | None] = [None] * thread_cnt

    with ThreadPoolExecutor(
        max_workers=thread_cnt, thread_name_prefix="scm-"
    ) as executor:
        thread_indices = list(range(thread_cnt))
        shuffle(thread_indices)
        futures = {
            executor.submit(decorated_method, i, i): i for i in thread_indices
        }
        for future in as_completed(futures):
            i = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                exceptions[i] = exc
            else:
                results[i] = result

    return results, side_effects, exceptions


def test_single_call_method_decorator_default_no_args() -> None:
    decorator = gh.single_call_method
    results, side_effects, exceptions = _concurrent_side_effects(decorator)
    # the differing index (taken into account by default) breaks call coupling,
    # so this decoration has no effect and all calls get through
    assert results == side_effects


def test_single_call_method_decorator_default_args() -> None:
    decorator = gh.single_call_method()
    results, side_effects, exceptions = _concurrent_side_effects(decorator)
    # same as test_single_call_method_decorator_default_no_args, but checking
    # if the decorator factory works properly with no explicit args
    assert results == side_effects


def test_single_call_method_decorator_call_first() -> None:
    # using a constant hash key to put all threads in the same bucket
    decorator = gh.single_call_method(key=lambda *args: 0)
    threads = 4
    results, side_effects, exceptions = _concurrent_side_effects(
        decorator, threads
    )
    assert all(e is None for e in exceptions)
    # as there's just a sleep in the decorated_method, technically multiple
    # threads could enter the method call (and thus produce side_effects),
    # but the expectation is the sleep is long enough for all to get stuck
    chosen_ones = [se for se in side_effects if se is not None]
    # at least one thread got stuck
    assert len(chosen_ones) < threads
    assert all(r in chosen_ones for r in results)
