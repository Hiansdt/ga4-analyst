from ga4_agent.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_the_limit_within_the_window():
    limiter = RateLimiter(limit=2, window_s=60, clock=FakeClock())

    assert [limiter.allow("a") for _ in range(3)] == [True, True, False]


def test_clients_have_separate_budgets():
    limiter = RateLimiter(limit=1, window_s=60, clock=FakeClock())

    assert limiter.allow("a")
    assert limiter.allow("b")
    assert not limiter.allow("a")


def test_budget_comes_back_after_the_window():
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window_s=60, clock=clock)
    limiter.allow("a")

    clock.now = 60.1

    assert limiter.allow("a")


def test_forgets_clients_whose_window_has_passed():
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window_s=60, clock=clock)
    limiter.allow("a")

    clock.now = 61
    limiter.allow("b")

    assert limiter.tracked_clients() == 1
