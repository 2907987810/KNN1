from datetime import timedelta
import numpy as np
import warnings

import pandas as pd
from pandas.core.base import AbstractMethodError

from pandas.core.groupby import (BinGrouper, Grouper, _GroupBy, GroupBy,
                                 SeriesGroupBy, groupby, PanelGroupBy)

from pandas.tseries.frequencies import to_offset, is_subperiod, is_superperiod
from pandas.tseries.index import DatetimeIndex, date_range
from pandas.tseries.tdi import TimedeltaIndex
from pandas.tseries.offsets import DateOffset, Tick, Day, _delta_to_nanoseconds
from pandas.tseries.period import PeriodIndex, period_range
import pandas.core.common as com
import pandas.compat as compat

from pandas.lib import Timestamp
import pandas.lib as lib
import pandas.tslib as tslib


class Resampler(_GroupBy):

    # to the groupby descriptor
    _attributes = ['freq', 'axis', 'closed', 'label', 'convention',
                   'loffset', 'base', 'kind']

    # API compat of allowed attributes
    _deprecated_valids = _attributes + ['_ipython_display_', '__doc__',
                                        '_cache', '_attributes', 'binner',
                                        'grouper', 'groupby', 'keys',
                                        'sort', 'kind', 'squeeze',
                                        'group_keys', 'as_index',
                                        'exclusions']

    # API compat of disallowed attributes
    _deprecated_invalids = ['iloc', 'loc', 'ix']

    def __init__(self, obj, groupby, axis=0, kind=None, **kwargs):
        self.groupby = groupby
        self.keys = None
        self.sort = True
        self.axis = axis
        self.kind = kind
        self.squeeze = False
        self.group_keys = True
        self.as_index = True
        self.exclusions = set()

        self.groupby._set_grouper(self._convert_obj(obj), sort=True)

    def __unicode__(self):
        """ provide a nice str repr of our rolling object """
        attrs = ["{k}={v}".format(k=k, v=getattr(self.groupby, k))
                 for k in self._attributes if
                 getattr(self.groupby, k, None) is not None]
        return "{klass} [{attrs}]".format(klass=self.__class__.__name__,
                                          attrs=','.join(attrs))

    @property
    def obj(self):
        return self.groupby.obj

    @property
    def ax(self):
        return self.groupby.ax

    @property
    def _typ(self):
        """ masquerade for compat as a Series or a DataFrame """
        if isinstance(self._selected_obj, pd.Series):
            return 'series'
        return 'dataframe'

    def _deprecated(self):
        warnings.warn(".resample() is now a deferred operation\n"
                      "use .resample(...).mean() instead of .resample(...)",
                      FutureWarning, stacklevel=2)
        return self.mean()

    def _make_deprecated_binop(op):
        # op is a string

        def _evaluate_numeric_binop(self, other):
            result = self._deprecated()
            return getattr(result, op)(other)
        return _evaluate_numeric_binop

    def _make_deprecated_unary(op):
        # op is a callable

        def _evaluate_numeric_unary(self):
            result = self._deprecated()
            return op(result)
        return _evaluate_numeric_unary

    def __array__(self):
        return self._deprecated().__array__()

    __gt__ = _make_deprecated_binop('__gt__')
    __ge__ = _make_deprecated_binop('__ge__')
    __lt__ = _make_deprecated_binop('__lt__')
    __le__ = _make_deprecated_binop('__le__')
    __eq__ = _make_deprecated_binop('__eq__')
    __ne__ = _make_deprecated_binop('__ne__')

    __add__ = __radd__ = _make_deprecated_binop('__add__')
    __sub__ = __rsub__ = _make_deprecated_binop('__sub__')
    __mul__ = __rmul__ = _make_deprecated_binop('__mul__')
    __floordiv__ = __rfloordiv__ = _make_deprecated_binop('__floordiv__')
    __truediv__ = __rtruediv__ = _make_deprecated_binop('__truediv__')
    if not compat.PY3:
        __div__ = __rdiv__ = _make_deprecated_binop('__div__')
    __neg__ = _make_deprecated_unary(lambda x: -x)
    __pos__ = _make_deprecated_unary(lambda x: x)
    __abs__ = _make_deprecated_unary(lambda x: np.abs(x))
    __inv__ = _make_deprecated_unary(lambda x: -x)

    def __getattr__(self, attr):
        if attr in self._internal_names_set:
            return object.__getattribute__(self, attr)
        if attr in self._attributes:
            return getattr(self.groupby, attr)
        if attr in self.obj:
            return self[attr]

        if attr in self._deprecated_invalids:
            raise ValueError(".resample() is now a deferred operation\n"
                             "\tuse .resample(...).mean() instead of "
                             ".resample(...)\n"
                             "\tassignment will have no effect as you "
                             "are working on a copy")
        if attr not in self._deprecated_valids:
            self = self._deprecated()
        return object.__getattribute__(self, attr)

    def __setattr__(self, attr, value):
        if attr not in self._deprecated_valids:
            raise ValueError("cannot set values on {0}".format(
                self.__class__.__name__))
        object.__setattr__(self, attr, value)

    def __setitem__(self, attr, value):
        raise ValueError("cannot set items on {0}".format(
            self.__class__.__name__))

    def _convert_obj(self, obj):
        """
        provide any conversions for the object in order to correctly handle

        Parameters
        ----------
        obj : the object to be resampled
        """
        obj = obj.consolidate()
        return obj

    def _get_binner_for_time(self):
        raise AbstractMethodError(self)

    def _set_binner(self):
        """ setup our binners """
        self.binner, self.grouper = self._get_binner()

    def _get_binner(self):
        """
        create the BinGrouper, assume that self.set_grouper(obj)
        has already been called
        """

        binner, bins, binlabels = self._get_binner_for_time()
        bin_grouper = BinGrouper(bins, binlabels)
        return binner, bin_grouper

    def aggregate(self, arg, *args, **kwargs):

        self._set_binner()
        result, how = self._aggregate(arg, *args, **kwargs)
        if result is None:
            return self._groupby_and_aggregate(self.grouper,
                                               arg,
                                               *args,
                                               **kwargs)

        return result

    agg = aggregate
    apply = aggregate

    def transform(self, arg, *args, **kwargs):
        """
        Provide a transformation on the Resampler
        Return the same size as input
        """
        return self._selected_obj.groupby(self.groupby).transform(
            arg, *args, **kwargs)

    def _downsample(self, f):
        raise AbstractMethodError(self)

    def _upsample(self, f, limit=None):
        raise AbstractMethodError(self)

    def _gotitem(self, key, ndim, subset=None):
        """
        sub-classes to define
        return a sliced object

        Parameters
        ----------
        key : string / list of selections
        ndim : 1,2
            requested ndim of result
        subset : object, default None
            subset to act on
        """
        self._set_binner()
        grouper = self.grouper
        if subset is None:
            subset = self.obj
        grouped = groupby(subset, by=None, grouper=grouper, axis=self.axis)

        # try the key selection
        try:
            return grouped[key]
        except KeyError:
            return grouped

    def _groupby_and_aggregate(self, grouper, how, *args, **kwargs):
        """ revaluate the obj with a groupby aggregation """

        if grouper is None:
            self._set_binner()
            grouper = self.grouper

        obj = self._selected_obj

        try:
            grouped = groupby(obj, by=None, grouper=grouper, axis=self.axis)
        except TypeError:

            # panel grouper
            grouped = PanelGroupBy(obj, grouper=grouper, axis=self.axis)

        result = grouped.aggregate(how, *args, **kwargs)
        return self._wrap_result(result)

    def _wrap_result(self, result):
        """ potentially wrap any results """
        return result

    def pad(self, limit=None):
        """
        Forward fill the values

        Parameters
        ----------
        limit : integer, optional
            limit of how many values to fill
        """
        return self._upsample('pad', limit=limit)
    ffill = pad

    def backfill(self, limit=None):
        """
        Backward fill the values

        Parameters
        ----------
        limit : integer, optional
            limit of how many values to fill
        """
        return self._upsample('backfill', limit=limit)
    bfill = backfill

    def fillna(self, method, limit=None):
        """
        Parameters
        ----------
        limit : integer, optional
            limit of how many values to fill
        """
        return self._upsample(None, limit=limit)

    def asfreq(self):
        """
        return the values at the new freq,
        essentially a reindex with (no filling)
        """
        return self._upsample(None)

    def std(self, ddof=1):
        """
        Compute standard deviation of groups, excluding missing values

        Parameters
        ----------
        ddof : integer, default 1
        degrees of freedom
        """
        return self._downsample('std', ddof=ddof)

    def var(self, ddof=1):
        """
        Compute variance of groups, excluding missing values

        Parameters
        ----------
        ddof : integer, default 1
        degrees of freedom
        """
        return self._downsample('var', ddof=ddof)
