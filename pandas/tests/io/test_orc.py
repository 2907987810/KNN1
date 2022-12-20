""" test orc compat """
import datetime
from io import BytesIO
import os

import numpy as np
import pytest

import pandas.util._test_decorators as td

import pandas as pd
from pandas import read_orc
import pandas._testing as tm

pytest.importorskip("pyarrow.orc")

import pyarrow as pa


@pytest.fixture
def dirpath(datapath):
    return datapath("io", "data", "orc")


# Examples of dataframes with dtypes for which conversion to ORC
# hasn't been implemented yet, that is, Category, unsigned integers,
# interval, period and sparse.
orc_writer_dtypes_not_supported = [
    pd.DataFrame({"unimpl": np.array([1, 20], dtype="uint64")}),
    pd.DataFrame({"unimpl": pd.Series(["a", "b", "a"], dtype="category")}),
    pd.DataFrame(
        {"unimpl": [pd.Interval(left=0, right=2), pd.Interval(left=0, right=5)]}
    ),
    pd.DataFrame(
        {
            "unimpl": [
                pd.Period("2022-01-03", freq="D"),
                pd.Period("2022-01-04", freq="D"),
            ]
        }
    ),
    pd.DataFrame({"unimpl": [np.nan] * 50}).astype(pd.SparseDtype("float", np.nan)),
]


def test_orc_reader_empty(dirpath):
    columns = [
        "boolean1",
        "byte1",
        "short1",
        "int1",
        "long1",
        "float1",
        "double1",
        "bytes1",
        "string1",
    ]
    dtypes = [
        "bool",
        "int8",
        "int16",
        "int32",
        "int64",
        "float32",
        "float64",
        "object",
        "object",
    ]
    expected = pd.DataFrame(index=pd.RangeIndex(0))
    for colname, dtype in zip(columns, dtypes):
        expected[colname] = pd.Series(dtype=dtype)

    inputfile = os.path.join(dirpath, "TestOrcFile.emptyFile.orc")
    got = read_orc(inputfile, columns=columns)

    tm.assert_equal(expected, got)


def test_orc_reader_basic(dirpath):
    data = {
        "boolean1": np.array([False, True], dtype="bool"),
        "byte1": np.array([1, 100], dtype="int8"),
        "short1": np.array([1024, 2048], dtype="int16"),
        "int1": np.array([65536, 65536], dtype="int32"),
        "long1": np.array([9223372036854775807, 9223372036854775807], dtype="int64"),
        "float1": np.array([1.0, 2.0], dtype="float32"),
        "double1": np.array([-15.0, -5.0], dtype="float64"),
        "bytes1": np.array([b"\x00\x01\x02\x03\x04", b""], dtype="object"),
        "string1": np.array(["hi", "bye"], dtype="object"),
    }
    expected = pd.DataFrame.from_dict(data)

    inputfile = os.path.join(dirpath, "TestOrcFile.test1.orc")
    got = read_orc(inputfile, columns=data.keys())

    tm.assert_equal(expected, got)


def test_orc_reader_decimal(dirpath):
    from decimal import Decimal

    # Only testing the first 10 rows of data
    data = {
        "_col0": np.array(
            [
                Decimal("-1000.50000"),
                Decimal("-999.60000"),
                Decimal("-998.70000"),
                Decimal("-997.80000"),
                Decimal("-996.90000"),
                Decimal("-995.10000"),
                Decimal("-994.11000"),
                Decimal("-993.12000"),
                Decimal("-992.13000"),
                Decimal("-991.14000"),
            ],
            dtype="object",
        )
    }
    expected = pd.DataFrame.from_dict(data)

    inputfile = os.path.join(dirpath, "TestOrcFile.decimal.orc")
    got = read_orc(inputfile).iloc[:10]

    tm.assert_equal(expected, got)


