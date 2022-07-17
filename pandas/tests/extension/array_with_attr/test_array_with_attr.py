import numpy as np
import pytest

import pandas as pd
import pandas._testing as tm
from pandas.tests.extension.array_with_attr import (
    FloatAttrArray,
    FloatAttrDtype,
    make_data,
)


@pytest.fixture
def dtype():
    return FloatAttrDtype()


@pytest.fixture
def data():
    return FloatAttrArray(make_data())


def test_concat_with_all_na(data):
    # https://github.com/pandas-dev/pandas/pull/47762
    # ensure that attribute of the column array is preserved (when it gets
    # preserved in reindexing the array) during merge
    arr = FloatAttrArray(np.array([np.nan, np.nan], dtype="float64"), attr="test")

    df1 = pd.DataFrame({"col": arr, "key": [0, 1]})
    df2 = pd.DataFrame({"key": [0, 1], "col2": [1, 2]})
    result = pd.merge(df1, df2, on="key")
    expected = pd.DataFrame({"col": arr, "key": [0, 1], "col2": [1, 2]})
    tm.assert_frame_equal(result, expected)
    assert result["col"].array.attr == "test"

    df1 = pd.DataFrame({"col": arr, "key": [0, 1]})
    df2 = pd.DataFrame({"key": [0, 2], "col2": [1, 2]})
    result = pd.merge(df1, df2, on="key")
    expected = pd.DataFrame({"col": arr.take([0]), "key": [0], "col2": [1]})
    tm.assert_frame_equal(result, expected)
    assert result["col"].array.attr == "test"