Resampler._deprecated_valids += dir(Resampler)

# downsample methods
for method in ['min', 'max', 'first', 'last', 'sum', 'mean', 'sem',
               'median', 'prod', 'ohlc']:

    def f(self, _method=method):
        return self._downsample(_method)
    f.__doc__ = getattr(GroupBy, method).__doc__
    setattr(Resampler, method, f)

# groupby & aggregate methods
for method in ['count', 'size']:

    def f(self, _method=method):
        return self._groupby_and_aggregate(None, _method)
    f.__doc__ = getattr(GroupBy, method).__doc__
    setattr(Resampler, method, f)

# series only methods
for method in ['nunique']:
    def f(self, _method=method):
        return self._groupby_and_aggregate(None, _method)
    f.__doc__ = getattr(SeriesGroupBy, method).__doc__
    setattr(Resampler, method, f)


class DatetimeIndexResampler(Resampler):

    def _get_binner_for_time(self):

        # this is how we are actually creating the bins
        if self.kind == 'period':
            return self.groupby._get_time_period_bins(self.ax)
        return self.groupby._get_time_bins(self.ax)

    def _downsample(self, how, **kwargs):
        """
        Downsample the cython defined function

        Parameters
        ----------
        how : string / cython mapped function
        **kwargs : kw args passed to how function
        """
        self._set_binner()
        how = self._is_cython_func(how) or how
        ax = self.ax
        obj = self._selected_obj

        if not len(ax):
            # reset to the new freq
            obj = obj.copy()
            obj.index.freq = self.freq
            return obj

        # do we have a regular frequency
        if ax.freq is not None or ax.inferred_freq is not None:

            if len(self.grouper.binlabels) > len(ax):

                # let's do an asfreq
                return self.asfreq()

        # we are downsampling
        # we want to call the actual grouper method here
        result = obj.groupby(
            self.grouper, axis=self.axis).aggregate(how, **kwargs)

        loffset = self.loffset
        if isinstance(loffset, compat.string_types):
            loffset = to_offset(self.loffset)

        if isinstance(loffset, (DateOffset, timedelta)):
            if (isinstance(result.index, DatetimeIndex)
                    and len(result.index) > 0):
                result.index = result.index + loffset

        return self._wrap_result(result)

    def _upsample(self, method, limit=None):
        """
        method : string {'backfill', 'bfill', 'pad', 'ffill'}
            method for upsampling
        limit : int, default None
            Maximum size gap to fill when reindexing

        See also
        --------
        .fillna

        """
        self._set_binner()
        if self.axis:
            raise AssertionError('axis must be 0')

        ax = self.ax
        obj = self._selected_obj
        binner = self.binner

        if self.closed == 'right':
            res_index = binner[1:]
        else:
            res_index = binner[:-1]

        # if we have the same frequency as our axis, then we are equal sampling
        if limit is None and to_offset(ax.inferred_freq) == self.freq:
            result = obj.copy()
            result.index = res_index
        else:
            result = obj.reindex(res_index, method=method,
                                 limit=limit)

        return self._wrap_result(result)

    def _wrap_result(self, result):
        result = super(DatetimeIndexResampler, self)._wrap_result(result)

        # we may have a different kind that we were asked originally
        # convert if needed
        if self.kind == 'period' and not isinstance(result.index, PeriodIndex):
            result.index = result.index.to_period(self.freq)
        return result


