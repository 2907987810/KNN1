import pandas as pd
from pandas import Categorical, Index
import pandas._testing as tm


class TestCategoricalSeries:
    def test_unused_category_retention(self):
        # Init case
        exp_cats = Index(["a", "b", "c", "d"])
        ser = pd.Series(Categorical(["a", "b", "c"], categories=exp_cats))
        tm.assert_index_equal(ser.cat.categories, exp_cats)

        # Modify case
        ser.loc[0] = "b"
        expected = pd.Series(Categorical(["b", "b", "c"], categories=exp_cats))
        tm.assert_index_equal(ser.cat.categories, exp_cats)
        tm.assert_series_equal(ser, expected)

    def test_loc_new_category_row_raises(self):
        df = pd.DataFrame(
            {
                "int": [0, 1, 2],
                "cat": Categorical(["a", "b", "c"], categories=["a", "b", "c"]),
            }
        )
        df.loc[3] = [3, "d"]

        expected = pd.DataFrame(
            {
                "int": [0, 1, 2, 3],
                "cat": Categorical(["a", "b", "c", pd.NA], categories=["a", "b", "c"]),
            }
        )
        tm.assert_frame_equal(df, expected)

    def test_loc_new_row_category_dtype_retention(self):
        df = pd.DataFrame(
            {
                "int": [0, 1, 2],
                "cat": pd.Categorical(["a", "b", "c"], categories=["a", "b", "c"]),
            }
        )
        df.loc[3] = [3, "c"]

        expected = pd.DataFrame(
            {
                "int": [0, 1, 2, 3],
                "cat": pd.Categorical(["a", "b", "c", "c"], categories=["a", "b", "c"]),
            }
        )

        tm.assert_frame_equal(df, expected)
