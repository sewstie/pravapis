from __future__ import annotations

from pravapis.baseline import Metric, raised


def test_precision_metric_regresses_when_it_falls() -> None:
    assert Metric("dev_n2t_precision", recorded=0.90, measured=0.80).regressed
    assert not Metric("dev_n2t_precision", recorded=0.90, measured=0.95).regressed


def test_rate_metric_regresses_when_it_rises() -> None:
    """A `_rate` metric is a ceiling: rising is the regression, falling is the win —
    the opposite polarity from `_recall`/`_precision`."""
    assert Metric("dev_n2t_unresolved_flag_rate", recorded=0.02, measured=0.05).regressed
    assert not Metric("dev_n2t_unresolved_flag_rate", recorded=0.05, measured=0.02).regressed


def test_rate_metric_within_tolerance_does_not_regress() -> None:
    assert not Metric("dev_n2t_unresolved_flag_rate", recorded=0.02, measured=0.0205).regressed


def test_raised_keeps_the_lower_rate() -> None:
    recorded = {"dev_n2t_unresolved_flag_rate": 0.05}
    measured = {"dev_n2t_unresolved_flag_rate": 0.02}
    assert raised(recorded, measured)["dev_n2t_unresolved_flag_rate"] == 0.02


def test_raised_does_not_learn_a_worse_rate() -> None:
    recorded = {"dev_n2t_unresolved_flag_rate": 0.02}
    measured = {"dev_n2t_unresolved_flag_rate": 0.05}
    assert raised(recorded, measured)["dev_n2t_unresolved_flag_rate"] == 0.02


def test_raised_keeps_the_higher_precision() -> None:
    recorded = {"dev_n2t_unresolved_flag_precision": 0.5}
    measured = {"dev_n2t_unresolved_flag_precision": 0.6}
    assert raised(recorded, measured)["dev_n2t_unresolved_flag_precision"] == 0.6