class PeriodIndexResampler(DatetimeIndexResampler):

    def _convert_obj(self, obj):
        obj = super(PeriodIndexResampler, self)._convert_obj(obj)

        offset = to_offset(self.freq)
        if offset.n > 1:
            if self.kind == 'period':  # pragma: no cover
                print('Warning: multiple of frequency -> timestamps')

            # Cannot have multiple of periods, convert to timestamp
            self.kind = 'timestamp'

        if not len(obj):
            self.kind = 'timestamp'

        # convert to timestamp
        if not (self.kind is None or self.kind == 'period'):
            obj = obj.to_timestamp(how=self.convention)
        return obj

    def aggregate(self, arg, *args, **kwargs):
        result, how = self._aggregate(arg, *args, **kwargs)
        if result is None:
            return self._wrap_result(
                self._python_agg_general(arg, *args, **kwargs))
        return result

    agg = aggregate

    def _get_new_index(self):
        """ return our new index """
        ax = self.ax
        obj = self._selected_obj

        if len(ax) == 0:
            new_index = PeriodIndex(data=[], freq=self.freq)
            return obj.reindex(new_index)

        start = ax[0].asfreq(self.freq, how=self.convention)
        end = ax[-1].asfreq(self.freq, how='end')

        return period_range(start, end, freq=self.freq)

    def _downsample(self, how, **kwargs):
        """
        Downsample the cython defined function

        Parameters
        ----------
        how : string / cython mapped function
        **kwargs : kw args passed to how function
        """

        # we may need to actually resample as if we are timestamps
        if self.kind == 'timestamp':
            return super(PeriodIndexResampler, self)._downsample(how, **kwargs)

        how = self._is_cython_func(how) or how
        ax = self.ax

        new_index = self._get_new_index()
        if len(new_index) == 0:
            return self._wrap_result(new_index)

        # Start vs. end of period
        memb = ax.asfreq(self.freq, how=self.convention)

        if is_subperiod(ax.freq, self.freq):
            # Downsampling
            rng = np.arange(memb.values[0], memb.values[-1] + 1)
            bins = memb.searchsorted(rng, side='right')
            grouper = BinGrouper(bins, new_index)
            return self._groupby_and_aggregate(grouper, how)
        elif is_superperiod(ax.freq, self.freq):
            return self.asfreq()

        raise ValueError('Frequency {axfreq} cannot be '
                         'resampled to {freq}'.format(
                             axfreq=ax.freq,
                             freq=self.freq))

    def _upsample(self, method, limit=None):
        """
        method : string {'backfill', 'bfill', 'pad', 'ffill'}
            method for upsampling
        limit : int, default None
            Maximum size gap to fill when reindexing

        See also
        --------
        .fillna

        """
        # we may need to actually resample as if we are timestamps
        if self.kind == 'timestamp':
            return super(PeriodIndexResampler, self)._upsample(method,
                                                               limit=limit)

        ax = self.ax
        obj = self.obj

        new_index = self._get_new_index()
        if len(new_index) == 0:
            return self._wrap_result(new_index)

        if not is_superperiod(ax.freq, self.freq):
            return self.asfreq()

        # Start vs. end of period
        memb = ax.asfreq(self.freq, how=self.convention)

        # Get the fill indexer
        indexer = memb.get_indexer(new_index, method=method, limit=limit)
        return self._wrap_result(_take_new_index(obj,
                                                 indexer,
                                                 new_index,
                                                 axis=self.axis))


