# -*- coding: utf-8 -*-
from datetime import timedelta

import numpy as np

from pandas._libs import tslibs, lib, algos
from pandas._libs.tslibs import Timedelta, Timestamp, NaT
from pandas._libs.tslibs.fields import get_timedelta_field
from pandas._libs.tslibs.timedeltas import array_to_timedelta64

from pandas import compat

from pandas.core.dtypes.common import (
    _TD_DTYPE, is_list_like, is_object_dtype, is_timedelta64_dtype)
from pandas.core.dtypes.generic import ABCSeries
from pandas.core.dtypes.missing import isna

import pandas.core.common as com
from pandas.core.algorithms import checked_add_with_arr

from pandas.tseries.offsets import Tick

from . import datetimelike as dtl


def _to_m8(key):
    """
    Timedelta-like => dt64
    """
    if not isinstance(key, Timedelta):
        # this also converts strings
        key = Timedelta(key)

    # return an type that can be compared
    return np.int64(key.value).view(_TD_DTYPE)


def _is_convertible_to_td(key):
    return isinstance(key, (Tick, timedelta,
                            np.timedelta64, compat.string_types))


def _field_accessor(name, alias, docstring=None):
    def f(self):
        values = self.asi8
        result = get_timedelta_field(values, alias)
        if self.hasnans:
            result = self._maybe_mask_results(result, fill_value=None,
                                              convert='float64')

        return result

    f.__name__ = name
    f.__doc__ = docstring
    return property(f)


def _td_array_cmp(cls, op):
    """
    Wrap comparison operations to convert timedelta-like to timedelta64
    """
    opname = '__{name}__'.format(name=op.__name__)
    nat_result = True if opname == '__ne__' else False

    def wrapper(self, other):
        msg = "cannot compare a {cls} with type {typ}"
        meth = getattr(dtl.DatetimeLikeArrayMixin, opname)
        if _is_convertible_to_td(other) or other is NaT:
            try:
                other = _to_m8(other)
            except ValueError:
                # failed to parse as timedelta
                raise TypeError(msg.format(cls=type(self).__name__,
                                           typ=type(other).__name__))
            result = meth(self, other)
            if isna(other):
                result.fill(nat_result)

        elif not is_list_like(other):
            raise TypeError(msg.format(cls=type(self).__name__,
                                       typ=type(other).__name__))
        else:
            other = type(self)(other).values
            result = meth(self, other)
            result = com.values_from_object(result)

            o_mask = np.array(isna(other))
            if o_mask.any():
                result[o_mask] = nat_result

        if self.hasnans:
            result[self._isnan] = nat_result

        return result

    return compat.set_function_name(wrapper, opname, cls)


