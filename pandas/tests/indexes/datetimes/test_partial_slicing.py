""" test partial slicing on Series/Frame """

from datetime import datetime
import operator

import numpy as np
import pytest

from pandas import (
    DataFrame,
    DatetimeIndex,
    Index,
    Series,
    Timedelta,
    Timestamp,
    date_range,
)
import pandas._testing as tm
from pandas.core.indexing import IndexingError


class TestSlicing:
    def test_monotone_DTI_indexing_bug(self):
        # GH 19362
        # Testing accessing the first element in a monotonic descending
        # partial string indexing.

        df = DataFrame(list(range(5)))
        date_list = [
            "2018-01-02",
            "2017-02-10",
            "2016-03-10",
            "2015-03-15",
            "2014-03-16",
        ]
        date_index = DatetimeIndex(date_list)
        df["date"] = date_index
        expected = DataFrame({0: list(range(5)), "date": date_index})
        tm.assert_frame_equal(df, expected)

        df = DataFrame({"A": [1, 2, 3]}, index=date_range("20170101", periods=3)[::-1])
        expected = DataFrame({"A": 1}, index=date_range("20170103", periods=1)[::-1])
        tm.assert_frame_equal(df.loc["2017-01-03"], expected)

    def test_slice_year(self):
        dti = date_range(freq="B", start=datetime(2005, 1, 1), periods=500)

        s = Series(np.arange(len(dti)), index=dti)
        result = s["2005"]
        expected = s[s.index.year == 2005]
        tm.assert_series_equal(result, expected)

        df = DataFrame(np.random.rand(len(dti), 5), index=dti)
        result = df.loc["2005"]
        expected = df[df.index.year == 2005]
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize(
        "partial_dtime",
        [
            "2019",
            "2019Q4",
            "Dec 2019",
            "2019-12-31",
            "2019-12-31 23",
            "2019-12-31 23:59",
        ],
    )
    def test_slice_end_of_period_resolution(self, partial_dtime):
        # GH#31064
        dti = date_range("2019-12-31 23:59:55.999999999", periods=10, freq="s")

        ser = Series(range(10), index=dti)
        result = ser[partial_dtime]
        expected = ser.iloc[:5]
        tm.assert_series_equal(result, expected)

    def test_slice_quarter(self):
        dti = date_range(freq="D", start=datetime(2000, 6, 1), periods=500)

        s = Series(np.arange(len(dti)), index=dti)
        assert len(s["2001Q1"]) == 90

        df = DataFrame(np.random.rand(len(dti), 5), index=dti)
        assert len(df.loc["1Q01"]) == 90

    def test_slice_month(self):
        dti = date_range(freq="D", start=datetime(2005, 1, 1), periods=500)
        s = Series(np.arange(len(dti)), index=dti)
        assert len(s["2005-11"]) == 30

        df = DataFrame(np.random.rand(len(dti), 5), index=dti)
        assert len(df.loc["2005-11"]) == 30

        tm.assert_series_equal(s["2005-11"], s["11-2005"])

    def test_partial_slice(self):
        rng = date_range(freq="D", start=datetime(2005, 1, 1), periods=500)
        s = Series(np.arange(len(rng)), index=rng)

        result = s["2005-05":"2006-02"]
        expected = s["20050501":"20060228"]
        tm.assert_series_equal(result, expected)

        result = s["2005-05":]
        expected = s["20050501":]
        tm.assert_series_equal(result, expected)

        result = s[:"2006-02"]
        expected = s[:"20060228"]
        tm.assert_series_equal(result, expected)

        result = s["2005-1-1"]
        assert result == s.iloc[0]

        with pytest.raises(KeyError, match=r"^'2004-12-31'$"):
            s["2004-12-31"]

    def test_partial_slice_daily(self):
        rng = date_range(freq="H", start=datetime(2005, 1, 31), periods=500)
        s = Series(np.arange(len(rng)), index=rng)

        result = s["2005-1-31"]
        tm.assert_series_equal(result, s.iloc[:24])

        with pytest.raises(KeyError, match=r"^'2004-12-31 00'$"):
            s["2004-12-31 00"]

    def test_partial_slice_hourly(self):
        rng = date_range(freq="T", start=datetime(2005, 1, 1, 20, 0, 0), periods=500)
        s = Series(np.arange(len(rng)), index=rng)

        result = s["2005-1-1"]
        tm.assert_series_equal(result, s.iloc[: 60 * 4])

        result = s["2005-1-1 20"]
        tm.assert_series_equal(result, s.iloc[:60])

        assert s["2005-1-1 20:00"] == s.iloc[0]
        with pytest.raises(KeyError, match=r"^'2004-12-31 00:15'$"):
            s["2004-12-31 00:15"]

    def test_partial_slice_minutely(self):
        rng = date_range(freq="S", start=datetime(2005, 1, 1, 23, 59, 0), periods=500)
        s = Series(np.arange(len(rng)), index=rng)

        result = s["2005-1-1 23:59"]
        tm.assert_series_equal(result, s.iloc[:60])

        result = s["2005-1-1"]
        tm.assert_series_equal(result, s.iloc[:60])

        assert s[Timestamp("2005-1-1 23:59:00")] == s.iloc[0]
        with pytest.raises(KeyError, match=r"^'2004-12-31 00:00:00'$"):
            s["2004-12-31 00:00:00"]

    def test_partial_slice_second_precision(self):
        rng = date_range(
            start=datetime(2005, 1, 1, 0, 0, 59, microsecond=999990),
            periods=20,
            freq="US",
        )
        s = Series(np.arange(20), rng)

        tm.assert_series_equal(s["2005-1-1 00:00"], s.iloc[:10])
        tm.assert_series_equal(s["2005-1-1 00:00:59"], s.iloc[:10])

        tm.assert_series_equal(s["2005-1-1 00:01"], s.iloc[10:])
        tm.assert_series_equal(s["2005-1-1 00:01:00"], s.iloc[10:])

        assert s[Timestamp("2005-1-1 00:00:59.999990")] == s.iloc[0]
        with pytest.raises(KeyError, match="2005-1-1 00:00:00"):
            s["2005-1-1 00:00:00"]

    def test_partial_slicing_dataframe(self):
        # GH14856
        # Test various combinations of string slicing resolution vs.
        # index resolution
        # - If string resolution is less precise than index resolution,
        # string is considered a slice
        # - If string resolution is equal to or more precise than index
        # resolution, string is considered an exact match
        formats = [
            "%Y",
            "%Y-%m",
            "%Y-%m-%d",
            "%Y-%m-%d %H",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
        ]
        resolutions = ["year", "month", "day", "hour", "minute", "second"]
        for rnum, resolution in enumerate(resolutions[2:], 2):
            # we check only 'day', 'hour', 'minute' and 'second'
            unit = Timedelta("1 " + resolution)
            middate = datetime(2012, 1, 1, 0, 0, 0)
            index = DatetimeIndex([middate - unit, middate, middate + unit])
            values = [1, 2, 3]
            df = DataFrame({"a": values}, index, dtype=np.int64)
            assert df.index.resolution == resolution

            # Timestamp with the same resolution as index
            # Should be exact match for Series (return scalar)
            # and raise KeyError for Frame
            for timestamp, expected in zip(index, values):
                ts_string = timestamp.strftime(formats[rnum])
                # make ts_string as precise as index
                result = df["a"][ts_string]
                assert isinstance(result, np.int64)
                assert result == expected
                msg = fr"^'{ts_string}'$"
                with pytest.raises(KeyError, match=msg):
                    df[ts_string]

            # Timestamp with resolution less precise than index
            for fmt in formats[:rnum]:
                for element, theslice in [[0, slice(None, 1)], [1, slice(1, None)]]:
                    ts_string = index[element].strftime(fmt)

                    # Series should return slice
                    result = df["a"][ts_string]
                    expected = df["a"][theslice]
                    tm.assert_series_equal(result, expected)

                    # Frame should return slice as well
                    with tm.assert_produces_warning(FutureWarning):
                        # GH#36179 deprecated this indexing
                        result = df[ts_string]
                    expected = df[theslice]
                    tm.assert_frame_equal(result, expected)

            # Timestamp with resolution more precise than index
            # Compatible with existing key
            # Should return scalar for Series
            # and raise KeyError for Frame
            for fmt in formats[rnum + 1 :]:
                ts_string = index[1].strftime(fmt)
                result = df["a"][ts_string]
                assert isinstance(result, np.int64)
                assert result == 2
                msg = fr"^'{ts_string}'$"
                with pytest.raises(KeyError, match=msg):
                    df[ts_string]

            # Not compatible with existing key
            # Should raise KeyError
            for fmt, res in list(zip(formats, resolutions))[rnum + 1 :]:
                ts = index[1] + Timedelta("1 " + res)
                ts_string = ts.strftime(fmt)
                msg = fr"^'{ts_string}'$"
                with pytest.raises(KeyError, match=msg):
                    df["a"][ts_string]
                with pytest.raises(KeyError, match=msg):
                    df[ts_string]

    def test_partial_slicing_with_multiindex(self):

        # GH 4758
        # partial string indexing with a multi-index buggy
        df = DataFrame(
            {
                "ACCOUNT": ["ACCT1", "ACCT1", "ACCT1", "ACCT2"],
                "TICKER": ["ABC", "MNP", "XYZ", "XYZ"],
                "val": [1, 2, 3, 4],
            },
            index=date_range("2013-06-19 09:30:00", periods=4, freq="5T"),
        )
        df_multi = df.set_index(["ACCOUNT", "TICKER"], append=True)

        expected = DataFrame(
            [[1]], index=Index(["ABC"], name="TICKER"), columns=["val"]
        )
        result = df_multi.loc[("2013-06-19 09:30:00", "ACCT1")]
        tm.assert_frame_equal(result, expected)

        expected = df_multi.loc[
            (Timestamp("2013-06-19 09:30:00", tz=None), "ACCT1", "ABC")
        ]
        result = df_multi.loc[("2013-06-19 09:30:00", "ACCT1", "ABC")]
        tm.assert_series_equal(result, expected)

        # this is an IndexingError as we don't do partial string selection on
        # multi-levels.
        msg = "Too many indexers"
        with pytest.raises(IndexingError, match=msg):
            df_multi.loc[("2013-06-19", "ACCT1", "ABC")]

    def test_partial_slicing_with_multiindex_series(self):
        # GH 4294
        # partial slice on a series mi
        ser = DataFrame(
            np.random.rand(1000, 1000), index=date_range("2000-1-1", periods=1000)
        ).stack()

        s2 = ser[:-1].copy()
        expected = s2["2000-1-4"]
        result = s2[Timestamp("2000-1-4")]
        tm.assert_series_equal(result, expected)

        result = ser[Timestamp("2000-1-4")]
        expected = ser["2000-1-4"]
        tm.assert_series_equal(result, expected)

        df2 = DataFrame(ser)
        expected = df2.xs("2000-1-4")
        result = df2.loc[Timestamp("2000-1-4")]
        tm.assert_frame_equal(result, expected)

    def test_partial_slice_doesnt_require_monotonicity(self):
        # For historical reasons.
        ser = Series(np.arange(10), date_range("2014-01-01", periods=10))

        nonmonotonic = ser[[3, 5, 4]]
        expected = nonmonotonic.iloc[:0]
        timestamp = Timestamp("2014-01-10")
        with tm.assert_produces_warning(FutureWarning):
            result = nonmonotonic["2014-01-10":]
        tm.assert_series_equal(result, expected)

        with pytest.raises(KeyError, match=r"Timestamp\('2014-01-10 00:00:00'\)"):
            nonmonotonic[timestamp:]

        with tm.assert_produces_warning(FutureWarning):
            result = nonmonotonic.loc["2014-01-10":]
        tm.assert_series_equal(result, expected)

        with pytest.raises(KeyError, match=r"Timestamp\('2014-01-10 00:00:00'\)"):
            nonmonotonic.loc[timestamp:]

    def test_loc_datetime_length_one(self):
        # GH16071
        df = DataFrame(
            columns=["1"],
            index=date_range("2016-10-01T00:00:00", "2016-10-01T23:59:59"),
        )
        result = df.loc[datetime(2016, 10, 1) :]
        tm.assert_frame_equal(result, df)

        result = df.loc["2016-10-01T00:00:00":]
        tm.assert_frame_equal(result, df)

    @pytest.mark.parametrize(
        "datetimelike",
        [
            Timestamp("20130101"),
            datetime(2013, 1, 1),
            np.datetime64("2013-01-01T00:00", "ns"),
        ],
    )
    @pytest.mark.parametrize(
        "op,expected",
        [
            (operator.lt, [True, False, False, False]),
            (operator.le, [True, True, False, False]),
            (operator.eq, [False, True, False, False]),
            (operator.gt, [False, False, False, True]),
        ],
    )
    def test_selection_by_datetimelike(self, datetimelike, op, expected):
        # GH issue #17965, test for ability to compare datetime64[ns] columns
        # to datetimelike
        df = DataFrame(
            {
                "A": [
                    Timestamp("20120101"),
                    Timestamp("20130101"),
                    np.nan,
                    Timestamp("20130103"),
                ]
            }
        )
        result = op(df.A, datetimelike)
        expected = Series(expected, name="A")
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize(
        "start",
        [
            "2018-12-02 21:50:00+00:00",
            Timestamp("2018-12-02 21:50:00+00:00"),
            Timestamp("2018-12-02 21:50:00+00:00").to_pydatetime(),
        ],
    )
    @pytest.mark.parametrize(
        "end",
        [
            "2018-12-02 21:52:00+00:00",
            Timestamp("2018-12-02 21:52:00+00:00"),
            Timestamp("2018-12-02 21:52:00+00:00").to_pydatetime(),
        ],
    )
    def test_getitem_with_datestring_with_UTC_offset(self, start, end):
        # GH 24076
        idx = date_range(
            start="2018-12-02 14:50:00-07:00",
            end="2018-12-02 14:50:00-07:00",
            freq="1min",
        )
        df = DataFrame(1, index=idx, columns=["A"])
        result = df[start:end]
        expected = df.iloc[0:3, :]
        tm.assert_frame_equal(result, expected)

        # GH 16785
        start = str(start)
        end = str(end)
        with pytest.raises(ValueError, match="Both dates must"):
            df[start : end[:-4] + "1:00"]

        with pytest.raises(ValueError, match="The index must be timezone"):
            df = df.tz_localize(None)
            df[start:end]

    def test_slice_reduce_to_series(self):
        # GH 27516
        df = DataFrame({"A": range(24)}, index=date_range("2000", periods=24, freq="M"))
        expected = Series(
            range(12), index=date_range("2000", periods=12, freq="M"), name="A"
        )
        result = df.loc["2000", "A"]
        tm.assert_series_equal(result, expected)