class TimedeltaResampler(DatetimeIndexResampler):

    def _get_binner_for_time(self):
        return self.groupby._get_time_delta_bins(self.ax)


def resample(obj, kind=None, **kwds):
    """ create a TimeGrouper and return our resampler """
    tg = TimeGrouper(**kwds)
    return tg._get_resampler(obj, kind=kind)
resample.__doc__ = Resampler.__doc__


class TimeGrouper(Grouper):
    """
    Custom groupby class for time-interval grouping

    Parameters
    ----------
    freq : pandas date offset or offset alias for identifying bin edges
    closed : closed end of interval; left or right
    label : interval boundary to use for labeling; left or right
    nperiods : optional, integer
    convention : {'start', 'end', 'e', 's'}
        If axis is PeriodIndex

    Notes
    -----
    Use begin, end, nperiods to generate intervals that cannot be derived
    directly from the associated object
    """

    def __init__(self, freq='Min', closed=None, label=None, how='mean',
                 nperiods=None, axis=0,
                 fill_method=None, limit=None, loffset=None, kind=None,
                 convention=None, base=0, **kwargs):
        freq = to_offset(freq)

        end_types = set(['M', 'A', 'Q', 'BM', 'BA', 'BQ', 'W'])
        rule = freq.rule_code
        if (rule in end_types or
                ('-' in rule and rule[:rule.find('-')] in end_types)):
            if closed is None:
                closed = 'right'
            if label is None:
                label = 'right'
        else:
            if closed is None:
                closed = 'left'
            if label is None:
                label = 'left'

        self.closed = closed
        self.label = label
        self.nperiods = nperiods
        self.kind = kind

        self.convention = convention or 'E'
        self.convention = self.convention.lower()

        self.loffset = loffset
        self.how = how
        self.fill_method = fill_method
        self.limit = limit
        self.base = base

        # always sort time groupers
        kwargs['sort'] = True

        super(TimeGrouper, self).__init__(freq=freq, axis=axis, **kwargs)

    def _get_resampler(self, obj, kind=None):
        """
        return my resampler or raise if we have an invalid axis

        Parameters
        ----------
        obj : input object
        kind : string, optional
            'period','timestamp','timedelta' are valid

        Returns
        -------
        a Resampler

        Raises
        ------
        TypeError if incompatible axis

        """
        self._set_grouper(obj)

        ax = self.ax
        if isinstance(ax, DatetimeIndex):
            return DatetimeIndexResampler(obj,
                                          groupby=self,
                                          kind=kind,
                                          axis=self.axis)
        elif isinstance(ax, PeriodIndex) or kind == 'period':
            return PeriodIndexResampler(obj,
                                        groupby=self,
                                        kind=kind,
                                        axis=self.axis)
        elif isinstance(ax, TimedeltaIndex):
            return TimedeltaResampler(obj,
                                      groupby=self,
                                      axis=self.axis)

        raise TypeError("Only valid with DatetimeIndex, "
                        "TimedeltaIndex or PeriodIndex, "
                        "but got an instance of %r" % type(ax).__name__)

    def _get_grouper(self, obj):
        # create the resampler and return our binner
        r = self._get_resampler(obj)
        r._set_binner()
        return r.binner, r.grouper, r.obj

    def _get_binner_for_resample(self, kind=None):
        # create the BinGrouper
        # assume that self.set_grouper(obj) has already been called

        ax = self.ax
        if kind is None:
            kind = self.kind
        if kind is None or kind == 'timestamp':
            self.binner, bins, binlabels = self._get_time_bins(ax)
        elif kind == 'timedelta':
            self.binner, bins, binlabels = self._get_time_delta_bins(ax)
        else:
            self.binner, bins, binlabels = self._get_time_period_bins(ax)

        self.grouper = BinGrouper(bins, binlabels)
        return self.binner, self.grouper, self.obj

    def _get_binner_for_grouping(self, obj):
        # return an ordering of the transformed group labels,
        # suitable for multi-grouping, e.g the labels for
        # the resampled intervals
        binner, grouper, obj = self._get_grouper(obj)

        l = []
        for key, group in grouper.get_iterator(self.ax):
            l.extend([key] * len(group))
        grouper = binner.__class__(l, freq=binner.freq, name=binner.name)

        # since we may have had to sort
        # may need to reorder groups here
        if self.indexer is not None:
            indexer = self.indexer.argsort(kind='quicksort')
            grouper = grouper.take(indexer)
        return grouper

    def _get_time_bins(self, ax):
        if not isinstance(ax, DatetimeIndex):
            raise TypeError('axis must be a DatetimeIndex, but got '
                            'an instance of %r' % type(ax).__name__)

        if len(ax) == 0:
            binner = labels = DatetimeIndex(
                data=[], freq=self.freq, name=ax.name)
            return binner, [], labels

        first, last = ax.min(), ax.max()
        first, last = _get_range_edges(first, last, self.freq, closed=self.closed,
                                       base=self.base)
        tz = ax.tz
        binner = labels = DatetimeIndex(freq=self.freq,
                                        start=first.replace(tzinfo=None),
                                        end=last.replace(tzinfo=None),
                                        tz=tz,
                                        name=ax.name)

        # a little hack
        trimmed = False
        if (len(binner) > 2 and binner[-2] == last and
                self.closed == 'right'):

            binner = binner[:-1]
            trimmed = True

        ax_values = ax.asi8
        binner, bin_edges = self._adjust_bin_edges(binner, ax_values)

        # general version, knowing nothing about relative frequencies
        bins = lib.generate_bins_dt64(
            ax_values, bin_edges, self.closed, hasnans=ax.hasnans)

        if self.closed == 'right':
            labels = binner
            if self.label == 'right':
                labels = labels[1:]
            elif not trimmed:
                labels = labels[:-1]
        else:
            if self.label == 'right':
                labels = labels[1:]
            elif not trimmed:
                labels = labels[:-1]

        if ax.hasnans:
            binner = binner.insert(0, tslib.NaT)
            labels = labels.insert(0, tslib.NaT)

        # if we end up with more labels than bins
        # adjust the labels
        # GH4076
        if len(bins) < len(labels):
            labels = labels[:len(bins)]

        return binner, bins, labels

    def _adjust_bin_edges(self, binner, ax_values):
        # Some hacks for > daily data, see #1471, #1458, #1483

        bin_edges = binner.asi8

        if self.freq != 'D' and is_superperiod(self.freq, 'D'):
            day_nanos = _delta_to_nanoseconds(timedelta(1))
            if self.closed == 'right':
                bin_edges = bin_edges + day_nanos - 1

            # intraday values on last day
            if bin_edges[-2] > ax_values.max():
                bin_edges = bin_edges[:-1]
                binner = binner[:-1]

        return binner, bin_edges

    def _get_time_delta_bins(self, ax):
        if not isinstance(ax, TimedeltaIndex):
            raise TypeError('axis must be a TimedeltaIndex, but got '
                            'an instance of %r' % type(ax).__name__)

        if not len(ax):
            binner = labels = TimedeltaIndex(
                data=[], freq=self.freq, name=ax.name)
            return binner, [], labels

        labels = binner = TimedeltaIndex(start=ax[0],
                                         end=ax[-1],
                                         freq=self.freq,
                                         name=ax.name)

        end_stamps = labels + 1
        bins = ax.searchsorted(end_stamps, side='left')

        # Addresses GH #10530
        if self.base > 0:
            labels += type(self.freq)(self.base)

        return binner, bins, labels

    def _get_time_period_bins(self, ax):
        if not isinstance(ax, DatetimeIndex):
            raise TypeError('axis must be a DatetimeIndex, but got '
                            'an instance of %r' % type(ax).__name__)

        if not len(ax):
            binner = labels = PeriodIndex(
                data=[], freq=self.freq, name=ax.name)
            return binner, [], labels

        labels = binner = PeriodIndex(start=ax[0],
                                      end=ax[-1],
                                      freq=self.freq,
                                      name=ax.name)

        end_stamps = (labels + 1).asfreq(self.freq, 's').to_timestamp()
        if ax.tzinfo:
            end_stamps = end_stamps.tz_localize(ax.tzinfo)
        bins = ax.searchsorted(end_stamps, side='left')

        return binner, bins, labels


