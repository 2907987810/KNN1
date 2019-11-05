from distutils.version import LooseVersion

import numpy as np
import pytest

import pandas as pd
from pandas import (
    Index,
    Interval,
    IntervalIndex,
    Timedelta,
    Timestamp,
    date_range,
    timedelta_range,
)
from pandas.core.arrays import IntervalArray
import pandas.util.testing as tm

try:
    import pyarrow

    _PYARROW_INSTALLED = True
except ImportError:
    _PYARROW_INSTALLED = False


@pytest.fixture(
    params=[
        (Index([0, 2, 4]), Index([1, 3, 5])),
        (Index([0.0, 1.0, 2.0]), Index([1.0, 2.0, 3.0])),
        (timedelta_range("0 days", periods=3), timedelta_range("1 day", periods=3)),
        (date_range("20170101", periods=3), date_range("20170102", periods=3)),
        (
            date_range("20170101", periods=3, tz="US/Eastern"),
            date_range("20170102", periods=3, tz="US/Eastern"),
        ),
    ],
    ids=lambda x: str(x[0].dtype),
)
def left_right_dtypes(request):
    """
    Fixture for building an IntervalArray from various dtypes
    """
    return request.param


class TestAttributes:
    @pytest.mark.parametrize(
        "left, right",
        [
            (0, 1),
            (Timedelta("0 days"), Timedelta("1 day")),
            (Timestamp("2018-01-01"), Timestamp("2018-01-02")),
            (
                Timestamp("2018-01-01", tz="US/Eastern"),
                Timestamp("2018-01-02", tz="US/Eastern"),
            ),
        ],
    )
    @pytest.mark.parametrize("constructor", [IntervalArray, IntervalIndex])
    def test_is_empty(self, constructor, left, right, closed):
        # GH27219
        tuples = [(left, left), (left, right), np.nan]
        expected = np.array([closed != "both", False, False])
        result = constructor.from_tuples(tuples, closed=closed).is_empty
        tm.assert_numpy_array_equal(result, expected)


class TestMethods:
    @pytest.mark.parametrize("new_closed", ["left", "right", "both", "neither"])
    def test_set_closed(self, closed, new_closed):
        # GH 21670
        array = IntervalArray.from_breaks(range(10), closed=closed)
        result = array.set_closed(new_closed)
        expected = IntervalArray.from_breaks(range(10), closed=new_closed)
        tm.assert_extension_array_equal(result, expected)

    @pytest.mark.parametrize(
        "other",
        [
            Interval(0, 1, closed="right"),
            IntervalArray.from_breaks([1, 2, 3, 4], closed="right"),
        ],
    )
    def test_where_raises(self, other):
        ser = pd.Series(IntervalArray.from_breaks([1, 2, 3, 4], closed="left"))
        match = "'value.closed' is 'right', expected 'left'."
        with pytest.raises(ValueError, match=match):
            ser.where([True, False, True], other=other)


class TestSetitem:
    def test_set_na(self, left_right_dtypes):
        left, right = left_right_dtypes
        result = IntervalArray.from_arrays(left, right)
        result[0] = np.nan

        expected_left = Index([left._na_value] + list(left[1:]))
        expected_right = Index([right._na_value] + list(right[1:]))
        expected = IntervalArray.from_arrays(expected_left, expected_right)

        tm.assert_extension_array_equal(result, expected)


def test_repr():
    # GH 25022
    arr = IntervalArray.from_tuples([(0, 1), (1, 2)])
    result = repr(arr)
    expected = (
        "<IntervalArray>\n"
        "[(0, 1], (1, 2]]\n"
        "Length: 2, closed: right, dtype: interval[int64]"
    )
    assert result == expected


# ----------------------------------------------------------------------------
# Arrow interaction


pyarrow_skip = pytest.mark.skipif(
    not _PYARROW_INSTALLED
    or _PYARROW_INSTALLED
    and LooseVersion(pyarrow.__version__) < LooseVersion("0.15.1.dev"),
    reason="pyarrow > 0.15 required",
)


@pyarrow_skip
def test_arrow_extension_type():
    import pyarrow as pa
    from pandas.core.arrays.interval import ArrowIntervalType

    p1 = ArrowIntervalType(pa.int64(), "left")
    p2 = ArrowIntervalType(pa.int64(), "left")
    p3 = ArrowIntervalType(pa.int64(), "right")

    assert p1.closed == "left"
    assert p1 == p2
    assert not p1 == p3
    assert hash(p1) == hash(p2)
    assert not hash(p1) == hash(p3)


@pyarrow_skip
def test_arrow_array():
    import pyarrow as pa
    from pandas.core.arrays.interval import ArrowIntervalType

    intervals = pd.interval_range(1, 5, freq=1).array

    result = pa.array(intervals)
    assert isinstance(result.type, ArrowIntervalType)
    assert result.type.closed == intervals.closed
    assert result.type.subtype == pa.int64()
    assert result.storage.field("left").equals(pa.array([1, 2, 3, 4], type="int64"))
    assert result.storage.field("right").equals(pa.array([2, 3, 4, 5], type="int64"))

    expected = pa.array([{"left": i, "right": i + 1} for i in range(1, 5)])
    assert result.storage.equals(expected)

    # convert to its storage type
    result = pa.array(intervals, type=expected.type)
    assert result.equals(expected)

    # unsupported conversions
    with pytest.raises(TypeError):
        pa.array(intervals, type="float64")

    with pytest.raises(TypeError, match="different 'subtype'"):
        pa.array(intervals, type=ArrowIntervalType(pa.float64(), "left"))
