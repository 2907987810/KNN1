import numpy as np
import pytest

from pandas import (
    DataFrame,
    Series,
)
import pandas._testing as tm
from pandas.core.reshape.reshape import from_dummies


@pytest.fixture
def dummies_basic():
    return DataFrame(
        {
            "C": [1, 2, 3],
            "col1_a": [1, 0, 1],
            "col1_b": [0, 1, 0],
            "col2_a": [0, 1, 0],
            "col2_b": [1, 0, 0],
            "col2_c": [0, 0, 1],
        },
    )


@pytest.fixture
def dummies_with_unassigned():
    return DataFrame(
        {
            "C": [1, 2, 3],
            "col1_a": [1, 0, 0],
            "col1_b": [0, 1, 0],
            "col2_a": [0, 1, 0],
            "col2_b": [0, 0, 0],
            "col2_c": [0, 0, 1],
        },
    )


def test_from_dummies_to_series_basic():
    dummies = DataFrame({"a": [1, 0, 0, 1], "b": [0, 1, 0, 0], "c": [0, 0, 1, 0]})
    expected = Series(list("abca"))
    result = from_dummies(dummies, to_series=True)
    tm.assert_series_equal(result, expected)


def test_from_dummies_to_series_contains_get_dummies_NaN_column():
    dummies = DataFrame({"a": [1, 0, 0], "b": [0, 1, 0], "NaN": [0, 0, 1]})
    expected = Series(["a", "b", "NaN"])
    result = from_dummies(dummies, to_series=True)
    tm.assert_series_equal(result, expected)


def test_from_dummies_to_series_contains_nan():
    dummies = DataFrame({"a": [1, 0, 0], "b": [0, 1, 0]})
    expected = Series(["a", "b", "nan"])
    result = from_dummies(dummies, to_series=True)
    tm.assert_series_equal(result, expected)


def test_from_dummies_to_series_dropped_first():
    dummies = DataFrame({"a": [1, 0, 0], "b": [0, 1, 0]})
    expected = Series(["a", "b", "c"])
    result = from_dummies(dummies, to_series=True, dropped_first="c")
    tm.assert_series_equal(result, expected)


def test_from_dummies_to_series_fillna_True():
    dummies = DataFrame({"a": [1, 0, 0], "b": [0, 1, np.nan]})
    expected = Series(["a", "b", "b"])
    result = from_dummies(dummies, to_series=True, fillna=True)
    tm.assert_series_equal(result, expected)


def test_from_dummies_to_series_fillna_False():
    dummies = DataFrame({"a": [1, 0, 0], "b": [0, 1, np.nan]})
    expected = Series(["a", "b", "nan"])
    result = from_dummies(dummies, to_series=True, fillna=False)
    tm.assert_series_equal(result, expected)


def test_from_dummies_to_series_wrong_dropped_first():
    dummies = DataFrame({"a": [1, 0, 1], "b": [0, 1, 1]})
    with pytest.raises(
        ValueError,
        match=r"Only one dropped first value possible in 1D dummy DataFrame.",
    ):
        from_dummies(dummies, to_series=True, dropped_first=["c", "d"])


def test_from_dummies_to_series_multi_assignment():
    dummies = DataFrame({"a": [1, 0, 1], "b": [0, 1, 1]})
    with pytest.raises(
        ValueError, match=r"Dummy DataFrame contains multi-assignment in row 2."
    ):
        from_dummies(dummies, to_series=True)


def test_from_dummies_to_series_no_fillna_but_na_value():
    dummies = DataFrame({"a": [1, 0, 0], "b": [0, 1, np.nan]})
    with pytest.raises(
        ValueError, match=r"Dummy DataFrame contains NA value in column: 'b'"
    ):
        from_dummies(dummies, to_series=True)


