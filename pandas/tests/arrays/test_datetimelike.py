# -*- coding: utf-8 -*-
import numpy as np
import pytest

import pandas as pd
import pandas.util.testing as tm
from pandas.core.arrays import (
    DatetimeArray, PeriodArray, TimedeltaArrayMixin
)


# TODO: more freq variants
@pytest.fixture(params=['D', 'B', 'W', 'M', 'Q', 'Y'])
def period_index(request):
    """
    A fixture to provide PeriodIndex objects with different frequencies.

    Most PeriodArray behavior is already tested in PeriodIndex tests,
    so here we just test that the PeriodArray behavior matches
    the PeriodIndex behavior.
    """
    freqstr = request.param
    # TODO: non-monotone indexes; NaTs, different start dates
    pi = pd.period_range(start=pd.Timestamp('2000-01-01'),
                         periods=100,
                         freq=freqstr)
    return pi


@pytest.fixture(params=['D', 'B', 'W', 'M', 'Q', 'Y'])
def datetime_index(request):
    """
    A fixture to provide DatetimeIndex objects with different frequencies.

    Most DatetimeArray behavior is already tested in DatetimeIndex tests,
    so here we just test that the DatetimeArray behavior matches
    the DatetimeIndex behavior.
    """
    freqstr = request.param
    # TODO: non-monotone indexes; NaTs, different start dates, timezones
    pi = pd.date_range(start=pd.Timestamp('2000-01-01'),
                       periods=100,
                       freq=freqstr)
    return pi


@pytest.fixture
def timedelta_index(request):
    """
    A fixture to provide TimedeltaIndex objects with different frequencies.
     Most TimedeltaArray behavior is already tested in TimedeltaIndex tests,
    so here we just test that the TimedeltaArray behavior matches
    the TimedeltaIndex behavior.
    """
    # TODO: flesh this out
    return pd.TimedeltaIndex(['1 Day', '3 Hours', 'NaT'])


def index_to_array(index):
    """
    Helper function to construct a Datetime/Timedelta/Period Array from an
    instance of the corresponding Index subclass.
    """
    if isinstance(index, pd.DatetimeIndex):
        return DatetimeArray(index)
    elif isinstance(index, pd.TimedeltaIndex):
        return TimedeltaArrayMixin(index)
    elif isinstance(index, pd.PeriodIndex):
        return PeriodArray(index)
    else:
        raise TypeError(type(index))


class SharedTests(object):
    index_cls = None

    def test_take(self):
        data = np.arange(100, dtype='i8')
        np.random.shuffle(data)

        idx = self.index_cls._simple_new(data, freq='D')
        arr = index_to_array(idx)

        takers = [1, 4, 94]
        result = arr.take(takers)
        expected = idx.take(takers)

        tm.assert_index_equal(self.index_cls(result), expected)

        takers = np.array([1, 4, 94])
        result = arr.take(takers)
        expected = idx.take(takers)

        tm.assert_index_equal(self.index_cls(result), expected)

    def test_take_fill(self):
        data = np.arange(10, dtype='i8')

        idx = self.index_cls._simple_new(data, freq='D')
        arr = index_to_array(idx)

        result = arr.take([-1, 1], allow_fill=True, fill_value=None)
        assert result[0] is pd.NaT

        result = arr.take([-1, 1], allow_fill=True, fill_value=np.nan)
        assert result[0] is pd.NaT

        result = arr.take([-1, 1], allow_fill=True, fill_value=pd.NaT)
        assert result[0] is pd.NaT

        with pytest.raises(ValueError):
            arr.take([0, 1], allow_fill=True, fill_value=2)

        with pytest.raises(ValueError):
            arr.take([0, 1], allow_fill=True, fill_value=2.0)

        with pytest.raises(ValueError):
            arr.take([0, 1], allow_fill=True,
                     fill_value=pd.Timestamp.now().time)

    def test_concat_same_type(self):
        data = np.arange(10, dtype='i8')

        idx = self.index_cls._simple_new(data, freq='D').insert(0, pd.NaT)
        arr = index_to_array(idx)

        result = arr._concat_same_type([arr[:-1], arr[1:], arr])
        expected = idx._concat_same_dtype([idx[:-1], idx[1:], idx], None)

        tm.assert_index_equal(self.index_cls(result), expected)


