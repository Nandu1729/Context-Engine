"""The copyable rolling-summary example runs offline and actually uses its summary."""

import pytest

from context_engine.tokens import TiktokenCounter
from examples import rolling_summary as example
from scripts.incident_demo import offline_network


@pytest.fixture(autouse=True)
def cached_offline():
    TiktokenCounter()  # Public vocabulary initialization, before socket denial.
    with offline_network():
        yield


def test_summary_is_used_once_history_outgrows_the_window():
    reasons = example.run(40)
    assert reasons[0] == "no_old_history"
    assert "summary_reused_prefix" in reasons or "summary_reused" in reasons
    # Once created, the summary keeps applying as WINDOW slides forward.
    first = next(i for i, r in enumerate(reasons) if r.startswith("summary_reused"))
    assert all(r.startswith("summary_reused") for r in reasons[first:])


def test_main_prints_summary(capsys):
    assert example.main() == 0
    assert "summary used on" in capsys.readouterr().out