def _take_new_index(obj, indexer, new_index, axis=0):
    from pandas.core.api import Series, DataFrame

    if isinstance(obj, Series):
        new_values = com.take_1d(obj.values, indexer)
        return Series(new_values, index=new_index, name=obj.name)
    elif isinstance(obj, DataFrame):
        if axis == 1:
            raise NotImplementedError("axis 1 is not supported")
        return DataFrame(obj._data.reindex_indexer(
            new_axis=new_index, indexer=indexer, axis=1))
    else:
        raise ValueError("'obj' should be either a Series or a DataFrame")


def _get_range_edges(first, last, offset, closed='left', base=0):
    if isinstance(offset, compat.string_types):
        offset = to_offset(offset)

    if isinstance(offset, Tick):
        is_day = isinstance(offset, Day)
        day_nanos = _delta_to_nanoseconds(timedelta(1))

        # #1165
        if (is_day and day_nanos % offset.nanos == 0) or not is_day:
            return _adjust_dates_anchored(first, last, offset,
                                          closed=closed, base=base)

    if not isinstance(offset, Tick):  # and first.time() != last.time():
        # hack!
        first = first.normalize()
        last = last.normalize()

    if closed == 'left':
        first = Timestamp(offset.rollback(first))
    else:
        first = Timestamp(first - offset)

    last = Timestamp(last + offset)

    return first, last


