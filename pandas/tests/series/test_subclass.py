import numpy as np
import pytest

import pandas as pd
import pandas._testing as tm

warn_msg = "_metadata propagation is deprecated"


class TestSeriesSubclassing:
    @pytest.mark.parametrize(
        "idx_method, indexer, exp_data, exp_idx",
        [
            ["loc", ["a", "b"], [1, 2], "ab"],
            ["iloc", [2, 3], [3, 4], "cd"],
        ],
    )
    def test_indexing_sliced(self, idx_method, indexer, exp_data, exp_idx):
        s = tm.SubclassedSeries([1, 2, 3, 4], index=list("abcd"))
        with tm.assert_produces_warning(FutureWarning, match=warn_msg):
            res = getattr(s, idx_method)[indexer]
        exp = tm.SubclassedSeries(exp_data, index=list(exp_idx))
        tm.assert_series_equal(res, exp)

    def test_to_frame(self):
        s = tm.SubclassedSeries([1, 2, 3, 4], index=list("abcd"), name="xxx")
        with tm.assert_produces_warning(FutureWarning, match=warn_msg):
            res = s.to_frame()
        exp = tm.SubclassedDataFrame({"xxx": [1, 2, 3, 4]}, index=list("abcd"))
        with tm.assert_produces_warning(FutureWarning, match=warn_msg):
            tm.assert_frame_equal(res, exp)

    def test_subclass_unstack(self):
        # GH 15564
        s = tm.SubclassedSeries([1, 2, 3, 4], index=[list("aabb"), list("xyxy")])

        res = s.unstack()
        exp = tm.SubclassedDataFrame({"x": [1, 3], "y": [2, 4]}, index=["a", "b"])

        with tm.assert_produces_warning(FutureWarning, match=warn_msg):
            tm.assert_frame_equal(res, exp)

    def test_subclass_empty_repr(self):
        sub_series = tm.SubclassedSeries()
        assert "SubclassedSeries" in repr(sub_series)

    def test_asof(self):
        N = 3
        rng = pd.date_range("1/1/1990", periods=N, freq="53s")

        with tm.assert_produces_warning(FutureWarning, match=warn_msg):
            s = tm.SubclassedSeries({"A": [np.nan, np.nan, np.nan]}, index=rng)

        with tm.assert_produces_warning(FutureWarning, match=warn_msg):
            result = s.asof(rng[-2:])
        assert isinstance(result, tm.SubclassedSeries)

    def test_explode(self):
        s = tm.SubclassedSeries([[1, 2, 3], "foo", [], [3, 4]])
        result = s.explode()
        assert isinstance(result, tm.SubclassedSeries)

    def test_equals(self):
        # https://github.com/pandas-dev/pandas/pull/34402
        # allow subclass in both directions
        s1 = pd.Series([1, 2, 3])
        s2 = tm.SubclassedSeries([1, 2, 3])
        assert s1.equals(s2)
        assert s2.equals(s1)