class TestDatetimeArray(object):
    index_cls = pd.DatetimeIndex

    def test_from_dti(self, tz_naive_fixture):
        tz = tz_naive_fixture
        dti = pd.date_range('2016-01-01', periods=3, tz=tz)
        arr = DatetimeArray(dti)
        assert list(dti) == list(arr)

        # Check that Index.__new__ knows what to do with DatetimeArray
        dti2 = pd.Index(arr)
        assert isinstance(dti2, pd.DatetimeIndex)
        assert list(dti2) == list(arr)

    def test_astype_object(self, tz_naive_fixture):
        tz = tz_naive_fixture
        dti = pd.date_range('2016-01-01', periods=3, tz=tz)
        arr = DatetimeArray(dti)
        asobj = arr.astype('O')
        assert isinstance(asobj, np.ndarray)
        assert asobj.dtype == 'O'
        assert list(asobj) == list(dti)

    @pytest.mark.parametrize('freqstr', ['D', 'B', 'W', 'M', 'Q', 'Y'])
    def test_to_perioddelta(self, datetime_index, freqstr):
        # GH#23113
        dti = datetime_index
        arr = DatetimeArray(dti)

        expected = dti.to_perioddelta(freq=freqstr)
        result = arr.to_perioddelta(freq=freqstr)
        assert isinstance(result, TimedeltaArrayMixin)

        # placeholder until these become actual EA subclasses and we can use
        #  an EA-specific tm.assert_ function
        tm.assert_index_equal(pd.Index(result), pd.Index(expected))

    @pytest.mark.parametrize('freqstr', ['D', 'B', 'W', 'M', 'Q', 'Y'])
    def test_to_period(self, datetime_index, freqstr):
        dti = datetime_index
        arr = DatetimeArray(dti)

        expected = dti.to_period(freq=freqstr)
        result = arr.to_period(freq=freqstr)
        assert isinstance(result, PeriodArray)

        # placeholder until these become actual EA subclasses and we can use
        #  an EA-specific tm.assert_ function
        tm.assert_index_equal(pd.Index(result), pd.Index(expected))

    @pytest.mark.parametrize('propname', pd.DatetimeIndex._bool_ops)
    def test_bool_properties(self, datetime_index, propname):
        # in this case _bool_ops is just `is_leap_year`
        dti = datetime_index
        arr = DatetimeArray(dti)
        assert dti.freq == arr.freq

        result = getattr(arr, propname)
        expected = np.array(getattr(dti, propname), dtype=result.dtype)

        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize('propname', pd.DatetimeIndex._field_ops)
    def test_int_properties(self, datetime_index, propname):
        dti = datetime_index
        arr = DatetimeArray(dti)

        result = getattr(arr, propname)
        expected = np.array(getattr(dti, propname), dtype=result.dtype)

        tm.assert_numpy_array_equal(result, expected)

    def test_take_fill_valid(self, datetime_index, tz_naive_fixture):
        dti = datetime_index.tz_localize(tz_naive_fixture)
        arr = index_to_array(dti)

        now = pd.Timestamp.now().tz_localize(dti.tz)
        result = arr.take([-1, 1], allow_fill=True, fill_value=now)
        assert result[0] == now

        with pytest.raises(ValueError):
            # fill_value Timedelta invalid
            arr.take([-1, 1], allow_fill=True, fill_value=now - now)

        with pytest.raises(ValueError):
            # fill_value Period invalid
            arr.take([-1, 1], allow_fill=True, fill_value=pd.Period('2014Q1'))

        tz = None if dti.tz is not None else 'US/Eastern'
        now = pd.Timestamp.now().tz_localize(tz)
        with pytest.raises(TypeError):
            # Timestamp with mismatched tz-awareness
            arr.take([-1, 1], allow_fill=True, fill_value=now)

    def test_concat_same_type_invalid(self, datetime_index):
        # different timezones
        dti = datetime_index
        arr = DatetimeArray(dti)

        if arr.tz is None:
            other = arr.tz_localize('UTC')
        else:
            other = arr.tz_localize(None)

        with pytest.raises(AssertionError):
            arr._concat_same_type([arr, other])