def _adjust_dates_anchored(first, last, offset, closed='right', base=0):
    # First and last offsets should be calculated from the start day to fix an
    # error cause by resampling across multiple days when a one day period is
    # not a multiple of the frequency.
    #
    # See https://github.com/pydata/pandas/issues/8683

    first_tzinfo = first.tzinfo
    first = first.tz_localize(None)
    last = last.tz_localize(None)
    start_day_nanos = first.normalize().value

    base_nanos = (base % offset.n) * offset.nanos // offset.n
    start_day_nanos += base_nanos

    foffset = (first.value - start_day_nanos) % offset.nanos
    loffset = (last.value - start_day_nanos) % offset.nanos

    if closed == 'right':
        if foffset > 0:
            # roll back
            fresult = first.value - foffset
        else:
            fresult = first.value - offset.nanos

        if loffset > 0:
            # roll forward
            lresult = last.value + (offset.nanos - loffset)
        else:
            # already the end of the road
            lresult = last.value
    else:  # closed == 'left'
        if foffset > 0:
            fresult = first.value - foffset
        else:
            # start of the road
            fresult = first.value

        if loffset > 0:
            # roll forward
            lresult = last.value + (offset.nanos - loffset)
        else:
            lresult = last.value + offset.nanos

#     return (Timestamp(fresult, tz=first.tz),
#             Timestamp(lresult, tz=last.tz))

    return (Timestamp(fresult).tz_localize(first_tzinfo),
            Timestamp(lresult).tz_localize(first_tzinfo))


def asfreq(obj, freq, method=None, how=None, normalize=False):
    """
    Utility frequency conversion method for Series/DataFrame
    """
    if isinstance(obj.index, PeriodIndex):
        if method is not None:
            raise NotImplementedError("'method' argument is not supported")

        if how is None:
            how = 'E'

        new_index = obj.index.asfreq(freq, how=how)
        new_obj = obj.copy()
        new_obj.index = new_index
        return new_obj
    else:
        if len(obj.index) == 0:
            return obj.copy()
        dti = date_range(obj.index[0], obj.index[-1], freq=freq)
        dti.name = obj.index.name
        rs = obj.reindex(dti, method=method)
        if normalize:
            rs.index = rs.index.normalize()
        return rs