def test_orc_reader_date_low(dirpath):
    data = {
        "time": np.array(
            [
                "1900-05-05 12:34:56.100000",
                "1900-05-05 12:34:56.100100",
                "1900-05-05 12:34:56.100200",
                "1900-05-05 12:34:56.100300",
                "1900-05-05 12:34:56.100400",
                "1900-05-05 12:34:56.100500",
                "1900-05-05 12:34:56.100600",
                "1900-05-05 12:34:56.100700",
                "1900-05-05 12:34:56.100800",
                "1900-05-05 12:34:56.100900",
            ],
            dtype="datetime64[ns]",
        ),
        "date": np.array(
            [
                datetime.date(1900, 12, 25),
                datetime.date(1900, 12, 25),
                datetime.date(1900, 12, 25),
                datetime.date(1900, 12, 25),
                datetime.date(1900, 12, 25),
                datetime.date(1900, 12, 25),
                datetime.date(1900, 12, 25),
                datetime.date(1900, 12, 25),
                datetime.date(1900, 12, 25),
                datetime.date(1900, 12, 25),
            ],
            dtype="object",
        ),
    }
    expected = pd.DataFrame.from_dict(data)

    inputfile = os.path.join(dirpath, "TestOrcFile.testDate1900.orc")
    got = read_orc(inputfile).iloc[:10]

    tm.assert_equal(expected, got)


def test_orc_reader_date_high(dirpath):
    data = {
        "time": np.array(
            [
                "2038-05-05 12:34:56.100000",
                "2038-05-05 12:34:56.100100",
                "2038-05-05 12:34:56.100200",
                "2038-05-05 12:34:56.100300",
                "2038-05-05 12:34:56.100400",
                "2038-05-05 12:34:56.100500",
                "2038-05-05 12:34:56.100600",
                "2038-05-05 12:34:56.100700",
                "2038-05-05 12:34:56.100800",
                "2038-05-05 12:34:56.100900",
            ],
            dtype="datetime64[ns]",
        ),
        "date": np.array(
            [
                datetime.date(2038, 12, 25),
                datetime.date(2038, 12, 25),
                datetime.date(2038, 12, 25),
                datetime.date(2038, 12, 25),
                datetime.date(2038, 12, 25),
                datetime.date(2038, 12, 25),
                datetime.date(2038, 12, 25),
                datetime.date(2038, 12, 25),
                datetime.date(2038, 12, 25),
                datetime.date(2038, 12, 25),
            ],
            dtype="object",
        ),
    }
    expected = pd.DataFrame.from_dict(data)

    inputfile = os.path.join(dirpath, "TestOrcFile.testDate2038.orc")
    got = read_orc(inputfile).iloc[:10]

    tm.assert_equal(expected, got)


def test_orc_reader_snappy_compressed(dirpath):
    data = {
        "int1": np.array(
            [
                -1160101563,
                1181413113,
                2065821249,
                -267157795,
                172111193,
                1752363137,
                1406072123,
                1911809390,
                -1308542224,
                -467100286,
            ],
            dtype="int32",
        ),
        "string1": np.array(
            [
                "f50dcb8",
                "382fdaaa",
                "90758c6",
                "9e8caf3f",
                "ee97332b",
                "d634da1",
                "2bea4396",
                "d67d89e8",
                "ad71007e",
                "e8c82066",
            ],
            dtype="object",
        ),
    }
    expected = pd.DataFrame.from_dict(data)

    inputfile = os.path.join(dirpath, "TestOrcFile.testSnappy.orc")
    got = read_orc(inputfile).iloc[:10]

    tm.assert_equal(expected, got)