def test_from_dummies_no_dummies():
    dummies = DataFrame(
        {"a": [1, 6, 3, 1], "b": [0, 1, 0, 2], "c": ["c1", "c2", "c3", "c4"]}
    )
    expected = DataFrame(
        {"a": [1, 6, 3, 1], "b": [0, 1, 0, 2], "c": ["c1", "c2", "c3", "c4"]}
    )
    result = from_dummies(dummies)
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_basic(dummies_basic):
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a", "b", "a"], "col2": ["b", "a", "c"]}
    )
    result = from_dummies(dummies_basic)
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_prefix_sep_list():
    dummies = DataFrame(
        {
            "C": [1, 2, 3],
            "col1_a": [1, 0, 1],
            "col1_b": [0, 1, 0],
            "col2-a": [0, 1, 0],
            "col2-b": [1, 0, 0],
            "col2-c": [0, 0, 1],
        },
    )
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a", "b", "a"], "col2": ["b", "a", "c"]}
    )
    result = from_dummies(dummies, prefix_sep=["_", "-"])
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_prefix_sep_dict():
    dummies = DataFrame(
        {
            "C": [1, 2, 3],
            "col1_a-a": [1, 0, 1],
            "col1_b-b": [0, 1, 0],
            "col2-a_a": [0, 1, 0],
            "col2-b_b": [1, 0, 0],
            "col2-c_c": [0, 0, 1],
        },
    )
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a-a", "b-b", "a-a"], "col2": ["b_b", "a_a", "c_c"]}
    )
    result = from_dummies(
        dummies,
        prefix_sep={
            "col1": "_",
            "col2": "-",
        },
    )
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_contains_get_dummies_NaN_column():
    dummies = DataFrame(
        {
            "C": [1, 2, 3],
            "col1_a": [1, 0, 0],
            "col1_b": [0, 1, 0],
            "col1_NaN": [0, 0, 1],
            "col2_a": [0, 1, 0],
            "col2_b": [0, 0, 0],
            "col2_c": [0, 0, 1],
            "col2_NaN": [1, 0, 0],
        },
    )
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a", "b", "NaN"], "col2": ["NaN", "a", "c"]}
    )
    result = from_dummies(dummies)
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_contains_nan(dummies_with_unassigned):
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a", "b", "nan"], "col2": ["nan", "a", "c"]}
    )
    result = from_dummies(dummies_with_unassigned)
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_columns(dummies_basic):
    expected = DataFrame({"col1": ["a", "b", "a"], "col2": ["b", "a", "c"]})
    result = from_dummies(
        dummies_basic, columns=["col1_a", "col1_b", "col2_a", "col2_b", "col2_c"]
    )
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_dropped_first_str(dummies_with_unassigned):
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a", "b", "x"], "col2": ["x", "a", "c"]}
    )
    result = from_dummies(dummies_with_unassigned, dropped_first="x")
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_dropped_first_list(dummies_with_unassigned):
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a", "b", "x"], "col2": ["y", "a", "c"]}
    )
    result = from_dummies(dummies_with_unassigned, dropped_first=["x", "y"])
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_dropped_first_list_not_complete(dummies_with_unassigned):
    with pytest.raises(
        ValueError,
        match=(
            r"Length of 'dropped_first' \(1\) did not match "
            r"the length of the columns being encoded \(2\)."
        ),
    ):
        from_dummies(dummies_with_unassigned, dropped_first=["x"])


def test_from_dummies_to_df_dropped_first_dict(dummies_with_unassigned):
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a", "b", "y"], "col2": ["x", "a", "c"]}
    )
    result = from_dummies(
        dummies_with_unassigned, dropped_first={"col2": "x", "col1": "y"}
    )
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_dropped_first_dict_not_complete(dummies_with_unassigned):
    with pytest.raises(
        ValueError,
        match=(
            r"Length of 'dropped_first' \(1\) did not match "
            r"the length of the columns being encoded \(2\)."
        ),
    ):
        from_dummies(dummies_with_unassigned, dropped_first={"col1": "x"})


def test_from_dummies_to_df_fillna_True(dummies_basic):
    dummies_basic["col2_c"][2] = np.nan
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a", "b", "a"], "col2": ["b", "a", "c"]}
    )
    result = from_dummies(dummies_basic, fillna=True)
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_fillna_False(dummies_basic):
    dummies_basic["col2_c"][2] = np.nan
    expected = DataFrame(
        {"C": [1, 2, 3], "col1": ["a", "b", "a"], "col2": ["b", "a", "nan"]}
    )
    result = from_dummies(dummies_basic, fillna=False)
    tm.assert_frame_equal(result, expected)


def test_from_dummies_to_df_wrong_column_type(dummies_basic):
    with pytest.raises(
        TypeError,
        match=r"Input must be a list-like for parameter 'columns'",
    ):
        from_dummies(dummies_basic, columns="col1_a")


def test_from_dummies_to_df_no_fillna_but_na_value(dummies_basic):
    dummies_basic["col2_c"][2] = np.nan
    with pytest.raises(
        ValueError, match=r"Dummy DataFrame contains NA value in column: 'col2_c'"
    ):
        from_dummies(dummies_basic)


def test_from_dummies_to_df_double_assignment():
    dummies = DataFrame(
        {
            "C": [1, 2, 3],
            "col1_a": [1, 0, 1],
            "col1_b": [1, 1, 0],
            "col2_a": [0, 1, 0],
            "col2_b": [1, 0, 0],
            "col2_c": [0, 0, 1],
        },
    )
    with pytest.raises(
        ValueError,
        match=(
            r"Dummy DataFrame contains multi-assignment\(s\) for prefix: "
            r"'col1' in row 0."
        ),
    ):
        from_dummies(dummies)


def test_from_dummies_to_df_fillna_True_double_assignment():
    dummies = DataFrame(
        {
            "C": [1, 2, 3],
            "col1_a": [1, 0, 1],
            "col1_b": [1, np.nan, 0],
            "col2_a": [0, 1, 0],
            "col2_b": [1, 0, 0],
            "col2_c": [0, 0, 1],
        },
    )
    with pytest.raises(
        ValueError,
        match=(
            r"Dummy DataFrame contains multi-assignment\(s\) for prefix: "
            r"'col1' in row 0."
        ),
    ):
        from_dummies(dummies, fillna=True)
