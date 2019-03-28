# -*- coding: utf-8 -*-
"""Tests for functions from pandas._libs.tslibs"""

from datetime import date, datetime

import pytest

from pandas._libs import tslibs

from pandas import Timestamp


@pytest.mark.parametrize("value,expected", [
    (date(2012, 9, 7), datetime(2012, 9, 7)),
    (datetime(2012, 9, 7, 12), datetime(2012, 9, 7)),
    (datetime(2007, 10, 1, 1, 12, 5, 10), datetime(2007, 10, 1))
])
def test_normalize_date(value, expected):
    result = tslibs.normalize_date(value)
    assert result == expected


class SubDatetime(datetime):
    pass


@pytest.mark.parametrize("dt, expected", [
    pytest.param(Timestamp(2000, 1, 1, 1),
                 Timestamp(2000, 1, 1, 0)),
    pytest.param(datetime(2000, 1, 1, 1),
                 datetime(2000, 1, 1, 0)),
    pytest.param(SubDatetime(2000, 1, 1, 1),
                 SubDatetime(2000, 1, 1, 0))])
def test_normalize_date_sub_types(dt, expected):
    # GH 25851
    # ensure that subclassed datetime works with
    # normalize_date
    result = tslibs.normalize_date(dt)
    assert result == expected