@td.skip_if_no("pyarrow", min_version="7.0.0")
def test_orc_roundtrip_file(dirpath):
    # GH44554
    # PyArrow gained ORC write support with the current argument order
    data = {
        "boolean1": np.array([False, True], dtype="bool"),
        "byte1": np.array([1, 100], dtype="int8"),
        "short1": np.array([1024, 2048], dtype="int16"),
        "int1": np.array([65536, 65536], dtype="int32"),
        "long1": np.array([9223372036854775807, 9223372036854775807], dtype="int64"),
        "float1": np.array([1.0, 2.0], dtype="float32"),
        "double1": np.array([-15.0, -5.0], dtype="float64"),
        "bytes1": np.array([b"\x00\x01\x02\x03\x04", b""], dtype="object"),
        "string1": np.array(["hi", "bye"], dtype="object"),
    }
    expected = pd.DataFrame.from_dict(data)

    with tm.ensure_clean() as path:
        expected.to_orc(path)
        got = read_orc(path)

        tm.assert_equal(expected, got)


@td.skip_if_no("pyarrow", min_version="7.0.0")
def test_orc_roundtrip_bytesio():
    # GH44554
    # PyArrow gained ORC write support with the current argument order
    data = {
        "boolean1": np.array([False, True], dtype="bool"),
        "byte1": np.array([1, 100], dtype="int8"),
        "short1": np.array([1024, 2048], dtype="int16"),
        "int1": np.array([65536, 65536], dtype="int32"),
        "long1": np.array([9223372036854775807, 9223372036854775807], dtype="int64"),
        "float1": np.array([1.0, 2.0], dtype="float32"),
        "double1": np.array([-15.0, -5.0], dtype="float64"),
        "bytes1": np.array([b"\x00\x01\x02\x03\x04", b""], dtype="object"),
        "string1": np.array(["hi", "bye"], dtype="object"),
    }
    expected = pd.DataFrame.from_dict(data)

    bytes = expected.to_orc()
    got = read_orc(BytesIO(bytes))

    tm.assert_equal(expected, got)


@td.skip_if_no("pyarrow", min_version="7.0.0")
@pytest.mark.parametrize("df_not_supported", orc_writer_dtypes_not_supported)
def test_orc_writer_dtypes_not_supported(df_not_supported):
    # GH44554
    # PyArrow gained ORC write support with the current argument order
    msg = "The dtype of one or more columns is not supported yet."
    with pytest.raises(NotImplementedError, match=msg):
        df_not_supported.to_orc()


def test_orc_use_nullable_dtypes_pandas_backend_not_supported(dirpath):
    input_file = os.path.join(dirpath, "TestOrcFile.emptyFile.orc")
    with pytest.raises(
        NotImplementedError,
        match="mode.nullable_backend set to pandas is not implemented.",
    ):
        with pd.option_context("mode.nullable_backend", "pandas"):
            read_orc(input_file, use_nullable_dtypes=True)


@td.skip_if_no("pyarrow", min_version="7.0.0")
def test_orc_use_nullable_dtypes_pyarrow_backend():
    df = pd.DataFrame(
        {
            "string": list("abc"),
            "string_with_nan": ["a", np.nan, "c"],
            "string_with_none": ["a", None, "c"],
            "bytes": [b"foo", b"bar", None],
            "int": list(range(1, 4)),
            "float": np.arange(4.0, 7.0, dtype="float64"),
            "float_with_nan": [2.0, np.nan, 3.0],
            "bool": [True, False, True],
            "bool_with_na": [True, False, None],
            "datetime": pd.date_range("20130101", periods=3),
            "datetime_with_nat": [
                pd.Timestamp("20130101"),
                pd.NaT,
                pd.Timestamp("20130103"),
            ],
        }
    )
    bytes_data = df.copy().to_orc()
    with pd.option_context("mode.nullable_backend", "pyarrow"):
        result = read_orc(BytesIO(bytes_data), use_nullable_dtypes=True)
    expected = pd.DataFrame(
        {
            col: pd.arrays.ArrowExtensionArray(pa.array(df[col], from_pandas=True))
            for col in df.columns
        }
    )
    tm.assert_frame_equal(result, expected)
