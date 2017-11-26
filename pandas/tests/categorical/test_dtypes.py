# -*- coding: utf-8 -*-

import pytest

import pandas as pd
import pandas.util.testing as tm
from pandas.core.dtypes.dtypes import CategoricalDtype
from pandas import (Categorical, Index, Series, DataFrame, CategoricalIndex)


class TestCategoricalDtypes(object):

    def test_is_equal_dtype(self):

        # test dtype comparisons between cats

        c1 = Categorical(list('aabca'), categories=list('abc'), ordered=False)
        c2 = Categorical(list('aabca'), categories=list('cab'), ordered=False)
        c3 = Categorical(list('aabca'), categories=list('cab'), ordered=True)
        assert c1.is_dtype_equal(c1)
        assert c2.is_dtype_equal(c2)
        assert c3.is_dtype_equal(c3)
        assert c1.is_dtype_equal(c2)
        assert not c1.is_dtype_equal(c3)
        assert not c1.is_dtype_equal(Index(list('aabca')))
        assert not c1.is_dtype_equal(c1.astype(object))
        assert c1.is_dtype_equal(CategoricalIndex(c1))
        assert (c1.is_dtype_equal(
            CategoricalIndex(c1, categories=list('cab'))))
        assert not c1.is_dtype_equal(CategoricalIndex(c1, ordered=True))

    def test_set_dtype_same(self):
        c = Categorical(['a', 'b', 'c'])
        result = c._set_dtype(CategoricalDtype(['a', 'b', 'c']))
        tm.assert_categorical_equal(result, c)

    def test_set_dtype_new_categories(self):
        c = Categorical(['a', 'b', 'c'])
        result = c._set_dtype(CategoricalDtype(list('abcd')))
        tm.assert_numpy_array_equal(result.codes, c.codes)
        tm.assert_index_equal(result.dtype.categories, Index(list('abcd')))

    @pytest.mark.parametrize('values, categories, new_categories', [
        # No NaNs, same cats, same order
        (['a', 'b', 'a'], ['a', 'b'], ['a', 'b'],),
        # No NaNs, same cats, different order
        (['a', 'b', 'a'], ['a', 'b'], ['b', 'a'],),
        # Same, unsorted
        (['b', 'a', 'a'], ['a', 'b'], ['a', 'b'],),
        # No NaNs, same cats, different order
        (['b', 'a', 'a'], ['a', 'b'], ['b', 'a'],),
        # NaNs
        (['a', 'b', 'c'], ['a', 'b'], ['a', 'b']),
        (['a', 'b', 'c'], ['a', 'b'], ['b', 'a']),
        (['b', 'a', 'c'], ['a', 'b'], ['a', 'b']),
        (['b', 'a', 'c'], ['a', 'b'], ['a', 'b']),
        # Introduce NaNs
        (['a', 'b', 'c'], ['a', 'b'], ['a']),
        (['a', 'b', 'c'], ['a', 'b'], ['b']),
        (['b', 'a', 'c'], ['a', 'b'], ['a']),
        (['b', 'a', 'c'], ['a', 'b'], ['a']),
        # No overlap
        (['a', 'b', 'c'], ['a', 'b'], ['d', 'e']),
    ])
    @pytest.mark.parametrize('ordered', [True, False])
    def test_set_dtype_many(self, values, categories, new_categories,
                            ordered):
        c = Categorical(values, categories)
        expected = Categorical(values, new_categories, ordered)
        result = c._set_dtype(expected.dtype)
        tm.assert_categorical_equal(result, expected)

    def test_set_dtype_no_overlap(self):
        c = Categorical(['a', 'b', 'c'], ['d', 'e'])
        result = c._set_dtype(CategoricalDtype(['a', 'b']))
        expected = Categorical([None, None, None], categories=['a', 'b'])
        tm.assert_categorical_equal(result, expected)


class TestCategoricalBlockDtypes(object):

    def test_dtypes(self):

        # GH8143
        index = ['cat', 'obj', 'num']
        cat = Categorical(['a', 'b', 'c'])
        obj = Series(['a', 'b', 'c'])
        num = Series([1, 2, 3])
        df = pd.concat([Series(cat), obj, num], axis=1, keys=index)

        result = df.dtypes == 'object'
        expected = Series([False, True, False], index=index)
        tm.assert_series_equal(result, expected)

        result = df.dtypes == 'int64'
        expected = Series([False, False, True], index=index)
        tm.assert_series_equal(result, expected)

        result = df.dtypes == 'category'
        expected = Series([True, False, False], index=index)
        tm.assert_series_equal(result, expected)

    def test_codes_dtypes(self):

        # GH 8453
        result = Categorical(['foo', 'bar', 'baz'])
        assert result.codes.dtype == 'int8'

        result = Categorical(['foo%05d' % i for i in range(400)])
        assert result.codes.dtype == 'int16'

        result = Categorical(['foo%05d' % i for i in range(40000)])
        assert result.codes.dtype == 'int32'

        # adding cats
        result = Categorical(['foo', 'bar', 'baz'])
        assert result.codes.dtype == 'int8'
        result = result.add_categories(['foo%05d' % i for i in range(400)])
        assert result.codes.dtype == 'int16'

        # removing cats
        result = result.remove_categories(['foo%05d' % i for i in range(300)])
        assert result.codes.dtype == 'int8'

    @pytest.mark.parametrize('columns', [['x'], ['x', 'y'], ['x', 'y', 'z']])
    def test_empty_astype(self, columns):
        # GH 18004
        msg = '> 1 ndim Categorical are not supported at this time'
        with tm.assert_raises_regex(NotImplementedError, msg):
            DataFrame(columns=columns).astype('category')
