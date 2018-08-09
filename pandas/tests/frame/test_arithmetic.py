# -*- coding: utf-8 -*-
import pytest
import numpy as np

from pandas.compat import range

import pandas as pd
import pandas.util.testing as tm


# -------------------------------------------------------------------
# Comparisons

class TestFrameComparisons(object):
    def test_flex_comparison_nat(self):
        # GH#15697, GH#22163 df.eq(pd.NaT) should behave like df == pd.NaT,
        # and _definitely_ not be NaN
        df = pd.DataFrame([pd.NaT])

        result = df == pd.NaT
        # result.iloc[0, 0] is a np.bool_ object
        assert result.iloc[0, 0].item() is False

        result = df.eq(pd.NaT)
        assert result.iloc[0, 0].item() is False

        result = df != pd.NaT
        assert result.iloc[0, 0].item() is True

        result = df.ne(pd.NaT)
        assert result.iloc[0, 0].item() is True

    def test_mixed_comparison(self):
        # GH#13128, GH#22163 != datetime64 vs non-dt64 should be False,
        # not raise TypeError
        # (this appears to be fixed before #22163, not sure when)
        df = pd.DataFrame([['1989-08-01', 1], ['1989-08-01', 2]])
        other = pd.DataFrame([['a', 'b'], ['c', 'd']])

        result = df == other
        assert not result.any().any()

        result = df != other
        assert result.all().all()

    def test_df_numeric_cmp_dt64_raises(self):
        # GH#8932, GH#22163
        ts = pd.Timestamp.now()
        df = pd.DataFrame({'x': range(5)})
        with pytest.raises(TypeError):
            df > ts
        with pytest.raises(TypeError):
            df < ts
        with pytest.raises(TypeError):
            ts < df
        with pytest.raises(TypeError):
            ts > df

        assert not (df == ts).any().any()
        assert (df != ts).all().all()

    def test_df_boolean_comparison_error(self):
        # GH#4576
        # boolean comparisons with a tuple/list give unexpected results
        df = pd.DataFrame(np.arange(6).reshape((3, 2)))

        # not shape compatible
        with pytest.raises(ValueError):
            df == (2, 2)
        with pytest.raises(ValueError):
            df == [2, 2]

    def test_df_float_none_comparison(self):
        df = pd.DataFrame(np.random.randn(8, 3), index=range(8),
                          columns=['A', 'B', 'C'])

        result = df.__eq__(None)
        assert not result.any().any()

    def test_df_string_comparison(self):
        df = pd.DataFrame([{"a": 1, "b": "foo"}, {"a": 2, "b": "bar"}])
        mask_a = df.a > 1
        tm.assert_frame_equal(df[mask_a], df.loc[1:1, :])
        tm.assert_frame_equal(df[-mask_a], df.loc[0:0, :])

        mask_b = df.b == "foo"
        tm.assert_frame_equal(df[mask_b], df.loc[0:0, :])
        tm.assert_frame_equal(df[-mask_b], df.loc[1:1, :])

    @pytest.mark.parametrize('opname', ['eq', 'ne', 'gt', 'lt', 'ge', 'le'])
    def test_df_flex_cmp_constant_return_types(self, opname):
        # GH#15077, non-empty DataFrame
        df = pd.DataFrame({'x': [1, 2, 3], 'y': [1., 2., 3.]})
        const = 2

        result = getattr(df, opname)(const).get_dtype_counts()
        tm.assert_series_equal(result, pd.Series([2], ['bool']))

    @pytest.mark.parametrize('opname', ['eq', 'ne', 'gt', 'lt', 'ge', 'le'])
    def test_df_flex_cmp_constant_return_types_empty(self, opname):
        # GH#15077 empty DataFrame
        df = pd.DataFrame({'x': [1, 2, 3], 'y': [1., 2., 3.]})
        const = 2

        empty = df.iloc[:0]
        result = getattr(empty, opname)(const).get_dtype_counts()
        tm.assert_series_equal(result, pd.Series([2], ['bool']))


# -------------------------------------------------------------------
# Arithmetic

class TestFrameFlexArithmetic(object):
    def test_df_add_flex_filled_mixed_dtypes(self):
        # GH#19611
        dti = pd.date_range('2016-01-01', periods=3)
        ser = pd.Series(['1 Day', 'NaT', '2 Days'], dtype='timedelta64[ns]')
        df = pd.DataFrame({'A': dti, 'B': ser})
        other = pd.DataFrame({'A': ser, 'B': ser})
        fill = pd.Timedelta(days=1).to_timedelta64()
        result = df.add(other, fill_value=fill)

        expected = pd.DataFrame(
            {'A': pd.Series(['2016-01-02', '2016-01-03', '2016-01-05'],
                            dtype='datetime64[ns]'),
             'B': ser * 2})
        tm.assert_frame_equal(result, expected)


class TestFrameArithmetic(object):
    def test_df_bool_mul_int(self):
        # GH#22047, GH#22163 multiplication by 1 should result in int dtype,
        # not object dtype
        df = pd.DataFrame([[False, True], [False, False]])
        result = df * 1

        # On appveyor this comes back as np.int32 instead of np.int64,
        # so we check dtype.kind instead of just dtype
        kinds = result.dtypes.apply(lambda x: x.kind)
        assert (kinds == 'i').all()

        result = 1 * df
        kinds = result.dtypes.apply(lambda x: x.kind)
        assert (kinds == 'i').all()