class TestTimedeltaArray(object):
    index_cls = pd.TimedeltaIndex

    def test_from_tdi(self):
        tdi = pd.TimedeltaIndex(['1 Day', '3 Hours'])
        arr = TimedeltaArrayMixin(tdi)
        assert list(arr) == list(tdi)

        # Check that Index.__new__ knows what to do with TimedeltaArray
        tdi2 = pd.Index(arr)
        assert isinstance(tdi2, pd.TimedeltaIndex)
        assert list(tdi2) == list(arr)

    def test_astype_object(self):
        tdi = pd.TimedeltaIndex(['1 Day', '3 Hours'])
        arr = TimedeltaArrayMixin(tdi)
        asobj = arr.astype('O')
        assert isinstance(asobj, np.ndarray)
        assert asobj.dtype == 'O'
        assert list(asobj) == list(tdi)

    def test_to_pytimedelta(self, timedelta_index):
        tdi = timedelta_index
        arr = TimedeltaArrayMixin(tdi)

        expected = tdi.to_pytimedelta()
        result = arr.to_pytimedelta()

        tm.assert_numpy_array_equal(result, expected)

    def test_total_seconds(self, timedelta_index):
        tdi = timedelta_index
        arr = TimedeltaArrayMixin(tdi)

        expected = tdi.total_seconds()
        result = arr.total_seconds()

        tm.assert_numpy_array_equal(result, expected.values)

    @pytest.mark.parametrize('propname', pd.TimedeltaIndex._field_ops)
    def test_int_properties(self, timedelta_index, propname):
        tdi = timedelta_index
        arr = TimedeltaArrayMixin(tdi)

        result = getattr(arr, propname)
        expected = np.array(getattr(tdi, propname), dtype=result.dtype)

        tm.assert_numpy_array_equal(result, expected)

    def test_take_fill_valid(self, timedelta_index):
        tdi = timedelta_index
        arr = index_to_array(tdi)

        td1 = pd.Timedelta(days=1)
        result = arr.take([-1, 1], allow_fill=True, fill_value=td1)
        assert result[0] == td1

        now = pd.Timestamp.now()
        with pytest.raises(ValueError):
            # fill_value Timestamp invalid
            arr.take([0, 1], allow_fill=True, fill_value=now)

        with pytest.raises(ValueError):
            # fill_value Period invalid
            arr.take([0, 1], allow_fill=True, fill_value=now.to_period('D'))

    def test_concat_same_type_invalid(self, timedelta_index):
        # different freqs
        tdi = timedelta_index
        arr = TimedeltaArrayMixin(tdi)
        other = pd.timedelta_range('1D', periods=5, freq='2D')
        # FIXME: TimedeltaArray should inherit freq='2D' without specifying it
        other = TimedeltaArrayMixin(other, freq='2D')
        assert other.freq != arr.freq

        with pytest.raises(AssertionError):
            arr._concat_same_type([arr, other])


class TestPeriodArray(object):
    index_cls = pd.PeriodIndex

    def test_from_pi(self, period_index):
        pi = period_index
        arr = PeriodArray(pi)
        assert list(arr) == list(pi)

        # Check that Index.__new__ knows what to do with PeriodArray
        pi2 = pd.Index(arr)
        assert isinstance(pi2, pd.PeriodIndex)
        assert list(pi2) == list(arr)

    def test_astype_object(self, period_index):
        pi = period_index
        arr = PeriodArray(pi)
        asobj = arr.astype('O')
        assert isinstance(asobj, np.ndarray)
        assert asobj.dtype == 'O'
        assert list(asobj) == list(pi)

    @pytest.mark.parametrize('how', ['S', 'E'])
    def test_to_timestamp(self, how, period_index):
        pi = period_index
        arr = PeriodArray(pi)

        expected = DatetimeArray(pi.to_timestamp(how=how))
        result = arr.to_timestamp(how=how)
        assert isinstance(result, DatetimeArray)

        # placeholder until these become actual EA subclasses and we can use
        #  an EA-specific tm.assert_ function
        tm.assert_index_equal(pd.Index(result), pd.Index(expected))

    @pytest.mark.parametrize('propname', PeriodArray._bool_ops)
    def test_bool_properties(self, period_index, propname):
        # in this case _bool_ops is just `is_leap_year`
        pi = period_index
        arr = PeriodArray(pi)

        result = getattr(arr, propname)
        expected = np.array(getattr(pi, propname))

        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize('propname', PeriodArray._field_ops)
    def test_int_properties(self, period_index, propname):
        pi = period_index
        arr = PeriodArray(pi)

        result = getattr(arr, propname)
        expected = np.array(getattr(pi, propname))

        tm.assert_numpy_array_equal(result, expected)
