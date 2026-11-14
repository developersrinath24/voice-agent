from datetime import date, timedelta

from app.services.voice_budget import CallBudget


def test_takes_calls_up_to_the_limit_and_no_further():
    budget = CallBudget(3)

    assert budget.take() is True
    assert budget.take() is True
    assert budget.remaining() == 1
    assert budget.take() is True

    assert budget.remaining() == 0
    assert budget.take() is False


def test_the_allowance_returns_at_the_day_boundary():
    # Reaching into the clock fields is the point: the alternative is waiting
    # until midnight to test the only behaviour that matters here.
    budget = CallBudget(1)
    assert budget.take() is True

    budget._day = date.today() - timedelta(days=1)
    assert budget.remaining() == 1
    assert budget.take() is True
    assert budget.remaining() == 0
    assert budget._day == date.today()


def test_zero_limit_means_voice_is_off():
    budget = CallBudget(0)
    assert budget.remaining() == 0
    assert budget.take() is False