class TimedeltaArrayMixin(dtl.DatetimeLikeArrayMixin):
    @property
    def _box_func(self):
        return lambda x: Timedelta(x, unit='ns')

    @property
    def dtype(self):
        return _TD_DTYPE

    # ----------------------------------------------------------------
    # Constructors
    _attributes = ["freq"]

    @classmethod
    def _simple_new(cls, values, freq=None, dtype=_TD_DTYPE):
        _require_m8ns_dtype(dtype)
        assert isinstance(values, np.ndarray), type(values)

        if values.dtype == 'i8':
            values = values.view('m8[ns]')

        assert values.dtype == 'm8[ns]'

        result = object.__new__(cls)
        result._data = values
        result._freq = freq
        return result

    def __new__(cls, values, freq=None, dtype=_TD_DTYPE, copy=False):
        _require_m8ns_dtype(dtype)

        if isinstance(values, (list, tuple)) or is_object_dtype(values):
            values = cls._from_sequence(values, copy=copy)._data
            # TODO: can we set copy=False to avoid re-copying?

        freq, freq_infer = dtl.maybe_infer_freq(freq)

        if lib.is_scalar(values):
            raise TypeError(dtl.scalar_data_error(values, cls))
        elif isinstance(values, TimedeltaArrayMixin):
            if freq is None and values.freq is not None:
                freq = values.freq
                freq_infer = False
            values = values._data

        values = np.array(values, copy=copy)

        if values.dtype == 'i8':
            pass
        elif not is_timedelta64_dtype(values):
            raise TypeError(values.dtype)
        elif values.dtype != _TD_DTYPE:
            # i.e. non-nano unit
            # TODO: use tslibs.conversion func? watch out for overflows
            values = values.astype(_TD_DTYPE)

        result = cls._simple_new(values, freq=freq)
        dtl.maybe_define_freq(freq_infer, result)
        return result

    @classmethod
    def _from_sequence(cls, scalars, dtype=_TD_DTYPE, copy=False):
        # list, tuple, or object-dtype ndarray/Index
        values = np.array(scalars, dtype=np.object_, copy=copy)
        if values.ndim != 1:
            raise TypeError("Values must be 1-dimensional")

        result = array_to_timedelta64(values)
        return cls(result, dtype=dtype)

    @classmethod
    def _generate_range(cls, start, end, periods, freq, closed=None):

        periods = dtl.validate_periods(periods)
        if freq is None and any(x is None for x in [periods, start, end]):
            raise ValueError('Must provide freq argument if no data is '
                             'supplied')

        if com.count_not_none(start, end, periods, freq) != 3:
            raise ValueError('Of the four parameters: start, end, periods, '
                             'and freq, exactly three must be specified')

        if start is not None:
            start = Timedelta(start)

        if end is not None:
            end = Timedelta(end)

        if start is None and end is None:
            if closed is not None:
                raise ValueError("Closed has to be None if not both of start"
                                 "and end are defined")

        left_closed, right_closed = dtl.validate_endpoints(closed)

        if freq is not None:
            index = _generate_regular_range(start, end, periods, freq)
        else:
            index = np.linspace(start.value, end.value, periods).astype('i8')

        if not left_closed:
            index = index[1:]
        if not right_closed:
            index = index[:-1]

        return cls._simple_new(index, freq=freq)

    # ----------------------------------------------------------------
    # Array-Like Methods
    # NB: these are appreciably less efficient than the TimedeltaIndex versions

    @property
    def is_monotonic_increasing(self):
        return algos.is_monotonic(self.asi8, timelike=True)[0]

    @property
    def is_monotonic_decreasing(self):
        return algos.is_monotonic(self.asi8, timelike=True)[1]

    @property
    def is_unique(self):
        from pandas.core.algorithms import unique1d
        return len(unique1d(self.asi8)) == len(self)

    # ----------------------------------------------------------------
    # Arithmetic Methods

    _create_comparison_method = classmethod(_td_array_cmp)

    def _add_offset(self, other):
        assert not isinstance(other, Tick)
        raise TypeError("cannot add the type {typ} to a {cls}"
                        .format(typ=type(other).__name__,
                                cls=type(self).__name__))

    def _add_delta(self, delta):
        """
        Add a timedelta-like, Tick, or TimedeltaIndex-like object
        to self, yielding a new TimedeltaArray

        Parameters
        ----------
        other : {timedelta, np.timedelta64, Tick,
                 TimedeltaIndex, ndarray[timedelta64]}

        Returns
        -------
        result : TimedeltaArray
        """
        new_values = dtl.DatetimeLikeArrayMixin._add_delta(self, delta)
        return type(self)(new_values, freq='infer')

    def _add_datetime_arraylike(self, other):
        """Add DatetimeArray/Index or ndarray[datetime64] to TimedeltaArray"""
        if isinstance(other, np.ndarray):
            # At this point we have already checked that dtype is datetime64
            from pandas.core.arrays import DatetimeArrayMixin
            other = DatetimeArrayMixin(other)

        # defer to implementation in DatetimeArray
        return other + self

    def _add_datetimelike_scalar(self, other):
        # adding a timedeltaindex to a datetimelike
        from pandas.core.arrays import DatetimeArrayMixin

        assert other is not NaT
        other = Timestamp(other)
        if other is NaT:
            # In this case we specifically interpret NaT as a datetime, not
            # the timedelta interpretation we would get by returning self + NaT
            result = self.asi8.view('m8[ms]') + NaT.to_datetime64()
            return DatetimeArrayMixin(result)

        i8 = self.asi8
        result = checked_add_with_arr(i8, other.value,
                                      arr_mask=self._isnan)
        result = self._maybe_mask_results(result)
        return DatetimeArrayMixin(result, tz=other.tz)

    def _addsub_offset_array(self, other, op):
        # Add or subtract Array-like of DateOffset objects
        try:
            # TimedeltaIndex can only operate with a subset of DateOffset
            # subclasses.  Incompatible classes will raise AttributeError,
            # which we re-raise as TypeError
            return dtl.DatetimeLikeArrayMixin._addsub_offset_array(self, other,
                                                                   op)
        except AttributeError:
            raise TypeError("Cannot add/subtract non-tick DateOffset to {cls}"
                            .format(cls=type(self).__name__))

    def _evaluate_with_timedelta_like(self, other, op):
        if isinstance(other, ABCSeries):
            # GH#19042
            return NotImplemented

        opstr = '__{opname}__'.format(opname=op.__name__).replace('__r', '__')
        # allow division by a timedelta
        if opstr in ['__div__', '__truediv__', '__floordiv__']:
            if _is_convertible_to_td(other):
                other = Timedelta(other)
                if isna(other):
                    raise NotImplementedError(
                        "division by pd.NaT not implemented")

                i8 = self.asi8
                left, right = i8, other.value

                if opstr in ['__floordiv__']:
                    result = op(left, right)
                else:
                    result = op(left, np.float64(right))
                result = self._maybe_mask_results(result, fill_value=None,
                                                  convert='float64')
                return result

        return NotImplemented

    # ----------------------------------------------------------------
    # Conversion Methods - Vectorized analogues of Timedelta methods

    def total_seconds(self):
        """
        Return total duration of each element expressed in seconds.

        This method is available directly on TimedeltaArray, TimedeltaIndex
        and on Series containing timedelta values under the ``.dt`` namespace.

        Returns
        -------
        seconds : [ndarray, Float64Index, Series]
            When the calling object is a TimedeltaArray, the return type
            is ndarray.  When the calling object is a TimedeltaIndex,
            the return type is a Float64Index. When the calling object
            is a Series, the return type is Series of type `float64` whose
            index is the same as the original.

        See Also
        --------
        datetime.timedelta.total_seconds : Standard library version
            of this method.
        TimedeltaIndex.components : Return a DataFrame with components of
            each Timedelta.

        Examples
        --------
        **Series**

        >>> s = pd.Series(pd.to_timedelta(np.arange(5), unit='d'))
        >>> s
        0   0 days
        1   1 days
        2   2 days
        3   3 days
        4   4 days
        dtype: timedelta64[ns]

        >>> s.dt.total_seconds()
        0         0.0
        1     86400.0
        2    172800.0
        3    259200.0
        4    345600.0
        dtype: float64

        **TimedeltaIndex**

        >>> idx = pd.to_timedelta(np.arange(5), unit='d')
        >>> idx
        TimedeltaIndex(['0 days', '1 days', '2 days', '3 days', '4 days'],
                       dtype='timedelta64[ns]', freq=None)

        >>> idx.total_seconds()
        Float64Index([0.0, 86400.0, 172800.0, 259200.00000000003, 345600.0],
                     dtype='float64')
        """
        return self._maybe_mask_results(1e-9 * self.asi8, fill_value=None)

    def to_pytimedelta(self):
        """
        Return Timedelta Array/Index as object ndarray of datetime.timedelta
        objects

        Returns
        -------
        datetimes : ndarray
        """
        return tslibs.ints_to_pytimedelta(self.asi8)

    days = _field_accessor("days", "days",
                           " Number of days for each element. ")
    seconds = _field_accessor("seconds", "seconds",
                              " Number of seconds (>= 0 and less than 1 day) "
                              "for each element. ")
    microseconds = _field_accessor("microseconds", "microseconds",
                                   "\nNumber of microseconds (>= 0 and less "
                                   "than 1 second) for each\nelement. ")
    nanoseconds = _field_accessor("nanoseconds", "nanoseconds",
                                  "\nNumber of nanoseconds (>= 0 and less "
                                  "than 1 microsecond) for each\nelement.\n")

    @property
    def components(self):
        """
        Return a dataframe of the components (days, hours, minutes,
        seconds, milliseconds, microseconds, nanoseconds) of the Timedeltas.

        Returns
        -------
        a DataFrame
        """
        from pandas import DataFrame

        columns = ['days', 'hours', 'minutes', 'seconds',
                   'milliseconds', 'microseconds', 'nanoseconds']
        hasnans = self.hasnans
        if hasnans:
            def f(x):
                if isna(x):
                    return [np.nan] * len(columns)
                return x.components
        else:
            def f(x):
                return x.components

        result = DataFrame([f(x) for x in self], columns=columns)
        if not hasnans:
            result = result.astype('int64')
        return result


TimedeltaArrayMixin._add_comparison_ops()
TimedeltaArrayMixin._add_datetimelike_methods()


# ---------------------------------------------------------------------
# Constructor Helpers

def _generate_regular_range(start, end, periods, offset):
    stride = offset.nanos
    if periods is None:
        b = Timedelta(start).value
        e = Timedelta(end).value
        e += stride - e % stride
    elif start is not None:
        b = Timedelta(start).value
        e = b + periods * stride
    elif end is not None:
        e = Timedelta(end).value + stride
        b = e - periods * stride
    else:
        raise ValueError("at least 'start' or 'end' should be specified "
                         "if a 'period' is given.")

    data = np.arange(b, e, stride, dtype=np.int64)
    return data


def _require_m8ns_dtype(dtype):
    """
    `dtype` is included in the constructor signature for consistency with
    DatetimeArray and PeriodArray, but only timedelta64[ns] is considered
    valid.  Raise if anything else is passed.

    Parameters
    ----------
    dtype : dtype

    Raises
    ------
    ValueError
    """
    if dtype != _TD_DTYPE:
        raise ValueError("Only timedelta64[ns] dtype is valid.", dtype)
