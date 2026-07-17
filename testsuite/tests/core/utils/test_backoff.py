# encoding: utf-8
""" Tests for :mod:`Cerebrum.utils.backoff`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from datetime import timedelta

import pytest

import Cerebrum.utils.backoff


@pytest.mark.parametrize(
    'step,timeout',
    [(-1, 1), (0, 1), (1, 1), (2, 2)]
)
def test_linear(step, timeout):
    get_backoff = Cerebrum.utils.backoff.Linear()
    assert get_backoff(step) == timeout


@pytest.mark.parametrize(
    'step,timeout',
    [(-1, 1), (0, 1), (1, 1), (2, 2), (3, 4)]
)
def test_exp_2(step, timeout):
    get_backoff = Cerebrum.utils.backoff.Exponential(2)
    assert get_backoff(step) == timeout


@pytest.mark.parametrize(
    'step,timeout',
    [(-1, 1), (0, 1), (1, 1), (2, 10), (3, 100)]
)
def test_exp_10(step, timeout):
    get_backoff = Cerebrum.utils.backoff.Exponential(10)
    assert get_backoff(step) == timeout


@pytest.mark.parametrize(
    'value,result',
    [(-1, -3), (0, 0), (1, 3), (2, 6)]
)
def test_factor_3(value, result):
    get_result = Cerebrum.utils.backoff.Factor(3)
    assert get_result(value) == result


@pytest.mark.parametrize(
    'value,result',
    [(-1, timedelta(hours=-1)), (0, timedelta(0)),
     (1, timedelta(hours=1)), (2, timedelta(hours=2))]
)
def test_factor_delta_1hr(value, result):
    get_result = Cerebrum.utils.backoff.Factor(timedelta(hours=1))
    assert get_result(value) == result


@pytest.mark.parametrize(
    'value,result',
    [(-1, -1), (0, 0), (3, 3), (9, 9), (10, 10), (11, 10)]
)
def test_truncate_int_10(value, result):
    get_result = Cerebrum.utils.backoff.Truncate(10)
    assert get_result(value) == result


@pytest.mark.parametrize(
    'value,result',
    [(timedelta(hours=-1), timedelta(hours=-1)),
     (timedelta(hours=0), timedelta(hours=0)),
     (timedelta(minutes=30), timedelta(minutes=30)),
     (timedelta(hours=1), timedelta(hours=1)),
     (timedelta(hours=2), timedelta(hours=1))]
)
def test_truncate_1hr(value, result):
    get_result = Cerebrum.utils.backoff.Truncate(timedelta(hours=1))
    assert get_result(value) == result


@pytest.mark.parametrize(
    'step,timeout',
    (
        (1, timedelta(seconds=225)),
        (2, timedelta(minutes=7, seconds=30)),
        (3, timedelta(minutes=15)),
        (8, timedelta(hours=8)),
        (9, timedelta(hours=12)),
        (10, timedelta(hours=12)),
    ),
)
def test_backoff(step, timeout):
    get_backoff = Cerebrum.utils.backoff.Backoff(
        Cerebrum.utils.backoff.Exponential(2),
        Cerebrum.utils.backoff.Factor(timedelta(hours=1) // 16),
        Cerebrum.utils.backoff.Truncate(timedelta(hours=12)))
    assert get_backoff(step) == timeout
