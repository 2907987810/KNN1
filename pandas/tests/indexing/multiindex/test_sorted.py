import numpy as np
from numpy.random import randn

from pandas import DataFrame, MultiIndex, Series
import pandas._testing as tm


class TestMultiIndexSorted:
    def test_getitem_multilevel_index_tuple_not_sorted(self):
        index_columns = list("abc")
        df = DataFrame(
            [[0, 1, 0, "x"], [0, 0, 1, "y"]], columns=index_columns + ["data"]
        )
        df = df.set_index(index_columns)
        query_index = df.index[:1]
        rs = df.loc[query_index, "data"]

        xp_idx = MultiIndex.from_tuples([(0, 1, 0)], names=["a", "b", "c"])
        xp = Series(["x"], index=xp_idx, name="data")
        tm.assert_series_equal(rs, xp)

    def test_getitem_slice_not_sorted(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        df = frame.sort_index(level=1).T

        # buglet with int typechecking
        result = df.iloc[:, : np.int32(3)]
        expected = df.reindex(columns=df.columns[:3])
        tm.assert_frame_equal(result, expected)

    def test_frame_getitem_not_sorted2(self):
        # 13431
        df = DataFrame(
            {
                "col1": ["b", "d", "b", "a"],
                "col2": [3, 1, 1, 2],
                "data": ["one", "two", "three", "four"],
            }
        )

        df2 = df.set_index(["col1", "col2"])
        df2_original = df2.copy()

        df2.index.set_levels(["b", "d", "a"], level="col1", inplace=True)
        df2.index.set_codes([0, 1, 0, 2], level="col1", inplace=True)
        assert not df2.index.is_lexsorted()
        assert not df2.index.is_monotonic is True

        assert df2_original.index.equals(df2.index)
        expected = df2.sort_index()
        assert expected.index.is_lexsorted()
        assert expected.index.is_monotonic is True

        result = df2.sort_index(level=0)
        assert result.index.is_lexsorted()
        assert result.index.is_monotonic is True
        tm.assert_frame_equal(result, expected)

    def test_frame_getitem_not_sorted(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data
        df = frame.T
        df["foo", "four"] = "foo"

        arrays = [np.array(x) for x in zip(*df.columns.values)]

        result = df["foo"]
        result2 = df.loc[:, "foo"]
        expected = df.reindex(columns=df.columns[arrays[0] == "foo"])
        expected.columns = expected.columns.droplevel(0)
        tm.assert_frame_equal(result, expected)
        tm.assert_frame_equal(result2, expected)

        df = df.T
        result = df.xs("foo")
        result2 = df.loc["foo"]
        expected = df.reindex(df.index[arrays[0] == "foo"])
        expected.index = expected.index.droplevel(0)
        tm.assert_frame_equal(result, expected)
        tm.assert_frame_equal(result2, expected)

    def test_series_getitem_not_sorted(self):
        arrays = [
            ["bar", "bar", "baz", "baz", "qux", "qux", "foo", "foo"],
            ["one", "two", "one", "two", "one", "two", "one", "two"],
        ]
        tuples = zip(*arrays)
        index = MultiIndex.from_tuples(tuples)
        s = Series(randn(8), index=index)

        arrays = [np.array(x) for x in zip(*index.values)]

        result = s["qux"]
        result2 = s.loc["qux"]
        expected = s[arrays[0] == "qux"]
        expected.index = expected.index.droplevel(0)
        tm.assert_series_equal(result, expected)
        tm.assert_series_equal(result2, expected)
