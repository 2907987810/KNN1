# coding=utf-8

import numpy as np
import random

from pandas import (DataFrame, Series, MultiIndex)

from pandas.util.testing import (assert_series_equal, assert_almost_equal)
import pandas.util.testing as tm

from .common import TestData


class TestSeriesSorting(TestData, tm.TestCase):

    _multiprocess_can_split_ = True

    def test_sort(self):

        ts = self.ts.copy()

        # 9816 deprecated
        with tm.assert_produces_warning(FutureWarning):
            ts.sort()  # sorts inplace
        self.assert_series_equal(ts, self.ts.sort_values())

    def test_order(self):

        # 9816 deprecated
        with tm.assert_produces_warning(FutureWarning):
            result = self.ts.order()
        self.assert_series_equal(result, self.ts.sort_values())

    def test_sort_values(self):

        # check indexes are reordered corresponding with the values
        ser = Series([3, 2, 4, 1], ['A', 'B', 'C', 'D'])
        expected = Series([1, 2, 3, 4], ['D', 'B', 'A', 'C'])
        result = ser.sort_values()
        self.assert_series_equal(expected, result)

        ts = self.ts.copy()
        ts[:5] = np.NaN
        vals = ts.values

        result = ts.sort_values()
        self.assertTrue(np.isnan(result[-5:]).all())
        self.assert_numpy_array_equal(result[:-5].values, np.sort(vals[5:]))

        # na_position
        result = ts.sort_values(na_position='first')
        self.assertTrue(np.isnan(result[:5]).all())
        self.assert_numpy_array_equal(result[5:].values, np.sort(vals[5:]))

        # something object-type
        ser = Series(['A', 'B'], [1, 2])
        # no failure
        ser.sort_values()

        # ascending=False
        ordered = ts.sort_values(ascending=False)
        expected = np.sort(ts.valid().values)[::-1]
        assert_almost_equal(expected, ordered.valid().values)
        ordered = ts.sort_values(ascending=False, na_position='first')
        assert_almost_equal(expected, ordered.valid().values)

        # inplace=True
        ts = self.ts.copy()
        ts.sort_values(ascending=False, inplace=True)
        self.assert_series_equal(ts, self.ts.sort_values(ascending=False))
        self.assert_index_equal(ts.index,
                                self.ts.sort_values(ascending=False).index)

        # GH 5856/5853
        # Series.sort_values operating on a view
        df = DataFrame(np.random.randn(10, 4))
        s = df.iloc[:, 0]

        def f():
            s.sort_values(inplace=True)

        self.assertRaises(ValueError, f)

    def test_sort_index(self):
        rindex = list(self.ts.index)
        random.shuffle(rindex)

        random_order = self.ts.reindex(rindex)
        sorted_series = random_order.sort_index()
        assert_series_equal(sorted_series, self.ts)

        # descending
        sorted_series = random_order.sort_index(ascending=False)
        assert_series_equal(sorted_series,
                            self.ts.reindex(self.ts.index[::-1]))

        # compat on level
        sorted_series = random_order.sort_index(level=0)
        assert_series_equal(sorted_series, self.ts)

        # compat on axis
        sorted_series = random_order.sort_index(axis=0)
        assert_series_equal(sorted_series, self.ts)

        self.assertRaises(ValueError, lambda: random_order.sort_values(axis=1))

        sorted_series = random_order.sort_index(level=0, axis=0)
        assert_series_equal(sorted_series, self.ts)

        self.assertRaises(ValueError,
                          lambda: random_order.sort_index(level=0, axis=1))


    def test_sort_index_inplace(self):

        # For #11402
        rindex = list(self.ts.index)
        random.shuffle(rindex)

        # descending
        random_order = self.ts.reindex(rindex)
        result = random_order.sort_index(ascending=False, inplace=True)
        self.assertIs(result, None,
                      msg='sort_index() inplace should return None')
        assert_series_equal(random_order, self.ts.reindex(self.ts.index[::-1]))

        # ascending
        random_order = self.ts.reindex(rindex)
        result = random_order.sort_index(ascending=True, inplace=True)
        self.assertIs(result, None,
                      msg='sort_index() inplace should return None')
        assert_series_equal(random_order, self.ts)

    def test_sort_index_multiindex(self):

        mi = MultiIndex.from_tuples([[1, 1, 3], [1, 1, 1]], names=list('ABC'))
        s = Series([1, 2], mi)
        backwards = s.iloc[[1, 0]]

        res = s.sort_index(level='A')
        assert_series_equal(backwards, res)

